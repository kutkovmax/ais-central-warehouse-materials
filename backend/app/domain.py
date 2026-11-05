from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


QC_UNDER_CONTROL = "UNDER_CONTROL"
QC_ACCEPTED = "ACCEPTED"
QC_REJECTED = "REJECTED_QUARANTINE"
QC_SCRAPPED = "SCRAPPED"

REQUEST_DRAFT = "DRAFT"
REQUEST_SUBMITTED = "SUBMITTED"
REQUEST_RESERVED = "RESERVED"
REQUEST_PARTIALLY_RESERVED = "PARTIALLY_RESERVED"
REQUEST_PICKING = "PICKING"
REQUEST_ISSUED = "ISSUED"
REQUEST_CANCELED = "CANCELED"


class DomainError(Exception):
    """Ошибка бизнес-правила предметной области."""


class InsufficientStock(DomainError):
    pass


@dataclass(frozen=True)
class FifoCandidate:
    batch_id: int
    received_at: datetime
    expiration_date: date | None
    available_quantity: Decimal
    qc_status: str


def allocate_fifo(
    candidates: list[FifoCandidate],
    requested_quantity: Decimal,
    *,
    today: date | None = None,
    allow_partial: bool = False,
) -> list[tuple[int, Decimal]]:
    """Распределяет количество по годным партиям в порядке FEFO/FIFO."""
    if requested_quantity <= 0:
        raise DomainError("Запрашиваемое количество должно быть больше нуля")

    current_day = today or date.today()
    eligible = [
        candidate
        for candidate in candidates
        if candidate.qc_status == QC_ACCEPTED
        and candidate.available_quantity > 0
        and (candidate.expiration_date is None or candidate.expiration_date >= current_day)
    ]
    eligible.sort(
        key=lambda candidate: (
            candidate.expiration_date is None,
            candidate.expiration_date or date.max,
            candidate.received_at,
            candidate.batch_id,
        )
    )

    remaining = requested_quantity
    allocations: list[tuple[int, Decimal]] = []
    for candidate in eligible:
        quantity = min(candidate.available_quantity, remaining)
        if quantity > 0:
            allocations.append((candidate.batch_id, quantity))
            remaining -= quantity
        if remaining <= 0:
            break

    if remaining > 0 and not allow_partial:
        raise InsufficientStock(
            f"Недостаточно годного остатка: не хватает {remaining} единиц"
        )
    return allocations
