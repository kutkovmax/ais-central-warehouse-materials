from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import Base, engine, get_session
from app.domain import DomainError, InsufficientStock
from app.models import (
    Batch,
    Department,
    LocationBalance,
    Sku,
    StorageCell,
    Supplier,
    WarehouseZone,
)
from app.schemas import (
    CellCreate,
    CellRead,
    IssueRequestCreate,
    IssueRequestRead,
    MaterialCreate,
    MaterialRead,
    QcInspect,
    QcResult,
    ReceiptCreate,
    ReceiptRead,
    ReserveRequest,
    ReserveResult,
    StockRead,
    SupplierCreate,
    SupplierRead,
    ZoneCreate,
    ZoneRead,
)
from app.services import (
    create_issue_request,
    create_material,
    create_receipt,
    create_supplier,
    inspect_batch,
    reserve_issue_request,
)

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_tables() -> None:
    """Временный bootstrap MVP; промышленная схема должна перейти на Alembic."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def domain_http_error(error: DomainError) -> HTTPException:
    code = status.HTTP_409_CONFLICT if "уже" in str(error) else status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(error, InsufficientStock):
        code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(error))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/materials", response_model=MaterialRead, status_code=201)
def create_material_endpoint(
    payload: MaterialCreate,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    try:
        material = create_material(session, payload)
        session.commit()
        session.refresh(material)
        return {
            "id": material.id,
            "code": material.article,
            "name": material.name,
            "unit": material.uom.code,
            "category": material.category,
            "material_grade": material.material_grade,
        }
    except DomainError as error:
        session.rollback()
        raise domain_http_error(error) from error
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Нарушено ограничение уникальности") from error


@app.get("/api/v1/materials", response_model=list[MaterialRead])
def list_materials(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    materials = session.scalars(select(Sku).options(joinedload(Sku.uom)).order_by(Sku.article))
    return [
        {
            "id": item.id,
            "code": item.article,
            "name": item.name,
            "unit": item.uom.code,
            "category": item.category,
            "material_grade": item.material_grade,
        }
        for item in materials
    ]


@app.post("/api/v1/suppliers", response_model=SupplierRead, status_code=201)
def create_supplier_endpoint(
    payload: SupplierCreate,
    session: Session = Depends(get_session),
) -> Supplier:
    try:
        supplier = create_supplier(session, payload)
        session.commit()
        session.refresh(supplier)
        return supplier
    except DomainError as error:
        session.rollback()
        raise domain_http_error(error) from error


@app.post("/api/v1/zones", response_model=ZoneRead, status_code=201)
def create_zone(payload: ZoneCreate, session: Session = Depends(get_session)) -> WarehouseZone:
    zone = WarehouseZone(**payload.model_dump())
    session.add(zone)
    try:
        session.commit()
        session.refresh(zone)
        return zone
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Зона с таким кодом уже существует") from error


@app.post("/api/v1/storage-cells", response_model=CellRead, status_code=201)
def create_cell(payload: CellCreate, session: Session = Depends(get_session)) -> StorageCell:
    if not session.get(WarehouseZone, payload.zone_id):
        raise HTTPException(status_code=404, detail="Зона не найдена")
    cell = StorageCell(**payload.model_dump())
    session.add(cell)
    try:
        session.commit()
        session.refresh(cell)
        return cell
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Ячейка с таким адресом уже существует") from error


@app.post("/api/v1/receipts", response_model=ReceiptRead, status_code=201)
def post_receipt(
    payload: ReceiptCreate,
    session: Session = Depends(get_session),
) -> object:
    try:
        receipt = create_receipt(session, payload)
        session.commit()
        session.refresh(receipt)
        return receipt
    except DomainError as error:
        session.rollback()
        raise domain_http_error(error) from error
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Конфликт уникального идентификатора") from error


@app.post("/api/v1/qc/inspect", response_model=QcResult)
def inspect_endpoint(payload: QcInspect, session: Session = Depends(get_session)) -> QcResult:
    try:
        protocol = inspect_batch(session, payload)
        session.commit()
        session.refresh(protocol)
        return QcResult(
            batch_id=protocol.batch_id,
            qc_status=protocol.batch.qc_status,
            protocol_id=protocol.id,
            message=(
                "Партия допущена к размещению"
                if payload.verdict == "PASSED"
                else "Партия изолирована; сформируйте акт ТОРГ-2"
            ),
        )
    except DomainError as error:
        session.rollback()
        raise domain_http_error(error) from error


@app.get("/api/v1/stock", response_model=list[StockRead])
def list_stock(session: Session = Depends(get_session)) -> list[StockRead]:
    balances = session.scalars(
        select(LocationBalance)
        .options(joinedload(LocationBalance.batch), joinedload(LocationBalance.cell))
        .order_by(LocationBalance.updated_at.desc())
    )
    return [
        StockRead(
            batch_id=balance.batch_id,
            sku_id=balance.batch.sku_id,
            cell_id=balance.cell_id,
            address_code=balance.cell.address_code,
            batch_number=balance.batch.batch_number,
            qc_status=balance.batch.qc_status,
            physical_quantity=balance.physical_quantity,
            reserved_quantity=balance.reserved_quantity,
            available_quantity=balance.physical_quantity - balance.reserved_quantity,
        )
        for balance in balances
        if balance.physical_quantity > 0
    ]


@app.post("/api/v1/issue-requests", response_model=IssueRequestRead, status_code=201)
def create_issue_request_endpoint(
    payload: IssueRequestCreate,
    session: Session = Depends(get_session),
) -> object:
    if not session.get(Department, payload.department_id):
        raise HTTPException(status_code=404, detail="Подразделение не найдено")
    try:
        request = create_issue_request(session, payload)
        session.commit()
        session.refresh(request)
        return request
    except DomainError as error:
        session.rollback()
        raise domain_http_error(error) from error


@app.post("/api/v1/issue-requests/{request_id}/reserve", response_model=ReserveResult)
def reserve_request_endpoint(
    request_id: int,
    payload: ReserveRequest,
    session: Session = Depends(get_session),
) -> ReserveResult:
    try:
        request, allocations = reserve_issue_request(
            session,
            request_id,
            allow_partial=payload.allow_partial,
        )
        session.commit()
        return ReserveResult(
            request_id=request.id,
            status=request.status,
            allocations=[
                {
                    "request_item_id": allocation.request_item_id,
                    "batch_id": allocation.location_balance.batch_id,
                    "location_balance_id": allocation.location_balance_id,
                    "quantity": allocation.quantity,
                }
                for allocation in allocations
            ],
        )
    except DomainError as error:
        session.rollback()
        raise domain_http_error(error) from error
