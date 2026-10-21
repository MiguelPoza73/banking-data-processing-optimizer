"""Muestreo RSS en ejecuciones independientes de las mediciones temporales."""

from dataclasses import dataclass
from threading import Event, Thread


SAMPLE_INTERVAL_SECONDS = 0.01
MIB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class MemoryMeasurement:
    workers: int
    repetition: int
    baseline_mib: float
    observed_peak_mib: float
    sample_count: int
    max_children_observed: int


class MemoryMonitor:
    def __init__(self) -> None:
        # Importación diferida: las mediciones de tiempo no cargan psutil.
        try:
            import psutil
        except ImportError as exc:
            raise RuntimeError(
                "Falta psutil en el Python que abrió esta ventana. "
                "Cierra la aplicación y ábrela con ejecutar.cmd, en la carpeta del proyecto. "
                "Si aún falta, ejecuta: .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt"
            ) from exc
        self.psutil = psutil
        self.parent = psutil.Process()
        self.stop_event = Event()
        self.samples = 0
        self.peak_bytes = 0
        self.max_children = 0
        self.error: Exception | None = None
        self.thread = Thread(target=self._run, daemon=True)

    def _sample(self) -> int:
        total = self.parent.memory_info().rss
        observed = 0
        for child in self.parent.children(recursive=True):
            try:
                total += child.memory_info().rss
                observed += 1
            except self.psutil.NoSuchProcess:
                # Un trabajador puede finalizar entre enumeración y lectura.
                continue
        self.samples += 1
        self.max_children = max(self.max_children, observed)
        self.peak_bytes = max(self.peak_bytes, total)
        return total

    def _run(self) -> None:
        try:
            while not self.stop_event.wait(SAMPLE_INTERVAL_SECONDS):
                self._sample()
        except Exception as exc:
            self.error = exc

    def start(self) -> None:
        self.baseline_bytes = self._sample()
        self.thread.start()

    def finish(self, workers: int, repetition: int) -> MemoryMeasurement:
        self.stop_event.set()
        self.thread.join()
        if self.error is not None:
            raise RuntimeError(f"No se pudo completar el muestreo de memoria: {self.error}") from self.error
        self._sample()
        return MemoryMeasurement(
            workers, repetition, self.baseline_bytes / MIB, self.peak_bytes / MIB,
            self.samples, self.max_children,
        )
