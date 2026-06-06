"""
vocal_classifier.py
══════════════════════════════════════════════════════════════════════
Módulo de clasificación de tipo vocal basado en features de ventanas
de frames de audio. Se integra con el pipeline del challenge y con
el comparador multi-artista (Idea C).

ESTRATEGIA DE DATASET
─────────────────────
  El problema: 6 artistas × ~41 notas cada uno = sólo 246 muestras
  a nivel de secuencia. Insuficiente para ML.

  La solución: ventanas deslizantes de 2 segundos (stride 0.5s)
  sobre los frames simulados o reales.
    - 6 artistas × ~180 ventanas = 1056 muestras balanceadas
    - Cada ventana → 22 features derivadas del pitch e intensidad

FEATURES EXTRAÍDAS POR VENTANA
──────────────────────────────────
  Grupo Hz (pitch)
    hz_mean, hz_std, hz_cv         media, dispersión, coef. variación
    hz_min, hz_max                 extremos del pitch en la ventana
    hz_range_st                    rango en semitonos
    hz_median, hz_q25, hz_q75     percentiles de distribución
    hz_diff_mean                   movimiento frame-a-frame promedio
    semitone_jumps_5               tasa de saltos ≥5 semitonos

  Grupo Intensidad (dinámica)
    int_mean, int_std, int_cv     nivel y variabilidad dinámica

  Grupo Registro (% del tiempo)
    pct_grave, pct_mediograve
    pct_medioagudo, pct_agudo
    pct_sobreagudo
    ratio_agudo_grave              cociente tiempo agudo / tiempo grave

CLASES
──────
  6 tipos vocales: Barítono · Contratenor · Mezzo-soprano ·
                   Soprano · Tenor dramático · Tenor lírico-pop
  3 grupos:        Voz grave · Voz media · Voz aguda

USO
───
  from vocal_classifier import build_dataset, VocalClassifier

  dataset = build_dataset(artist_dataset_json='results/artist_dataset.json')
  clf     = VocalClassifier()
  clf.fit(dataset['X'], dataset['y6'])
  pred    = clf.predict_song(frames_from_csv)

  # Standalone CLI:
  python vocal_classifier.py --train results/artist_dataset.json
  python vocal_classifier.py --predict results/realtime_frames.csv --model vocal_rf.pkl
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────────

WINDOW_SEC   = 2.0    # duración de cada ventana (segundos)
STRIDE_SEC   = 0.5    # paso entre ventanas (segundos)
MIN_FRAMES   = 10     # mínimo de frames para procesar una ventana
FPS_SYNTH    = 20     # frames/seg en la simulación

# Mapeo tipo vocal → grupo de 3 clases
GRUPO3 = {
    "Barítono":        "Voz grave",
    "Tenor lírico-pop":"Voz grave",
    "Tenor dramático": "Voz media",
    "Mezzo-soprano":   "Voz media",
    "Soprano":         "Voz aguda",
    "Contratenor":     "Voz aguda",
}

FEATURE_NAMES = [
    "hz_mean", "hz_std", "hz_cv",
    "hz_min", "hz_max", "hz_range_st",
    "hz_median", "hz_q25", "hz_q75",
    "hz_diff_mean", "semitone_jumps_5",
    "int_mean", "int_std", "int_cv",
    "pct_grave", "pct_mediograve", "pct_medioagudo",
    "pct_agudo", "pct_sobreagudo",
    "ratio_agudo_grave",
]


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def classify_register(hz: float) -> str:
    if hz < 165:   return "grave"
    elif hz < 330: return "medio-grave"
    elif hz < 660: return "medio-agudo"
    elif hz < 1047:return "agudo"
    else:          return "sobreagudo"


def timeline_to_frames(timeline: list, fps: int = FPS_SYNTH,
                        seed: int = 42) -> list:
    """
    Convierte la timeline de notas de un artista a frames sintéticos.
    Agrega ruido gaussiano leve para simular variación de pitch real.
    """
    rng    = np.random.default_rng(seed)
    frames = []
    for seg in timeline:
        hz       = seg["hz"]
        n_frames = max(1, int((seg["te"] - seg["ts"]) * fps))
        for i in range(n_frames):
            hz_j  = max(50.0, hz + rng.normal(0, hz * 0.005))
            int_j = max(0.0,  seg["intensity"] + rng.normal(0, 0.02))
            frames.append({
                "time":      seg["ts"] + i / fps,
                "hz":        hz_j,
                "intensity": int_j,
                "register":  classify_register(hz),
            })
    return frames


def load_frames_from_csv(csv_path: str) -> list:
    """
    Carga frames desde el CSV de realtime_frames.csv del pipeline.
    Maneja el símbolo ♯ de librosa.
    """
    frames = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("is_voiced", "").lower() != "true":
                continue
            try:
                hz  = float(row["hz"])
                int_= float(row.get("intensity", 0))
            except (ValueError, KeyError):
                continue
            frames.append({
                "time":      float(row["time_s"]),
                "hz":        hz,
                "intensity": int_,
                "register":  row.get("register", classify_register(hz)),
            })
    return frames


# ──────────────────────────────────────────────────────────────────
# EXTRACCIÓN DE FEATURES
# ──────────────────────────────────────────────────────────────────

def extract_features(frames: list) -> dict | None:
    """
    Extrae el vector de 20 features de una lista de frames (ventana).
    Retorna None si la ventana no tiene suficiente señal.
    """
    if len(frames) < MIN_FRAMES:
        return None

    hzs  = np.array([f["hz"]        for f in frames], dtype=float)
    ints = np.array([f["intensity"]  for f in frames], dtype=float)
    regs = [f["register"] for f in frames]
    n    = len(frames)
    rc   = Counter(regs)

    hz_mean  = float(np.mean(hzs))
    hz_std   = float(np.std(hzs))
    if hz_mean <= 0:
        return None

    hz_min  = float(np.min(hzs))
    hz_max  = float(np.max(hzs))

    # Rango en semitonos (log scale)
    hz_range_st = float(12 * math.log2(hz_max / max(hz_min, 1))) if hz_min > 0 else 0.0

    # Movimiento frame-a-frame
    hz_diffs = np.abs(np.diff(hzs))
    hz_diff_mean = float(np.mean(hz_diffs)) if len(hz_diffs) > 0 else 0.0

    # Tasa de saltos grandes (≥5 semitonos)
    st_diffs = [
        12 * math.log2(b / a)
        for a, b in zip(hzs[:-1], hzs[1:])
        if a > 0 and b > 0
    ]
    semitone_jumps_5 = (
        sum(1 for s in st_diffs if abs(s) >= 5) / len(st_diffs)
        if st_diffs else 0.0
    )

    int_mean = float(np.mean(ints))
    int_std  = float(np.std(ints))

    return {
        "hz_mean":           hz_mean,
        "hz_std":            hz_std,
        "hz_cv":             hz_std / hz_mean,
        "hz_min":            hz_min,
        "hz_max":            hz_max,
        "hz_range_st":       hz_range_st,
        "hz_median":         float(np.median(hzs)),
        "hz_q25":            float(np.percentile(hzs, 25)),
        "hz_q75":            float(np.percentile(hzs, 75)),
        "hz_diff_mean":      hz_diff_mean,
        "semitone_jumps_5":  semitone_jumps_5,
        "int_mean":          int_mean,
        "int_std":           int_std,
        "int_cv":            int_std / int_mean if int_mean > 0 else 0.0,
        "pct_grave":         rc.get("grave",       0) / n * 100,
        "pct_mediograve":    rc.get("medio-grave",  0) / n * 100,
        "pct_medioagudo":    rc.get("medio-agudo",  0) / n * 100,
        "pct_agudo":         rc.get("agudo",        0) / n * 100,
        "pct_sobreagudo":    rc.get("sobreagudo",   0) / n * 100,
        "ratio_agudo_grave": (
            rc.get("agudo", 0) + rc.get("sobreagudo", 0)
        ) / max(1, rc.get("grave", 0) + rc.get("medio-grave", 0)),
    }


def frames_to_windows(frames: list,
                       window: float = WINDOW_SEC,
                       stride: float = STRIDE_SEC) -> list:
    """
    Divide una lista de frames en ventanas deslizantes.
    Retorna lista de dicts de features.
    """
    times   = np.array([f["time"] for f in frames])
    t_max   = times.max() if len(times) > 0 else 0.0
    t_start = 0.0
    windows = []
    while t_start + window <= t_max:
        mask  = (times >= t_start) & (times < t_start + window)
        wf    = [frames[i] for i in range(len(frames)) if mask[i]]
        feats = extract_features(wf)
        if feats is not None:
            windows.append({**feats, "_t_start": round(t_start, 2)})
        t_start += stride
    return windows


# ──────────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DEL DATASET
# ──────────────────────────────────────────────────────────────────

def build_dataset(artist_json: str = "results/artist_dataset.json",
                  extra_csv: list = None,
                  window: float = WINDOW_SEC,
                  stride: float = STRIDE_SEC) -> dict:
    """
    Construye el dataset completo de features y etiquetas.

    Parameters
    ----------
    artist_json : path al JSON del comparador multi-artista (Idea C)
    extra_csv   : lista de (csv_path, tipo_vocal) para artistas reales
    window      : duración de cada ventana en segundos
    stride      : paso entre ventanas en segundos

    Returns
    -------
    dict con:
        X       : DataFrame de features
        y6      : array de etiquetas 6 clases (tipo vocal)
        y3      : array de etiquetas 3 grupos
        meta    : DataFrame con artist_id y t_start por fila
        le6     : LabelEncoder para y6
        le3     : LabelEncoder para y3
        feature_names : lista de nombres de features
    """
    from sklearn.preprocessing import LabelEncoder

    with open(artist_json) as f:
        ds = json.load(f)

    rows_X, rows_y6, rows_y3, rows_meta = [], [], [], []

    # ── Artistas sintéticos (de Idea C) ──────────────────────────
    for d in ds:
        if not d.get("timeline"):
            continue
        frames = timeline_to_frames(d["timeline"])
        wins   = frames_to_windows(frames, window=window, stride=stride)
        for w in wins:
            t = w.pop("_t_start", 0)
            rows_X.append(w)
            rows_y6.append(d["tipo"])
            rows_y3.append(GRUPO3.get(d["tipo"], d["tipo"]))
            rows_meta.append({"artist_id": d["id"], "t_start": t, "source": "synth"})

    # ── Artistas reales (CSVs opcionales) ────────────────────────
    if extra_csv:
        for csv_path, tipo_vocal in extra_csv:
            frames = load_frames_from_csv(csv_path)
            if not frames:
                print(f"[WARN] Sin frames válidos en {csv_path}")
                continue
            wins = frames_to_windows(frames, window=window, stride=stride)
            for w in wins:
                t = w.pop("_t_start", 0)
                rows_X.append(w)
                rows_y6.append(tipo_vocal)
                rows_y3.append(GRUPO3.get(tipo_vocal, tipo_vocal))
                rows_meta.append({"artist_id": "real", "t_start": t, "source": "real"})
            print(f"[CSV] {csv_path} → {len(wins)} ventanas etiquetadas como '{tipo_vocal}'")

    X    = pd.DataFrame(rows_X)[FEATURE_NAMES]
    le6  = LabelEncoder().fit(rows_y6)
    le3  = LabelEncoder().fit(rows_y3)
    meta = pd.DataFrame(rows_meta)

    print(f"\n[DATASET] {len(X)} ventanas | {X.shape[1]} features | "
          f"{le6.classes_} clases")
    print(f"  Distribución: {dict(Counter(rows_y6))}")
    return {
        "X":             X,
        "y6":            le6.transform(rows_y6),
        "y3":            le3.transform(rows_y3),
        "y6_labels":     rows_y6,
        "y3_labels":     rows_y3,
        "meta":          meta,
        "le6":           le6,
        "le3":           le3,
        "feature_names": FEATURE_NAMES,
    }


# ──────────────────────────────────────────────────────────────────
# CLASIFICADOR
# ──────────────────────────────────────────────────────────────────

class VocalClassifier:
    """
    Wrapper del Random Forest optimizado para clasificación vocal.
    Incluye predicción por ventana y predicción global de canción.
    """

    def __init__(self, n_estimators: int = 200, random_state: int = 42):
        from sklearn.ensemble import RandomForestClassifier
        self.rf = RandomForestClassifier(
            n_estimators=n_estimators,
            min_samples_leaf=3,
            max_features="sqrt",
            random_state=random_state,
        )
        self.le6   = None
        self.fitted = False

    def fit(self, X: pd.DataFrame, y: np.ndarray, le6=None):
        """Entrena el clasificador."""
        self.rf.fit(X.values, y)
        self.le6    = le6
        self.fitted = True
        print(f"[RF] Entrenado con {len(X)} muestras, "
              f"{X.shape[1]} features, {len(set(y))} clases.")

    def predict_windows(self, frames: list,
                        window: float = WINDOW_SEC,
                        stride: float = STRIDE_SEC) -> list:
        """
        Predice el tipo vocal para cada ventana de una lista de frames.
        Retorna lista de dicts con t_start, clase predicha y probabilidades.
        """
        if not self.fitted:
            raise RuntimeError("Llamar a fit() primero.")
        wins = frames_to_windows(frames, window=window, stride=stride)
        if not wins:
            return []

        meta_ts = [w.pop("_t_start", 0) for w in wins]  # ya fue sacado en build
        X = pd.DataFrame(wins)[FEATURE_NAMES].values
        proba = self.rf.predict_proba(X)
        results = []
        for i, (ts, p) in enumerate(zip(meta_ts, proba)):
            pred_idx = int(np.argmax(p))
            results.append({
                "t_start": ts,
                "pred":    self.le6.classes_[pred_idx] if self.le6 else str(pred_idx),
                "conf":    round(float(p[pred_idx]), 3),
                "proba":   {
                    self.le6.classes_[j]: round(float(v), 3)
                    for j, v in enumerate(p)
                } if self.le6 else {},
            })
        return results

    def predict_song(self, frames: list) -> dict:
        """
        Predicción global de la canción completa: voto mayoritario
        ponderado por confianza de las ventanas.
        """
        window_preds = self.predict_windows(frames)
        if not window_preds:
            return {"pred": None, "conf": 0.0, "votes": {}}

        # Contar votos ponderados por confianza
        votes: dict[str, float] = {}
        for wp in window_preds:
            for clase, prob in wp["proba"].items():
                votes[clase] = votes.get(clase, 0.0) + prob

        total = sum(votes.values())
        votes_norm = {k: round(v / total, 3) for k, v in votes.items()}
        pred = max(votes_norm, key=votes_norm.get)
        return {
            "pred":         pred,
            "conf":         votes_norm[pred],
            "votes":        votes_norm,
            "n_windows":    len(window_preds),
            "window_preds": window_preds,
        }

    def feature_importance(self, feature_names: list = None) -> pd.DataFrame:
        """Retorna DataFrame de importancia de features ordenado."""
        names = feature_names or FEATURE_NAMES
        return (
            pd.DataFrame({
                "feature":    names,
                "importance": self.rf.feature_importances_,
            })
            .sort_values("importance", ascending=False)
            .reset_index(drop=True)
        )

    def save(self, path: str):
        with open(path, "wb") as f:
            pickle.dump({"rf": self.rf, "le6": self.le6}, f)
        print(f"[SAVE] Modelo guardado: {path}")

    @classmethod
    def load(cls, path: str) -> "VocalClassifier":
        vc = cls()
        with open(path, "rb") as f:
            data = pickle.load(f)
        vc.rf     = data["rf"]
        vc.le6    = data["le6"]
        vc.fitted = True
        print(f"[LOAD] Modelo cargado: {path}")
        return vc


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Clasificador de tipo vocal (Random Forest)"
    )
    ap.add_argument("--train",   default=None,
                    help="Path a artist_dataset.json para entrenar")
    ap.add_argument("--predict", default=None,
                    help="Path a realtime_frames.csv para predecir")
    ap.add_argument("--model",   default="vocal_rf.pkl",
                    help="Path para guardar/cargar el modelo")
    ap.add_argument("--csv-real", nargs=2, action="append",
                    metavar=("CSV","TIPO"),
                    help="CSV real + etiqueta (puede repetirse)")
    ap.add_argument("--out",     default="results",
                    help="Directorio de salida")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.train:
        extra = [(c, t) for c, t in (args.csv_real or [])]
        data  = build_dataset(args.train, extra_csv=extra or None)

        clf = VocalClassifier()
        clf.fit(data["X"], data["y6"], le6=data["le6"])
        clf.save(str(out / "vocal_rf.pkl"))

        # Cross-validation report
        from sklearn.model_selection import StratifiedKFold, cross_val_predict
        from sklearn.metrics import classification_report
        cv     = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        y_pred = cross_val_predict(clf.rf, data["X"].values, data["y6"], cv=cv)
        print("\n[EVAL] Cross-validation 5-fold:\n")
        print(classification_report(
            data["y6"], y_pred,
            target_names=data["le6"].classes_
        ))

    if args.predict:
        if not Path(str(out / "vocal_rf.pkl")).exists() and not args.train:
            print("[ERROR] Entrenar primero con --train o proveer --model existente")
        else:
            model_path = args.model if Path(args.model).exists() else str(out / "vocal_rf.pkl")
            clf = VocalClassifier.load(model_path)
            frames = load_frames_from_csv(args.predict)
            result = clf.predict_song(frames)
            print(f"\n[PREDICCIÓN] {args.predict}")
            print(f"  Tipo vocal predicho : {result['pred']}")
            print(f"  Confianza           : {result['conf']:.1%}")
            print(f"  Ventanas analizadas : {result['n_windows']}")
            print(f"  Votos ponderados    :")
            for clase, v in sorted(result["votes"].items(), key=lambda x: -x[1]):
                bar = "█" * int(v * 30)
                print(f"    {clase:<25} {v:.1%}  {bar}")

            json_path = str(out / "prediction_result.json")
            with open(json_path, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n[GUARDADO] → {json_path}")
