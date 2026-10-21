"""Interfaz pequeña para el prototipo secuencial."""

from decimal import Decimal, InvalidOperation
from uuid import uuid4
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from benchmark import (BenchmarkResult, ComparisonResult, MAX_REPETITIONS,
                       export_csv, run_comparison, run_sequential_benchmark)

from data_generator import generate_transactions
from processing import process_transactions


MAX_TRANSACTIONS = 10_000
PREVIEW_ROWS = 100


def format_eur(cents: int) -> str:
    whole, fraction = divmod(cents, 100)
    return f"{whole:,}".replace(",", ".") + f",{fraction:02d} EUR"


def parse_threshold(text: str) -> int:
    # Se admite coma o punto decimal, sin separadores de miles.
    try:
        value = Decimal(text.strip().replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Introduce un umbral numérico, por ejemplo 10000 o 10000,50.") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError("El umbral debe ser un número positivo y finito.")
    cents = value * 100
    if cents != cents.to_integral_value():
        raise ValueError("El umbral admite como máximo dos decimales.")
    return int(cents)


class Application:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.report: BenchmarkResult | ComparisonResult | None = None
        self.busy = False
        self.events = Queue()
        self.history: list[ComparisonResult] = []
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("Banking Data Processing Optimizer")
        root.geometry("1100x780")
        root.minsize(800, 480)
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Procesamiento bancario sintético", font=("Segoe UI", 16, "bold")).pack(anchor="w")

        controls = ttk.Frame(frame)
        controls.pack(fill="x")
        self.count = tk.StringVar(value="100")
        self.seed = tk.StringVar(value="42")
        self.threshold = tk.StringVar(value="10000")
        for column, (label, variable) in enumerate((
            ("Transacciones", self.count), ("Semilla", self.seed), ("Umbral EUR (sin miles)", self.threshold)
        )):
            ttk.Label(controls, text=label).grid(row=0, column=column, sticky="w", padx=(0, 12))
            ttk.Entry(controls, textvariable=variable, width=24).grid(row=1, column=column, padx=(0, 12), sticky="w")
        self.run_button = ttk.Button(controls, text="Generar y procesar", command=self.run)
        self.run_button.grid(row=1, column=3)
        benchmark_controls = ttk.Frame(frame)
        benchmark_controls.pack(fill="x", pady=(10, 0))
        self.repetitions = tk.StringVar(value="3")
        ttk.Label(benchmark_controls, text="Repeticiones").pack(side="left")
        ttk.Entry(benchmark_controls, textvariable=self.repetitions, width=6).pack(side="left", padx=8)
        self.sequential_button = ttk.Button(benchmark_controls, text="Medir secuencial", command=lambda: self.run(benchmark=True))
        self.sequential_button.pack(side="left")
        self.batch_size = tk.StringVar(value="25")
        ttk.Label(benchmark_controls, text="Lote").pack(side="left", padx=(8, 0))
        ttk.Entry(benchmark_controls, textvariable=self.batch_size, width=6).pack(side="left", padx=8)
        self.compare_button = ttk.Button(benchmark_controls, text="Comparar 1 / 2 / 4", command=lambda: self.run(benchmark=True, comparison=True))
        self.compare_button.pack(side="left")
        self.export_button = ttk.Button(benchmark_controls, text="Exportar benchmark CSV", command=self.save_report, state="disabled")
        self.export_button.pack(side="left", padx=8)
        report_controls = ttk.Frame(frame)
        report_controls.pack(fill="x", pady=(8, 0))
        self.measure_memory = tk.BooleanVar(value=True)
        ttk.Checkbutton(report_controls, text="Medir memoria (ronda adicional)", variable=self.measure_memory).pack(side="left")
        self.charts_button = ttk.Button(report_controls, text="Ver gráficos", command=self.show_charts, state="disabled")
        self.charts_button.pack(side="left", padx=8)
        self.history_button = ttk.Button(report_controls, text="Comparar escenarios", command=lambda: self.show_charts(scenarios=True), state="disabled")
        self.history_button.pack(side="left", padx=(0, 8))
        ttk.Label(report_controls, text="Los gráficos se guardan como PNG; el CSV contiene las cifras.").pack(side="left")
        ttk.Label(frame, text="Inicio: 100 transacciones. Límite provisional: 10.000. Umbral inclusivo (≥).").pack(anchor="w", pady=(10, 4))
        self.summary = tk.StringVar(value="Configura los parámetros y pulsa «Generar y procesar».")
        ttk.Label(frame, textvariable=self.summary, wraplength=950).pack(anchor="w", pady=(4, 12))

        self.benchmark_summary = tk.StringVar(value="Benchmark pendiente. Se mide solo el procesamiento; datos generados una vez.")
        ttk.Label(frame, textvariable=self.benchmark_summary, wraplength=1000).pack(anchor="w", pady=(0, 6))
        metrics_frame = ttk.Frame(frame)
        metrics_frame.pack(fill="x", pady=(0, 12))
        self.metrics = ttk.Treeview(metrics_frame, columns=("workers", "repetition", "seconds", "throughput", "speedup", "improvement", "memory", "validation"), show="headings", height=4)
        for name, title in (("workers", "Procesos"), ("repetition", "Repetición"), ("seconds", "Tiempo (s)"), ("throughput", "Transacciones/s"), ("speedup", "Speedup*"), ("improvement", "Mejora (%)*"), ("memory", "RSS obs. (MiB)**"), ("validation", "Equivalencia")):
            self.metrics.heading(name, text=title)
            self.metrics.column(name, width=115, minwidth=55)
        metrics_scroll = ttk.Scrollbar(metrics_frame, orient="vertical", command=self.metrics.yview)
        self.metrics.configure(yscrollcommand=metrics_scroll.set)
        metrics_scroll.pack(side="right", fill="y")
        self.metrics.pack(fill="x", expand=True)
        ttk.Label(frame, text="* Razón/mejora de medianas. Speedup > 1: más rápido; mejora negativa: más lento. ** Memoria en otra ejecución.", wraplength=1000).pack(anchor="w", pady=(0, 5))

        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True)
        columns = ("id", "account", "amount", "country", "type", "timestamp", "classification")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings")
        for name, label, width in zip(columns,
            ("ID", "Cuenta ficticia", "Importe", "País", "Tipo", "Fecha UTC", "Clasificación"),
            (50, 100, 130, 50, 110, 155, 130)):
            self.table.heading(name, text=label)
            self.table.column(name, width=width, minwidth=40)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table.pack(side="left", fill="both", expand=True)
        self.status = tk.StringVar(value="Sin ejecutar. Con 100 transacciones los tiempos serán muy pequeños y variables.")
        ttk.Label(frame, textvariable=self.status).pack(anchor="w", pady=(10, 0))

    def run(self, benchmark: bool = False, comparison: bool = False) -> None:
        if self.busy:
            return
        # Una nueva ejecución invalida la exportación anterior, incluso si falla.
        self.report = None
        self.export_button.configure(state="disabled")
        self.charts_button.configure(state="disabled")
        metric_rows = self.metrics.get_children()
        if metric_rows:
            self.metrics.delete(*metric_rows)
        self.benchmark_summary.set("Benchmark pendiente.")
        try:
            try:
                count = int(self.count.get())
                seed = int(self.seed.get())
            except ValueError as exc:
                raise ValueError("La cantidad y la semilla deben ser números enteros.") from exc
            if not 1 <= count <= MAX_TRANSACTIONS:
                raise ValueError(f"Introduce entre 1 y {MAX_TRANSACTIONS} transacciones.")
            threshold = parse_threshold(self.threshold.get())
            repetitions = 3
            if benchmark:
                try:
                    repetitions = int(self.repetitions.get())
                except ValueError as exc:
                    raise ValueError("Las repeticiones deben ser un número entero.") from exc
                if not 1 <= repetitions <= MAX_REPETITIONS:
                    raise ValueError(f"Introduce entre 1 y {MAX_REPETITIONS} repeticiones.")
            batch_size = 25
            if comparison:
                try:
                    batch_size = int(self.batch_size.get())
                except ValueError as exc:
                    raise ValueError("El tamaño de lote debe ser un entero positivo.") from exc
                if not 1 <= batch_size <= MAX_TRANSACTIONS:
                    raise ValueError(f"El lote debe estar entre 1 y {MAX_TRANSACTIONS}.")
        except ValueError as exc:
            self.status.set("Ejecución cancelada. No hay un benchmark exportable; la tabla conserva la última ejecución completada.")
            messagebox.showerror("Revisa los parámetros", str(exc), parent=self.root)
            return

        self.busy = True
        self.history_button.configure(state="disabled")
        measure_memory = self.measure_memory.get()
        for button in (self.run_button, self.sequential_button, self.compare_button):
            button.configure(state="disabled")
        self.status.set("Procesando… Se medirá memoria en una segunda ronda; espera a que finalice."
                        if comparison and measure_memory else "Procesando… Espera a que finalice.")

        def work() -> None:
            # El hilo solo mantiene disponible la ventana; el cálculo usa 1/2/4 procesos.
            # Ninguna llamada Tkinter debe ejecutarse desde este hilo.
            try:
                transactions = generate_transactions(count, seed)
                report = None
                if comparison:
                    report = run_comparison(transactions, seed, threshold, repetitions, batch_size, measure_memory)
                elif benchmark:
                    report = run_sequential_benchmark(transactions, seed, threshold, repetitions)
                result = report.processing_result if report is not None else process_transactions(transactions, threshold)
                self.events.put((transactions, result, report, count, seed, threshold, repetitions))
            except Exception as exc:
                self.events.put(exc)

        Thread(target=work, daemon=True).start()
        self.root.after(100, self.poll_result)

    def poll_result(self) -> None:
        try:
            event = self.events.get_nowait()
        except Empty:
            self.root.after(100, self.poll_result)
            return
        self.busy = False
        self.history_button.configure(state="normal" if len(self.history) >= 2 else "disabled")
        for button in (self.run_button, self.sequential_button, self.compare_button):
            button.configure(state="normal")
        if isinstance(event, Exception):
            self.status.set("Ejecución fallida. No hay benchmark exportable; la tabla conserva la última ejecución completada.")
            messagebox.showerror("No se pudo completar", str(event) or type(event).__name__, parent=self.root)
            return
        transactions, result, self.report, count, seed, threshold, repetitions = event
        self.show_result(transactions, result, count, seed, threshold, repetitions)

    def show_result(self, transactions, result, count, seed, threshold, repetitions) -> None:
        if isinstance(self.report, ComparisonResult):
            self.history.append(self.report)
            self.history = self.history[-6:]
            self.history_button.configure(state="normal" if len(self.history) >= 2 else "disabled")
            memory_by_run = {(row.workers, row.repetition): row for row in self.report.memory_measurements}
            for row in sorted(self.report.measurements, key=lambda row: (row.workers, row.repetition)):
                strategy = "Secuencial" if row.workers == 1 else f"{row.workers} procesos"
                memory = memory_by_run.get((row.workers, row.repetition))
                self.metrics.insert("", "end", values=(strategy, row.repetition, f"{row.elapsed_seconds:.9f}", f"{row.transactions_per_second:,.2f}",
                    f"{self.report.speedup(row.workers):.6g}", f"{self.report.time_improvement_percent(row.workers):.2f}",
                    f"{memory.observed_peak_mib:.2f}" if memory else "No medida", "Correcta"))
            medians = {workers: self.report.median_seconds(workers) for workers in (1, 2, 4)}
            fastest = min(medians, key=medians.get)
            self.benchmark_summary.set(
                "Equivalencia correcta: clasificaciones en orden, recuentos y total coinciden en todas las ejecuciones.\n"
                + " · ".join(f"Mediana {workers} procesos: {seconds:.9f} s" for workers, seconds in medians.items())
                + f"\nMenor mediana observada: {fastest} procesos · Lote: {self.report.batch_size} · "
                f"{repetitions} repeticiones por estrategia. Incluye creación y cierre de trabajadores."
            )
            self.export_button.configure(state="normal")
            self.charts_button.configure(state="normal")
        elif self.report is not None:
            for row in self.report.measurements:
                self.metrics.insert("", "end", values=(1, row.repetition, f"{row.elapsed_seconds:.9f}", f"{row.transactions_per_second:,.2f}", "—", "—", "No medida", "No aplica"))
            self.benchmark_summary.set(
                f"Mediana: {self.report.median_seconds:.9f} s · "
                f"Mediana de rendimiento: {self.report.median_throughput:,.2f} transacciones/s\n"
                f"Mínimo: {min(row.elapsed_seconds for row in self.report.measurements):.9f} s · "
                f"Máximo: {max(row.elapsed_seconds for row in self.report.measurements):.9f} s · "
                f"{repetitions} repeticiones · {count} transacciones · Semilla {seed} · Umbral {format_eur(threshold)}\n"
                "Sin calentamiento. Con 100 transacciones, interpreta las diferencias con cautela."
            )
            self.export_button.configure(state="normal")

        children = self.table.get_children()
        if children:
            self.table.delete(*children)
        for transaction, elevated in zip(transactions[:PREVIEW_ROWS], result.high_amount_flags[:PREVIEW_ROWS]):
            self.table.insert("", "end", values=(
                transaction.transaction_id, transaction.account_id,
                format_eur(transaction.amount_cents), transaction.country,
                transaction.transaction_type, transaction.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Importe elevado" if elevated else "Importe inferior",
            ))
        self.summary.set(
            f"Procesadas: {result.processed_count} · Importe elevado: {result.high_amount_count} · "
            f"Importe inferior: {result.processed_count - result.high_amount_count}\n"
            f"Total: {format_eur(result.total_cents)} · Umbral: {format_eur(threshold)} · Semilla: {seed}"
        )
        mode = "Comparación 1 / 2 / 4" if isinstance(self.report, ComparisonResult) else "Ejecución secuencial"
        self.status.set(f"Finalizado · Vista de las primeras {min(count, PREVIEW_ROWS)} de {count} transacciones · {mode}")

    def close(self) -> None:
        if self.busy:
            messagebox.showinfo("Ejecución en curso", "Espera a que termine la ejecución antes de cerrar.", parent=self.root)
            return
        self.root.destroy()

    def show_charts(self, scenarios: bool = False) -> None:
        if self.busy or (not scenarios and not isinstance(self.report, ComparisonResult)):
            return
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from reporting import create_figure, create_scenarios_figure
        except ImportError:
            messagebox.showerror("Faltan dependencias", "Instala requirements.txt y ejecuta con el Python del entorno virtual.", parent=self.root)
            return
        # La ventana conserva esta ejecución, aunque después se mida otra.
        window = tk.Toplevel(self.root)
        window.title("Gráficos de la comparación")
        window.geometry("1100x760")
        figure = create_scenarios_figure(tuple(self.history)) if scenarios else create_figure(self.report)

        def save() -> None:
            path = filedialog.asksaveasfilename(parent=window, title="Guardar gráficos PNG", defaultextension=".png",
                filetypes=[("Imagen PNG", "*.png")], initialfile=f"graficos_{uuid4().hex}.png")
            if path:
                try:
                    figure.savefig(path, dpi=150)
                except OSError as exc:
                    messagebox.showerror("No se pudo guardar", str(exc), parent=window)

        ttk.Button(window, text="Guardar gráficos PNG", command=save).pack(pady=6)
        canvas = FigureCanvasTkAgg(figure, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        def close_chart() -> None:
            figure.clear()
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close_chart)

    def save_report(self) -> None:
        if self.report is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Guardar benchmark",
            defaultextension=".csv", filetypes=[("Archivo CSV", "*.csv")],
            initialfile=f"benchmark_{'comparacion' if isinstance(self.report, ComparisonResult) else 'secuencial'}_{uuid4().hex}.csv",
        )
        if not path:
            return
        try:
            export_csv(self.report, path)
        except OSError as exc:
            messagebox.showerror("No se pudo guardar", str(exc), parent=self.root)
            return
        self.status.set(f"Benchmark exportado: {path}")


def launch() -> None:
    root = tk.Tk()
    Application(root)
    root.mainloop()
