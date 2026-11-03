from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class MaterialCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=32)


class MaterialRead(MaterialCreate):
    id: UUID
    is_active: bool

    model_config = {"from_attributes": True}


class LocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)


class LocationRead(LocationCreate):
    id: UUID

    model_config = {"from_attributes": True}


class ReceiptLineCreate(BaseModel):
    material_id: UUID
    lot_number: str = Field(min_length=1, max_length=128)
    location_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class ReceiptCreate(BaseModel):
    document_number: str = Field(min_length=1, max_length=64)
    lines: list[ReceiptLineCreate] = Field(min_length=1)


class ReceiptRead(BaseModel):
    id: UUID
    document_number: str
    status: str

    model_config = {"from_attributes": True}


class BalanceRead(BaseModel):
    material_id: UUID
    lot_id: UUID
    location_id: UUID
    quantity: Decimal

    model_config = {"from_attributes": True}
