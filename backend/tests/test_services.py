import os
import unittest
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    Batch,
    LocationBalance,
    Sku,
    StorageCell,
    Supplier,
    Uom,
    WarehouseZone,
)
from app.schemas import MaterialCreate, QcInspect, ReceiptCreate, ReceiptLineCreate
from app.services import create_material, create_receipt, inspect_batch


class WarehouseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        material = create_material(
            self.session,
            MaterialCreate(code="BEARING-001", name="Подшипник", unit="шт"),
        )
        zone = WarehouseZone(code="Q", name="Карантин", zone_type="RECEIVING_QUARANTINE")
        self.session.add(zone)
        self.session.flush()
        cell = StorageCell(
            address_code="Q-01-01-1-01",
            zone_id=zone.id,
            rack_number=1,
            section_number=1,
            tier_number=1,
            position_number=1,
            max_weight_kg=Decimal("1000"),
            max_volume_m3=Decimal("10"),
        )
        self.session.add_all([cell, Supplier(inn="7700000000", name="Поставщик")])
        self.session.flush()
        self.material_id = material.id
        self.cell_id = cell.id
        self.supplier_id = self.session.scalar(select(Supplier.id))

    def tearDown(self) -> None:
        self.session.close()

    def test_receipt_starts_in_quarantine(self) -> None:
        receipt = create_receipt(
            self.session,
            ReceiptCreate(
                document_number="M4-001",
                supplier_id=self.supplier_id,
                lines=[
                    ReceiptLineCreate(
                        sku_id=self.material_id,
                        batch_number="B-001",
                        quantity=Decimal("10"),
                        quarantine_cell_id=self.cell_id,
                    )
                ],
            ),
        )
        self.session.commit()
        batch = self.session.scalar(select(Batch).where(Batch.receipt_order_id == receipt.id))
        balance = self.session.scalar(select(LocationBalance).where(LocationBalance.batch_id == batch.id))
        self.assertEqual(batch.qc_status, "UNDER_CONTROL")
        self.assertEqual(balance.physical_quantity, Decimal("10.000"))

    def test_failed_qc_changes_status_and_keeps_quarantine_balance(self) -> None:
        receipt = create_receipt(
            self.session,
            ReceiptCreate(
                document_number="M4-002",
                supplier_id=self.supplier_id,
                lines=[
                    ReceiptLineCreate(
                        sku_id=self.material_id,
                        batch_number="B-002",
                        quantity=Decimal("4"),
                        quarantine_cell_id=self.cell_id,
                    )
                ],
            ),
        )
        self.session.flush()
        batch = self.session.scalar(select(Batch).where(Batch.receipt_order_id == receipt.id))
        inspect_batch(
            self.session,
            QcInspect(
                batch_id=batch.id,
                protocol_number="QC-002",
                verdict="FAILED",
            ),
        )
        self.session.commit()
        self.session.refresh(batch)
        self.assertEqual(batch.qc_status, "REJECTED_QUARANTINE")
        balance = self.session.scalar(select(LocationBalance).where(LocationBalance.batch_id == batch.id))
        self.assertEqual(balance.cell_id, self.cell_id)
