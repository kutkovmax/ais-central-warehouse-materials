from datetime import date, datetime
from decimal import Decimal
import unittest

from app.domain import FifoCandidate, InsufficientStock, QC_ACCEPTED, allocate_fifo


class FifoAllocationTests(unittest.TestCase):
    def test_expiring_accepted_batch_is_selected_first(self) -> None:
        candidates = [
            FifoCandidate(2, datetime(2026, 1, 1), date(2027, 1, 1), Decimal("10"), QC_ACCEPTED),
            FifoCandidate(1, datetime(2025, 1, 1), date(2028, 1, 1), Decimal("10"), QC_ACCEPTED),
        ]
        result = allocate_fifo(candidates, Decimal("5"), today=date(2026, 11, 5))
        self.assertEqual(result, [(2, Decimal("5"))])

    def test_insufficient_accepted_stock_is_rejected(self) -> None:
        candidates = [
            FifoCandidate(1, datetime(2026, 1, 1), None, Decimal("2"), QC_ACCEPTED),
        ]
        with self.assertRaises(InsufficientStock):
            allocate_fifo(candidates, Decimal("3"))

    def test_non_accepted_stock_is_never_allocated(self) -> None:
        candidates = [
            FifoCandidate(1, datetime(2026, 1, 1), None, Decimal("20"), "REJECTED_QUARANTINE"),
        ]
        with self.assertRaises(InsufficientStock):
            allocate_fifo(candidates, Decimal("1"))
