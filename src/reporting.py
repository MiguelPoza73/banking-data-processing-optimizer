"""Gráficos de mediciones reales; no ejecuta benchmarks ni abre ventanas al importar."""

from pathlib import Path
from statistics import median

from benchmark import ComparisonResult
from memory_monitor import SAMPLE_INTERVAL_SECONDS


def create_figure(report: ComparisonResult):
    from matplotlib.figure import Figure

    workers = (1, 2, 4)
    labels = ("Secuencial", "2 procesos", "4 procesos")
    colors = ("#2563eb", "#0f766e", "#d97706")
    figure = Figure(figsize=(12, 8), dpi=100)
    axes = figure.subplots(2, 3).flat
    times = [report.median_seconds(count) for count in workers]
    throughputs = [median(row.transactions_per_second for row in report.measurements if row.workers == count) for count in workers]
    metrics = (
        ("Tiempo mediano (menor es mejor)", "Segundos · escala logarítmica", times, True),
        ("Rendimiento mediano (mayor es mejor)", "Transacciones/s · escala logarítmica", throughputs, True),
        ("Speedup respecto al secuencial", "Razón de medianas · escala logarítmica", [report.speedup(count) for count in workers], True),
        ("Mejora del tiempo", "% · negativo significa más lento", [report.time_improvement_percent(count) for count in workers], False),
        ("Memoria RSS observada", "MiB · mediana de máximos muestreados", [report.median_memory_mib(count) for count in workers], False),
    )
    for index, (title, ylabel, values, logarithmic) in enumerate(metrics):
        axis = axes[index]
        axis.set_title(title, fontsize=10, fontweight="bold", pad=12)
        axis.set_ylabel(ylabel, fontsize=8)
        axis.set_xticks(range(3), labels, fontsize=9)
        axis.grid(axis="y", alpha=0.18)
        axis.set_axisbelow(True)
        available = [(position, value) for position, value in enumerate(values) if value is not None]
        if available:
            bars = axis.bar([position for position, _ in available], [value for _, value in available],
                            color=[colors[position] for position, _ in available], width=0.6)
            if logarithmic:
                axis.set_yscale("log")
            else:
                axis.axhline(0, color="#64748b", linewidth=0.8)
            if index == 2:
                axis.axhline(1, color="#64748b", linestyle="--", linewidth=1)
            axis.margins(y=0.25)
            axis.bar_label(bars, labels=[f"{value:.3g}" for _, value in available], padding=4, fontsize=8)
        else:
            axis.text(0.5, 0.5, "Memoria no medida", transform=axis.transAxes, ha="center")

    detail = axes[5]
    detail.axis("off")
    repetitions = sum(row.workers == 1 for row in report.measurements)
    fastest = min(workers, key=report.median_seconds)
    child_counts = [max((row.max_children_observed for row in report.memory_measurements if row.workers == count), default=0) for count in workers]
    detail.text(0, 0.98,
        f"CONFIGURACIÓN MEDIDA\n\n"
        f"Transacciones: {report.transaction_count}\nSemilla: {report.seed}\n"
        f"Umbral: {report.threshold_cents / 100:.2f} EUR\nLote: {report.batch_size}\n"
        f"Repeticiones por estrategia: {repetitions}\n"
        f"Menor mediana: {'secuencial' if fastest == 1 else str(fastest) + ' procesos'}\n\n"
        "Equivalencia correcta en todas las salidas.\n"
        "Tiempo incluye creación/cierre de procesos.\n"
        "Memoria: ronda separada de los tiempos.\n"
        f"Intervalo objetivo: {SAMPLE_INTERVAL_SECONDS * 1000:.0f} ms.\n"
        f"Máx. hijos detectados (1/2/4): {child_counts[0]}/{child_counts[1]}/{child_counts[2]}\n"
        "RSS incluye la aplicación y páginas compartidas.\n"
        "Puede perder picos y procesos breves.",
        va="top", fontsize=8, linespacing=1.4, transform=detail.transAxes)
    figure.suptitle("Banking Data Processing Optimizer — Comparación medida", fontsize=15, fontweight="bold")
    figure.subplots_adjust(left=0.08, right=0.97, bottom=0.09, top=0.88, wspace=0.4, hspace=0.5)
    figure.text(0.5, 0.025, "Un escenario medido; no extrapolar a otros volúmenes. RSS observado no equivale a memoria exclusiva ni a un pico exacto.",
                ha="center", fontsize=8, color="#475569")
    return figure


def save_png(report: ComparisonResult, path: str | Path) -> None:
    figure = create_figure(report)
    try:
        figure.savefig(path, dpi=150)
    finally:
        figure.clear()


def create_scenarios_figure(reports: tuple[ComparisonResult, ...]):
    """Compara escenarios ejecutados manualmente, sin lanzar nuevas cargas."""
    from matplotlib.figure import Figure

    if len(reports) < 2:
        raise ValueError("Completa al menos dos comparaciones para ver escenarios.")
    figure = Figure(figsize=(12, 8), dpi=100)
    axes = figure.subplots(2, 2).flat
    colors = ("#2563eb", "#0f766e", "#d97706")
    labels = [f"#{index + 1}: N={report.transaction_count}\nlote={report.batch_size}, semilla={report.seed}\n"
              f"umbral={report.threshold_cents / 100:g} EUR, R={sum(row.workers == 1 for row in report.measurements)}"
              for index, report in enumerate(reports)]
    for index, (title, ylabel) in enumerate((
        ("Tiempo mediano", "Segundos · escala logarítmica"),
        ("Rendimiento mediano", "Transacciones/s · escala logarítmica"),
        ("Speedup", "Razón de medianas · escala logarítmica"),
        ("Memoria RSS observada", "MiB · mediana de máximos muestreados"),
    )):
        axis = axes[index]
        for workers, offset, color in zip((1, 2, 4), (-0.25, 0, 0.25), colors):
            points = []
            for position, report in enumerate(reports):
                if index == 0:
                    value = report.median_seconds(workers)
                elif index == 1:
                    value = median(row.transactions_per_second for row in report.measurements if row.workers == workers)
                elif index == 2:
                    value = report.speedup(workers)
                else:
                    value = report.median_memory_mib(workers)
                if value is not None:
                    points.append((position + offset, value))
            if points:
                axis.bar([point[0] for point in points], [point[1] for point in points], width=0.23, color=color,
                         label="Secuencial" if workers == 1 else f"{workers} procesos")
        if index != 3:
            axis.set_yscale("log")
        else:
            axis.set_ylim(bottom=0)
        if index == 2:
            axis.axhline(1, linestyle="--", color="#64748b", linewidth=1)
        axis.set_title(title, fontsize=11)
        axis.set_ylabel(ylabel, fontsize=8)
        axis.set_xticks(range(len(reports)), labels, fontsize=7)
        axis.grid(axis="y", alpha=0.15)
        axis.set_axisbelow(True)
        handles, _ = axis.get_legend_handles_labels()
        if handles:
            axis.legend(fontsize=8)
        else:
            axis.text(0.5, 0.5, "Memoria no medida", ha="center", transform=axis.transAxes)
    figure.suptitle("Comparación de escenarios medidos en esta sesión", fontsize=15, fontweight="bold")
    figure.subplots_adjust(left=0.09, right=0.97, bottom=0.17, top=0.9, hspace=0.75, wspace=0.32)
    figure.text(0.5, 0.025, "Cambiar volumen, lote, semilla o umbral modifica el escenario. RSS incluye la aplicación; valores ausentes no significan cero.",
                ha="center", fontsize=8)
    return figure
