"""Lotes equivalentes para ejecución secuencial y Pool con spawn."""

from collections.abc import Iterator, Sequence
from multiprocessing import get_context

from data_generator import Transaction
from processing import ProcessingResult, process_transactions


def batches(transactions: Sequence[Transaction], batch_size: int) -> Iterator[Sequence[Transaction]]:
    if batch_size <= 0:
        raise ValueError("El tamaño de lote debe ser positivo.")
    for start in range(0, len(transactions), batch_size):
        yield transactions[start:start + batch_size]


def combine(results: Sequence[ProcessingResult]) -> ProcessingResult:
    return ProcessingResult(
        tuple(flag for result in results for flag in result.high_amount_flags),
        sum(result.total_cents for result in results),
        sum(result.high_amount_count for result in results),
    )


def process_in_batches(
    transactions: Sequence[Transaction], threshold_cents: int,
    batch_size: int, workers: int,
) -> ProcessingResult:
    if workers not in (1, 2, 4):
        raise ValueError("Selecciona 1, 2 o 4 procesos.")
    tasks = [(batch, threshold_cents) for batch in batches(transactions, batch_size)]
    if workers == 1:
        return combine([process_transactions(*task) for task in tasks])
    # Cada tarea ya es un lote; chunksize=1 evita un segundo agrupamiento.
    with get_context("spawn").Pool(processes=workers) as pool:
        results = pool.starmap_async(process_transactions, tasks, chunksize=1).get(timeout=30)
        pool.close()
        pool.join()
    return combine(results)
