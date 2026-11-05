from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MaterialCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=50)
    category: str = Field(default="OTHER", max_length=50)
    material_grade: str | None = Field(default=None, max_length=100)
    standard_code: str | None = Field(default=None, max_length=100)


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    unit: str
    category: str
    material_grade: str | None


class ZoneCreate(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=100)
    zone_type: str = Field(min_length=1, max_length=30)


class ZoneRead(ZoneCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CellCreate(BaseModel):
    address_code: str = Field(min_length=1, max_length=32)
    zone_id: int
    rack_number: int = Field(ge=0)
    section_number: int = Field(ge=0)
    tier_number: int = Field(ge=0)
    position_number: int = Field(ge=0)
    max_weight_kg: Decimal = Field(gt=0)
    max_volume_m3: Decimal = Field(gt=0)


class CellRead(CellCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cell_status: str


class SupplierCreate(BaseModel):
    inn: str = Field(min_length=5, max_length=12)
    name: str = Field(min_length=1, max_length=255)
    contact_info: str | None = None


class SupplierRead(SupplierCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ReceiptLineCreate(BaseModel):
    sku_id: int
    batch_number: str = Field(min_length=1, max_length=64)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    quarantine_cell_id: int
    manufacture_date: date | None = None
    expiration_date: date | None = None
    barcode: str | None = Field(default=None, max_length=64)


class ReceiptCreate(BaseModel):
    document_number: str = Field(min_length=1, max_length=64)
    supplier_id: int
    incoming_invoice_num: str | None = Field(default=None, max_length=64)
    incoming_invoice_date: date | None = None
    lines: list[ReceiptLineCreate] = Field(min_length=1)


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku_id: int
    batch_number: str
    current_quantity: Decimal
    qc_status: str
    barcode: str


class ReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    doc_number: str
    status: str
    batches: list[BatchRead]


class QcInspect(BaseModel):
    batch_id: int
    protocol_number: str = Field(min_length=1, max_length=64)
    certificate_number: str | None = Field(default=None, max_length=128)
    verdict: Literal["PASSED", "FAILED"]
    inspector_user_id: int | None = None
    certificate_file_path: str | None = Field(default=None, max_length=512)
    rejected_cell_id: int | None = None
    notes: str | None = None


class QcResult(BaseModel):
    batch_id: int
    qc_status: str
    protocol_id: int
    message: str


class StockRead(BaseModel):
    batch_id: int
    sku_id: int
    cell_id: int
    address_code: str
    batch_number: str
    qc_status: str
    physical_quantity: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal


class IssueLineCreate(BaseModel):
    sku_id: int
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class IssueRequestCreate(BaseModel):
    request_number: str = Field(min_length=1, max_length=64)
    department_id: int
    production_order: str | None = Field(default=None, max_length=64)
    created_by_user_id: int | None = None
    lines: list[IssueLineCreate] = Field(min_length=1)


class IssueRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    request_number: str
    department_id: int
    status: str
    created_at: datetime | None


class ReserveRequest(BaseModel):
    allow_partial: bool = False


class AllocationRead(BaseModel):
    request_item_id: int
    batch_id: int
    location_balance_id: int
    quantity: Decimal


class ReserveResult(BaseModel):
    request_id: int
    status: str
    allocations: list[AllocationRead]
