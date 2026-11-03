from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, engine, get_session
from app.models import Material, MaterialLot, Receipt, ReceiptLine, StockBalance, StockMovement, StorageLocation
from app.schemas import (
    BalanceRead,
    LocationCreate,
    LocationRead,
    MaterialCreate,
    MaterialRead,
    ReceiptCreate,
    ReceiptRead,
)

app = FastAPI(title="АС центрального склада материалов", version="0.1.0")


@app.on_event("startup")
def create_tables() -> None:
    # Временный bootstrap для MVP. Перед первым промышленным релизом заменить на Alembic.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/materials", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
def create_material(payload: MaterialCreate, session: Session = Depends(get_session)) -> Material:
    material = Material(**payload.model_dump())
    session.add(material)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Материал с таким кодом уже существует") from error
    session.refresh(material)
    return material


@app.get("/api/v1/materials", response_model=list[MaterialRead])
def list_materials(session: Session = Depends(get_session)) -> list[Material]:
    return list(session.scalars(select(Material).order_by(Material.code)))


@app.post("/api/v1/storage-locations", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationCreate, session: Session = Depends(get_session)) -> StorageLocation:
    location = StorageLocation(**payload.model_dump())
    session.add(location)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Место хранения с таким кодом уже существует") from error
    session.refresh(location)
    return location


@app.get("/api/v1/stock", response_model=list[BalanceRead])
def list_stock(material_id: UUID | None = None, session: Session = Depends(get_session)) -> list[StockBalance]:
    query = select(StockBalance).order_by(StockBalance.updated_at.desc())
    if material_id:
        query = query.where(StockBalance.material_id == material_id)
    return list(session.scalars(query))


@app.post("/api/v1/receipts", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
def post_receipt(payload: ReceiptCreate, session: Session = Depends(get_session)) -> Receipt:
    if session.scalar(select(Receipt).where(Receipt.document_number == payload.document_number)):
        raise HTTPException(status_code=409, detail="Документ приёмки уже существует")

    receipt = Receipt(document_number=payload.document_number)
    session.add(receipt)
    session.flush()

    for line_number, line in enumerate(payload.lines, start=1):
        material = session.get(Material, line.material_id)
        location = session.get(StorageLocation, line.location_id)
        if not material or not material.is_active:
            raise HTTPException(status_code=404, detail=f"Материал не найден: {line.material_id}")
        if not location:
            raise HTTPException(status_code=404, detail=f"Место хранения не найдено: {line.location_id}")

        lot = session.scalar(
            select(MaterialLot).where(
                MaterialLot.material_id == line.material_id,
                MaterialLot.lot_number == line.lot_number,
            )
        )
        if not lot:
            lot = MaterialLot(material_id=line.material_id, lot_number=line.lot_number)
            session.add(lot)
            session.flush()

        session.add(
            ReceiptLine(
                receipt_id=receipt.id,
                material_id=line.material_id,
                lot_id=lot.id,
                location_id=line.location_id,
                quantity=line.quantity,
            )
        )

        balance = session.scalar(
            select(StockBalance).where(
                StockBalance.material_id == line.material_id,
                StockBalance.lot_id == lot.id,
                StockBalance.location_id == line.location_id,
            )
        )
        if not balance:
            balance = StockBalance(
                material_id=line.material_id,
                lot_id=lot.id,
                location_id=line.location_id,
                quantity=0,
            )
            session.add(balance)

        balance.quantity += line.quantity
        session.add(
            StockMovement(
                material_id=line.material_id,
                lot_id=lot.id,
                location_id=line.location_id,
                quantity_delta=line.quantity,
                movement_type="receipt",
                idempotency_key=f"receipt:{payload.document_number}:{line_number}",
            )
        )

    session.commit()
    session.refresh(receipt)
    return receipt
