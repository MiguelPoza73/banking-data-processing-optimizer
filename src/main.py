"""Punto de entrada; importar módulos no inicia la ventana."""

import argparse
from multiprocessing import freeze_support
from pathlib import Path
import subprocess
import sys


def use_project_environment() -> None:
    """Si se arranca con Python global, usar el entorno local ya preparado."""
    if sys.prefix != sys.base_prefix or getattr(sys, "frozen", False):
        return
    script = Path(__file__).resolve()
    environment = script.parent.parent / ".venv"
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if python.is_file() and python.resolve() != Path(sys.executable).resolve():
        # Lista de argumentos: las rutas con espacios se transmiten correctamente.
        # Solo se ejecuta desde main; los trabajadores spawn no se relanzan.
        raise SystemExit(subprocess.call([str(python), str(script), *sys.argv[1:]]))


def main() -> None:
    use_project_environment()
    parser = argparse.ArgumentParser(description="Procesamiento bancario sintético")
    parser.add_argument("--compare", action="store_true", help="Comparación pequeña sin abrir la ventana")
    parser.add_argument("--csv", help="Ruta de exportación de la comparación")
    parser.add_argument("--png", help="Ruta para guardar los gráficos de la comparación")
    parser.add_argument("--transactions", type=int, default=100)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold-cents", type=int, default=1_000_000)
    parser.add_argument("--no-memory", action="store_true", help="Omitir la ronda adicional de memoria")
    args = parser.parse_args()
    if args.compare:
        from benchmark import export_csv, run_comparison
        from data_generator import generate_transactions
        if not 1 <= args.transactions <= 10_000:
            parser.error("Las transacciones deben estar entre 1 y 10.000.")
        if not 1 <= args.repetitions <= 30 or not 1 <= args.batch_size <= 10_000 or args.threshold_cents <= 0:
            parser.error("Revisa repeticiones (1-30), lote (1-10.000) y umbral positivo en céntimos.")
        report = run_comparison(generate_transactions(args.transactions, args.seed), args.seed,
                                args.threshold_cents, args.repetitions, args.batch_size, not args.no_memory)
        for workers in (1, 2, 4):
            print(f"{workers} procesos: mediana {report.median_seconds(workers):.9f} s; "
                  f"speedup {report.speedup(workers):.6g}; mejora {report.time_improvement_percent(workers):.2f}%; "
                  f"RSS observado {report.median_memory_mib(workers)} MiB; equivalencia correcta")
        for memory in report.memory_measurements:
            print(f"Memoria {memory.workers} procesos, repetición {memory.repetition}: "
                  f"{memory.sample_count} muestras; máx. hijos detectados {memory.max_children_observed}")
        if args.csv:
            export_csv(report, args.csv)
        if args.png:
            from reporting import save_png
            save_png(report, args.png)
    else:
        from gui import launch
        launch()


if __name__ == "__main__":
    freeze_support()
    main()
