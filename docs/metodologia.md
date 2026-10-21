# Metodología y guía detallada

Proyecto educativo de Python para estudiar el procesamiento de transacciones bancarias sintéticas y, en fases posteriores, comparar ejecución secuencial con dos y cuatro trabajadores.

**Estado: Fase 5, métricas comparativas, memoria y gráficos.** Las reglas no constituyen un sistema real de detección de blanqueo de capitales.

## Ejecutar en Windows y Visual Studio Code

Requiere Python con Tkinter, `psutil` para memoria de procesos y Matplotlib para gráficos. No utiliza GPU, servicios ni bases de datos. La generación y el procesamiento siguen utilizando la biblioteca estándar; NumPy se instala como dependencia de Matplotlib, pero no interviene en las reglas ni en el benchmark.

1. Abre esta carpeta de proyecto en Visual Studio Code.
2. Después de preparar el entorno virtual, abre la terminal integrada y ejecuta:

```powershell
.\.venv\Scripts\python.exe src/main.py
```

Se abrirá una ventana. Mantén inicialmente 100 transacciones, semilla 42 y umbral 10000 EUR. Pulsa **Generar y procesar** para ver el resumen y las operaciones. Para detener la aplicación, cierra la ventana. No se generan datos automáticamente al abrirla.

También puedes hacer doble clic en **ejecutar.cmd** dentro de esta carpeta. Este acceso utiliza el entorno virtual correcto. En Visual Studio Code selecciona `.venv\Scripts\python.exe` como intérprete si utilizas su botón de ejecución.

El comando habitual `python src/main.py` también funciona: si se inicia con el Python global y existe `.venv` en el proyecto, el arranque se redirige a ese entorno conservando los argumentos. Si ya tienes otro entorno virtual activo, se respeta tu selección. No instala paquetes automáticamente ni modifica el Python global. Los trabajadores de multiprocessing no realizan esta redirección.

Para preparar una copia nueva del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe src/main.py
```

`requirements-lock.txt` fija las versiones usadas en las mediciones de esta fase; `requirements.txt` declara los rangos compatibles. La primera instalación necesita conexión a Internet. Si ejecutas con otro Python, puede indicar que faltan dependencias.

Si falta Tkinter, revisa la instalación de Python y su componente Tcl/Tk. No se instala mediante `pip`. El entorno inicial del desarrollo dispone de Python 3.13 y Tk 8.6.

## Parámetros y resultados

- **Transacciones:** de 1 a 10.000, con 100 por defecto. El límite provisional evita aumentos accidentales de carga; no es una garantía de consumo de recursos. Aumentar el volumen será una decisión posterior.
- **Semilla:** entero que controla el generador aleatorio local. Con la misma versión de Python, código y parámetros se repiten los datos.
- **Umbral:** importe positivo en EUR, sin separadores de miles y con hasta dos decimales. Ejemplos: `10000`, `10000,50` o `10000.50`.
- **Importe elevado:** operación cuyo importe es mayor o igual al umbral. Exactamente 10.000 EUR se incluye con el umbral inicial. Se usa este término porque pagos y retiradas no son necesariamente ingresos.
- El resumen abarca todas las transacciones; la tabla muestra como máximo las primeras 100 para mantener ligera la interfaz.

Los importes se guardan en céntimos enteros y son positivos, entre 0,01 y 20.000 EUR. Los identificadores de cuenta son ficticios. Países y tipos se eligen de catálogos pequeños. Las fechas parten del 1 de enero de 2026 UTC y no dependen del reloj. La distribución uniforme es una simplificación didáctica, no un modelo de actividad bancaria real.

## Arquitectura y decisiones

`main.py` inicia la ventana → `gui.py` valida parámetros y presenta resultados → `data_generator.py` genera una lista reproducible → `processing.py` clasifica y agrega.

La transacción es una dataclass inmutable con slots y campos con nombre. El generador usa `random.Random(seed)` sin modificar el azar global. La clasificación de cada operación es independiente; el recuento y la suma son agregaciones. El resultado conserva una tupla de clasificaciones en el orden de entrada para comparar exactamente las estrategias. `parallel.py` divide en lotes y combina los resultados; `benchmark.py` mide y valida la comparación.

La interfaz y las reglas están separadas. Un hilo de coordinación mantiene disponible la ventana; Tkinter se actualiza exclusivamente desde su hilo principal mediante una cola. Los cálculos secuenciales se realizan en el proceso principal; los paralelos usan procesos independientes. No se admiten ejecuciones simultáneas ni cerrar la ventana durante una ejecución. No hay botón de cancelación en esta fase. El renderizado queda fuera del benchmark.

## Medir el procesamiento secuencial

1. Ejecuta la aplicación con `.\.venv\Scripts\python.exe src/main.py` o `ejecutar.cmd`.
2. Empieza con 100 transacciones, semilla 42, umbral 10000 y **3 repeticiones**.
3. Pulsa **Medir secuencial**. No necesitas pulsar antes «Generar y procesar». El campo Lote solo se aplica al botón de comparación.
4. La ventana mostrará el tiempo y las transacciones por segundo de cada repetición, las medianas y los tiempos mínimo y máximo. El resumen bancario corresponde a la última repetición.
5. Pulsa **Exportar benchmark CSV** y elige dónde guardar el archivo. Cada exportación propone un nombre con un identificador UUID nuevo, como `benchmark_secuencial_9f23b68b533b47178c515a59ad6ad9f8.csv`, para evitar repetir nombres. Puedes recorrer las repeticiones con la barra de desplazamiento.

Se permiten de 1 a 30 repeticiones. Una repetición permite ejecutar la herramienta, pero no estudiar la variación. El CSV conserva la configuración medida aunque cambies después los campos de entrada. Iniciar otra ejecución desactiva la exportación anterior hasta completar una nueva medición. La tabla y la exportación corresponden al último benchmark; exporta antes de sustituirlo. Las últimas seis comparaciones válidas permanecen en RAM para el gráfico de escenarios y desaparecen al cerrar la aplicación.

### Metodología

El módulo `benchmark.py` recibe una lista generada una sola vez antes del cronómetro. Cada repetición procesa esa misma lista, en el mismo orden y con el mismo umbral. No hay calentamiento previo: la primera repetición se conserva. Las ejecuciones siguientes pueden beneficiarse de cachés y del estado del intérprete; no son arranques independientes.

Se utiliza `time.perf_counter()` inmediatamente antes y después de `process_transactions`. Incluye el recorrido completo, la comparación inclusiva, suma de importes, creación de clasificaciones y construcción del resultado. Quedan fuera generación, liberación del resultado anterior, cálculo de métricas, consultas del entorno, actualización de la interfaz y exportación CSV. El benchmark rechaza duraciones no positivas o no finitas y rendimientos no finitos. Si la ejecución falla no se ofrece un informe parcial.

- **Throughput por repetición:** cantidad de transacciones / segundos de esa repetición.
- **Mediana temporal:** mediana de los tiempos individuales.
- **Mediana de throughput:** mediana de los rendimientos individuales. Se calcula directamente; para un número par de repeticiones no tiene por qué coincidir con cantidad / mediana temporal.

El CSV usa UTF-8 con BOM, separador `;` y coma decimal para Excel con configuración española. Los tiempos se exportan con 12 decimales y el rendimiento con 2, sin notación científica ni separadores de miles. Este redondeo de presentación no cambia las mediciones en memoria. Si Excel no reconoce los números, importa con **Datos → Desde texto/CSV** y selecciona la configuración regional española. Cada fila contiene una repetición con solo seis columnas:

| Columna | Significado |
|---|---|
| `repeticion` | Número de ejecución dentro del benchmark. |
| `transacciones` | Cantidad procesada en cada ejecución. |
| `semilla` | Semilla utilizada para generar los datos. |
| `umbral_eur` | Umbral inclusivo expresado en EUR, por ejemplo `10000,00`. |
| `tiempo_segundos` | Duración medida en segundos, mostrada con 12 decimales. |
| `transacciones_por_segundo` | Cantidad de transacciones dividida por esa duración. |

Las medianas, el mínimo y el máximo siguen disponibles en la ventana; no se repiten en el CSV. El archivo no contiene transacciones individuales ni datos del equipo. Es una exportación sencilla del proceso secuencial, no un registro completo del entorno experimental. No se generan archivos técnicos adicionales.

Si una celda aparece como `########` en Excel, amplía la columna haciendo doble clic en el borde derecho de su encabezado. Si persiste, cambia su formato a **General** o **Número**. El CSV no almacena anchos de columna ni formatos de celda; estos dependen de Excel. La columna `transacciones` contiene la cantidad entera procesada, no una fecha.

El botón **Medir secuencial** conserva la metodología original sin lotes, con CSV de seis columnas y sin muestreo de memoria. El botón de comparación incorpora speedup, mejora temporal y memoria opcional mediante otra metodología, descrita abajo: no mezcles sus tiempos con los CSV secuenciales históricos.

Con 100 transacciones las duraciones son muy pequeñas: ruido del sistema, planificación y cachés pueden dominar las diferencias. Mostrar nueve decimales evita redondear a cero; no implica nueve decimales de precisión. No extrapoles estas cifras a volúmenes grandes ni a procesos paralelos. Mantén las mismas condiciones y evita otras cargas si quieres comparar ejecuciones.

## Alcance y revisión

No se incluyen tests automatizados ni pruebas unitarias, por decisión del proyecto. La comparación entre resultados secuenciales y paralelos es una comprobación obligatoria dentro del propio benchmark.

La interfaz guarda CSV y PNG únicamente cuando lo solicitas. El README principal presenta el proyecto y esta guía conserva el detalle de las decisiones y la metodología. El archivo `results/sequential_100_transactions.csv` conserva las mediciones reales de la ejecución inicial, adaptadas al formato reducido.

## Comparar 1, 2 y 4 procesos

1. Abre el programa con `.\.venv\Scripts\python.exe src/main.py` o `ejecutar.cmd`.
2. Mantén inicialmente **100 transacciones, semilla 42, umbral 10000, 3 repeticiones y lote 25**.
3. Pulsa **Comparar 1 / 2 / 4**. Con tres repeticiones se ejecutan nueve mediciones de tiempo. La opción **Medir memoria** está activada inicialmente y añade otras nueve ejecuciones separadas; puedes desmarcarla para terminar antes.
4. Espera a que termine. Verás las mediciones, la equivalencia y la mediana de cada estrategia. La tabla bancaria muestra el conjunto común a las tres.
5. Puedes exportar el CSV comparativo con nombre único. La primera columna es `procesos` (1 para secuencial, 2 o 4), seguida de las seis columnas habituales, `tamano_lote`, `validacion` y tres métricas nuevas: `speedup_mediana`, `mejora_tiempo_pct_mediana` y `memoria_rss_observada_mib`. En la ventana y el CSV las filas se agrupan por estrategia: primero secuencial, después 2 procesos y finalmente 4, con las repeticiones en orden dentro de cada grupo. La validación debe ser `correcta` en todas las filas. El CSV secuencial sigue teniendo seis columnas.

Un lote es un grupo de transacciones enviado como una tarea. Con 100 transacciones y lote 25 hay cuatro tareas; dos trabajadores se reparten esas tareas y cuatro pueden recibir una cada uno. Un lote mayor que el conjunto deja una sola tarea: crear cuatro trabajadores no garantiza que todos tengan trabajo. El último lote puede contener menos transacciones. Se permiten lotes de 1 a 10.000 en la ventana.

### Equivalencia y tiempos comparables

Se genera un único conjunto de datos fuera del cronómetro. Primero se obtiene una referencia secuencial directa sin medir. Cada estrategia procesa las mismas entradas con el mismo umbral y los mismos límites de lote. La estrategia de un proceso también divide y combina los lotes; esto permite comparar la misma organización del trabajo.

Después de cada medición se compara el resultado completo con la referencia: todas las clasificaciones en su orden original, el recuento elevado y la suma de importes. La igualdad se comprueba fuera del cronómetro. Si hay una diferencia o una ejecución falla, se descarta la comparación completa: no se muestran ni se exportan métricas parciales. Validar equivalencia acredita que las estrategias coinciden; no demuestra que la regla modele un problema bancario real.

La medición comparativa incluye particionado, clasificación y agregación. Con 2 y 4 trabajadores incluye además creación del Pool, arranque de intérpretes con `spawn`, serialización de entradas, transferencia entre procesos, recogida de resultados y cierre de trabajadores. Se crea un Pool nuevo por medición; no se mide un servicio con trabajadores reutilizados. `starmap_async` preserva el orden y usa `chunksize=1` porque cada tarea ya representa un lote. La espera del resultado tiene un límite de 30 segundos por configuración; si se supera, se termina el Pool y se invalida el informe. Ese límite no es un límite global de tiempo e incluye la espera del arranque y trabajo, pero no acota todo el cierre.

El orden de ejecución rota entre repeticiones: 1/2/4, 2/4/1 y 4/1/2. La referencia previa ya ha recorrido los datos; no se realizan calentamientos adicionales del Pool. La referencia, generación, validación, métricas y representación quedan fuera del intervalo medido. Los módulos de trabajo son importables y el arranque está protegido por `if __name__ == "__main__"` y `freeze_support()` para Windows.

Crear intérpretes, serializar objetos y coordinar tareas tiene un coste fijo. También coexisten la lista principal, los lotes, las copias transferidas y la memoria de los trabajadores. Por eso se mantienen volúmenes pequeños y se ejecutan estrategias de una en una. La memoria se mide por separado según la metodología de Fase 5.

### Primera medición real

`results/comparison_100_transactions.csv` contiene 100 transacciones, semilla 42, umbral 10.000 EUR, lote 25 y tres repeticiones por estrategia. La ejecución local de desarrollo utilizó Python 3.13 en Windows. Las nueve salidas coincidieron con la referencia. Medianas observadas:

| Procesos de cálculo | Mediana (segundos) |
|---|---:|
| 1 | 0,000070500 |
| 2 trabajadores | 1,347556900 |
| 4 trabajadores | 1,868088500 |

En esta ejecución pequeña, la referencia de un proceso fue más rápida. El coste de procesos es grande en relación con una regla tan sencilla. Estos resultados no permiten extrapolar a cargas mayores y no se comparan directamente con el benchmark histórico sin lotes. Dos o cuatro se refiere a trabajadores, además del proceso principal y los hilos internos de coordinación.

Para repetir la configuración pequeña sin abrir la interfaz:

```powershell
.\.venv\Scripts\python.exe src/main.py --compare
```

Para guardarla en una ruta elegida explícitamente (este comando puede sobrescribir esa ruta):

```powershell
.\.venv\Scripts\python.exe src/main.py --compare --csv results/mi_comparacion.csv
```

## Fase 5: métricas, memoria y gráficos

### ¿Dónde están los gráficos?

Un **CSV contiene texto y cifras, no gráficos**. Al abrirlo en Excel verás una tabla; Excel no dibuja gráficos automáticamente. Después de completar una comparación, pulsa **Ver gráficos** en la aplicación. Se abrirá otra ventana con tiempo, rendimiento, speedup, mejora temporal y memoria. El botón **Guardar gráficos PNG** guarda una imagen con nombre único que puedes insertar en una hoja de Excel, en el README o en un informe. Los gráficos no se guardan automáticamente.

Tiempo, rendimiento y speedup usan escala logarítmica para representar diferencias de varios órdenes de magnitud; lee los valores y las unidades, no interpretes la altura como una proporción lineal. Memoria y mejora porcentual usan escala lineal. Sin memoria medida, el panel lo indica y el CSV deja la celda vacía: no se sustituye por cero.

### Speedup y mejora temporal

Se calculan sobre las **medianas de tiempo** de esta misma comparación con lotes:

- **Speedup:** mediana secuencial / mediana de la estrategia. Mayor que 1 significa más rápido; menor que 1, más lento. El secuencial tiene 1.
- **Mejora temporal (%):** 100 × (mediana secuencial − mediana de la estrategia) / mediana secuencial. El secuencial tiene 0. Un porcentaje negativo indica empeoramiento; no está limitado a −100 % y puede ser muy grande cuando el trabajo secuencial dura apenas microsegundos.

La tabla y el CSV repiten estas dos métricas de estrategia en cada repetición, de ahí los nombres `speedup_mediana` y `mejora_tiempo_pct_mediana`. La memoria de cada fila corresponde a la repetición de la **ronda adicional**, no a la misma ejecución que produjo el tiempo. Una reducción de tiempo no implica una reducción de memoria.

### Metodología de memoria en Windows

La casilla **Medir memoria (ronda adicional)** solo se aplica a **Comparar 1 / 2 / 4**. Con tres repeticiones son nueve ejecuciones para tiempo y nueve adicionales para memoria; todas se validan contra la misma referencia. Las estrategias se ejecutan consecutivamente, nunca simultáneamente. El muestreo se inicia después de completar todas las mediciones temporales, para no incluir su coste en ellas.

`memory_monitor.py` usa `psutil.Process.memory_info().rss` del proceso principal y de los descendientes encontrados con `children(recursive=True)`. Un hilo realiza lecturas con un intervalo objetivo de 10 ms, además de una lectura anterior y otra posterior al procesamiento. Se conserva el mayor total RSS observado de cada ejecución; el gráfico presenta la mediana de esos máximos. MiB significa 1.048.576 bytes. En Windows RSS representa el working set residente. Se utiliza psutil porque permite consultar también los trabajadores; `tracemalloc` del proceso principal no mide su memoria total.

Limitaciones que forman parte de la interpretación:

- Incluye el intérprete, los datos ya generados, resultados retenidos, interfaz y bibliotecas cargadas. **No es memoria exclusiva del algoritmo ni un incremento sobre la memoria inicial.** Tampoco es el porcentaje de toda la RAM del equipo.
- Las páginas compartidas pueden contarse varias veces al sumar RSS. No equivale a memoria física única del conjunto.
- Las lecturas de procesos no son atómicas y los intervalos reales pueden superar 10 ms. Pueden perderse picos y procesos de vida breve; no se afirma medir el pico exacto.
- Se registran el número de muestras y el máximo de hijos detectados. El gráfico muestra este último como contexto, sin garantizar que capture todos los procesos durante toda su vida. En el CLI se imprimen ambos detalles por repetición.
- Una carga secuencial de 100 transacciones puede terminar antes de la primera lectura periódica. En ese caso habrá solo las lecturas anterior y posterior: el valor describe el nivel observado de la aplicación, no demuestra que el algoritmo no haya usado memoria transitoria.
- Los procesos desaparecidos entre enumeración y lectura se omiten. Otros errores de lectura invalidan el informe en lugar de fingir un consumo cero. Un fallo de equivalencia, incluido el de la ronda de memoria, invalida toda la comparación.
- Abrir gráficos carga Matplotlib en el proceso principal. Una comparación posterior puede tener una base de memoria mayor. No compares como equivalentes el CLI, la interfaz y sesiones con distintos módulos o ventanas cargados; para comparar escenarios mantén las mismas condiciones. El motor y los trabajadores no importan Matplotlib.

La documentación técnica utilizada está en [psutil: información de memoria](https://psutil.readthedocs.io/en/stable/#psutil.Process.memory_info) y [Matplotlib: integración con Tkinter](https://matplotlib.org/stable/gallery/user_interfaces/embedding_in_tk_sgskip.html).

### Comparar volúmenes y lotes sin lanzar cargas automáticas

La aplicación conserva en RAM las últimas **seis comparaciones válidas**. Tras completar dos, se habilita **Comparar escenarios**, con gráficos agrupados de tiempo, rendimiento, speedup y memoria. Cada escenario identifica volumen, lote, semilla, umbral y repeticiones. Puedes guardar ese gráfico como PNG. Los datos del historial desaparecen al cerrar; exporta cada CSV antes de sustituirlo si quieres conservarlo.

Ejemplo gradual: completa primero 100 transacciones con lote 25; después cambia solo la cantidad a 200 y repite. Para estudiar el lote, mantén los datos y cambia solo 25 por 50. Cambiar varias variables a la vez dificulta atribuir una diferencia a una causa. No hay barridos automáticos ni aumentos de volumen. En una misma sesión las bibliotecas y la memoria retenida pueden cambiar la base; la comparación es exploratoria y debe interpretarse con esas limitaciones.

### Ejecución sin ventana y artefactos reales de esta fase

```powershell
.\.venv\Scripts\python.exe src/main.py --compare --transactions 100 --repetitions 3 --batch-size 25 --csv results/mi_comparacion.csv --png results/mi_comparacion.png
```

`--no-memory` omite la ronda adicional. También están disponibles `--seed` y `--threshold-cents` (umbral en céntimos). Los nombres explícitos del CLI pueden sobrescribirse; la ventana propone identificadores únicos. La primera creación de gráficos puede tardar más por la caché de fuentes, fuera del cronómetro del procesamiento.

`results/phase5_100_transactions.csv` y su PNG contienen una ejecución real por CLI, con 100 transacciones, lote 25, semilla 42, umbral 10.000 EUR y tres repeticiones, más tres perfiles de memoria por estrategia. Entorno: Python 3.13, Windows x64, psutil 7.2.2 y Matplotlib 3.11.2; dependencias completas en `requirements-lock.txt`. Las 18 salidas coincidieron con la referencia. Medianas de tiempo y de máximos RSS observados:

| Estrategia | Tiempo (s) | RSS observado (MiB) |
|---|---:|---:|
| Secuencial por lotes | 0,000091700 | 25,65 |
| 2 trabajadores | 1,484123700 | 64,05 |
| 4 trabajadores | 1,617703900 | 102,33 |

En este escenario pequeño el secuencial fue más rápido y tuvo menor RSS observado. En las rondas paralelas se detectaron hasta 2 y 4 hijos; el secuencial solo tuvo las dos lecturas de los extremos. No se generaliza a cargas mayores, reglas más costosas ni mediciones de memoria exclusiva. Los archivos de Fase 4 se conservan como históricos y no tienen las métricas nuevas.

También se ejecutaron **200 transacciones**, manteniendo el resto de parámetros y las tres repeticiones, en `results/phase5_200_transactions.csv` y su PNG. Las 18 salidas coincidieron con la referencia. Las medianas temporales fueron 0,000152100 s, 1,523157300 s y 1,653311400 s para 1, 2 y 4 procesos respectivamente; las medianas RSS observadas fueron 25,89, 64,23 y 101,05 MiB. `results/phase5_scenarios.png` compara las dos ejecuciones reales, con todos los parámetros identificados. Los gráficos guardados se regeneraron a partir de esos CSV con su redondeo de presentación. El secuencial fue más rápido en ambos escenarios pequeños; no se ha localizado un volumen donde el paralelismo compense sus costes.
