# 🎤 Vocal Intelligence Pipeline

**Análisis vocal en tiempo real con IA, streaming y Machine Learning**

> *Balda Javier · Caracoix Juan · Casas Facundo*  
> Universidad Católica Argentina — Análisis y Procesamiento de Datos Streaming — 2026

---

## ¿Qué hace este proyecto?

Toma el audio de una canción, lo analiza nota por nota a 20 frames por segundo, y produce en tiempo real tres tipos de output: una predicción del tipo de voz del intérprete, alertas sobre eventos técnicos vocales (clímax, breaks, caídas de intensidad), y métricas comparativas contra seis perfiles vocales de referencia.

Todo el sistema corre sobre Apache Kafka. El audio entra como stream de frames y sale como mensajes clasificados en dos tópicos distintos.

---

## Vista rápida — 4 pasos para ver el proyecto funcionando

```
1.  Abrir results/vocal_unified_dashboard.html en el navegador
2.  Cargar musica.mp3 con el botón 🎵
3.  Dar play → la nota se actualiza en tiempo real con el audio
4.  Explorar las 4 pestañas: Análisis · Comparador · Anomalías · Kafka
```

El dashboard tiene todos los resultados pre-calculados embebidos. No necesita servidor ni dependencias instaladas.

---

## Arquitectura del sistema

```
musica.mp3 / WAV
      │
      ▼ src/audio_loader.py (yt-dlp + Demucs)
      │
      ▼ src/pipeline.py (pYIN + torchcrepe)
      │
results/realtime_frames.csv   ← 1801 frames · 50ms/frame
      │
      ├──► comparador_multiartista/vocal_comparador.py  ──► comparador_dashboard.html
      │         (16 métricas × 6 perfiles)
      │
      ├──► anomalias/anomaly_detector.py  ──────────────► anomaly_dashboard.html
      │         (212 eventos · 6 tipos)
      │
      ├──► clasificador_ml/vocal_classifier.py  ─────────► vocal_rf.pkl
      │         (Random Forest · 69% acc · 20 features)
      │
      └──► kafka_streaming/vocal_producer.py
                  │   vocal.frames (50ms/frame)
                  ▼
           Kafka KRaft 3.9.1  (kafka_2.13-3.9.1/)
                  │
                  ▼ kafka_streaming/vocal_consumer.py
                  ├── vocal.analyzed  (predicción por ventana 2s)
                  └── vocal.alerts    (anomalías en tiempo real)

Todo visible en:  results/vocal_unified_dashboard.html
```

### Cómo se conectan los módulos

| Módulo | Ubicación | Qué hace |
|--------|-----------|----------|
| `pipeline.py` | `src/` | Analiza audio con pYIN + torchcrepe → CSV |
| `audio_loader.py` | `src/` | Descarga de YouTube, corte de segmentos, Demucs |
| `artist_profiles.py` | `comparador_multiartista/` | 6 perfiles vocales sintéticos con timbre/vibrato |
| `vocal_comparador.py` | `comparador_multiartista/` | Extrae 16 métricas por perfil |
| `anomaly_detector.py` | `anomalias/` | 6 reglas de detección sobre los frames |
| `pipeline_with_anomaly.py` | `anomalias/` | Pipeline + detección integrados |
| `vocal_classifier.py` | `clasificador_ml/` | Random Forest sobre ventanas de 2s |
| `vocal_producer.py` | `kafka_streaming/` | Emite frames a `vocal.frames` (50ms/frame) |
| `vocal_consumer.py` | `kafka_streaming/` | Clasifica y detecta en tiempo real |

---

## Estructura del repositorio

```
challenge_streaming-main/
│
├── src/                              ← pipeline base (challenge original)
│   ├── pipeline.py                   # pYIN + torchcrepe → realtime_frames.csv
│   ├── audio_loader.py               # YouTube, MP3 local, segmentos, Demucs
│   ├── generate_demo.py              # audio sintético S.O.S
│   └── metrics.py                    # métricas musicales
│
├── comparador_multiartista/          ← Idea C: comparación entre voces
│   ├── artist_profiles.py            # 6 perfiles (barítono, soprano, tenor, ...)
│   ├── vocal_comparador.py           # extracción de 16 métricas
│   ├── artist_dataset.json           # dataset completo con timelines
│   ├── artist_metrics.csv            # tabla comparativa 6×16
│   └── comparador_dashboard.html     # dashboard interactivo
│
├── anomalias/                        ← Idea D: detección de eventos vocales
│   ├── anomaly_detector.py           # 6 tipos de anomalías con severidad
│   ├── pipeline_with_anomaly.py      # pipeline.py + detector integrados
│   ├── anomalies.json                # 212 eventos detectados en S.O.S
│   └── anomaly_dashboard.html        # dashboard con timeline anotado
│
├── clasificador_ml/                  ← Idea A: clasificador de tipo vocal
│   ├── vocal_classifier.py           # Random Forest, 20 features, 6 clases
│   ├── vocal_rf.pkl                  # modelo entrenado (no subir a Git*)
│   └── experiment_metrics.json       # accuracy 68.9%, F1 macro 66.8%
│
├── kafka_streaming/                  ← Idea B: pipeline en streaming
│   ├── vocal_producer.py             # emite CSV a vocal.frames (50ms/frame)
│   ├── vocal_consumer.py             # clasifica + detecta en tiempo real
│   ├── kafka_dashboard.html          # dashboard Kafka standalone
│   └── stream_output_demo.json       # resultado pre-generado para la demo
│
├── kafka_2.13-3.9.1/                 ← Apache Kafka KRaft (incluido en el repo)
│   ├── bin/                          # kafka-server-start.sh, kafka-storage.sh, ...
│   └── config/kraft/server.properties
│
├── results/                          ← outputs del análisis (pre-calculados)
│   ├── realtime_frames.csv           # 1801 frames del análisis de S.O.S
│   ├── metrics.json                  # métricas de la canción
│   ├── dashboard.html                # dashboard original del challenge
│   ├── live_dashboard.html           # dashboard con audio sincronizado
│   ├── vocal_unified_dashboard.html  # ★ dashboard unificado (punto de entrada)
│   ├── vocal_rf.pkl                  # modelo RF entrenado
│   ├── stream_output.json            # resultado del stream Kafka real
│   └── prediction_result.json        # predicción sobre S.O.S
│
├── vocal_analysis/output/            ← outputs del pipeline en vivo
│   ├── bogdan_sos_synthetic.wav      # audio sintético generado
│   ├── frame_analysis.json           # frames en JSON (alternativa al CSV)
│   └── metrics.json                  # métricas del análisis en vivo
│
├── docs/
│   ├── GUION_PRESENTACION.md         # guion detallado con explicaciones de scripts
│   └── GUIA_EXPOSICION.md            # estructura de la exposición
│
├── musica.mp3                        # canción de referencia (S.O.S — Bogdan)
├── requirements.txt
└── README.md

* vocal_rf.pkl pesa ~7MB. Agregar a .gitignore y regenerar con el Paso 4.
```

---

## Instalación

### Requisitos

- Python 3.10+
- Java 17 (solo necesario para el pipeline Kafka — Pasos 6–7)
- FFmpeg (para conversión de audio con `audio_loader.py`)

### Dependencias Python

```bash
pip install -r requirements.txt
```

El archivo `requirements.txt` cubre todo el proyecto. Si querés instalar por módulo:

```bash
# Pipeline base
pip install librosa numpy scipy pandas matplotlib

# Detección de pitch con CNN (GPU opcional)
pip install torchcrepe torch

# Separación vocal
pip install demucs

# Descarga de YouTube
pip install yt-dlp

# Machine Learning
pip install scikit-learn

# Kafka
pip install confluent-kafka
```

---

## Ejecución — orden correcto

El diagrama de dependencias es este:

```
Paso 1 (pipeline)  →  Paso 2 (anomalías)
                   →  Paso 3 (comparador)
                            ↓
                       Paso 4 (clasificador)
                            ↓
                   Pasos 5–6–7 (Kafka)
```

Los pasos 2, 3 y 4 son independientes entre sí. Los pasos 5–7 requieren que el Paso 4 haya generado `results/vocal_rf.pkl`.

---

### Paso 1 — Análisis de audio → CSV de frames

Este es el paso base. Genera `results/realtime_frames.csv`, que es la entrada de todos los módulos siguientes.

```bash
# Opción A: audio sintético (no requiere descargar nada, ~2 min)
python src/pipeline.py --demo

# Opción B: canción local
python src/pipeline.py --audio musica.mp3

# Opción C: desde YouTube (requiere yt-dlp + cookies.txt para autenticación) (Under Development)
python src/audio_loader.py --youtube "https://youtu.be/CduA0TULnow" \
  --cookies-browser chrome
# El WAV descargado y separado queda en vocal_analysis/output/
python src/pipeline.py --audio vocal_analysis/output/audio_descargado.wav --no-demucs

# Opción D: segmento específico (ej: solo el estribillo, 1:30 a 2:30)
python src/audio_loader.py --audio musica.mp3 --start 90 --end 150
python src/pipeline.py --audio vocal_analysis/output/musica_converted.wav --no-demucs
```

Output: `results/realtime_frames.csv`, `results/metrics.json`, `results/dashboard.html`

---

### Paso 2 — Detección de anomalías

Lee el CSV del Paso 1 y detecta 6 tipos de eventos vocales.

```bash
python anomalias/anomaly_detector.py \
  --csv results/realtime_frames.csv \
  --out anomalias/anomalies.json
```

O con el pipeline integrado (Pasos 1 + 2 en un solo comando):

```bash
python anomalias/pipeline_with_anomaly.py --demo
# equivale a: pipeline.py --demo + anomaly_detector.py
```

Output: `anomalias/anomalies.json` (212 eventos), imprime reporte en consola.

---

### Paso 3 — Comparador multi-artista

Genera los perfiles sintéticos y extrae las 16 métricas para el dashboard comparativo.

```bash
python comparador_multiartista/vocal_comparador.py --out results/

# Para agregar la canción real al comparador:
python comparador_multiartista/vocal_comparador.py \
  --out results/ \
  --csv results/realtime_frames.csv \
  --id bogdan_real \
  --name "Bogdan (análisis real)"
```

Output: `comparador_multiartista/artist_dataset.json`, `comparador_multiartista/artist_metrics.csv`

---

### Paso 4 — Entrenar el clasificador ML

Entrena el Random Forest sobre ventanas de 2 segundos del dataset del Paso 3.

```bash
# Opción A: solo perfiles sintéticos
python clasificador_ml/vocal_classifier.py \
  --train comparador_multiartista/artist_dataset.json \
  --out results/

# Opción B: sintéticos + CSV real (mayor precisión)
# IMPORTANTE: --csv-real toma DOS argumentos juntos: ruta y etiqueta
python clasificador_ml/vocal_classifier.py \
  --train comparador_multiartista/artist_dataset.json \
  --csv-real results/realtime_frames.csv "Tenor dramático" \
  --out results/
```

Output: `results/vocal_rf.pkl`, `clasificador_ml/experiment_metrics.json`  
Accuracy esperada: **68.9%** en 6 clases (baseline aleatorio: 16.7%)

Para predecir sobre una canción nueva:

```bash
python clasificador_ml/vocal_classifier.py \
  --predict results/realtime_frames.csv \
  --model results/vocal_rf.pkl
# → Predicción: Tenor dramático (98.5% confianza)
```

---

### Paso 5 — Ver los resultados en el dashboard unificado

Abrir directamente en el navegador — no requiere servidor:

```bash
# macOS
open results/vocal_unified_dashboard.html

# Linux
xdg-open results/vocal_unified_dashboard.html

# Windows
start results/vocal_unified_dashboard.html
```

El dashboard tiene **4 pestañas**:

| Pestaña | Contenido | Requiere |
|---------|-----------|----------|
| 📊 Análisis base | Pitch, intensidad, distribución de registros. Cargar `musica.mp3` para sincronizar audio | Resultados del Paso 1 (pre-cargados) |
| 🎙 Comparador | 6 perfiles, radar, stacked bar, timeline de pitch por artista | Pre-cargado |
| ⚡ Anomalías | Timeline con 212 eventos anotados, log por tipo y severidad | Pre-cargado |
| 🔀 Kafka Stream | Simulación del stream: tópicos, confianza temporal, alertas en vivo | Pre-cargado (sin Kafka real) |

> **Reproducción de audio sincronizada:** en la pestaña "Análisis base", hacer clic en "🎵 Cargar audio WAV/MP3" y seleccionar `musica.mp3`. La nota y el registro se actualizan cuadro a cuadro con el audio mientras suena.

---

### Paso 6 — Iniciar Kafka KRaft (para el pipeline en vivo)

Kafka ya está incluido en el repositorio en `kafka_2.13-3.9.1/`. Solo requiere Java 17.

```bash
# Verificar Java
java -version  # debe ser 17+

# Instalar si no está (Ubuntu / Colab)
sudo apt-get install -y openjdk-17-jdk-headless
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Configurar y arrancar el broker
export KAFKA_DIR=kafka_2.13-3.9.1

# Generar cluster ID y formatear storage (solo la primera vez)
CLUSTER_ID=$($KAFKA_DIR/bin/kafka-storage.sh random-uuid)
$KAFKA_DIR/bin/kafka-storage.sh format \
  -t "$CLUSTER_ID" \
  -c $KAFKA_DIR/config/kraft/server.properties

# Arrancar el broker en background
$KAFKA_DIR/bin/kafka-server-start.sh \
  $KAFKA_DIR/config/kraft/server.properties > /tmp/kafka.log 2>&1 &

# Verificar que está corriendo (esperar ~8 segundos)
sleep 8
$KAFKA_DIR/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
# Si no hay error, Kafka está activo
```

> **En Google Colab:** usar el notebook `kafka_streaming/Pipeline_Kafka_Vocal_Streaming_Balda_Caracoix_Casas.ipynb` que automatiza la instalación de Java y el setup de Kafka en las primeras dos secciones.

---

### Paso 7 — Correr el pipeline Kafka en vivo

Con Kafka corriendo (Paso 6), abrir **dos terminales**:

```bash
# Terminal A — Consumer (arranca primero, espera mensajes)
python kafka_streaming/vocal_consumer.py \
  --model results/vocal_rf.pkl \
  --out results/stream_output.json

# Terminal B — Producer (emite los frames)
python kafka_streaming/vocal_producer.py \
  --csv results/realtime_frames.csv

# Modo turbo (sin delay entre frames, útil para demos):
python kafka_streaming/vocal_producer.py \
  --csv results/realtime_frames.csv --fast

# Modo demo con artista sintético (sin CSV):
python kafka_streaming/vocal_producer.py --demo --artist soprano
```

El consumer imprime cada predicción y cada alerta en tiempo real:

```
[ANALYZED] w0001 t=0.0s  → Tenor dramático       (98%)
[ANALYZED] w0002 t=0.5s  → Tenor dramático       (99%)
[ALERT]    ⏸  SILENCIO_LARGO    t=44.0s  sev=media
[ALERT]    🎯 AGUDO_EXTREMO     t=59.7s  sev=alta
[ALERT]    🔥 CLIMAX_VOCAL      t=67.4s  sev=media
```

Output: `results/stream_output.json` con todas las predicciones y alertas del stream.

---

### Flujo alternativo — Colab (todo en un notebook)

Para ejecutar el pipeline completo en Google Colab sin terminales separadas, el notebook del Paso 6 incluye una celda de **modo threading** que lanza producer y consumer en paralelo:

```python
import threading
t_consumer = threading.Thread(target=run_consumer, daemon=True)
t_producer = threading.Thread(target=run_producer)
t_consumer.start()
t_producer.start()
t_producer.join()
t_consumer.join(timeout=15)
```

---

## Datos y resultados pre-calculados

Los archivos en `results/` contienen los resultados del análisis de S.O.S de Bogdan Shuvalov. Se pueden usar directamente sin re-ejecutar los pasos de análisis.

### Canción de referencia

| Métrica | Valor |
|---------|-------|
| Canción | S.O.S — Bogdan Shuvalov |
| Duración analizada | 90 segundos |
| Rango vocal | A2 → C6 (3.28 oct, 39.3 semitonos) |
| Nota más frecuente | G5 |
| Frecuencia promedio | 502.5 Hz (≈ B4) |
| Pico de intensidad | C6 @ 69.35s (36.5 RMS) |
| Frames totales | 1801 (97% con voz detectada) |

### Clasificador ML

| Clase | Precision | Recall | F1 |
|-------|-----------|--------|----|
| Soprano | 0.84 | 0.88 | **0.86** |
| Tenor dramático | 0.84 | 0.78 | **0.81** |
| Barítono | 0.70 | 0.80 | 0.74 |
| Mezzo-soprano | 0.50 | 0.64 | 0.56 |
| Tenor lírico-pop | 0.62 | 0.49 | 0.55 |
| Contratenor | 0.52 | 0.47 | 0.49 |

Accuracy global 5-fold CV: **68.9%** · Baseline aleatorio: 16.7%  
Feature más discriminativa: `int_mean` (21% — nivel de proyección vocal)  
Predicción sobre S.O.S: **Tenor dramático · 98.5% confianza**

### Anomalías detectadas

| Tipo | Eventos | Umbral |
|------|---------|--------|
| CLIMAX_VOCAL | 95 | 8 frames consecutivos en agudo (0.4s) |
| INESTABILIDAD | 64 | CV de Hz > 2.5% en ventana de 8 frames |
| CAIDA_INTENS | 51 | Caída ≥ 50% del pico local en 10 frames |
| AGUDO_EXTREMO | 1 | Primera nota sobreaguda — C6 @ 59.7s |
| SILENCIO_LARGO | 1 | Pausa estructural — 0.8s @ 44s |

### Comparador multi-artista

| Perfil | Rango | Hz medio | % grave | % agudo+sobreagudo |
|--------|-------|----------|---------|--------------------|
| Tenor Dramático (Bogdan) | A2–C6 (3.25 oct) | 502 Hz | 10% | 28% |
| Barítono Lírico | F2–A4 (2.33 oct) | 213 Hz | **43%** | 0% |
| Soprano Lírica | C4–F6 (2.42 oct) | 693 Hz | 0% | **46%** |
| Tenor Pop / Belting | B2–E5 (2.42 oct) | 313 Hz | 18% | 0% |
| Contratenor | G3–C6 (2.42 oct) | 551 Hz | 0% | 30% |
| Mezzo-Soprano | F3–A5 (2.33 oct) | 432 Hz | 0% | 14% |

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Análisis de pitch | librosa (pYIN), torchcrepe (CREPE CNN) |
| Separación vocal | Demucs htdemucs |
| Descarga de audio | yt-dlp + FFmpeg |
| Machine Learning | scikit-learn (RandomForest, PCA, IsolationForest) |
| Streaming | Apache Kafka 3.9.1 KRaft (sin Zookeeper) |
| Cliente Kafka | confluent-kafka |
| Datos | pandas, numpy, scipy |
| Visualización | Chart.js 4.4 (HTML standalone, sin servidor) |
| Entorno | Python 3.10+ / Google Colab |

---

## Notas de compatibilidad

**`vocal_rf.pkl`** — El modelo entrenado se regenera en el Paso 4. Si el archivo no está o da error de versión de scikit-learn, re-entrenar con `python clasificador_ml/vocal_classifier.py --train ...`.

**Kafka en Windows** — Usar los scripts `.bat` en `kafka_2.13-3.9.1/bin/windows/` en lugar de los `.sh`. El resto de los comandos Python son idénticos.

**Audio de YouTube** — Si aparece el error "Sign in to confirm you're not a bot", exportar `cookies.txt` desde el navegador con la extensión "Get cookies.txt LOCALLY" y copiarlo a la raíz del repositorio. El script lo detecta automáticamente. Ver `src/audio_loader.py` para más opciones.

---

## Integrantes

| Nombre | GitHub |
|--------|--------|
| Balda Javier | [@jbalda](https://github.com/) |
| Caracoix Juan | [@jcaracoix](https://github.com/) |
| Casas Facundo | [@fcasas](https://github.com/) |

*Universidad Católica Argentina · Análisis y Procesamiento de Datos Streaming · 2026*