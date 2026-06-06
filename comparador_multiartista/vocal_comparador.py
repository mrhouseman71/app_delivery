"""
vocal_comparador.py
══════════════════════════════════════════════════════════════════════
Analizador multi-artista: extrae métricas de cada perfil vocal
y construye el dataset comparativo.

No requiere librosa ni torchcrepe — calcula pitch directamente
desde las secuencias de notas de los perfiles (análisis sintético
determinístico, sin incertidumbre de estimación de pitch).
Para audio real, usar pipeline.py del challenge y luego
cargar el CSV resultante con load_from_csv().

MÉTRICAS CALCULADAS POR ARTISTA
────────────────────────────────
  Rango y alturas
    nota_grave / nota_aguda     : notas extremas del rango
    hz_grave / hz_aguda         : frecuencias correspondientes
    rango_semitonos             : semitonos entre extremos
    rango_octavas               : octavas entre extremos
    hz_medio                    : frecuencia media ponderada por duración
    nota_modal                  : nota más frecuente (por duración)

  Distribución de registros (% del tiempo con voz)
    pct_grave / pct_medio_grave / pct_medio_agudo
    pct_agudo / pct_sobreagudo

  Dinámica
    intensidad_media            : media de intensidad
    intensidad_max              : intensidad pico (normalizada 0–1)
    intensidad_variacion        : desviación estándar de intensidad
    pct_alta_intensidad         : % del tiempo sobre el percentil 75

  Estilo
    n_notas_distintas           : diversidad melódica
    n_cambios_nota              : transiciones de nota
    densidad_melodica           : cambios de nota por segundo
    duracion_media_nota_s       : duración media de cada nota sostenida
    ratio_agudo_grave           : tiempo en registros agudos vs graves

USO
───
  python vocal_comparador.py                     # analiza todos los artistas
  python vocal_comparador.py --out results/      # directorio de salida
  python vocal_comparador.py --csv mi_analisis.csv --id mi_artista  # audio real
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import json
import math
import csv
from collections import Counter
from pathlib import Path

import numpy as np

from artist_profiles import ARTISTS, note_freq


# ──────────────────────────────────────────────────────────────────
# CLASIFICACIÓN DE REGISTRO (igual que pipeline.py)
# ──────────────────────────────────────────────────────────────────

def _safe_note_freq(name: str) -> float:
    """Wrapper para note_freq que maneja el símbolo ♯ de librosa."""
    return note_freq(name.replace('\u266f', '#'))


def classify_register(hz: float) -> str:
    if hz <= 0:       return "silencio"
    if hz < 165:      return "grave"
    elif hz < 330:    return "medio-grave"
    elif hz < 660:    return "medio-agudo"
    elif hz < 1047:   return "agudo"
    else:             return "sobreagudo"


# ──────────────────────────────────────────────────────────────────
# EXTRACTOR DE MÉTRICAS (desde secuencia de notas)
# ──────────────────────────────────────────────────────────────────

def extract_metrics_from_sequence(profile: dict) -> dict:
    """
    Calcula todas las métricas desde la VOCAL_SEQUENCE del perfil.
    Cada elemento: (note, t_start, t_end, intensity).
    """
    seq = profile["sequence"]
    fps = 20  # frames por segundo simulados (50ms por frame, igual que pipeline)

    # Expandir secuencia a frames sintéticos
    frames = []
    for note, ts, te, intensity in seq:
        hz  = note_freq(note)
        reg = classify_register(hz)
        n_frames = max(1, int((te - ts) * fps))
        for _ in range(n_frames):
            frames.append({
                "note":      note,
                "hz":        hz,
                "intensity": intensity,
                "register":  reg,
                "is_voiced": True,
            })

    if not frames:
        return {}

    hz_vals   = [f["hz"]        for f in frames]
    ints      = [f["intensity"] for f in frames]
    regs      = [f["register"]  for f in frames]
    notes_seq = [f["note"]      for f in frames]

    total = len(frames)
    reg_counts = Counter(regs)

    # ── Rango vocal ───────────────────────────────────────────────
    hz_grave  = min(hz_vals)
    hz_aguda  = max(hz_vals)
    nota_grave = min(seq, key=lambda x: note_freq(x[0]))[0]
    nota_aguda = max(seq, key=lambda x: note_freq(x[0]))[0]
    rango_st   = 12 * math.log2(hz_aguda / hz_grave)

    # ── Frecuencia media ponderada por duración ───────────────────
    dur_per_note = {}
    for note, ts, te, _ in seq:
        dur_per_note[note] = dur_per_note.get(note, 0) + (te - ts)
    hz_medio = sum(note_freq(n) * d for n, d in dur_per_note.items()) / sum(dur_per_note.values())

    # ── Nota modal (más tiempo cantada) ──────────────────────────
    nota_modal = max(dur_per_note, key=dur_per_note.get)

    # ── Distribución de registros (%): ──────────────────────────
    reg_pct = {f"pct_{r.replace('-','_')}": round(reg_counts.get(r, 0) / total * 100, 1)
               for r in ["grave","medio_grave","medio_agudo","agudo","sobreagudo"]}
    # Corrección: medio-grave → medio_grave
    reg_pct = {}
    for r in ["grave","medio-grave","medio-agudo","agudo","sobreagudo"]:
        key = "pct_" + r.replace("-", "_")
        reg_pct[key] = round(reg_counts.get(r, 0) / total * 100, 1)

    # ── Dinámica ──────────────────────────────────────────────────
    int_mean = float(np.mean(ints))
    int_std  = float(np.std(ints))
    int_max  = float(np.max(ints))
    p75      = float(np.percentile(ints, 75))
    pct_alta = sum(1 for i in ints if i >= p75) / total * 100

    # ── Métricas de estilo ────────────────────────────────────────
    notas_distintas = len(set(f["note"] for f in frames))
    cambios_nota    = sum(1 for a, b in zip(notes_seq, notes_seq[1:]) if a != b)
    duracion_total  = seq[-1][2]
    densidad_mel    = round(cambios_nota / duracion_total, 3)

    dur_nota_media = duracion_total / max(1, len(seq))

    t_agudo_sobreagudo = reg_counts.get("agudo", 0) + reg_counts.get("sobreagudo", 0)
    t_grave_mediograve = reg_counts.get("grave", 0) + reg_counts.get("medio-grave", 0)
    ratio_ag_gr = round(t_agudo_sobreagudo / max(1, t_grave_mediograve), 3)

    return {
        # Identificación
        "id":     profile["id"],
        "name":   profile["name"],
        "tipo":   profile["tipo"],
        "genero": profile["genero"],
        "ref":    profile["ref"],
        "color":  profile["color"],

        # Rango
        "nota_grave":        nota_grave,
        "nota_aguda":        nota_aguda,
        "hz_grave":          round(hz_grave, 1),
        "hz_aguda":          round(hz_aguda, 1),
        "rango_semitonos":   round(rango_st, 1),
        "rango_octavas":     round(rango_st / 12, 2),
        "hz_medio":          round(hz_medio, 1),
        "nota_modal":        nota_modal,

        # Registros (%)
        **reg_pct,

        # Dinámica
        "intensidad_media":    round(int_mean, 3),
        "intensidad_max":      round(int_max, 3),
        "intensidad_variacion": round(int_std, 3),
        "pct_alta_intensidad": round(pct_alta, 1),

        # Estilo
        "n_notas_distintas":   notas_distintas,
        "n_cambios_nota":      cambios_nota,
        "densidad_melodica":   densidad_mel,
        "duracion_media_nota_s": round(dur_nota_media, 2),
        "ratio_agudo_grave":   ratio_ag_gr,

        # Para gráficos de timeline
        "timeline": [
            {
                "note": n, "hz": round(note_freq(n), 1),
                "ts": ts, "te": te, "intensity": intensity,
                "register": classify_register(note_freq(n))
            }
            for n, ts, te, intensity in profile["sequence"]
        ],
    }


def load_from_csv(csv_path: str, artist_id: str, name: str,
                  tipo: str = "Real", genero: str = "Real",
                  color: str = "#94a3b8") -> dict:
    """
    Carga métricas desde un CSV generado por pipeline.py.
    Permite integrar análisis de audio real al comparador.
    """
    frames = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            voiced = row.get("is_voiced", "").lower() == "true"
            if not voiced:
                continue
            hz = float(row["hz"]) if row.get("hz") else None
            if not hz:
                continue
            frames.append({
                "note":      row.get("note"),
                "hz":        hz,
                "intensity": float(row.get("intensity", 0)),
                "register":  row.get("register", ""),
            })

    if not frames:
        return {}

    hz_vals   = [f["hz"] for f in frames]
    ints      = [f["intensity"] for f in frames]
    regs      = [f["register"] for f in frames]
    notes_seq = [f["note"] for f in frames]
    total     = len(frames)
    reg_counts = Counter(regs)

    hz_grave = min(hz_vals); hz_aguda = max(hz_vals)
    rango_st = 12 * math.log2(hz_aguda / hz_grave)
    hz_medio = float(np.mean(hz_vals))

    nc = Counter(notes_seq)
    nota_grave = min(nc, key=lambda n: _safe_note_freq(n) if n else float('inf'))
    nota_aguda = max(nc, key=lambda n: _safe_note_freq(n) if n else 0)
    nota_modal = nc.most_common(1)[0][0]

    reg_pct = {}
    for r in ["grave","medio-grave","medio-agudo","agudo","sobreagudo"]:
        reg_pct["pct_" + r.replace("-","_")] = round(
            reg_counts.get(r, 0) / total * 100, 1)

    int_mean = float(np.mean(ints)); int_std = float(np.std(ints))
    int_max  = float(np.max(ints))
    p75      = float(np.percentile(ints, 75))
    pct_alta = sum(1 for i in ints if i >= p75) / total * 100

    notas_distintas = len(set(n for n in notes_seq if n))
    cambios_nota    = sum(1 for a, b in zip(notes_seq, notes_seq[1:]) if a != b)
    densidad_mel    = round(cambios_nota / (total * 0.05), 3)

    t_ag = reg_counts.get("agudo",0) + reg_counts.get("sobreagudo",0)
    t_gr = reg_counts.get("grave",0) + reg_counts.get("medio-grave",0)

    return {
        "id": artist_id, "name": name, "tipo": tipo,
        "genero": genero, "ref": csv_path, "color": color,
        "nota_grave": nota_grave, "nota_aguda": nota_aguda,
        "hz_grave": round(hz_grave,1), "hz_aguda": round(hz_aguda,1),
        "rango_semitonos": round(rango_st,1),
        "rango_octavas":   round(rango_st/12,2),
        "hz_medio": round(hz_medio,1), "nota_modal": nota_modal,
        **reg_pct,
        "intensidad_media":    round(int_mean,3),
        "intensidad_max":      round(int_max,3),
        "intensidad_variacion": round(int_std,3),
        "pct_alta_intensidad": round(pct_alta,1),
        "n_notas_distintas":   notas_distintas,
        "n_cambios_nota":      cambios_nota,
        "densidad_melodica":   densidad_mel,
        "duracion_media_nota_s": 0,
        "ratio_agudo_grave":   round(t_ag / max(1, t_gr), 3),
        "timeline": [],
    }


# ──────────────────────────────────────────────────────────────────
# DATASET COMPLETO
# ──────────────────────────────────────────────────────────────────

def build_dataset(extra_csv: list = None) -> list:
    """
    Construye el dataset completo de artistas.
    extra_csv: lista de (csv_path, artist_id, name, tipo, color)
    """
    dataset = []
    for aid, profile in ARTISTS.items():
        metrics = extract_metrics_from_sequence(profile)
        dataset.append(metrics)
        print(f"  [{aid}] {profile['name']}: "
              f"{metrics['nota_grave']}–{metrics['nota_aguda']} "
              f"({metrics['rango_octavas']} oct)")

    if extra_csv:
        for entry in extra_csv:
            csv_path, aid, name, tipo, color = entry
            m = load_from_csv(csv_path, aid, name, tipo=tipo, color=color)
            if m:
                dataset.append(m)
                print(f"  [{aid}] {name} (CSV real): {m['nota_grave']}–{m['nota_aguda']}")

    return dataset


def save_dataset(dataset: list, out_dir: str = "results") -> dict:
    """Guarda dataset completo y CSV de métricas."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # JSON completo
    json_path = str(out / "artist_dataset.json")
    with open(json_path, "w") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    # CSV de métricas (sin timeline)
    csv_path = str(out / "artist_metrics.csv")
    skip = {"timeline", "ref"}
    if dataset:
        fields = [k for k in dataset[0] if k not in skip]
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(dataset)

    print(f"\n  ✅ dataset JSON  → {json_path}")
    print(f"  ✅ métricas CSV  → {csv_path}")
    return {"json": json_path, "csv": csv_path}


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Extrae métricas de todos los perfiles vocales"
    )
    ap.add_argument("--out", default="results", help="Directorio de salida")
    ap.add_argument("--csv", default=None,
                    help="CSV de pipeline.py para agregar artista real")
    ap.add_argument("--id",   default="real_artist")
    ap.add_argument("--name", default="Artista Real")
    ap.add_argument("--tipo", default="Real")
    ap.add_argument("--color", default="#94a3b8")
    args = ap.parse_args()

    print("\n[ANÁLISIS] Calculando métricas de artistas...\n")
    extra = None
    if args.csv:
        extra = [(args.csv, args.id, args.name, args.tipo, args.color)]

    dataset = build_dataset(extra_csv=extra)
    paths   = save_dataset(dataset, out_dir=args.out)

    # Resumen tabla
    print("\n" + "─"*78)
    print(f"  {'Artista':<35} {'Rango':>12}  {'Hz medio':>10}  {'Reg. dom.':>14}")
    print("─"*78)
    reg_order = ["grave","medio-grave","medio-agudo","agudo","sobreagudo"]
    for m in dataset:
        dom_reg = max(
            ["grave","medio_grave","medio_agudo","agudo","sobreagudo"],
            key=lambda r: m.get(f"pct_{r}", 0)
        ).replace("_","-")
        print(f"  {m['name']:<35} "
              f"{m['nota_grave']+'–'+m['nota_aguda']:>12}  "
              f"{m['hz_medio']:>8.0f}Hz  "
              f"{dom_reg:>14}")
    print("─"*78)
    print(f"\n  Total artistas analizados: {len(dataset)}\n")
