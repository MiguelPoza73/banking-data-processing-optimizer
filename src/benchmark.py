"""Medición secuencial sobre un conjunto generado antes del cronómetro."""

import csv
import math
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import get_clock_info, perf_counter
from collections.abc import Sequence

from data_generator import Transaction
from processing import ProcessingResult, process_transactions
from parallel import process_in_batches
from memory_monitor import MemoryMeasurement, MemoryMonitor


MAX_REPETITIONS = 30
CSV_FIELDS = (
    "repeticion", "transacciones", "semilla", "umbral_eur",
    "tiempo_segundos", "transacciones_por_segundo",
)


@dataclass(frozen=True, slots=True)
class Measurement:
    repetition: int
    elapsed_seconds: float
    transactions_per_second: float


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    started_at_utc: str
    transaction_count: int
    seed: int
    threshold_cents: int
    measurements: tuple[Measurement, ...]
    processing_result: ProcessingResult
    python_version: str
    operating_system: str
    machine: str
    processor: str
    clock_resolution_seconds: float

    @property
    def median_seconds(self) -> float:
        return median(row.elapsed_seconds for row in self.measurements)

    @property
    def median_throughput(self) -> float:
        return median(row.transactions_per_second for row in self.measurements)


@dataclass(frozen=True, slots=True)
class ComparisonMeasurement:
    workers: int
    repetition: int
    elapsed_seconds: float
    transactions_per_second: float


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    transaction_count: int
    seed: int
    threshold_cents: int
    batch_size: int
    measurements: tuple[ComparisonMeasurement, ...]
    processing_result: ProcessingResult
    memory_measurements: tuple[MemoryMeasurement, ...] = ()

    def median_seconds(self, workers: int) -> float:
        return median(row.elapsed_seconds for row in self.measurements if row.workers == workers)

    def speedup(self, workers: int) -> float:
        return self.median_seconds(1) / self.median_seconds(workers)

    def time_improvement_percent(self, workers: int) -> float:
        baseline = self.median_seconds(1)
        return 100 * (baseline - self.median_seconds(workers)) / baseline

    def median_memory_mib(self, workers: int) -> float | None:
        values = [row.observed_peak_mib for row in self.memory_measurements if row.workers == workers]
        return median(values) if values else None


def run_comparison(
    transactions: Sequence[Transaction], seed: int, threshold_cents: int,
    repetitions: int = 3, batch_size: int = 25, measure_memory: bool = True,
) -> ComparisonResult:
    if not transactions or batch_size <= 0:
        raise ValueError("Se requieren transacciones y un tamaño de lote positivo.")
    if not 1 <= repetitions <= MAX_REPETITIONS:
        raise ValueError(f"Introduce entre 1 y {MAX_REPETITIONS} repeticiones.")
    if measure_memory:
        MemoryMonitor()  # Detectar la dependencia ausente antes de las mediciones.
    # Referencia directa fuera del cronómetro: comparar todos los flags, no solo totales.
    reference = process_transactions(transactions, threshold_cents)
    measurements: list[ComparisonMeasurement] = []
    orders = ((1, 2, 4), (2, 4, 1), (4, 1, 2))
    for repetition in range(1, repetitions + 1):
        for workers in orders[(repetition - 1) % len(orders)]:
            start = perf_counter()
            result = process_in_batches(transactions, threshold_cents, batch_size, workers)
            elapsed = perf_counter() - start
            if result != reference:
                raise ValueError(f"Resultados diferentes con {workers} procesos. Comparación invalidada.")
            if not math.isfinite(elapsed) or elapsed <= 0:
                raise ValueError("Tiempo de comparación no válido.")
            throughput = len(transactions) / elapsed
            if not math.isfinite(throughput):
                raise ValueError("Rendimiento de comparación no válido.")
            measurements.append(ComparisonMeasurement(workers, repetition, elapsed, throughput))
            del result
    memory_measurements: list[MemoryMeasurement] = []
    if measure_memory:
        # Segunda ronda: el muestreo no contamina los tiempos anteriores.
        for repetition in range(1, repetitions + 1):
            for workers in orders[(repetition - 1) % len(orders)]:
                monitor = MemoryMonitor()
                monitor.start()
                try:
                    result = process_in_batches(transactions, threshold_cents, batch_size, workers)
                finally:
                    memory = monitor.finish(workers, repetition)
                if result != reference:
                    raise ValueError(f"Equivalencia incorrecta al medir memoria con {workers} procesos.")
                memory_measurements.append(memory)
                del result
    return ComparisonResult(len(transactions), seed, threshold_cents, batch_size,
                            tuple(measurements), reference, tuple(memory_measurements))


def run_sequential_benchmark(
    transactions: Sequence[Transaction], seed: int,
    threshold_cents: int, repetitions: int = 3,
) -> BenchmarkResult:
    if not transactions:
        raise ValueError("El benchmark requiere al menos una transacción.")
    if not 1 <= repetitions <= MAX_REPETITIONS:
        raise ValueError(f"Introduce entre 1 y {MAX_REPETITIONS} repeticiones.")
    started_at = datetime.now(timezone.utc).isoformat()
    measurements: list[Measurement] = []
    result = None
    for repetition in range(1, repetitions + 1):
        # Liberar la salida anterior queda fuera de la siguiente medición.
        result = None
        start = perf_counter()
        result = process_transactions(transactions, threshold_cents)
        elapsed = perf_counter() - start
        if not math.isfinite(elapsed) or elapsed <= 0:
            raise ValueError("Tiempo no válido; no se puede calcular el rendimiento.")
        throughput = len(transactions) / elapsed
        if not math.isfinite(throughput):
            raise ValueError("El rendimiento calculado no es válido.")
        if result.processed_count != len(transactions):
            raise ValueError("El procesamiento no ha completado todas las transacciones.")
        measurements.append(Measurement(repetition, elapsed, throughput))
    assert result is not None  # El intervalo de repeticiones garantiza una ejecución.
    return BenchmarkResult(
        started_at, len(transactions), seed, threshold_cents,
        tuple(measurements), result, platform.python_version(),
        platform.platform(), platform.machine(), platform.processor(),
        get_clock_info("perf_counter").resolution,
    )


def export_csv(report: BenchmarkResult | ComparisonResult, path: str | Path) -> None:
    """Exporta las seis columnas esenciales, sin metadatos ni resúmenes repetidos."""
    euros, cents = divmod(report.threshold_cents, 100)
    comparison = isinstance(report, ComparisonResult)
    fields = ("procesos", *CSV_FIELDS, "tamano_lote", "validacion") if comparison else CSV_FIELDS
    rows = sorted(report.measurements, key=lambda row: (row.workers, row.repetition)) if comparison else report.measurements
    if comparison:
        fields = (*fields, "speedup_mediana", "mejora_tiempo_pct_mediana", "memoria_rss_observada_mib")
    memory_by_run = {(row.workers, row.repetition): row for row in report.memory_measurements} if comparison else {}
    # BOM y punto y coma facilitan la apertura en Excel en Windows en español.
    with Path(path).open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for row in rows:
            values = {
                "repeticion": row.repetition,
                "transacciones": report.transaction_count,
                "semilla": report.seed,
                "umbral_eur": f"{euros},{cents:02d}",
                # Coma decimal y formato fijo para Excel con configuración española.
                "tiempo_segundos": f"{row.elapsed_seconds:.12f}".replace(".", ","),
                "transacciones_por_segundo": f"{row.transactions_per_second:.2f}".replace(".", ","),
            }
            if comparison:
                values.update(procesos=row.workers, tamano_lote=report.batch_size, validacion="correcta")
                memory = memory_by_run.get((row.workers, row.repetition))
                values.update(
                    speedup_mediana=f"{report.speedup(row.workers):.9f}".replace(".", ","),
                    mejora_tiempo_pct_mediana=f"{report.time_improvement_percent(row.workers):.2f}".replace(".", ","),
                    memoria_rss_observada_mib=f"{memory.observed_peak_mib:.2f}".replace(".", ",") if memory else "",
                )
            writer.writerow(values)
