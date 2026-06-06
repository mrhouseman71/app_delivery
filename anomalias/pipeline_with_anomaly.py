"""
pipeline_with_anomaly.py
══════════════════════════════════════════════════════════════════════
Pipeline original de análisis vocal + detección de anomalías integrada.
Extiende pipeline.py del challenge_streaming sin modificarlo.

CAMBIOS RESPECTO AL ORIGINAL
─────────────────────────────
  1. Al finalizar analyze_audio(), se instancia VocalAnomalyDetector.
  2. Los eventos se agregan al JSON de métricas bajo la clave "anomalias".
  3. El log de consola muestra los eventos en tiempo real (marcados con ⚡).
  4. Se exporta anomalies.json independiente en el directorio de salida.

USO (idéntico al original, más flag opcional)
──────────────────────────────────────────────
  python pipeline_with_anomaly.py --demo
  python pipeline_with_anomaly.py --audio ruta/al/audio.wav
  python pipeline_with_anomaly.py --demo --no-anomaly   # desactivar
══════════════════════════════════════════════════════════════════════
"""

# ── Importar todo del pipeline original ──────────────────────────
# (asumimos que pipeline.py está en el mismo directorio o en src/)
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Si corrés desde la raíz del challenge_streaming:
try:
    from pipeline import (
        generate_synthetic_audio,
        separate_vocals_demucs,
        analyze_audio,
        compute_metrics,
        SAMPLE_RATE, FRAME_LENGTH, HOP_LENGTH, F_MIN, F_MAX,
    )
except ImportError:
    # Fallback: pipeline en mismo directorio
    from pipeline import (
        generate_synthetic_audio,
        separate_vocals_demucs,
        analyze_audio,
        compute_metrics,
        SAMPLE_RATE, FRAME_LENGTH, HOP_LENGTH, F_MIN, F_MAX,
    )

from anomaly_detector import VocalAnomalyDetector, summarize, print_report

import argparse
import json
from pathlib import Path


OUTPUT_DIR = Path("vocal_analysis/output")


# ──────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL EXTENDIDA
# ──────────────────────────────────────────────────────────────────

def run_pipeline_with_anomaly(args):
    global OUTPUT_DIR
    OUTPUT_DIR = Path(args.out)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Obtener audio (igual que original) ────────────────────
    audio_path = None

    if args.demo or (not args.audio and not getattr(args, "youtube", None)):
        synthetic = str(OUTPUT_DIR / "bogdan_sos_synthetic.wav")
        audio_path = generate_synthetic_audio(synthetic, duration=90)

    elif getattr(args, "youtube", None):
        try:
            import yt_dlp
            opts = {
                "format": "bestaudio/best",
                "outtmpl": str(OUTPUT_DIR / "downloaded.%(ext)s"),
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([args.youtube])
            audio_path = str(next(OUTPUT_DIR.glob("downloaded.wav")))
        except Exception as e:
            print(f"[ERROR] Descarga fallida: {e}")
            sys.exit(1)
    else:
        audio_path = args.audio
        if not os.path.exists(audio_path):
            print(f"[ERROR] Archivo no encontrado: {audio_path}")
            sys.exit(1)

    # ── 2. Separar voz ───────────────────────────────────────────
    if not args.no_demucs:
        audio_path = separate_vocals_demucs(audio_path)

    # ── 3. Análisis de frames (pipeline original) ─────────────────
    frames = analyze_audio(audio_path, realtime_display=True)

    # ── 4. Guardar frames ─────────────────────────────────────────
    frames_path = OUTPUT_DIR / "frame_analysis.json"
    with open(frames_path, "w") as f:
        json.dump(frames, f, indent=2)
    print(f"\n[GUARDADO] Frames → {frames_path}")

    # ── 5. Métricas originales ────────────────────────────────────
    metrics = compute_metrics(frames)

    # ── 6. DETECCIÓN DE ANOMALÍAS (extensión) ─────────────────────
    if not getattr(args, "no_anomaly", False):
        print("\n[ANOMALÍAS] Ejecutando detector de anomalías vocales...")
        detector = VocalAnomalyDetector(frames)
        events   = detector.detect()
        summary  = summarize(events)

        # Imprimir reporte en consola
        print_report(events)

        # Adjuntar al JSON de métricas
        metrics["anomalias"] = summary

        # Exportar JSON independiente
        anom_path = OUTPUT_DIR / "anomalies.json"
        with open(anom_path, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"[GUARDADO] Anomalías → {anom_path}")
    else:
        print("[INFO] Detección de anomalías desactivada (--no-anomaly).")

    # ── 7. Guardar métricas enriquecidas ──────────────────────────
    metrics_path = OUTPUT_DIR / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"[GUARDADO] Métricas → {metrics_path}")

    dashboard = OUTPUT_DIR / "dashboard.html"
    if dashboard.exists():
        print(f"\n[LISTO] Dashboard: {dashboard.resolve()}")


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline vocal + detección de anomalías"
    )
    parser.add_argument("--audio",      help="Ruta a archivo WAV/MP3")
    parser.add_argument("--youtube",    help="URL de YouTube")
    parser.add_argument("--demo",       action="store_true", help="Usar audio sintético")
    parser.add_argument("--no-demucs",  action="store_true", help="Omitir separación vocal")
    parser.add_argument("--no-anomaly", action="store_true", help="Omitir detección de anomalías")
    parser.add_argument("--out",        default="vocal_analysis/output", help="Directorio de salida")
    args = parser.parse_args()
    run_pipeline_with_anomaly(args)


if __name__ == "__main__":
    main()
