# 🎤 Vocal Intelligence Pipeline

**Análisis vocal en tiempo real con IA, streaming y Machine Learning**

> *Balda Javier · Caracoix Juan · Casas Facundo*  
> Universidad Católica Argentina — Análisis y Procesamiento de Datos Streaming — 2026

---

## ¿Qué hace este proyecto?

Toma el audio de una canción, lo analiza nota por nota a 20 frames por segundo, y produce en tiempo real tres tipos de output: una predicción del tipo de voz del intérprete, alertas sobre eventos técnicos vocales (clímax, breaks, caídas de intensidad), y métricas comparativas contra un catálogo de seis perfiles vocales de referencia.

Todo el sistema corre sobre Apache Kafka. El audio entra como un stream de frames y sale como mensajes clasificados en dos tópicos distintos.

---

## Arquitectura

```
Audio (WAV / CSV de frames pYIN)
          │
          ▼
  vocal_producer.py          ← 1 mensaje cada 50ms
          │
          ▼  vocal.frames
  ┌───────────────────────────────────┐
  │         Kafka KRaft               │
  │  vocal.frames  (entrada)          │
  │  vocal.analyzed  (clasificado)    │
  │  vocal.alerts  (anomalías)        │
  └───────────────┬───────────────────┘
                  │
                  ▼
  vocal_consumer.py
    ├── extract_features()  ──►  VocalClassifier (RF, 69% acc.)  ──►  vocal.analyzed
    └── VocalAnomalyDetector  ──────────────────────────────────►  vocal.alerts
                  │
                  ▼
  kafka_dashboard.html     ← dashboard en vivo
```

### Cómo se conectan las 4 ideas

| Módulo | Idea | Rol |
|--------|------|-----|
| `challenge_streaming/` | Base | Pipeline pYIN → `realtime_frames.csv` |
| `idea_c/artist_profiles.py` | Idea C | 6 perfiles vocales + generación de audio sintético |
| `idea_c/vocal_comparador.py` | Idea C | 16 métricas comparativas por artista |
| `idea_d/anomaly_detector.py` | Idea D | 6 tipos de anomalías vocales con severidad |
| `idea_a/vocal_classifier.py` | Idea A | Random Forest sobre ventanas de 2s, 20 features |
| `idea_a/vocal_rf.pkl` | Idea A | Modelo entrenado (accuracy 69%, 1233 muestras) |
| `idea_b/vocal_producer.py` | Idea B | Producer Kafka (50ms/frame) |
| `idea_b/vocal_consumer.py` | Idea B | Consumer con buffer deslizante 2s/stride 0.5s |

---

## Estructura del repositorio

```
vocal-intelligence-pipeline/
│
├── challenge_streaming/          ← pipeline original (base del proyecto)
│   ├── src/
│   │   ├── pipeline.py           # análisis pYIN + torchcrepe
│   │   ├── generate_demo.py      # audio sintético (S.O.S — Bogdan)
│   │   └── metrics.py            # métricas musicales
│   ├── results/
│   │   ├── realtime_frames.csv   # 1801 frames del análisis real
│   │   ├── metrics.json          # métricas de la canción
│   │   └── dashboard.html        # dashboard original
│   └── requirements.txt
│
├── idea_a/                       ← Clasificador ML
│   ├── vocal_classifier.py       # extracción de features + Random Forest
│   ├── vocal_rf.pkl              # modelo entrenado
│   ├── experiment_metrics.json   # accuracy 68.9%, F1 macro 66.8%
│   └── Clasificador_Tipo_Vocal_ML_Balda_Caracoix_Casas.ipynb
│
├── idea_b/                       ← Pipeline Kafka
│   ├── vocal_producer.py         # emite frames a vocal.frames
│   ├── vocal_consumer.py         # clasifica + detecta anomalías
│   ├── kafka_dashboard.html      # dashboard en vivo
│   ├── stream_output_demo.json   # resultado pre-generado (demo)
│   └── Pipeline_Kafka_Vocal_Streaming_Balda_Caracoix_Casas.ipynb
│
├── idea_c/                       ← Comparador multi-artista
│   ├── artist_profiles.py        # 6 perfiles vocales sintéticos
│   ├── vocal_comparador.py       # extracción de 16 métricas
│   ├── artist_dataset.json       # dataset completo con timelines
│   ├── artist_metrics.csv        # tabla comparativa (6×16)
│   ├── comparador_dashboard.html # dashboard interactivo de comparación
│   └── Comparador_Vocal_Multi_Artista_Balda_Caracoix_Casas.ipynb
│
├── idea_d/                       ← Detección de anomalías
│   ├── anomaly_detector.py       # 6 tipos de anomalías con severidad
│   ├── pipeline_with_anomaly.py  # pipeline original + detector integrado
│   ├── anomalies.json            # 212 eventos detectados en S.O.S
│   ├── anomaly_dashboard.html    # dashboard de anomalías
│   └── Deteccion_Anomalias_Vocales_Balda_Caracoix_Casas.ipynb
│
├── requirements.txt              ← todas las dependencias
└── README.md
```

---

## Instalación y ejecución

### Requisitos previos

- Python 3.10+
- Java 17 (para Kafka)
- Google Colab o entorno local con GPU opcional

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/vocal-intelligence-pipeline.git
cd vocal-intelligence-pipeline
```

### 2. Instalar dependencias Python

```bash
# Dependencias del pipeline de audio
pip install librosa numpy scipy pandas matplotlib scikit-learn

# Para análisis real con torchcrepe (GPU opcional)
pip install torchcrepe torch
pip install demucs  # separación vocal

# Para Kafka
pip install confluent-kafka
```

### 3. Ejecutar en orden (sin Kafka)

Cada idea puede ejecutarse de forma independiente. El orden recomendado respeta las dependencias:

```bash
# Paso 1 — Generar los frames del audio (base de todo)
cd challenge_streaming/
python src/pipeline.py --demo            # audio sintético, ~2 min
# → genera results/realtime_frames.csv

# Paso 2 — Detectar anomalías sobre los frames
cd ../idea_d/
python anomalias/anomaly_detector.py --csv ../challenge_streaming/results/realtime_frames.csv --out anomalies.json
# → imprime 212 eventos, guarda anomalies.json

# Paso 3 — Generar el dataset multi-artista
cd ../idea_c/
python comparador_multiartista/vocal_comparador.py --out results/
# → genera artist_dataset.json, artist_metrics.csv

# Paso 4 — Entrenar el clasificador ML
cd ../clasificador_ml/
python vocal_classifier.py \
  --train ..results/artist_dataset.json \
  --csv-real ..results/realtime_frames.csv "Tenor dramático" \
  --out results/
# → entrena RF, guarda vocal_rf.pkl, imprime accuracy 68.9%

# Paso 5 — Predecir tipo vocal de una canción
cd /workspaces/challenge_streaming
python clasificador_ml/vocal_classifier.py \
  --predict results/realtime_frames.csv \
  --model results/vocal_rf.pkl
# → Predicción: Tenor dramático (98.5% confianza)
```

### 4. Ejecutar el pipeline Kafka completo

Requiere Java 17 instalado. En Google Colab, usar el notebook `idea_b/Pipeline_Kafka_Vocal_Streaming_Balda_Caracoix_Casas.ipynb` que automatiza todo.

```bash
# Terminal 1 — iniciar Kafka KRaft
wget https://archive.apache.org/dist/kafka/3.9.1/kafka_2.13-3.9.1.tgz
tar -xzf kafka_2.13-3.9.1.tgz

export KAFKA_DIR=/workspaces/challenge_streaming/kafka_2.13-3.9.1
$KAFKA_DIR/bin/kafka-storage.sh random-uuid | xargs -I{} \
  $KAFKA_DIR/bin/kafka-storage.sh format -t {} \
  -c $KAFKA_DIR/config/kraft/server.properties
$KAFKA_DIR/bin/kafka-server-start.sh \
  $KAFKA_DIR/config/kraft/server.properties &

# Terminal 2 — iniciar producer (emite a 50ms/frame)
cd /workspaces/challenge_streaming
python kafka_streaming/vocal_producer.py --csv results/realtime_frames.csv
# opción turbo (sin espera): agregar --fast

# Terminal 3 — iniciar consumer (espera al producer)
cd idea_b/
python kafka_streaming/vocal_consumer.py \
  --model ../clasificador_ml/vocal_rf.pkl \
  --out results/stream_output.json
```

### 5. Ver los dashboards

Todos los dashboards son archivos HTML standalone. Abrir directamente en el navegador:

```bash
# Dashboard de anomalías
open anomalias/anomaly_dashboard.html

# Comparador multi-artista (interactivo, seleccionar artista)
open comparador_multiartista/comparador_dashboard.html

# Dashboard Kafka en vivo (simula el stream con los datos del demo)
open kafka_streaming/kafka_dashboard.html
```

---

## Datos y resultados

### Canción de referencia

S.O.S — Bogdan Shuvalov · 90 segundos · análisis torchcrepe + pYIN

| Métrica | Valor |
|---------|-------|
| Rango vocal | A2 → C6 (3.28 octavas, 39.3 semitonos) |
| Nota más frecuente | G5 |
| Nota más aguda | C6 (1059 Hz) @ 61.2s |
| Nota más grave | A2 (109 Hz) @ 51.6s |
| Frecuencia promedio | 502.5 Hz |
| Frames analizados | 1801 (97% con voz) |
| Pico de intensidad | C6 @ 69.35s (RMS 36.5) |

### Clasificador ML (Idea A)

| Clase | F1 |
|-------|----|
| Soprano | 0.86 |
| Tenor dramático | 0.81 |
| Barítono | 0.74 |
| Tenor lírico-pop | 0.55 |
| Mezzo-soprano | 0.56 |
| Contratenor | 0.49 |

Accuracy global 5-fold CV: **68.9%** (baseline aleatorio: 16.7%)  
Feature más importante: `int_mean` (21% — nivel de proyección vocal)  
Predicción sobre S.O.S: **Tenor dramático 98.5% confianza**

### Detección de anomalías (Idea D)

212 eventos detectados en 90 segundos:

| Tipo | Cantidad | Descripción |
|------|----------|-------------|
| CLIMAX_VOCAL | 95 | Nota aguda sostenida ≥8 frames (zona 30–70s) |
| INESTABILIDAD | 64 | Coeficiente de variación elevado en ventana |
| CAIDA_INTENS | 51 | Caída de intensidad ≥50% (3 caídas severas) |
| AGUDO_EXTREMO | 1 | Primera nota sobreaguda C6 @ 59.7s |
| SILENCIO_LARGO | 1 | Pausa estructural @ 44s |

### Comparador multi-artista (Idea C)

6 perfiles · 16 métricas · dataset de 1056 ventanas

| Perfil | Rango | Hz medio | Registro dominante |
|--------|-------|----------|-------------------|
| Tenor Dramático (Bogdan) | A2–C6 (3.25 oct) | 502 Hz | medio-agudo |
| Barítono Lírico | F2–A4 (2.33 oct) | 213 Hz | grave |
| Soprano Lírica | C4–F6 (2.42 oct) | 693 Hz | medio-agudo |
| Tenor Pop / Belting | B2–E5 (2.42 oct) | 313 Hz | medio-grave |
| Contratenor | G3–C6 (2.42 oct) | 551 Hz | medio-agudo |
| Mezzo-Soprano | F3–A5 (2.33 oct) | 432 Hz | medio-agudo |

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Análisis de audio | librosa (pYIN), torchcrepe (CREPE CNN), Demucs (htdemucs) |
| Machine Learning | scikit-learn (RandomForest, IsolationForest, PCA) |
| Streaming | Apache Kafka 3.9 KRaft (sin Zookeeper), confluent-kafka |
| Datos | pandas, numpy, scipy |
| Visualización | Chart.js (dashboards HTML standalone) |
| Síntesis audio | scipy.io.wavfile, síntesis aditiva con ADSR |
| Entorno | Google Colab / Python 3.10+ |

---

## Integrantes

| Nombre | GitHub |
|--------|--------|
| Balda Javier | [@jbalda](https://github.com/) |
| Caracoix Juan | [@jcaracoix](https://github.com/) |
| Casas Facundo | [@fcasas](https://github.com/) |

---

*Universidad Católica Argentina · Materia: Análisis y Procesamiento de Datos Streaming · 2026*
