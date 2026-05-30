"""
src/metrics.py
────────────────────────────────────────────────────
Módulo de cálculo de métricas musicales a partir
de los frames del análisis vocal.

Importable como módulo o ejecutable directamente:
    python src/metrics.py --frames results/realtime_frames.json
────────────────────────────────────────────────────
"""
import json
import argparse
import numpy as np
from collections import Counter
from pathlib import Path


def compute(frames: list) -> dict:
    """
    Calcula todas las métricas del challenge a partir
    de la lista de frames del análisis.

    Parámetros
    ----------
    frames : list[dict]
        Cada dict debe tener: time, note, hz, intensity,
        register, is_voiced.

    Retorna
    -------
    dict con todas las métricas del tablero final.
    """
    voiced = [r for r in frames if r.get('is_voiced') and r.get('hz')]
    if not voiced:
        return {"error": "No se detectaron frames con voz"}

    hz_vals = [r['hz']        for r in voiced]
    notes   = [r['note']      for r in voiced]
    regs    = [r['register']  for r in voiced]
    ints    = [r.get('intensity', 0) for r in voiced]

    nc = Counter(notes)
    rc = Counter(regs)

    low  = min(voiced, key=lambda x: x['hz'])
    high = max(voiced, key=lambda x: x['hz'])
    rng  = 12 * np.log2(high['hz'] / low['hz'])
    chg  = sum(1 for a, b in zip(notes, notes[1:]) if a != b)

    # Highlights: frames en top 5% de intensidad, separados ≥2s
    thr = np.percentile(ints, 95)
    hl, lt = [], -99.0
    for r in sorted(voiced, key=lambda x: x['time']):
        if r.get('intensity', 0) >= thr and r['time'] - lt >= 2.0:
            hl.append(r); lt = r['time']

    return {
        # Identificación
        "song":    "S.O.S — Bogdan Shuvalov",
        "source":  "torchcrepe + pYIN (librosa)",

        # ── Métricas del tablero ──────────────────────────
        "most_common_note":      nc.most_common(1)[0][0],
        "lowest_note":           {"note": low['note'],  "hz": round(low['hz'],2),  "time": low['time']},
        "highest_note":          {"note": high['note'], "hz": round(high['hz'],2), "time": high['time']},
        "avg_hz":                round(float(np.mean(hz_vals)), 2),
        "vocal_range_semitones": round(float(rng), 1),
        "vocal_range_octaves":   round(float(rng) / 12, 2),
        "note_changes":          chg,
        "voiced_frames":         len(voiced),
        "total_frames":          len(frames),
        "dominant_register":     rc.most_common(1)[0][0],
        "register_distribution": dict(rc),
        "top_notes":             nc.most_common(15),
        "note_distribution":     [{"note": n, "count": c} for n, c in nc.most_common(15)],

        # ── Para visualizaciones ────────────────────────
        "max_intensity": {
            "value": round(float(max(ints)), 4),
            "time":  max(voiced, key=lambda x: x.get('intensity',0))['time'],
            "note":  max(voiced, key=lambda x: x.get('intensity',0))['note'],
        },
        "highlight_moments": [
            {"time": r['time'], "note": r['note'],
             "hz": round(r['hz'],2), "intensity": round(r.get('intensity',0),4)}
            for r in hl[:8]
        ],
        "timeline_chart": [
            {"t": r['time'], "hz": r['hz'], "note": r['note'],
             "intensity": r.get('intensity',0), "register": r['register']}
            for r in voiced[::3]
        ],
    }


def print_summary(m: dict):
    sep = "─" * 52
    print(f"\n{sep}")
    print(f"  MÉTRICAS — {m.get('song','')}")
    print(sep)
    rows = [
        ("Nota más frecuente",    m['most_common_note']),
        ("Nota más grave",        f"{m['lowest_note']['note']}  ({m['lowest_note']['hz']} Hz)  @ {m['lowest_note']['time']}s"),
        ("Nota más aguda",        f"{m['highest_note']['note']}  ({m['highest_note']['hz']} Hz)  @ {m['highest_note']['time']}s"),
        ("Rango vocal",           f"{m['vocal_range_semitones']} semitonos  = {m['vocal_range_octaves']} octavas"),
        ("Frecuencia promedio",   f"{m['avg_hz']} Hz"),
        ("Cambios de nota",       m['note_changes']),
        ("Registro dominante",    m['dominant_register']),
        ("Frames con voz",        f"{m['voiced_frames']} / {m['total_frames']}"),
    ]
    for k, v in rows:
        print(f"  {k:<24}  {v}")
    print(sep)
    print(f"\n  Pico de intensidad: {m['max_intensity']['note']} @ {m['max_intensity']['time']}s")
    print(f"\n  Top 5 notas: {', '.join(n for n,_ in m['top_notes'][:5])}")
    print(f"\n  Distribución de registros:")
    for reg, cnt in sorted(m['register_distribution'].items(),
                           key=lambda x: -x[1]):
        bar = '█' * int(cnt / max(m['register_distribution'].values()) * 20)
        print(f"    {reg:<14} {bar}  ({cnt})")
    print()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', required=True, help='Path al JSON de frames')
    ap.add_argument('--out',    default=None,  help='Guardar métricas en JSON')
    args = ap.parse_args()

    with open(args.frames) as f:
        frames = json.load(f)

    m = compute(frames)
    print_summary(m)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, 'w') as f:
            json.dump(m, f, indent=2)
        print(f"Métricas guardadas: {args.out}")