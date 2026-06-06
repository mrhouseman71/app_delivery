"""
vocal_producer.py
══════════════════════════════════════════════════════════════════════
Producer Kafka que emite frames vocales al tópico `vocal.frames`.

FUENTE DE DATOS
───────────────
  Modo CSV (default): lee realtime_frames.csv del pipeline.py y emite
    cada fila como un mensaje JSON, respetando el timing original
    (50ms entre frames = 20fps, igual que el análisis pYIN).

  Modo demo: genera frames sintéticos desde los perfiles de
    artist_profiles.py (Idea C) sin necesitar el archivo CSV.

TÓPICO DE SALIDA
────────────────
  vocal.frames
    key  : artist_id (string)
    value: JSON con time_s, note, hz, confidence, intensity,
           register, is_voiced, artist_id, song_title

DISEÑO DEL STREAMING
────────────────────
  El producer respeta el timing real del audio: 1 frame cada 50ms.
  Esto significa que analizar una canción de 90s tarda 90s reales.
  Modo turbo (--fast): sin sleep, emite todos los frames lo más rápido
  posible (útil para demos y testing).

USO
───
  # Desde el CSV del challenge:
  python vocal_producer.py --csv results/realtime_frames.csv

  # Modo demo (sin CSV):
  python vocal_producer.py --demo

  # Modo turbo (sin delay entre frames):
  python vocal_producer.py --csv results/realtime_frames.csv --fast

  # Artista específico del comparador:
  python vocal_producer.py --demo --artist soprano
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

try:
    from confluent_kafka import Producer
    from confluent_kafka.admin import AdminClient, NewTopic
except ImportError:
    print("ERROR: Instalar confluent-kafka:  pip install confluent-kafka")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────

BOOTSTRAP  = "localhost:9092"
TOPIC      = "vocal.frames"
FRAME_INTERVAL_S = 0.05          # 50ms = 20fps
TURBO_BATCH_SIZE  = 50           # en modo turbo, flush cada N frames


# ──────────────────────────────────────────────────────────────────
# HELPERS DE KAFKA
# ──────────────────────────────────────────────────────────────────

def broker_disponible(bootstrap: str = BOOTSTRAP, timeout: int = 5) -> bool:
    """Verifica que el broker Kafka esté disponible."""
    try:
        admin = AdminClient({"bootstrap.servers": bootstrap,
                             "socket.timeout.ms": timeout * 1000})
        meta  = admin.list_topics(timeout=timeout)
        return meta is not None
    except Exception:
        return False


def crear_topico(topic: str, bootstrap: str = BOOTSTRAP,
                 partitions: int = 1, replication: int = 1):
    """Crea el tópico si no existe."""
    admin = AdminClient({"bootstrap.servers": bootstrap})
    metas = admin.list_topics(timeout=5)
    if topic in metas.topics:
        print(f"  [TOPIC] {topic} ya existe.")
        return
    res = admin.create_topics([
        NewTopic(topic, num_partitions=partitions,
                 replication_factor=replication)
    ])
    for t, f in res.items():
        try:
            f.result()
            print(f"  [TOPIC] '{t}' creado.")
        except Exception as e:
            print(f"  [TOPIC] '{t}' — {e}")


def conectar_producer(bootstrap: str = BOOTSTRAP,
                      retries: int = 6, wait: int = 4) -> Producer:
    """Conecta el producer con reintentos."""
    for i in range(retries):
        if broker_disponible(bootstrap):
            p = Producer({
                "bootstrap.servers": bootstrap,
                "acks": "all",
                "retries": 3,
                "message.timeout.ms": 30_000,
                "linger.ms": 5,          # micro-batching
            })
            print(f"  [PRODUCER] Conectado a {bootstrap}")
            return p
        print(f"  [PRODUCER] Intento {i+1}/{retries} — broker no disponible, "
              f"reintentando en {wait}s...")
        time.sleep(wait)
    raise RuntimeError(f"No se pudo conectar al broker en {bootstrap}")


def delivery_report(err, msg):
    """Callback de entrega — solo imprime errores."""
    if err:
        print(f"  [DELIVERY ERROR] {err}")


# ──────────────────────────────────────────────────────────────────
# FUENTES DE FRAMES
# ──────────────────────────────────────────────────────────────────

def frames_desde_csv(csv_path: str, artist_id: str = "bogdan_sos",
                     song_title: str = "S.O.S — Bogdan Shuvalov"):
    """
    Generador que lee el CSV de realtime_frames.csv del pipeline.py
    y produce dicts de frames con los campos necesarios.
    """
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            voiced = row.get("is_voiced", "").lower() == "true"
            yield {
                "time_s":     float(row["time_s"]),                "time":       float(row["time_s"]),                "note":       row.get("note") or None,
                "hz":         float(row["hz"])         if row.get("hz")         and voiced else None,
                "confidence": float(row["confidence"]) if row.get("confidence") and voiced else None,
                "intensity":  float(row["intensity"])  if row.get("intensity")  else 0.0,
                "register":   row.get("register", "silencio"),
                "is_voiced":  voiced,
                "artist_id":  artist_id,
                "song_title": song_title,
            }


def frames_desde_perfil(artist_id: str = "soprano"):
    """
    Generador que produce frames sintéticos desde los perfiles
    de artist_profiles.py (Idea C). No requiere CSV.
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "vocal_comparador"))
        from artist_profiles import ARTISTS, generate_audio
        from vocal_classifier import classify_register
        import numpy as np
    except ImportError:
        print("  [WARN] artist_profiles.py no encontrado. Usando demo mínimo.")
        yield from _frames_demo_minimo()
        return

    if artist_id not in ARTISTS:
        available = list(ARTISTS.keys())
        print(f"  [WARN] Artista '{artist_id}' no encontrado. "
              f"Disponibles: {available}. Usando 'soprano'.")
        artist_id = "soprano"

    profile = ARTISTS[artist_id]
    seq     = profile["sequence"]
    fps     = 20  # 50ms por frame

    t = 0.0
    for note, ts, te, intensity in seq:
        n_frames = max(1, int((te - ts) * fps))
        for i in range(n_frames):
            from artist_profiles import note_freq
            hz_base = note_freq(note)
            jitter  = np.random.normal(0, hz_base * 0.005)
            hz      = max(50.0, hz_base + jitter)
            yield {
                "time_s":     round(ts + i / fps, 3),
                "time":       round(ts + i / fps, 3),
                "note":       note,
                "hz":         round(hz, 2),
                "confidence": round(0.85 + np.random.normal(0, 0.03), 3),
                "intensity":  round(intensity * 20 + np.random.normal(0, 0.5), 3),
                "register":   classify_register(hz),
                "is_voiced":  True,
                "artist_id":  artist_id,
                "song_title": profile["name"],
            }


def _frames_demo_minimo():
    """Demo de emergencia — 30 frames sintéticos sin dependencias externas."""
    import math
    notas = ["A3","C4","E4","G4","B4","D5","F5","A5","G5","E5","C5"]
    for i in range(60):
        nota = notas[i % len(notas)]
        notes_map = {"C":261.6,"D":293.7,"E":329.6,"F":349.2,
                     "G":392.0,"A":440.0,"B":493.9}
        base = notes_map.get(nota[0], 440.0)
        octave_factor = 2 ** (int(nota[-1]) - 4)
        hz = base * octave_factor
        yield {
            "time_s": round(i * 0.5, 2), "time": round(i * 0.5, 2), "note": nota,
            "hz": round(hz, 1), "confidence": 0.87,
            "intensity": round(15 + 5 * math.sin(i * 0.3), 2),
            "register": "medio-agudo", "is_voiced": True,
            "artist_id": "demo", "song_title": "Demo",
        }


# ──────────────────────────────────────────────────────────────────
# PRODUCER PRINCIPAL
# ──────────────────────────────────────────────────────────────────

def producir(
    frames,
    producer: Producer,
    topic: str   = TOPIC,
    fast: bool   = False,
    interval: float = FRAME_INTERVAL_S,
    verbose: bool   = True,
) -> int:
    """
    Emite frames al tópico Kafka.

    Parameters
    ----------
    frames   : iterable de dicts de frames
    producer : Producer confluent-kafka ya conectado
    fast     : si True, sin sleep entre frames
    interval : tiempo de espera entre frames en segundos
    verbose  : si True, imprime progreso cada 100 frames

    Returns
    -------
    Número de frames emitidos.
    """
    enviados = 0
    t_start  = time.time()

    for frame in frames:
        key   = (frame.get("artist_id") or "unknown").encode("utf-8")
        value = json.dumps(frame, ensure_ascii=False).encode("utf-8")

        producer.produce(
            topic    = topic,
            key      = key,
            value    = value,
            callback = delivery_report,
        )
        enviados += 1

        # Flush periódico para no acumular en buffer
        if enviados % TURBO_BATCH_SIZE == 0:
            producer.poll(0)

        if verbose and enviados % 100 == 0:
            elapsed = time.time() - t_start
            fps_actual = enviados / elapsed if elapsed > 0 else 0
            print(f"  [PRODUCER] {enviados} frames emitidos "
                  f"| {frame['time_s']:.1f}s audio "
                  f"| {fps_actual:.0f} fps")

        if not fast:
            time.sleep(interval)

    producer.flush()
    elapsed = time.time() - t_start
    print(f"\n  [PRODUCER] ✅ Finalizado: {enviados} frames en {elapsed:.1f}s")
    return enviados


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Producer Kafka — emite frames vocales"
    )
    ap.add_argument("--csv",    default=None,
                    help="Path a realtime_frames.csv (pipeline.py)")
    ap.add_argument("--demo",   action="store_true",
                    help="Usar frames sintéticos (sin CSV)")
    ap.add_argument("--artist", default="soprano",
                    help="Artista para modo demo (id de artist_profiles.py)")
    ap.add_argument("--fast",   action="store_true",
                    help="Sin sleep entre frames (turbo mode)")
    ap.add_argument("--broker", default=BOOTSTRAP,
                    help=f"Bootstrap server (default: {BOOTSTRAP})")
    ap.add_argument("--topic",  default=TOPIC,
                    help=f"Tópico de salida (default: {TOPIC})")
    args = ap.parse_args()

    print(f"\n[PRODUCER] vocal_producer.py")
    print(f"  Broker: {args.broker}  |  Tópico: {args.topic}")
    print(f"  Modo: {'demo ('+args.artist+')' if args.demo else 'CSV: '+str(args.csv)}")
    print(f"  Velocidad: {'TURBO (sin sleep)' if args.fast else '50ms/frame (realtime)'}\n")

    p = conectar_producer(args.broker)
    crear_topico(args.topic, args.broker)

    if args.demo:
        frames = frames_desde_perfil(args.artist)
    elif args.csv:
        frames = frames_desde_csv(args.csv)
    else:
        print("ERROR: Especificar --csv <path> o --demo")
        sys.exit(1)

    n = producir(frames, p, topic=args.topic, fast=args.fast)
    print(f"\n  Total: {n} frames → tópico '{args.topic}'")
