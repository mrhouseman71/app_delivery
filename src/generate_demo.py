"""
src/generate_demo.py
────────────────────────────────────────────────────
Genera el audio sintético de demostración que simula
el rango vocal de S.O.S (Bogdan Shuvalov): A2 → C6.

Uso:
    python src/generate_demo.py
    python src/generate_demo.py --out data/samples/demo.wav --duration 90
────────────────────────────────────────────────────
"""
import argparse
import numpy as np
from scipy.io import wavfile
from pathlib import Path


def note_freq(name: str) -> float:
    """Nombre de nota → frecuencia Hz. Ej: 'A4' → 440.0"""
    notes = {'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,
             'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11}
    return 440.0 * 2**((int(name[-1])-4)*12 + notes[name[:-1]] - 9)/12


def vibrato_wave(freq, t_seg, sr, rate=5.5, depth=0.015):
    """Onda sinusoidal con vibrato."""
    phase = 2*np.pi*freq * np.cumsum(1 + depth*np.sin(2*np.pi*rate*t_seg)) / sr
    return np.sin(phase)


def adsr(n_samples, att=0.05, dec=0.10, sus=0.85, rel=0.15):
    """Envolvente ADSR normalizada."""
    att_n = int(att*n_samples); dec_n = int(dec*n_samples); rel_n = int(rel*n_samples)
    env = np.ones(n_samples)
    env[:att_n] = np.linspace(0, 1, att_n)
    env[att_n:att_n+dec_n] = np.linspace(1, sus, dec_n)
    env[-rel_n:] = np.linspace(sus, 0, rel_n)
    return env


# Secuencia de notas de S.O.S: (nota, inicio_s, fin_s, intensidad)
VOCAL_SEQUENCE = [
    # Introducción — registro medio-grave
    ('A3', 0,    2.5,  0.50), ('B3', 2.5,  4.5,  0.55),
    ('C4', 4.5,  6.5,  0.60), ('D4', 6.5,  8.5,  0.65),
    # Estrofa 1 — ascenso gradual
    ('E4', 8.5,  10.5, 0.60), ('F4', 10.5, 12.5, 0.65),
    ('G4', 12.5, 14.5, 0.70), ('A4', 14.5, 16.5, 0.72),
    ('G4', 16.5, 18.0, 0.68), ('F4', 18.0, 19.5, 0.65),
    ('E4', 19.5, 21.0, 0.62),
    # Subida al registro agudo
    ('B4', 21.0, 23.0, 0.75), ('C5', 23.0, 25.0, 0.80),
    ('D5', 25.0, 27.0, 0.82), ('E5', 27.0, 29.5, 0.85),
    ('F5', 29.5, 32.0, 0.88),
    # Coro — registro agudo / alta intensidad
    ('G5', 32.0, 35.0, 0.92), ('A5', 35.0, 38.0, 0.95),
    ('G5', 38.0, 40.0, 0.90), ('F5', 40.0, 42.0, 0.87),
    ('E5', 42.0, 44.0, 0.85),
    # Descenso dramático — graves
    ('D3', 44.0, 46.5, 0.70), ('C3', 46.5, 48.5, 0.65),
    ('B2', 48.5, 50.5, 0.60), ('A2', 50.5, 53.0, 0.55),  # ← nota grave extrema
    # Recuperación
    ('E4', 53.0, 55.0, 0.65), ('G4', 55.0, 57.0, 0.70),
    ('B4', 57.0, 59.5, 0.78),
    # Clímax — sobreagudo
    ('C6', 59.5, 62.0, 0.98), ('B5', 62.0, 64.5, 0.95),  # ← sobreagudo
    ('A5', 64.5, 67.0, 0.92), ('C6', 67.0, 70.0, 1.00),  # ← pico máximo
    # Cadencia final
    ('G5', 70.0, 72.5, 0.88), ('E5', 72.5, 74.5, 0.82),
    ('C5', 74.5, 76.5, 0.78), ('A4', 76.5, 78.5, 0.72),
    ('G4', 78.5, 80.0, 0.68), ('E4', 80.0, 82.0, 0.60),
    ('C4', 82.0, 84.5, 0.55), ('A3', 84.5, 87.0, 0.50),
    ('G3', 87.0, 90.0, 0.45),
]


def generate(out_path: str, duration: int = 90, sr: int = 44100):
    t_full = np.linspace(0, duration, sr * duration, endpoint=False)
    signal  = np.zeros(sr * duration)

    for note, ts, te, intensity in VOCAL_SEQUENCE:
        if ts >= duration: break
        te  = min(te, duration)
        f   = note_freq(note)
        ns, ne = int(ts*sr), int(te*sr)
        seg_t  = t_full[ns:ne]
        n      = ne - ns

        env  = adsr(n)
        # Suma de armónicos para timbre vocal
        wave = (vibrato_wave(f,   seg_t, sr) +
                0.45 * vibrato_wave(2*f, seg_t, sr, 5.2) +
                0.25 * vibrato_wave(3*f, seg_t, sr, 5.8) +
                0.15 * vibrato_wave(4*f, seg_t, sr) +
                0.08 * vibrato_wave(5*f, seg_t, sr, 6.0))
        wave /= np.abs(wave).max() + 1e-10
        signal[ns:ne] += wave * env * intensity

    signal = signal / (np.abs(signal).max() + 1e-10) * 0.85
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(out_path, sr, (signal * 32767).astype(np.int16))
    print(f"Audio demo generado: {out_path}  ({duration}s · {sr}Hz)")
    print(f"Rango vocal simulado: A2 ({note_freq('A2'):.0f}Hz) → C6 ({note_freq('C6'):.0f}Hz)")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out',      default='data/samples/demo_sos.wav')
    ap.add_argument('--duration', type=int, default=90)
    args = ap.parse_args()
    generate(args.out, args.duration)