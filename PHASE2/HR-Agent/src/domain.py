"""Deterministic leave-domain rules; this module must never call the model."""
from __future__ import annotations

from datetime import date

from .contracts import LeaveBalance, PrepareLeaveArgs


class DomainError(ValueError):
    pass


def business_days(start: date, end: date) -> int:
    """Count weekday-only days in range [start, end]. Raises on bad input."""
    if end < start:
        raise DomainError("end_date sebelum start_date")
    count = 0
    current = start
    from datetime import timedelta
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            count += 1
        current += timedelta(days=1)
    if count == 0:
        raise DomainError("Rentang tanggal tidak mengandung hari kerja")
    return count


def validate_leave_request(
    args: PrepareLeaveArgs,
    balances: list[LeaveBalance],
    overlaps: bool,
    today: date,
) -> tuple[int, list[str]]:
    """Apply business rules. Returns (business_days, validation_messages). Raises DomainError."""
    if args.end_date < args.start_date:
        raise DomainError("end_date sebelum start_date")
    if args.start_date <= today:
        raise DomainError("Tanggal mulai di masa lalu atau hari ini")
    if overlaps:
        raise DomainError("Tanggal bertumpang tindih dengan permintaan aktif")

    days = business_days(args.start_date, args.end_date)
    messages: list[str] = []

    # Check balance for annual and sick leave
    if args.leave_type in ("annual", "sick"):
        matching = [b for b in balances if b.leave_type == args.leave_type]
        if matching:
            available = matching[0].available_days
            if days > available:
                raise DomainError(
                    f"Saldo {args.leave_type} tidak cukup: butuh {days}, tersedia {available}"
                )
            messages.append(f"Saldo {args.leave_type} cukup: {available} hari, digunakan {days} hari")
        else:
            raise DomainError(f"Tidak ada saldo untuk tipe cuti {args.leave_type}")

    if args.leave_type == "parental":
        messages.append("Cuti orang tua memerlukan tinjauan HR untuk kelayakan dan durasi akhir")

    messages.append(f"Rentang: {args.start_date} s/d {args.end_date} ({days} hari kerja)")
    return days, messages


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    input_rate: float | None,
    output_rate: float | None,
) -> float | None:
    """Return None unless both instructor-supplied rates are configured."""
    if input_rate is None or output_rate is None:
        return None
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000

