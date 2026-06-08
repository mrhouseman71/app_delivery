"""
vocal_consumer.py
══════════════════════════════════════════════════════════════════════
Consumer Kafka que procesa frames vocales en tiempo real.

ARQUITECTURA
────────────
                    ┌─────────────────────────────────────────┐
  vocal.frames ───► │  Consumer A (este archivo)              │
                    │                                         │
                    │  Buffer deslizante (2s / 40 frames)     │
                    │       ↓                                 │
                    │  extract_features() ──► VocalClassifier │
                    │       ↓                                 │
  vocal.analyzed ◄──│  {prediction, confidence, probas,       │
                    │   window_features, timestamp}           │
                    │                                         │
                    │  VocalAnomalyDetector (frame-level)     │
                    │       ↓                                 │
  vocal.alerts  ◄───│  {tipo, severidad, descripcion, time}   │
                    └─────────────────────────────────────────┘

TÓPICOS
───────
  vocal.frames   (entrada)   frames del producer
  vocal.analyzed (salida A)  predicción de tipo vocal por ventana
  vocal.alerts   (salida B)  anomalías detectadas

ESTADO INTERNO
──────────────
  frame_buffer   : deque de los últimos N frames (ventana deslizante)
  all_frames     : lista completa para anomaly detector stateful
  window_counter : cuántas ventanas procesadas
  Cada 40 frames recibidos (= 2s de audio), clasifica y emite.

USO
───
  # En una terminal (con Kafka corriendo):
  python vocal_consumer.py

  # Con modelo específico:
  python vocal_consumer.py --model results/vocal_rf.pkl

  # Sin clasificador (solo anomalías):
  python vocal_consumer.py --no-classifier

  # Guardar resultados a JSON:
  python vocal_consumer.py --out results/stream_output.json
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from pathlib import Path

try:
    from confluent_kafka import Consumer, Producer, KafkaException
except ImportError:
    print("ERROR: Instalar confluent-kafka:  pip install confluent-kafka")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────

BOOTSTRAP        = "localhost:9092"
TOPIC_IN         = "vocal.frames"
TOPIC_ANALYZED   = "vocal.analyzed"
TOPIC_ALERTS     = "vocal.alerts"

WINDOW_FRAMES    = 40     # 40 frames × 50ms = 2.0 segundos
STRIDE_FRAMES    = 10     # nueva ventana cada 10 frames = 0.5 segundos
MAX_EMPTY_POLLS  = 30     # cuántos polls vacíos antes de cerrar
POLL_TIMEOUT     = 1.0    # segundos por poll


# ──────────────────────────────────────────────────────────────────
# CARGA DE MÓDULOS PROPIOS
# ──────────────────────────────────────────────────────────────────

def _load_classifier(model_path: str):
    """Carga el VocalClassifier (Idea A). Retorna None si falla."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from clasificador_ml.vocal_classifier import (
            VocalClassifier,
            extract_features,
            FEATURE_NAMES,
        )
        clf = VocalClassifier.load(model_path)
        print(f"  [CLASSIFIER] Modelo cargado: {model_path}")
        print(f"  [CLASSIFIER] Clases: {list(clf.le6.classes_)}")
        return clf, extract_features, FEATURE_NAMES
    except Exception as e:
        print(f"  [CLASSIFIER] No disponible ({e}). Continuando sin clasificador.")
        return None, None, None


def _load_anomaly_detector():
    """Carga VocalAnomalyDetector (Idea D). Retorna None si falla."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from anomalias.anomaly_detector import VocalAnomalyDetector
        print("  [ANOMALY] VocalAnomalyDetector cargado.")
        return VocalAnomalyDetector
    except Exception as e:
        print(f"  [ANOMALY] No disponible ({e}). Continuando sin detector.")
        return None


# ──────────────────────────────────────────────────────────────────
# PROCESADORES DE VENTANA
# ──────────────────────────────────────────────────────────────────

def procesar_ventana_clasificador(
    window_frames: list,
    clf,
    extract_features_fn,
    feature_names: list,
    window_idx: int,
) -> dict | None:
    """
    Extrae features de la ventana y predice el tipo vocal.
    Retorna el mensaje JSON para vocal.analyzed.
    """
    if clf is None or extract_features_fn is None:
        return None

    feats = extract_features_fn(window_frames)
    if feats is None:
        return None

    import pandas as pd
    import numpy as np

    X = pd.DataFrame([feats])[feature_names]
    proba    = clf.rf.predict_proba(X.values)[0]
    pred_idx = int(np.argmax(proba))

    last_frame = window_frames[-1]
    return {
        "window_idx":  window_idx,
        "t_start":     round(window_frames[0].get("time_s", 0), 3),
        "t_end":       round(last_frame.get("time_s", 0), 3),
        "artist_id":   last_frame.get("artist_id", "unknown"),
        "song_title":  last_frame.get("song_title", ""),
        "prediction":  clf.le6.classes_[pred_idx],
        "confidence":  round(float(proba[pred_idx]), 4),
        "probas": {
            str(cls): round(float(v), 4)
            for cls, v in zip(clf.le6.classes_, proba)
        },
        "features": {k: round(float(v), 4) for k, v in feats.items()},
        "ts_kafka": time.time(),
    }


def procesar_anomalias(
    new_frame: dict,
    all_frames_so_far: list,
    AnomalyDetectorClass,
    emitted_times: set,
) -> list[dict]:
    """
    Corre el AnomalyDetector sobre los frames acumulados y retorna
    los eventos nuevos (aún no emitidos).
    """
    if AnomalyDetectorClass is None:
        return []

    # El detector es stateless (procesa todos los frames cada vez).
    # Para eficiencia, solo lo corremos cada 20 frames nuevos.
    if len(all_frames_so_far) % 20 != 0:
        return []

    detector = AnomalyDetectorClass(all_frames_so_far)
    events   = detector.detect()

    nuevos = []
    for ev in events:
        key = (round(ev.time, 2), ev.tipo)
        if key not in emitted_times:
            emitted_times.add(key)
            nuevos.append({
                "time":        ev.time,
                "tipo":        ev.tipo,
                "severidad":   ev.severidad,
                "descripcion": ev.descripcion,
                "detalle":     ev.detalle,
                "artist_id":   new_frame.get("artist_id", "unknown"),
                "ts_kafka":    time.time(),
            })
    return nuevos


# ──────────────────────────────────────────────────────────────────
# CONSUMER PRINCIPAL
# ──────────────────────────────────────────────────────────────────

def consumir(
    bootstrap:       str   = BOOTSTRAP,
    topic_in:        str   = TOPIC_IN,
    topic_analyzed:  str   = TOPIC_ANALYZED,
    topic_alerts:    str   = TOPIC_ALERTS,
    model_path:      str   = "results/vocal_rf.pkl",
    use_classifier:  bool  = True,
    use_anomaly:     bool  = True,
    out_path:        str   = None,
    verbose:         bool  = True,
) -> dict:
    """
    Loop principal del consumer. Bloquea hasta que el stream se agote.

    Returns
    -------
    dict con listas 'analyzed' y 'alerts' de todos los mensajes emitidos.
    """

    # ── Cargar módulos ────────────────────────────────────────────
    clf = extract_features_fn = feature_names = None
    if use_classifier:
        clf, extract_features_fn, feature_names = _load_classifier(model_path)

    AnomalyDetectorClass = None
    if use_anomaly:
        AnomalyDetectorClass = _load_anomaly_detector()

    # ── Conectar Kafka ────────────────────────────────────────────
    consumer = Consumer({
        "bootstrap.servers":  bootstrap,
        "group.id":           "vocal-analyzer-v1",
        "auto.offset.reset":  "earliest",
        "enable.auto.commit": True,
        "session.timeout.ms": 30_000,
    })
    consumer.subscribe([topic_in])

    producer_out = Producer({
        "bootstrap.servers": bootstrap,
        "acks":              "1",
        "linger.ms":         2,
    })

    print(f"\n  [CONSUMER] Escuchando '{topic_in}'")
    print(f"  [CONSUMER] Salida classified → '{topic_analyzed}'")
    print(f"  [CONSUMER] Salida alerts     → '{topic_alerts}'\n")

    # ── Estado interno ────────────────────────────────────────────
    frame_buffer   : deque = deque(maxlen=WINDOW_FRAMES)
    all_frames     : list  = []
    emitted_times  : set   = set()
    frames_since_last_window = 0
    window_counter = 0

    # Acumuladores de salida
    all_analyzed = []
    all_alerts   = []

    # Métricas de progreso
    total_frames = 0
    empty_polls  = 0
    t_start      = time.time()

    try:
        while True:
            msg = consumer.poll(POLL_TIMEOUT)

            # Sin mensajes
            if msg is None:
                empty_polls += 1
                if empty_polls >= MAX_EMPTY_POLLS:
                    print(f"\n  [CONSUMER] Sin mensajes por {MAX_EMPTY_POLLS}s. "
                          "Cerrando...")
                    break
                continue

            empty_polls = 0

            # Error Kafka
            if msg.error():
                print(f"  [CONSUMER] Error Kafka: {msg.error()}")
                continue

            # ── Deserializar frame ────────────────────────────────
            try:
                frame = json.loads(msg.value().decode("utf-8"))
            except Exception as e:
                print(f"  [CONSUMER] Error deserialización: {e}")
                continue

            if "time" not in frame and "time_s" in frame:
                frame["time"] = frame["time_s"]
            elif "time_s" not in frame and "time" in frame:
                frame["time_s"] = frame["time"]

            total_frames += 1
            frame_buffer.append(frame)
            all_frames.append(frame)
            frames_since_last_window += 1

            # ── Clasificación por ventana ─────────────────────────
            if (len(frame_buffer) >= WINDOW_FRAMES and
                    frames_since_last_window >= STRIDE_FRAMES):
                frames_since_last_window = 0
                window_counter += 1

                analyzed = procesar_ventana_clasificador(
                    list(frame_buffer),
                    clf, extract_features_fn, feature_names,
                    window_idx=window_counter,
                )
                if analyzed:
                    all_analyzed.append(analyzed)
                    producer_out.produce(
                        topic    = topic_analyzed,
                        key      = analyzed["artist_id"].encode("utf-8"),
                        value    = json.dumps(analyzed, ensure_ascii=False).encode("utf-8"),
                    )
                    if verbose:
                        print(f"  [ANALYZED] w{window_counter:04d} "
                              f"t={analyzed['t_start']:.1f}s "
                              f"→ {analyzed['prediction']:<22} "
                              f"({analyzed['confidence']:.0%})")

            # ── Detección de anomalías ────────────────────────────
            nuevas = procesar_anomalias(
                frame, all_frames, AnomalyDetectorClass, emitted_times
            )
            for ev in nuevas:
                all_alerts.append(ev)
                producer_out.produce(
                    topic    = topic_alerts,
                    key      = ev["artist_id"].encode("utf-8"),
                    value    = json.dumps(ev, ensure_ascii=False).encode("utf-8"),
                )
                icon = {"CLIMAX_VOCAL":"🔥","CAIDA_INTENS":"📉",
                        "AGUDO_EXTREMO":"🎯","SILENCIO_LARGO":"⏸",
                        "BREAK_VOZ":"⚡","INESTABILIDAD":"〰"}.get(ev["tipo"], "●")
                print(f"  [ALERT]    {icon} {ev['tipo']:<18} "
                      f"t={ev['time']:.1f}s  sev={ev['severidad']}")

            # ── Progreso cada 200 frames ──────────────────────────
            if verbose and total_frames % 200 == 0:
                elapsed = time.time() - t_start
                fps = total_frames / elapsed if elapsed > 0 else 0
                print(f"  [CONSUMER] {total_frames} frames | "
                      f"{window_counter} ventanas | "
                      f"{len(all_alerts)} alertas | "
                      f"{fps:.0f} fps")

            producer_out.poll(0)

    except KeyboardInterrupt:
        print("\n  [CONSUMER] Interrumpido por el usuario.")
    finally:
        consumer.close()
        producer_out.flush()

    elapsed = time.time() - t_start
    print(f"\n  [CONSUMER] ✅ Finalizado")
    print(f"  Frames procesados  : {total_frames}")
    print(f"  Ventanas analizadas: {window_counter}")
    print(f"  Predicciones emitidas: {len(all_analyzed)}")
    print(f"  Alertas emitidas   : {len(all_alerts)}")
    print(f"  Tiempo total       : {elapsed:.1f}s")

    results = {"analyzed": all_analyzed, "alerts": all_alerts}

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"  Resultados → {out_path}")

    return results


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Consumer Kafka — clasifica frames vocales en tiempo real"
    )
    ap.add_argument("--broker",         default=BOOTSTRAP)
    ap.add_argument("--topic-in",       default=TOPIC_IN)
    ap.add_argument("--topic-analyzed", default=TOPIC_ANALYZED)
    ap.add_argument("--topic-alerts",   default=TOPIC_ALERTS)
    ap.add_argument("--model",          default="results/vocal_rf.pkl",
                    help="Path al modelo pkl (Idea A)")
    ap.add_argument("--no-classifier",  action="store_true")
    ap.add_argument("--no-anomaly",     action="store_true")
    ap.add_argument("--out",            default="results/stream_output.json",
                    help="Guardar resultados en JSON")
    ap.add_argument("--quiet",          action="store_true")
    args = ap.parse_args()

    consumir(
        bootstrap      = args.broker,
        topic_in       = args.topic_in,
        topic_analyzed = args.topic_analyzed,
        topic_alerts   = args.topic_alerts,
        model_path     = args.model,
        use_classifier = not args.no_classifier,
        use_anomaly    = not args.no_anomaly,
        out_path       = args.out,
        verbose        = not args.quiet,
    )
