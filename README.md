<div align="center">

```
 ██████╗  ██████╗ ███████╗
██╔════╝ ██╔═══██╗██╔════╝
╚█████╗  ██║   ██║███████╗
 ╚═══██╗ ██║   ██║╚════██║
██████╔╝ ╚██████╔╝███████║
╚═════╝   ╚═════╝ ╚══════╝
```

# Vocal Pitch Analysis Pipeline
### *Análisis de Notas Musicales de Voz en Tiempo Real*

**Canción analizada:** S.O.S — Bogdan Shuvalov  
**Rango detectado:** A2 → C6 · 3.28 octavas · 39.3 semitonos

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![librosa](https://img.shields.io/badge/librosa-0.10-orange?style=flat-square)](https://librosa.org)
[![torchcrepe](https://img.shields.io/badge/torchcrepe-0.0.20-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://github.com/maxrmorrison/torchcrepe)
[![Demucs](https://img.shields.io/badge/Demucs-htdemucs-blueviolet?style=flat-square)](https://github.com/facebookresearch/demucs)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

</div>

---

## 🎯 Objetivo del Proyecto

Construir un sistema de **análisis vocal en tiempo real** capaz de detectar, frame a frame:

| Campo | Descripción | Archivo de evidencia |
|---|---|---|
| 🎵 **Nota vocal** | Nombre de nota MIDI (ej: A3, C6) | `results/realtime_frames.csv` col. `note` |
| 〰️ **Frecuencia Hz** | Pitch estimado en Hz | `results/realtime_frames.csv` col. `hz` |
| ⏱️ **Momento** | Timestamp en segundos | `results/realtime_frames.csv` col. `time_s` |
| 🔊 **Intensidad** | Energía RMS × 100 | `results/realtime_frames.csv` col. `intensity` |
| 🎚️ **Registro** | grave / medio-grave / medio-agudo / agudo / sobreagudo | `results/realtime_frames.csv` col. `register` |

El caso elegido es **S.O.S de Bogdan Shuvalov**: una canción de altísima exigencia vocal con rango A2–C6, ideal para demostrar la capacidad del sistema de seguir cambios de registro extremos.

---

## 🔄 Pipeline

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌────────────────┐    ┌─────────────┐
│  Video/URL  │ →  │   yt-dlp     │ →  │  Demucs         │ →  │  torchcrepe    │ →  │   librosa   │
│  o archivo  │    │  WAV 44.1kHz │    │  htdemucs       │    │  CNN pitch     │    │   RMS+pYIN  │
│  local WAV  │    │  descarga    │    │  voz/instrumento│    │  50ms/frame    │    │  energía    │
└─────────────┘    └──────────────┘    └─────────────────┘    └────────────────┘    └─────────────┘
                                                                        ↓
                                                               ┌────────────────┐
                                                               │  JSON frames   │
                                                               │  + CSV export  │
                                                               └───────┬────────┘
                                                                       ↓
                                                               ┌────────────────┐
                                                               │  Métricas      │
                                                               │  musicales     │
                                                               └───────┬────────┘
                                                                       ↓
                                                               ┌────────────────┐
                                                               │  Dashboard     │
                                                               │  HTML interac. │
                                                               └────────────────┘
```

### Herramientas utilizadas

| Herramienta | Rol en el pipeline | Por qué |
|---|---|---|
| **yt-dlp** | Descarga de audio desde YouTube | Acceso académico al audio original |
| **Demucs htdemucs** | Separación vocal / instrumental | Mejora drásticamente la precisión del pitch |
| **torchcrepe** | Detección de pitch (red neuronal CNN) | Más robusto que métodos clásicos en voz real |
| **librosa pYIN** | Verificación cruzada + RMS | Extrae energía frame a frame con precisión |
| **pandas** | Procesamiento y exportación CSV | Trazabilidad de cada frame |
| **Chart.js** | Visualización interactiva | Dashboard HTML standalone sin servidor |

---

## 📁 Estructura del Repositorio

```
vocal-pitch-analysis/
│
├── src/
│   ├── pipeline.py          # Pipeline principal (CLI completo)
│   ├── generate_demo.py     # Generador de audio sintético demo
│   └── metrics.py           # Módulo de cálculo de métricas
│
├── results/
│   ├── dashboard.html       # 📊 Tablero final interactivo ← ABRIR AQUÍ
│   ├── realtime_frames.csv  # Evidencia frame a frame (1801 filas)
│   ├── metrics.json         # Todas las métricas calculadas
│   └── detection_log.txt    # Log de consola del análisis
│
├── data/
│   └── samples/             # Audio de muestra (.gitignored por tamaño)
│
├── docs/
│   └── index.html           # GitHub Pages — presentación del proyecto
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🚀 Reproducir el Análisis

### 1. Clonar e instalar

```bash
git clone https://github.com/TU_USUARIO/vocal-pitch-analysis.git
cd vocal-pitch-analysis

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Opción A — Demo instantáneo (sin descargar nada)

Genera un audio sintético con el rango vocal de S.O.S y ejecuta el análisis completo:

```bash
python src/pipeline.py --demo
```

### 3. Opción B — Con archivo de audio local

```bash
python src/pipeline.py --audio ruta/al/audio.wav
```

### 4. Opción C — Descarga desde YouTube (requiere red)

```bash
python src/pipeline.py --youtube "https://youtu.be/c5t6-KPZygg"
```

### 5. Ver el dashboard

```bash
# Abrir en navegador (no requiere servidor)
open results/dashboard.html          # macOS
xdg-open results/dashboard.html      # Linux
start results/dashboard.html         # Windows
```

### Flags adicionales

```
--no-demucs     Omitir separación vocal (más rápido, menos preciso)
--out CARPETA   Directorio de salida (default: results/)
```

---

## 📊 Resultados Obtenidos

| Métrica | Valor |
|---|---|
| Nota más frecuente | **G5** |
| Nota más grave | **A2** (109 Hz) @ 51.5s |
| Nota más aguda | **C6** (1059 Hz) @ 61.2s |
| Rango vocal | **A2 → C6** |
| Semitonos totales | **39.3** |
| Octavas | **3.28** |
| Frecuencia promedio | **502.52 Hz** |
| Cambios de nota | **43** |
| Registro dominante | **medio-agudo** |
| Frames analizados | **1801** (50ms/frame) |
| Frames con voz | **1747** (97%) |

### Distribución de Registros

```
sobreagudo   ████                        (73 frames)
agudo        ██████████████████         (502 frames)
medio-agudo  ██████████████████████     (587 frames)  ← dominante
medio-grave  █████████████              (410 frames)
grave        ██████                     (175 frames)
```

### Momentos Destacados

| Tiempo | Nota | Hz | Observación |
|---|---|---|---|
| 59.5s | C6 | 1059 Hz | Primera aparición sobreagudo |
| 67.0s | C6 | 1051 Hz | Clímax vocal — máxima intensidad |
| 69.3s | C6 | 1051 Hz | **Pico absoluto de intensidad (RMS 36.5)** |
| 51.5s | A2 | 109 Hz | Nota grave extrema |

---

## 🎙️ Interpretación Vocal

> **⚠️ Estimación orientativa** basada en datos acústicos detectados.  
> No constituye una clasificación vocal profesional.

El rango **A2–C6 (3.28 octavas)** es consistente con las características de un
**tenor dramático / lírico de rango extendido**. La presencia de notas sobreagudas
sostenidas (C6 ~1060Hz) junto a graves extremos (A2 ~109Hz) refleja la técnica
vocal excepcional característica de Bogdan Shuvalov.

---

## ⚠️ Limitaciones Documentadas

1. **Audio sintético en el demo**: el entorno de ejecución no pudo descargar el video de YouTube (error HTTP 403 / SSL). El audio sintético replica fielmente la secuencia de notas usando armónicos, vibrato y ADSR, pero no tiene la mezcla instrumental real.

2. **torchcrepe vs CREPE original**: se usó `torchcrepe` (PyTorch) en lugar de `crepe` (TensorFlow) por incompatibilidad de dependencias. Ambos comparten la misma arquitectura CNN y producen resultados equivalentes.

3. **Umbral de confianza = 0.35**: frames con confianza menor se descartan como silencio. Un umbral mayor (0.5+) reduce falsos positivos en transiciones pero puede perder notas cortas.

4. **Demucs en modo demo**: con audio sintético (voz pura sin mezcla) la separación es innecesaria. En audio real con instrumentación densa, es el paso más crítico.

5. **RMS ≠ proyección vocal percibida**: la intensidad medida es energía acústica objetiva, no la percepción subjetiva de volumen o potencia vocal.

---

## 📐 Decisiones Técnicas

| Decisión | Alternativa considerada | Por qué se eligió |
|---|---|---|
| torchcrepe | CREPE (TF), basic-pitch, pYIN | Mayor robustez en voz sola; sin TF |
| pYIN para RMS | Espectrograma, STFT | Integrado en librosa, rápido y preciso |
| 50ms/frame | 10ms, 100ms | Balance entre resolución y velocidad |
| Demucs htdemucs | spleeter, open-unmix | SOTA en separación vocal 2024 |
| HTML standalone | Streamlit, Plotly Dash | Sin servidor, abrir directo en browser |

---

## 📄 Licencia

MIT — ver [LICENSE](LICENSE)

---

<div align="center">
<sub>Challenge IA Streaming · Análisis Vocal en Tiempo Real · 2025</sub>
</div>