"""
artist_profiles.py
══════════════════════════════════════════════════════════════════════
Define los 6 perfiles de artistas sintéticos y genera sus audios WAV.

Cada perfil incluye:
  - Secuencia de notas representativa del estilo (VOCAL_SEQUENCE)
  - Parámetros de timbre (tasa de vibrato, profundidad, armónicos)
  - Metadatos (género, tipo vocal, rango real de referencia)

Los audios son completamente sintéticos — no requieren descargas.
Se generan con el mismo motor que generate_demo.py del challenge,
extendido con parámetros de timbre por artista.

USO
───
  python artist_profiles.py                   # genera los 6 artistas
  python artist_profiles.py --out data/       # directorio personalizado
  python artist_profiles.py --artist baritono # solo un artista
  python artist_profiles.py --list            # lista artistas disponibles
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.io import wavfile

# ──────────────────────────────────────────────────────────────────
# HELPERS DE AUDIO
# ──────────────────────────────────────────────────────────────────

def note_freq(name: str) -> float:
    """Nombre de nota (ej: 'A4', 'C#5') → frecuencia Hz."""
    notes = {
        'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,
        'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11
    }
    n   = name[:-1]
    oct_ = int(name[-1])
    semitones = (oct_ - 4) * 12 + notes[n] - 9
    return 440.0 * (2 ** (semitones / 12))


def vibrato_wave(freq: float, t_seg: np.ndarray, sr: int,
                 rate: float = 5.5, depth: float = 0.015) -> np.ndarray:
    """Onda sinusoidal con vibrato natural."""
    phase = 2 * np.pi * freq * np.cumsum(
        1 + depth * np.sin(2 * np.pi * rate * t_seg)
    ) / sr
    return np.sin(phase)


def adsr(n: int, att: float = 0.05, dec: float = 0.10,
         sus: float = 0.85, rel: float = 0.15) -> np.ndarray:
    """Envolvente ADSR normalizada."""
    a, d, r = int(att * n), int(dec * n), int(rel * n)
    env = np.ones(n)
    env[:a]   = np.linspace(0, 1, a)
    env[a:a+d] = np.linspace(1, sus, d)
    env[-r:]   = np.linspace(sus, 0, r)
    return env


def generate_audio(sequence: list, timbre: dict, duration: int = 90,
                   sr: int = 22050) -> np.ndarray:
    """
    Genera señal de audio sintética para una secuencia de notas.

    Parameters
    ----------
    sequence : list of (note, t_start, t_end, intensity)
    timbre   : dict con vibrato_rate, vibrato_depth, harmonics (list de pesos)
    duration : duración total en segundos
    sr       : sample rate
    """
    t_full = np.linspace(0, duration, sr * duration, endpoint=False)
    signal = np.zeros(sr * duration)

    vr = timbre.get('vibrato_rate',  5.5)
    vd = timbre.get('vibrato_depth', 0.015)
    hm = timbre.get('harmonics',     [1.0, 0.45, 0.25, 0.15, 0.08])

    for note, ts, te, intensity in sequence:
        if ts >= duration:
            break
        te = min(te, float(duration))
        f  = note_freq(note)
        ns, ne = int(ts * sr), int(te * sr)
        if ne <= ns:
            continue
        seg_t = t_full[ns:ne]
        n     = ne - ns

        env  = adsr(n)
        wave = np.zeros(n)
        for k, weight in enumerate(hm, start=1):
            wave += weight * vibrato_wave(k * f, seg_t, sr,
                                          vr * (1 + 0.05 * k),
                                          vd * (1 - 0.05 * k))

        wave /= (np.abs(wave).max() + 1e-10)
        signal[ns:ne] += wave * env * intensity

    signal = signal / (np.abs(signal).max() + 1e-10) * 0.85
    return signal


# ──────────────────────────────────────────────────────────────────
# PERFILES DE ARTISTAS
# ──────────────────────────────────────────────────────────────────
# Cada perfil define:
#   id       : clave usable como nombre de archivo
#   name     : nombre del perfil
#   tipo     : clasificación vocal clásica
#   genero   : género musical predominante
#   ref      : referencia estilística (no implica uso del audio real)
#   timbre   : parámetros de síntesis
#   sequence : lista (nota, t_inicio, t_fin, intensidad)
#
# Los rangos están diseñados para ser contrastantes entre sí:
#   - Bogdan-style    : A2–C6  (3.28 oct)  — el del challenge original
#   - Barítono lírico : G2–F4  (1.97 oct)  — rango cómodo, cálido
#   - Soprano lírica  : C4–G6  (2.58 oct)  — agudo femenino
#   - Tenor pop       : B2–E5  (2.33 oct)  — mezcla pecho/cabeza
#   - Contratenor     : G3–G6  (3.00 oct)  — altísimo masculino
#   - Mezzo-soprano   : A3–B5  (2.08 oct)  — registro medio femenino
# ──────────────────────────────────────────────────────────────────

ARTISTS: dict[str, dict] = {

    # ── 1. Bogdan-style (base del challenge, re-usado) ─────────────
    "bogdan_style": {
        "id":     "bogdan_style",
        "name":   "Tenor Dramático (estilo Bogdan)",
        "tipo":   "Tenor dramático",
        "genero": "Pop / Rock dramático",
        "ref":    "Bogdan Shuvalov — S.O.S",
        "color":  "#38bdf8",
        "timbre": {"vibrato_rate": 5.5, "vibrato_depth": 0.015,
                   "harmonics": [1.0, 0.45, 0.25, 0.15, 0.08]},
        "sequence": [
            ('A3',0,2.5,0.50), ('B3',2.5,4.5,0.55), ('C4',4.5,6.5,0.60),
            ('D4',6.5,8.5,0.65), ('E4',8.5,10.5,0.60), ('F4',10.5,12.5,0.65),
            ('G4',12.5,14.5,0.70), ('A4',14.5,16.5,0.72), ('G4',16.5,18,0.68),
            ('F4',18,19.5,0.65), ('E4',19.5,21,0.62), ('B4',21,23,0.75),
            ('C5',23,25,0.80), ('D5',25,27,0.82), ('E5',27,29.5,0.85),
            ('F5',29.5,32,0.88), ('G5',32,35,0.92), ('A5',35,38,0.95),
            ('G5',38,40,0.90), ('F5',40,42,0.87), ('E5',42,44,0.85),
            ('D3',44,46.5,0.70), ('C3',46.5,48.5,0.65), ('B2',48.5,50.5,0.60),
            ('A2',50.5,53,0.55), ('E4',53,55,0.65), ('G4',55,57,0.70),
            ('B4',57,59.5,0.78), ('C6',59.5,62,0.98), ('B5',62,64.5,0.95),
            ('A5',64.5,67,0.92), ('C6',67,70,1.00), ('G5',70,72.5,0.88),
            ('E5',72.5,74.5,0.82), ('C5',74.5,76.5,0.78), ('A4',76.5,78.5,0.72),
            ('G4',78.5,80,0.68), ('E4',80,82,0.60), ('C4',82,84.5,0.55),
            ('A3',84.5,87,0.50), ('G3',87,90,0.45),
        ],
    },

    # ── 2. Barítono lírico ─────────────────────────────────────────
    "baritono": {
        "id":     "baritono",
        "name":   "Barítono Lírico",
        "tipo":   "Barítono",
        "genero": "Ópera / Balada",
        "ref":    "Estilo Sinatra / Barrientos",
        "color":  "#a78bfa",
        "timbre": {"vibrato_rate": 4.8, "vibrato_depth": 0.018,
                   "harmonics": [1.0, 0.55, 0.30, 0.18, 0.10]},
        "sequence": [
            # Introducción grave y cálida
            ('G2',0,3,0.55), ('A2',3,6,0.60), ('B2',6,9,0.62),
            ('C3',9,12,0.65), ('D3',12,15,0.68), ('E3',15,17,0.65),
            # Zona cómoda del barítono
            ('F3',17,19,0.70), ('G3',19,22,0.72), ('A3',22,25,0.75),
            ('B3',25,27,0.72), ('C4',27,30,0.78), ('D4',30,33,0.80),
            # Registro de pasaje (passaggio) — esfuerzo visible
            ('E4',33,36,0.82), ('F4',36,39,0.85), ('G4',39,42,0.88),
            # Cima del rango — breve
            ('A4',42,45,0.90), ('G4',45,47,0.85), ('F4',47,49,0.80),
            # Descenso expresivo
            ('E4',49,51,0.75), ('D4',51,53,0.72), ('C4',53,56,0.70),
            ('B3',56,59,0.68), ('A3',59,62,0.65), ('G3',62,65,0.62),
            # Cadencia final — graves profundos
            ('F3',65,68,0.60), ('E3',68,71,0.58), ('D3',71,74,0.55),
            ('C3',74,77,0.52), ('B2',77,80,0.50), ('A2',80,83,0.48),
            ('G2',83,87,0.45), ('F2',87,90,0.40),
        ],
    },

    # ── 3. Soprano lírica ──────────────────────────────────────────
    "soprano": {
        "id":     "soprano",
        "name":   "Soprano Lírica",
        "tipo":   "Soprano",
        "genero": "Ópera / Música clásica",
        "ref":    "Estilo Callas / Netrebko",
        "color":  "#f472b6",
        "timbre": {"vibrato_rate": 6.2, "vibrato_depth": 0.012,
                   "harmonics": [1.0, 0.35, 0.20, 0.10, 0.05]},
        "sequence": [
            # Entrada aguda — zona natural
            ('E4',0,2.5,0.60), ('F4',2.5,5,0.62), ('G4',5,7.5,0.65),
            ('A4',7.5,10,0.68), ('B4',10,12.5,0.70), ('C5',12.5,15,0.75),
            # Ascenso al registro medio-agudo
            ('D5',15,17.5,0.78), ('E5',17.5,20,0.80), ('F5',20,22.5,0.83),
            ('G5',22.5,25,0.87), ('A5',25,28,0.90),
            # Pasaje al agudo — zona brillante
            ('B5',28,31,0.93), ('C6',31,34,0.96), ('D6',34,37,0.98),
            # Cima — sobreagudo
            ('E6',37,40,1.00), ('F6',40,42,0.98),
            # Descenso por escalas
            ('E6',42,44,0.95), ('D6',44,46,0.92), ('C6',46,49,0.90),
            ('B5',49,52,0.87), ('A5',52,55,0.83), ('G5',55,58,0.80),
            # Zona de confort — fraseo
            ('F5',58,61,0.78), ('E5',61,63,0.75), ('D5',63,65,0.72),
            ('C5',65,68,0.70), ('B4',68,71,0.67), ('A4',71,74,0.65),
            ('G4',74,77,0.62), ('F4',77,80,0.60), ('E4',80,83,0.58),
            # Cierre suave
            ('D4',83,86,0.55), ('C4',86,90,0.50),
        ],
    },

    # ── 4. Tenor pop (mezcla pecho/cabeza) ─────────────────────────
    "tenor_pop": {
        "id":     "tenor_pop",
        "name":   "Tenor Pop / Belting",
        "tipo":   "Tenor lírico-pop",
        "genero": "Pop / Rock",
        "ref":    "Estilo Freddie Mercury / Adam Lambert",
        "color":  "#fb923c",
        "timbre": {"vibrato_rate": 5.0, "vibrato_depth": 0.010,
                   "harmonics": [1.0, 0.50, 0.28, 0.12, 0.06]},
        "sequence": [
            # Zona media — comienzo moderado
            ('B2',0,2,0.55), ('C3',2,4,0.58), ('D3',4,6,0.60),
            ('E3',6,8,0.62), ('F3',8,10,0.65),
            # Zona principal del tenor pop
            ('G3',10,12,0.68), ('A3',12,15,0.72), ('B3',15,18,0.75),
            ('C4',18,21,0.78), ('D4',21,24,0.80), ('E4',24,27,0.83),
            # Belting — zona de potencia
            ('F4',27,30,0.88), ('G4',30,33,0.92), ('A4',33,36,0.95),
            ('B4',36,39,0.97), ('C5',39,42,0.99),
            # Cima — falsete / mix
            ('D5',42,44,0.95), ('E5',44,46,0.92),
            # Descenso con potencia
            ('D5',46,48,0.90), ('C5',48,50,0.87), ('B4',50,52,0.83),
            ('A4',52,55,0.80), ('G4',55,58,0.75), ('F4',58,61,0.70),
            # Vuelta al registro medio
            ('E4',61,64,0.65), ('D4',64,67,0.62), ('C4',67,70,0.60),
            ('B3',70,73,0.57), ('A3',73,76,0.55), ('G3',76,79,0.52),
            ('F3',79,82,0.50), ('E3',82,85,0.48), ('D3',85,88,0.45),
            ('C3',88,90,0.42),
        ],
    },

    # ── 5. Contratenor ─────────────────────────────────────────────
    "contratenor": {
        "id":     "contratenor",
        "name":   "Contratenor (falsete cultivado)",
        "tipo":   "Contratenor",
        "genero": "Música barroca / Ópera antigua",
        "ref":    "Estilo Philippe Jaroussky / Andreas Scholl",
        "color":  "#34d399",
        "timbre": {"vibrato_rate": 6.8, "vibrato_depth": 0.008,
                   "harmonics": [1.0, 0.30, 0.18, 0.08, 0.04]},
        "sequence": [
            # Falsete bajo — inicio delicado
            ('G3',0,3,0.55), ('A3',3,6,0.58), ('B3',6,9,0.60),
            ('C4',9,12,0.62),
            # Zona principal del contratenor (altus)
            ('D4',12,15,0.65), ('E4',15,18,0.68), ('F4',18,21,0.72),
            ('G4',21,24,0.75), ('A4',24,27,0.78),
            # Ascenso al registro mezzo-soprano
            ('B4',27,30,0.80), ('C5',30,33,0.83), ('D5',33,36,0.86),
            ('E5',36,39,0.89), ('F5',39,42,0.92),
            # Zona soprano — agudo masculino
            ('G5',42,45,0.95), ('A5',45,48,0.97),
            # Cima — sobreagudo de falsete
            ('B5',48,51,0.99), ('C6',51,54,1.00),
            ('B5',54,57,0.97), ('A5',57,60,0.94),
            # Cadencia descendente
            ('G5',60,63,0.90), ('F5',63,66,0.86), ('E5',66,69,0.82),
            ('D5',69,72,0.78), ('C5',72,75,0.74), ('B4',75,78,0.70),
            ('A4',78,81,0.65), ('G4',81,84,0.60), ('F4',84,87,0.55),
            ('E4',87,90,0.50),
        ],
    },

    # ── 6. Mezzo-soprano ───────────────────────────────────────────
    "mezzo": {
        "id":     "mezzo",
        "name":   "Mezzo-Soprano",
        "tipo":   "Mezzo-soprano",
        "genero": "Ópera / Lieder",
        "ref":    "Estilo Cecilia Bartoli / Joyce DiDonato",
        "color":  "#fbbf24",
        "timbre": {"vibrato_rate": 5.8, "vibrato_depth": 0.014,
                   "harmonics": [1.0, 0.40, 0.22, 0.12, 0.06]},
        "sequence": [
            # Zona grave — cálida y oscura
            ('A3',0,3,0.58), ('B3',3,6,0.62), ('C4',6,9,0.65),
            ('D4',9,12,0.68), ('E4',12,15,0.70),
            # Zona cómoda central
            ('F4',15,18,0.73), ('G4',18,21,0.76), ('A4',21,24,0.80),
            ('B4',24,27,0.82), ('C5',27,30,0.85),
            # Registro agudo — más esfuerzo
            ('D5',30,33,0.87), ('E5',33,36,0.90), ('F5',36,39,0.92),
            # Cima breve
            ('G5',39,42,0.95), ('A5',42,45,0.93),
            # Descenso expresivo — fuerza en el grave
            ('G5',45,47,0.90), ('F5',47,49,0.87),
            ('E5',49,51,0.83), ('D5',51,53,0.80), ('C5',53,56,0.77),
            ('B4',56,59,0.74), ('A4',59,62,0.72), ('G4',62,65,0.70),
            # Zona baja — color oscuro, característico de mezzo
            ('F4',65,68,0.68), ('E4',68,71,0.65), ('D4',71,74,0.62),
            ('C4',74,77,0.60), ('B3',77,80,0.57), ('A3',80,83,0.55),
            ('G3',83,86,0.52), ('F3',86,90,0.48),
        ],
    },
}


# ──────────────────────────────────────────────────────────────────
# GENERACIÓN DE AUDIOS
# ──────────────────────────────────────────────────────────────────

def generate_all(out_dir: str = "data/artists", sr: int = 22050,
                 artist_ids: list = None) -> dict:
    """
    Genera un WAV por artista en out_dir.
    Retorna dict {artist_id: wav_path}.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    paths = {}

    targets = artist_ids or list(ARTISTS.keys())
    for aid in targets:
        if aid not in ARTISTS:
            print(f"[WARN] Artista desconocido: {aid}")
            continue
        profile = ARTISTS[aid]
        seq      = profile["sequence"]
        duration = int(seq[-1][2]) + 2  # 2s de margen tras última nota
        duration = max(duration, 60)

        print(f"[GEN] {profile['name']} ({duration}s)...")
        signal = generate_audio(seq, profile["timbre"], duration=duration, sr=sr)
        wav_path = str(out_path / f"{aid}.wav")
        wavfile.write(wav_path, sr, (signal * 32767).astype(np.int16))
        paths[aid] = wav_path
        print(f"      → {wav_path}")

    return paths


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Genera audios sintéticos de 6 perfiles vocales"
    )
    ap.add_argument("--out",    default="data/artists", help="Directorio de salida")
    ap.add_argument("--artist", default=None,           help="ID de artista específico")
    ap.add_argument("--sr",     type=int, default=22050, help="Sample rate")
    ap.add_argument("--list",   action="store_true",     help="Listar artistas disponibles")
    args = ap.parse_args()

    if args.list:
        print("\nArtistas disponibles:\n")
        for aid, p in ARTISTS.items():
            seq = p["sequence"]
            low_note  = min(seq, key=lambda x: note_freq(x[0]))
            high_note = max(seq, key=lambda x: note_freq(x[0]))
            lo_hz = note_freq(low_note[0])
            hi_hz = note_freq(high_note[0])
            st = 12 * math.log2(hi_hz / lo_hz)
            print(f"  {aid:<18} {p['name']:<38} "
                  f"{low_note[0]}({lo_hz:.0f}Hz) → {high_note[0]}({hi_hz:.0f}Hz) "
                  f"= {st:.1f} st")
        print()
    else:
        artist_ids = [args.artist] if args.artist else None
        paths = generate_all(args.out, sr=args.sr, artist_ids=artist_ids)
        print(f"\n✅ {len(paths)} archivo(s) generado(s) en {args.out}/")
