"""Transacciones ficticias reproducibles; todos los importes representan EUR."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from random import Random


@dataclass(frozen=True, slots=True)
class Transaction:
    transaction_id: int
    account_id: int
    amount_cents: int
    country: str
    transaction_type: str
    timestamp: datetime


def generate_transactions(count: int, seed: int) -> list[Transaction]:
    if count <= 0:
        raise ValueError("La cantidad de transacciones debe ser positiva.")
    rng = Random(seed)
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    countries = ("ES", "FR", "PT", "DE", "IT")
    types = ("Transferencia", "Pago", "Retirada")
    # Fecha fija y generador local: no dependen del reloj ni del azar global.
    return [
        Transaction(
            transaction_id=index + 1,
            account_id=rng.randint(1, 100),
            amount_cents=rng.randint(1, 2_000_000),
            country=rng.choice(countries),
            transaction_type=rng.choice(types),
            timestamp=origin + timedelta(seconds=rng.randrange(31_536_000)),
        )
        for index in range(count)
    ]
