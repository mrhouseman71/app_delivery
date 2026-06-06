"""
anomaly_detector.py
══════════════════════════════════════════════════════════════════════
Módulo de detección de anomalías vocales para el pipeline de análisis.
Se integra directamente con pipeline.py (challenge_streaming).

ANOMALÍAS DETECTADAS
────────────────────
  BREAK_VOZ        Salto brusco de pitch ≥ SEMITONE_JUMP_THRESH semitonos
                   entre dos frames consecutivos con voz. Indica un "quiebre"
                   o cambio técnico de registro (chest → head voice).

  CLIMAX_VOCAL     Sostenimiento de una nota aguda (registro agudo o
                   sobreagudo) por más de CLIMAX_MIN_FRAMES consecutivos.
                   Marca los momentos de mayor exigencia técnica.

  CAIDA_INTENS     Descenso brusco de intensidad RMS ≥ INTENSITY_DROP_THRESH%
                   en una ventana corta. Detecta cortes de voz, calderones
                   o dinámicas abruptas (forte → piano).

  AGUDO_EXTREMO    Primera aparición de una nota en el registro sobreagudo
                   (> C6 / 1047 Hz). Evento único por sesión.

  SILENCIO_LARGO   Más de SILENCE_MIN_FRAMES frames sin voz consecutivos.
                   Identifica pausas estructurales de la canción.

  INESTABILIDAD    Coeficiente de variación de Hz elevado en ventana corta
                   (vibrato excesivo, notas temblorosas o desafinación).

USO STANDALONE
──────────────
  python anomaly_detector.py --csv results/realtime_frames.csv
  python anomaly_detector.py --json vocal_analysis/output/frame_analysis.json
  python anomaly_detector.py --csv results/realtime_frames.csv --out anomalies.json
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

import numpy as np


# ──────────────────────────────────────────────────────────────────
# PARÁMETROS TUNABLES
# ──────────────────────────────────────────────────────────────────

SEMITONE_JUMP_THRESH  = 5      # semitonos: salto mínimo para BREAK_VOZ
CLIMAX_MIN_FRAMES     = 8      # frames consecutivos en agudo para CLIMAX_VOCAL
CLIMAX_REGISTER_TRIG  = {"agudo", "sobreagudo"}  # registros que disparan clímax
INTENSITY_DROP_THRESH = 0.50   # fracción: caída ≥ 50% del pico local
INTENSITY_WINDOW      = 10     # frames de ventana para detectar caída
SILENCE_MIN_FRAMES    = 15     # frames sin voz consecutivos para SILENCIO_LARGO
INSTABILITY_WINDOW    = 8      # frames para medir variación de Hz
INSTABILITY_CV_THRESH = 0.025  # coef. variación > 2.5 % → inestabilidad
COOLDOWN_FRAMES       = 5      # frames mínimos entre dos eventos del mismo tipo


# ──────────────────────────────────────────────────────────────────
# DATACLASS DE EVENTO
# ──────────────────────────────────────────────────────────────────

@dataclass
class AnomalyEvent:
    time:        float
    tipo:        str
    severidad:   str          # "baja" | "media" | "alta"
    descripcion: str
    detalle:     dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def hz_to_semitones(hz_a: float, hz_b: float) -> float:
    """Diferencia en semitonos entre dos frecuencias."""
    if hz_a <= 0 or hz_b <= 0:
        return 0.0
    return abs(12.0 * math.log2(hz_b / hz_a))


def severity_by_jump(semitones: float) -> str:
    if semitones >= 12:
        return "alta"
    if semitones >= 7:
        return "media"
    return "baja"


def severity_by_climax(frames: int) -> str:
    if frames >= 20:
        return "alta"
    if frames >= 12:
        return "media"
    return "baja"


def severity_by_drop(ratio: float) -> str:
    if ratio >= 0.75:
        return "alta"
    if ratio >= 0.60:
        return "media"
    return "baja"


# ──────────────────────────────────────────────────────────────────
# DETECTOR PRINCIPAL
# ──────────────────────────────────────────────────────────────────

class VocalAnomalyDetector:
    """
    Detector de anomalías vocal que procesa una lista de frames
    de forma secuencial, simulando un análisis en streaming.

    Parámetros
    ----------
    frames : list[dict]
        Lista de frames generados por pipeline.py.
        Cada frame: {time, note, hz, intensity, register, is_voiced}
    """

    def __init__(self, frames: list):
        self.frames  = frames
        self.events: List[AnomalyEvent] = []
        self._cooldowns: dict[str, int] = {}  # tipo → frames hasta próximo evento

    # ── Registro de cooldown ──────────────────────────────────────

    def _can_fire(self, tipo: str) -> bool:
        remaining = self._cooldowns.get(tipo, 0)
        return remaining <= 0

    def _tick_cooldowns(self):
        for t in list(self._cooldowns):
            self._cooldowns[t] = max(0, self._cooldowns[t] - 1)

    def _fire(self, tipo: str, event: AnomalyEvent):
        self.events.append(event)
        self._cooldowns[tipo] = COOLDOWN_FRAMES

    # ── Reglas individuales ───────────────────────────────────────

    def _detect_break_voz(self, prev: dict, curr: dict):
        """Salto brusco de pitch entre frames consecutivos."""
        if not (prev.get("is_voiced") and curr.get("is_voiced")):
            return
        hz_prev = prev.get("hz") or 0
        hz_curr = curr.get("hz") or 0
        if hz_prev <= 0 or hz_curr <= 0:
            return
        st = hz_to_semitones(hz_prev, hz_curr)
        if st >= SEMITONE_JUMP_THRESH and self._can_fire("BREAK_VOZ"):
            sev = severity_by_jump(st)
            direction = "↑" if hz_curr > hz_prev else "↓"
            self._fire("BREAK_VOZ", AnomalyEvent(
                time=curr["time"],
                tipo="BREAK_VOZ",
                severidad=sev,
                descripcion=f"Salto de {st:.1f} st {direction} ({prev['note']} → {curr['note']})",
                detalle={
                    "nota_origen":  prev["note"],
                    "nota_destino": curr["note"],
                    "hz_origen":    hz_prev,
                    "hz_destino":   hz_curr,
                    "semitonos":    round(st, 2),
                    "direccion":    "ascendente" if hz_curr > hz_prev else "descendente",
                }
            ))

    def _detect_climax_vocal(self, window: list) -> Optional[AnomalyEvent]:
        """Sostenimiento de nota aguda durante N frames consecutivos."""
        if len(window) < CLIMAX_MIN_FRAMES:
            return None
        # Todos los frames de la ventana deben ser agudo/sobreagudo y con voz
        if all(
            f.get("is_voiced") and f.get("register") in CLIMAX_REGISTER_TRIG
            for f in window[-CLIMAX_MIN_FRAMES:]
        ):
            last = window[-1]
            if self._can_fire("CLIMAX_VOCAL"):
                n_frames = sum(
                    1 for f in reversed(window)
                    if f.get("is_voiced") and f.get("register") in CLIMAX_REGISTER_TRIG
                )
                sev = severity_by_climax(n_frames)
                return AnomalyEvent(
                    time=last["time"],
                    tipo="CLIMAX_VOCAL",
                    severidad=sev,
                    descripcion=f"Clímax: {last['note']} sostenida {n_frames} frames ({n_frames*0.05:.1f}s)",
                    detalle={
                        "nota":      last["note"],
                        "hz":        last.get("hz"),
                        "registro":  last["register"],
                        "duracion_s": round(n_frames * 0.05, 2),
                        "frames":    n_frames,
                    }
                )
        return None

    def _detect_caida_intensidad(self, window: list) -> Optional[AnomalyEvent]:
        """Caída brusca de intensidad en ventana deslizante."""
        if len(window) < INTENSITY_WINDOW:
            return None
        intensities = [f.get("intensity", 0) for f in window[-INTENSITY_WINDOW:]]
        peak = max(intensities[:INTENSITY_WINDOW // 2])
        current = intensities[-1]
        if peak <= 0:
            return None
        drop_ratio = 1.0 - (current / peak)
        if drop_ratio >= INTENSITY_DROP_THRESH and self._can_fire("CAIDA_INTENS"):
            last = window[-1]
            sev = severity_by_drop(drop_ratio)
            return AnomalyEvent(
                time=last["time"],
                tipo="CAIDA_INTENS",
                severidad=sev,
                descripcion=f"Caída de intensidad {drop_ratio*100:.0f}% (pico {peak:.1f} → actual {current:.1f})",
                detalle={
                    "intensidad_pico":    round(peak, 4),
                    "intensidad_actual":  round(current, 4),
                    "caida_porcentaje":   round(drop_ratio * 100, 1),
                }
            )
        return None

    def _detect_silencio_largo(self, silence_streak: int, frame: dict):
        """Silencio prolongado (pausa estructural)."""
        if silence_streak == SILENCE_MIN_FRAMES and self._can_fire("SILENCIO_LARGO"):
            sev = "media" if silence_streak < 30 else "alta"
            self._fire("SILENCIO_LARGO", AnomalyEvent(
                time=frame["time"],
                tipo="SILENCIO_LARGO",
                severidad=sev,
                descripcion=f"Silencio de {silence_streak*0.05:.1f}s detectado",
                detalle={"frames_silencio": silence_streak}
            ))

    def _detect_agudo_extremo(self, frame: dict, seen_sobreagudo: bool) -> bool:
        """Primera nota sobreaguda de la canción (evento único)."""
        if (
            not seen_sobreagudo
            and frame.get("register") == "sobreagudo"
            and frame.get("is_voiced")
        ):
            self._fire("AGUDO_EXTREMO", AnomalyEvent(
                time=frame["time"],
                tipo="AGUDO_EXTREMO",
                severidad="alta",
                descripcion=f"Primera nota sobreaguda: {frame['note']} ({frame.get('hz',0):.0f} Hz)",
                detalle={
                    "nota": frame["note"],
                    "hz":   frame.get("hz"),
                }
            ))
            return True
        return seen_sobreagudo

    def _detect_inestabilidad(self, window: list) -> Optional[AnomalyEvent]:
        """Variación excesiva de Hz en ventana corta (vibrato patológico)."""
        if len(window) < INSTABILITY_WINDOW:
            return None
        voiced_hz = [
            f.get("hz") for f in window[-INSTABILITY_WINDOW:]
            if f.get("is_voiced") and f.get("hz")
        ]
        if len(voiced_hz) < INSTABILITY_WINDOW // 2:
            return None
        mean_hz = np.mean(voiced_hz)
        if mean_hz <= 0:
            return None
        cv = np.std(voiced_hz) / mean_hz
        if cv >= INSTABILITY_CV_THRESH and self._can_fire("INESTABILIDAD"):
            last = window[-1]
            return AnomalyEvent(
                time=last["time"],
                tipo="INESTABILIDAD",
                severidad="baja" if cv < 0.04 else "media",
                descripcion=f"Inestabilidad de pitch (CV={cv:.3f}) en zona {last.get('note','?')}",
                detalle={
                    "coef_variacion": round(float(cv), 4),
                    "hz_medio":       round(float(mean_hz), 2),
                    "hz_std":         round(float(np.std(voiced_hz)), 2),
                    "nota_zona":      last.get("note"),
                }
            )
        return None

    # ── Loop principal ────────────────────────────────────────────

    def detect(self) -> List[AnomalyEvent]:
        """
        Procesa todos los frames y retorna la lista de eventos detectados.
        Simula un procesamiento en streaming frame a frame.
        """
        self.events = []
        window:  deque = deque(maxlen=max(INTENSITY_WINDOW, INSTABILITY_WINDOW, CLIMAX_MIN_FRAMES) + 2)
        silence_streak = 0
        seen_sobreagudo = False

        for i, frame in enumerate(self.frames):
            self._tick_cooldowns()
            window.append(frame)
            win_list = list(window)

            # — Break de voz (requiere frame anterior) —
            if i > 0:
                self._detect_break_voz(self.frames[i - 1], frame)

            # — Clímax vocal —
            ev = self._detect_climax_vocal(win_list)
            if ev:
                self._fire("CLIMAX_VOCAL", ev)

            # — Caída de intensidad —
            ev = self._detect_caida_intensidad(win_list)
            if ev:
                self._fire("CAIDA_INTENS", ev)

            # — Silencio largo —
            if not frame.get("is_voiced"):
                silence_streak += 1
                self._detect_silencio_largo(silence_streak, frame)
            else:
                silence_streak = 0

            # — Agudo extremo (evento único) —
            seen_sobreagudo = self._detect_agudo_extremo(frame, seen_sobreagudo)

            # — Inestabilidad —
            ev = self._detect_inestabilidad(win_list)
            if ev:
                self._fire("INESTABILIDAD", ev)

        # Ordenar por tiempo
        self.events.sort(key=lambda e: e.time)
        return self.events


# ──────────────────────────────────────────────────────────────────
# RESUMEN Y ESTADÍSTICAS
# ──────────────────────────────────────────────────────────────────

def summarize(events: List[AnomalyEvent]) -> dict:
    """Genera resumen estadístico de los eventos detectados."""
    from collections import Counter
    if not events:
        return {"total": 0, "por_tipo": {}, "por_severidad": {}, "eventos": []}

    tipos     = Counter(e.tipo      for e in events)
    severidades = Counter(e.severidad for e in events)

    return {
        "total":          len(events),
        "por_tipo":       dict(tipos),
        "por_severidad":  dict(severidades),
        "primer_evento":  events[0].time,
        "ultimo_evento":  events[-1].time,
        "eventos":        [e.to_dict() for e in events],
    }


def print_report(events: List[AnomalyEvent]):
    """Imprime reporte en consola."""
    icons = {
        "BREAK_VOZ":     "⚡",
        "CLIMAX_VOCAL":  "🔥",
        "CAIDA_INTENS":  "📉",
        "SILENCIO_LARGO":"⏸ ",
        "AGUDO_EXTREMO": "🎯",
        "INESTABILIDAD": "〰️",
    }
    sev_colors = {"alta": "!!!",  "media": " !! ", "baja": "  ! "}

    print("\n" + "═" * 66)
    print("  DETECCIÓN DE ANOMALÍAS VOCALES")
    print("═" * 66)
    if not events:
        print("  Sin anomalías detectadas.\n")
        return

    for e in events:
        icon = icons.get(e.tipo, "•")
        sev  = sev_colors.get(e.severidad, "    ")
        print(f"  {e.time:6.2f}s  {sev}  {icon}  [{e.tipo:<16}]  {e.descripcion}")

    from collections import Counter
    print("\n" + "─" * 66)
    print(f"  Total eventos: {len(events)}")
    for tipo, cnt in Counter(e.tipo for e in events).most_common():
        print(f"    {icons.get(tipo,'•')}  {tipo:<18} {cnt:>3}x")
    print("═" * 66 + "\n")


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def load_frames_csv(path: str) -> list:
    import csv
    frames = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            frames.append({
                "time":      float(row["time_s"]),
                "note":      row["note"] if row["note"] != "" else None,
                "hz":        float(row["hz"]) if row["hz"] else None,
                "intensity": float(row["intensity"]) if row["intensity"] else 0.0,
                "register":  row["register"],
                "is_voiced": row["is_voiced"].strip().lower() == "true",
            })
    return frames


def load_frames_json(path: str) -> list:
    with open(path) as f:
        return json.load(f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Detector de anomalías vocales")
    ap.add_argument("--csv",  help="Path al CSV de frames (realtime_frames.csv)")
    ap.add_argument("--json", help="Path al JSON de frames (frame_analysis.json)")
    ap.add_argument("--out",  help="Guardar resultado en JSON")
    args = ap.parse_args()

    if not args.csv and not args.json:
        ap.error("Proveer --csv o --json")

    frames = load_frames_csv(args.csv) if args.csv else load_frames_json(args.json)
    print(f"[INFO] {len(frames)} frames cargados.")

    detector = VocalAnomalyDetector(frames)
    events   = detector.detect()

    print_report(events)
    summary  = summarize(events)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"[GUARDADO] → {args.out}")
