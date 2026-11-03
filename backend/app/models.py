from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True)


class StorageLocation(Base):
    __tablename__ = "storage_locations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))


class MaterialLot(Base):
    __tablename__ = "material_lots"
    __table_args__ = (UniqueConstraint("material_id", "lot_number"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    material_id: Mapped[UUID] = mapped_column(ForeignKey("materials.id"), index=True)
    lot_number: Mapped[str] = mapped_column(String(128))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="posted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReceiptLine(Base):
    __tablename__ = "receipt_lines"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(ForeignKey("receipts.id"), index=True)
    material_id: Mapped[UUID] = mapped_column(ForeignKey("materials.id"), index=True)
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("material_lots.id"), index=True)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("storage_locations.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))


class StockBalance(Base):
    __tablename__ = "stock_balances"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_stock_balance_non_negative"),
        UniqueConstraint("material_id", "lot_id", "location_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    material_id: Mapped[UUID] = mapped_column(ForeignKey("materials.id"), index=True)
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("material_lots.id"), index=True)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("storage_locations.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    material_id: Mapped[UUID] = mapped_column(ForeignKey("materials.id"), index=True)
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("material_lots.id"), index=True)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("storage_locations.id"), index=True)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    movement_type: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
