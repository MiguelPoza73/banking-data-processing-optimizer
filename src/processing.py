"""Regla educativa independiente de la interfaz y de futuras mediciones."""

from dataclasses import dataclass
from collections.abc import Sequence

from data_generator import Transaction


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    high_amount_flags: tuple[bool, ...]
    total_cents: int
    high_amount_count: int

    @property
    def processed_count(self) -> int:
        return len(self.high_amount_flags)


def process_transactions(
    transactions: Sequence[Transaction], threshold_cents: int = 1_000_000
) -> ProcessingResult:
    if threshold_cents <= 0:
        raise ValueError("El umbral debe ser positivo.")
    flags: list[bool] = []
    total_cents = 0
    for transaction in transactions:
        if transaction.amount_cents <= 0:
            raise ValueError("Los importes deben ser positivos.")
        # El límite es inclusivo: exactamente 10.000 EUR también se clasifica.
        flags.append(transaction.amount_cents >= threshold_cents)
        total_cents += transaction.amount_cents
    return ProcessingResult(tuple(flags), total_cents, sum(flags))
