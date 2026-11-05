from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Uom(Base):
    __tablename__ = "uom"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    skus: Mapped[list["Sku"]] = relationship(back_populates="uom")


class Sku(Base):
    __tablename__ = "sku"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50), default="OTHER")
    material_grade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    standard_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    uom_id: Mapped[int] = mapped_column(ForeignKey("uom.id"), index=True)
    unit_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)

    uom: Mapped[Uom] = relationship(back_populates="skus")
    batches: Mapped[list["Batch"]] = relationship(back_populates="sku")


class WarehouseZone(Base):
    __tablename__ = "warehouse_zone"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    zone_type: Mapped[str] = mapped_column(String(30))
    cells: Mapped[list["StorageCell"]] = relationship(back_populates="zone")


class StorageCell(Base):
    __tablename__ = "storage_cell"
    __table_args__ = (
        UniqueConstraint(
            "zone_id",
            "rack_number",
            "section_number",
            "tier_number",
            "position_number",
            name="uq_cell_coordinate",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    address_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("warehouse_zone.id"), index=True)
    rack_number: Mapped[int] = mapped_column(Integer)
    section_number: Mapped[int] = mapped_column(Integer)
    tier_number: Mapped[int] = mapped_column(Integer)
    position_number: Mapped[int] = mapped_column(Integer)
    max_weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    max_volume_m3: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    cell_status: Mapped[str] = mapped_column(String(20), default="FREE")

    zone: Mapped[WarehouseZone] = relationship(back_populates="cells")
    balances: Mapped[list["LocationBalance"]] = relationship(back_populates="cell")


class Department(Base):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    responsible_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    users: Mapped[list["AppUser"]] = relationship(back_populates="department")
    requests: Mapped[list["IssueRequest"]] = relationship(back_populates="department")


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("department.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    department: Mapped[Department | None] = relationship(back_populates="users")
    roles: Mapped[list["UserRole"]] = relationship(back_populates="user")


class UserRole(Base):
    __tablename__ = "user_role"

    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    role_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    user: Mapped[AppUser] = relationship(back_populates="roles")


class Supplier(Base):
    __tablename__ = "supplier"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inn: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    contact_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_orders: Mapped[list["ReceiptOrder"]] = relationship(back_populates="supplier")


class ReceiptOrder(Base):
    __tablename__ = "receipt_order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier.id"), index=True)
    incoming_invoice_num: Mapped[str | None] = mapped_column(String(64), nullable=True)
    incoming_invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="IN_INSPECTION")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    supplier: Mapped[Supplier] = relationship(back_populates="receipt_orders")
    batches: Mapped[list["Batch"]] = relationship(back_populates="receipt_order")


class Batch(Base):
    __tablename__ = "batch"
    __table_args__ = (
        CheckConstraint("initial_quantity > 0", name="ck_batch_initial_positive"),
        CheckConstraint("current_quantity >= 0", name="ck_batch_current_non_negative"),
        CheckConstraint("current_quantity <= initial_quantity", name="ck_batch_quantity_limit"),
        Index("idx_batch_sku_qc", "sku_id", "qc_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_order_id: Mapped[int] = mapped_column(ForeignKey("receipt_order.id"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("sku.id"), index=True)
    batch_number: Mapped[str] = mapped_column(String(64))
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    initial_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    qc_status: Mapped[str] = mapped_column(String(30), default="UNDER_CONTROL", index=True)
    barcode: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    receipt_order: Mapped[ReceiptOrder] = relationship(back_populates="batches")
    sku: Mapped[Sku] = relationship(back_populates="batches")
    qc_protocol: Mapped["QcProtocol | None"] = relationship(back_populates="batch", uselist=False)
    balances: Mapped[list["LocationBalance"]] = relationship(back_populates="batch")


class QcProtocol(Base):
    __tablename__ = "qc_protocol"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"), unique=True, index=True)
    inspector_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    protocol_number: Mapped[str] = mapped_column(String(64), unique=True)
    certificate_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    certificate_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    verdict: Mapped[str] = mapped_column(String(20))
    inspection_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch: Mapped[Batch] = relationship(back_populates="qc_protocol")


class LocationBalance(Base):
    __tablename__ = "location_balance"
    __table_args__ = (
        UniqueConstraint("cell_id", "batch_id", name="uq_cell_batch"),
        CheckConstraint("physical_quantity >= reserved_quantity", name="ck_balance_reserved"),
        CheckConstraint("reserved_quantity >= 0", name="ck_balance_reserved_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cell_id: Mapped[int] = mapped_column(ForeignKey("storage_cell.id"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"), index=True)
    physical_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cell: Mapped[StorageCell] = relationship(back_populates="balances")
    batch: Mapped[Batch] = relationship(back_populates="balances")


class IssueRequest(Base):
    __tablename__ = "issue_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id"), index=True)
    production_order: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="SUBMITTED", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    department: Mapped[Department] = relationship(back_populates="requests")
    items: Mapped[list["RequestItem"]] = relationship(back_populates="request")


class RequestItem(Base):
    __tablename__ = "request_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("issue_request.id"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("sku.id"), index=True)
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    allocated_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    issued_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)

    request: Mapped[IssueRequest] = relationship(back_populates="items")
    allocations: Mapped[list["RequestAllocation"]] = relationship(back_populates="request_item")


class RequestAllocation(Base):
    __tablename__ = "request_allocation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_item_id: Mapped[int] = mapped_column(ForeignKey("request_item.id"), index=True)
    location_balance_id: Mapped[int] = mapped_column(ForeignKey("location_balance.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))

    request_item: Mapped[RequestItem] = relationship(back_populates="allocations")
    location_balance: Mapped[LocationBalance] = relationship()


class StockMovementLog(Base):
    __tablename__ = "stock_movement_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"), index=True)
    source_cell_id: Mapped[int | None] = mapped_column(ForeignKey("storage_cell.id"), nullable=True)
    target_cell_id: Mapped[int | None] = mapped_column(ForeignKey("storage_cell.id"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    movement_type: Mapped[str] = mapped_column(String(30))
    document_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    performed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
