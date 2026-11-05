from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import (
    QC_ACCEPTED,
    QC_REJECTED,
    QC_UNDER_CONTROL,
    REQUEST_PARTIALLY_RESERVED,
    REQUEST_RESERVED,
    DomainError,
    FifoCandidate,
    allocate_fifo,
)
from app.models import (
    Batch,
    IssueRequest,
    LocationBalance,
    QcProtocol,
    ReceiptOrder,
    RequestAllocation,
    RequestItem,
    Sku,
    StockMovementLog,
    StorageCell,
    Supplier,
    Uom,
)
from app.schemas import IssueRequestCreate, MaterialCreate, QcInspect, ReceiptCreate


def create_material(session: Session, payload: MaterialCreate) -> Sku:
    if session.scalar(select(Sku).where(Sku.article == payload.code)):
        raise DomainError("Материал с таким кодом уже существует")

    uom = session.scalar(select(Uom).where(Uom.code == payload.unit))
    if not uom:
        uom = Uom(code=payload.unit, name=payload.unit)
        session.add(uom)
        session.flush()

    material = Sku(
        article=payload.code,
        name=payload.name,
        category=payload.category,
        material_grade=payload.material_grade,
        standard_code=payload.standard_code,
        uom_id=uom.id,
    )
    session.add(material)
    session.flush()
    return material


def create_supplier(session: Session, payload) -> Supplier:
    if session.scalar(select(Supplier).where(Supplier.inn == payload.inn)):
        raise DomainError("Поставщик с таким ИНН уже существует")
    supplier = Supplier(**payload.model_dump())
    session.add(supplier)
    session.flush()
    return supplier


def create_receipt(session: Session, payload: ReceiptCreate) -> ReceiptOrder:
    if session.scalar(select(ReceiptOrder).where(ReceiptOrder.doc_number == payload.document_number)):
        raise DomainError("Приходный ордер с таким номером уже существует")
    if not session.get(Supplier, payload.supplier_id):
        raise DomainError("Поставщик не найден")

    receipt = ReceiptOrder(
        doc_number=payload.document_number,
        supplier_id=payload.supplier_id,
        incoming_invoice_num=payload.incoming_invoice_num,
        incoming_invoice_date=payload.incoming_invoice_date,
        status="IN_INSPECTION",
    )
    session.add(receipt)
    session.flush()

    for line_number, line in enumerate(payload.lines, start=1):
        sku = session.get(Sku, line.sku_id)
        cell = session.get(StorageCell, line.quarantine_cell_id)
        if not sku:
            raise DomainError(f"Материал не найден: {line.sku_id}")
        if not cell or cell.zone.zone_type != "RECEIVING_QUARANTINE":
            raise DomainError("Партия должна поступать в ячейку зоны входного карантина")

        batch = Batch(
            receipt_order_id=receipt.id,
            sku_id=sku.id,
            batch_number=line.batch_number,
            manufacture_date=line.manufacture_date,
            expiration_date=line.expiration_date,
            initial_quantity=line.quantity,
            current_quantity=line.quantity,
            qc_status=QC_UNDER_CONTROL,
            barcode=line.barcode or f"BATCH-{receipt.doc_number}-{line_number}",
        )
        session.add(batch)
        session.flush()

        session.add(
            LocationBalance(
                cell_id=cell.id,
                batch_id=batch.id,
                physical_quantity=line.quantity,
                reserved_quantity=0,
            )
        )
        session.add(
            StockMovementLog(
                batch_id=batch.id,
                target_cell_id=cell.id,
                quantity=line.quantity,
                movement_type="RECEIPT_TO_QUARANTINE",
                document_ref=receipt.doc_number,
                idempotency_key=f"receipt:{receipt.doc_number}:{line_number}",
            )
        )
    session.flush()
    return receipt


def _move_batch_to_cell(
    session: Session,
    batch: Batch,
    target_cell_id: int,
    *,
    movement_type: str,
    document_ref: str,
) -> None:
    source_balances = list(
        session.scalars(
            select(LocationBalance)
            .where(LocationBalance.batch_id == batch.id, LocationBalance.physical_quantity > 0)
            .with_for_update()
        )
    )
    target = session.scalar(
        select(LocationBalance)
        .where(
            LocationBalance.batch_id == batch.id,
            LocationBalance.cell_id == target_cell_id,
        )
        .with_for_update()
    )
    if not target:
        target = LocationBalance(cell_id=target_cell_id, batch_id=batch.id, physical_quantity=0)
        session.add(target)
        session.flush()

    moved = Decimal("0")
    for balance in source_balances:
        if balance.cell_id == target_cell_id:
            continue
        if balance.reserved_quantity > 0:
            raise DomainError("Нельзя переместить остаток с активным резервом")
        moved += balance.physical_quantity
        balance.physical_quantity = 0
    target.physical_quantity += moved

    if moved > 0:
        session.add(
            StockMovementLog(
                batch_id=batch.id,
                source_cell_id=source_balances[0].cell_id if source_balances else None,
                target_cell_id=target_cell_id,
                quantity=moved,
                movement_type=movement_type,
                document_ref=document_ref,
                idempotency_key=f"{movement_type.lower()}:{batch.id}:{target_cell_id}",
            )
        )


def inspect_batch(session: Session, payload: QcInspect) -> QcProtocol:
    batch = session.get(Batch, payload.batch_id)
    if not batch:
        raise DomainError("Партия не найдена")
    if batch.qc_status != QC_UNDER_CONTROL:
        raise DomainError("Партия уже прошла входной контроль")
    if session.scalar(select(QcProtocol).where(QcProtocol.batch_id == batch.id)):
        raise DomainError("Протокол ОТК для партии уже существует")

    batch.qc_status = QC_ACCEPTED if payload.verdict == "PASSED" else QC_REJECTED
    protocol = QcProtocol(
        batch_id=batch.id,
        inspector_user_id=payload.inspector_user_id,
        protocol_number=payload.protocol_number,
        certificate_number=payload.certificate_number,
        certificate_file_path=payload.certificate_file_path,
        verdict=payload.verdict,
        notes=payload.notes,
        inspection_date=datetime.now(timezone.utc),
    )
    session.add(protocol)
    session.flush()

    if payload.verdict == "FAILED" and payload.rejected_cell_id:
        target_cell = session.get(StorageCell, payload.rejected_cell_id)
        if not target_cell:
            raise DomainError("Ячейка изолятора брака не найдена")
        _move_batch_to_cell(
            session,
            batch,
            target_cell.id,
            movement_type="QC_REJECT_ISOLATION",
            document_ref=payload.protocol_number,
        )
    return protocol


def create_issue_request(session: Session, payload: IssueRequestCreate) -> IssueRequest:
    if session.scalar(
        select(IssueRequest).where(IssueRequest.request_number == payload.request_number)
    ):
        raise DomainError("Требование с таким номером уже существует")
    request = IssueRequest(
        request_number=payload.request_number,
        department_id=payload.department_id,
        production_order=payload.production_order,
        created_by_user_id=payload.created_by_user_id,
        status="SUBMITTED",
    )
    session.add(request)
    session.flush()
    for line in payload.lines:
        session.add(
            RequestItem(
                request_id=request.id,
                sku_id=line.sku_id,
                requested_quantity=line.quantity,
            )
        )
    session.flush()
    return request


def reserve_issue_request(
    session: Session,
    request_id: int,
    *,
    allow_partial: bool,
) -> tuple[IssueRequest, list[RequestAllocation]]:
    request = session.scalar(
        select(IssueRequest).where(IssueRequest.id == request_id).with_for_update()
    )
    if not request:
        raise DomainError("Требование не найдено")
    if request.status not in {"SUBMITTED", REQUEST_PARTIALLY_RESERVED}:
        raise DomainError("Требование нельзя резервировать в текущем статусе")

    allocations: list[RequestAllocation] = []
    for item in request.items:
        balances = list(
            session.scalars(
                select(LocationBalance)
                .join(LocationBalance.batch)
                .where(LocationBalance.batch.has(sku_id=item.sku_id))
                .with_for_update()
            )
        )
        candidates = [
            FifoCandidate(
                batch_id=balance.batch.id,
                received_at=balance.batch.received_at,
                expiration_date=balance.batch.expiration_date,
                available_quantity=balance.physical_quantity - balance.reserved_quantity,
                qc_status=balance.batch.qc_status,
            )
            for balance in balances
        ]
        selected = allocate_fifo(
            candidates,
            item.requested_quantity - item.allocated_quantity,
            allow_partial=allow_partial,
        )
        for batch_id, quantity in selected:
            balance = next(balance for balance in balances if balance.batch_id == batch_id)
            balance.reserved_quantity += quantity
            item.allocated_quantity += quantity
            allocation = RequestAllocation(
                request_item_id=item.id,
                location_balance_id=balance.id,
                quantity=quantity,
            )
            session.add(allocation)
            allocations.append(allocation)

    request.status = REQUEST_PARTIALLY_RESERVED if allow_partial else REQUEST_RESERVED
    session.flush()
    return request, allocations
