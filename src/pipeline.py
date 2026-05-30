"""
=============================================================
PIPELINE DE ANÁLISIS VOCAL EN TIEMPO REAL
Canción: S.O.S — Bogdan Shuvalov
Challenge: Streaming de notas musicales en tiempo real
=============================================================

ARQUITECTURA:
  Video/Audio → Separación vocal (Demucs) → Fragmentos
  → Análisis pYIN (librosa) → Notas + Registro + Intensidad
  → JSON de resultados → Dashboard HTML interactivo

DEPENDENCIAS:
  pip install librosa numpy scipy yt-dlp demucs matplotlib pandas

USO:
  # Opción 1: con archivo de audio real
  python pipeline_vocal_analysis.py --audio ruta/al/audio.wav

  # Opción 2: modo demo con audio sintético
  python pipeline_vocal_analysis.py --demo

  # Opción 3: descargar de YouTube (requiere acceso de red)
  python pipeline_vocal_analysis.py --youtube "https://youtu.be/c5t6-KPZygg"
=============================================================
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import librosa
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter


# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────
SAMPLE_RATE     = 22050   # Hz — librosa lo resampeará
FRAME_LENGTH    = 2048    # samples por frame
HOP_LENGTH      = 512     # step entre frames (~23ms a 22050Hz)
F_MIN           = librosa.note_to_hz('A1')   # ~55 Hz (grave extremo)
F_MAX           = librosa.note_to_hz('C7')   # ~2093 Hz (sobreagudo)
OUTPUT_DIR      = Path('vocal_analysis/output')


# ─────────────────────────────────────────────────────────────
# HELPERS MUSICALES
# ─────────────────────────────────────────────────────────────

def hz_to_note(hz: float):
    """Convierte frecuencia en Hz a nombre de nota MIDI."""
    if hz is None or np.isnan(hz) or hz <= 0:
        return None, None
    midi = librosa.hz_to_midi(hz)
    note = librosa.midi_to_note(int(round(midi)))
    return note, round(float(hz), 2)


def classify_register(hz: float) -> str:
    """Clasifica la frecuencia en registro vocal."""
    if hz is None or np.isnan(hz) or hz <= 0:
        return "silencio"
    if hz < 165:    return "grave"          # < E3
    elif hz < 330:  return "medio-grave"    # E3 – E4
    elif hz < 660:  return "medio-agudo"    # E4 – E5
    elif hz < 1047: return "agudo"          # E5 – C6
    else:           return "sobreagudo"     # > C6


# ─────────────────────────────────────────────────────────────
# GENERADOR DE AUDIO SINTÉTICO (modo demo)
# ─────────────────────────────────────────────────────────────

def generate_synthetic_audio(output_path: str, duration: int = 90) -> str:
    """
    Genera audio sintético que simula el rango vocal de S.O.S (Bogdan Shuvalov).
    Incluye: vibrato, armónicos, envolvente ADSR, cambios de registro.
    """
    print("[DEMO] Generando audio sintético con rango vocal A2–C6...")
    sr = 44100
    t_full = np.linspace(0, duration, sr * duration, endpoint=False)

    def note_to_freq(name: str) -> float:
        notes = {'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,
                 'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11}
        n, oct_ = name[:-1], int(name[-1])
        semi = (oct_ - 4) * 12 + notes[n] - 9
        return 440.0 * (2 ** (semi / 12))

    def make_vibrato(freq, t, rate=5.5, depth=0.015):
        vib = 1 + depth * np.sin(2 * np.pi * rate * t)
        phase = 2 * np.pi * freq * np.cumsum(vib) / sr
        return np.sin(phase)

    # Secuencia basada en S.O.S: (nota, t_inicio, t_fin, intensidad)
    sequence = [
        ('A3',0,2.5,0.5),   ('B3',2.5,4.5,0.55), ('C4',4.5,6.5,0.6),
        ('D4',6.5,8.5,0.65),('E4',8.5,10.5,0.6),  ('F4',10.5,12.5,0.65),
        ('G4',12.5,14.5,0.7),('A4',14.5,16.5,0.72),('G4',16.5,18,0.68),
        ('F4',18,19.5,0.65), ('E4',19.5,21,0.62),  ('B4',21,23,0.75),
        ('C5',23,25,0.8),    ('D5',25,27,0.82),     ('E5',27,29.5,0.85),
        ('F5',29.5,32,0.88), ('G5',32,35,0.92),     ('A5',35,38,0.95),
        ('G5',38,40,0.90),   ('F5',40,42,0.87),     ('E5',42,44,0.85),
        ('D3',44,46.5,0.70), ('C3',46.5,48.5,0.65), ('B2',48.5,50.5,0.60),
        ('A2',50.5,53,0.55), ('E4',53,55,0.65),     ('G4',55,57,0.70),
        ('B4',57,59.5,0.78), ('C6',59.5,62,0.98),   ('B5',62,64.5,0.95),
        ('A5',64.5,67,0.92), ('C6',67,70,1.0),      ('G5',70,72.5,0.88),
        ('E5',72.5,74.5,0.82),('C5',74.5,76.5,0.78),('A4',76.5,78.5,0.72),
        ('G4',78.5,80,0.68), ('E4',80,82,0.60),     ('C4',82,84.5,0.55),
        ('A3',84.5,87,0.50), ('G3',87,90,0.45),
    ]

    signal = np.zeros(sr * duration, dtype=np.float64)

    for note_name, t_s, t_e, intensity in sequence:
        freq = note_to_freq(note_name)
        ns, ne = int(t_s * sr), int(t_e * sr)
        seg_t  = t_full[ns:ne]
        n_seg  = ne - ns

        # ADSR
        att = int(0.05 * n_seg); dec = int(0.1 * n_seg); rel = int(0.15 * n_seg)
        env = np.ones(n_seg)
        env[:att]      = np.linspace(0, 1, att)
        env[att:att+dec] = np.linspace(1, 0.85, dec)
        env[-rel:]     = np.linspace(0.85, 0, rel)

        # Armónicos
        wave  = make_vibrato(freq,   seg_t)
        wave += 0.45 * make_vibrato(2*freq, seg_t, rate=5.2)
        wave += 0.25 * make_vibrato(3*freq, seg_t, rate=5.8)
        wave += 0.15 * make_vibrato(4*freq, seg_t, rate=5.5)
        wave += 0.08 * make_vibrato(5*freq, seg_t, rate=6.0)
        wave  = wave / (np.max(np.abs(wave)) + 1e-10)
        signal[ns:ne] += wave * env * intensity

    signal = signal / (np.max(np.abs(signal)) + 1e-10) * 0.85
    wavfile.write(output_path, sr, (signal * 32767).astype(np.int16))
    print(f"[DEMO] Audio sintético guardado: {output_path}")
    return output_path


# ─────────────────────────────────────────────────────────────
# SEPARACIÓN VOCAL CON DEMUCS (opcional)
# ─────────────────────────────────────────────────────────────

def separate_vocals_demucs(audio_path: str) -> str:
    """
    Separa la pista vocal usando Demucs (htdemucs).
    Retorna la ruta del archivo de voz aislada.

    Requiere: pip install demucs
    """
    try:
        import subprocess
        out_dir = OUTPUT_DIR / "demucs"
        cmd = [
            sys.executable, "-m", "demucs",
            "--two-stems", "vocals",
            "-o", str(out_dir),
            audio_path
        ]
        print("[DEMUCS] Separando voz del audio (puede tardar ~2-5 min)...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[DEMUCS] Error: {result.stderr}")
            return audio_path

        # Buscar vocals.wav generado
        vocals_path = next(out_dir.rglob("vocals.wav"), None)
        if vocals_path:
            print(f"[DEMUCS] Pista vocal guardada: {vocals_path}")
            return str(vocals_path)
    except Exception as e:
        print(f"[DEMUCS] No disponible ({e}). Usando audio original.")
    return audio_path


# ─────────────────────────────────────────────────────────────
# ANÁLISIS PRINCIPAL (pYIN + RMS)
# ─────────────────────────────────────────────────────────────

def analyze_audio(audio_path: str, realtime_display: bool = True) -> list:
    """
    Analiza el audio frame a frame con el algoritmo pYIN.

    Retorna lista de dicts con:
      time, note, hz, intensity, register, is_voiced
    """
    print(f"\n[ANÁLISIS] Cargando audio: {audio_path}")
    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE)
    duration = len(y) / sr
    print(f"[ANÁLISIS] Duración: {duration:.1f}s | Sample rate: {sr} Hz")

    print("[ANÁLISIS] Ejecutando pYIN (estimación de pitch)...")
    t0 = time.time()
    f0_vals, f0_voiced, _ = librosa.pyin(
        y,
        fmin=F_MIN,
        fmax=F_MAX,
        sr=sr,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH
    )
    f0_times = librosa.frames_to_time(
        np.arange(len(f0_vals)), sr=sr, hop_length=HOP_LENGTH
    )
    rms = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
    print(f"[ANÁLISIS] pYIN completado en {time.time()-t0:.1f}s | Frames: {len(f0_vals)}")

    results = []
    if realtime_display:
        print(f"\n{'Tiempo':>7} | {'Nota':>6} | {'Hz':>8} | {'Intensidad':>12} | Registro")
        print("─" * 62)

    for i, (t, f0, voiced) in enumerate(zip(f0_times, f0_vals, f0_voiced)):
        rms_idx   = min(int(t * sr / HOP_LENGTH), len(rms) - 1)
        intensity = float(rms[rms_idx]) * 100

        if voiced and f0 is not None and not np.isnan(f0):
            note_name, hz = hz_to_note(f0)
            register       = classify_register(f0)
            is_voiced      = True
        else:
            note_name, hz = None, None
            register       = "silencio"
            is_voiced      = False

        frame = {
            "time":      round(float(t), 3),
            "note":      note_name,
            "hz":        hz,
            "intensity": round(intensity, 4),
            "register":  register,
            "is_voiced": is_voiced
        }
        results.append(frame)

        # Mostrar en consola (cada 3 frames para no saturar)
        if realtime_display and is_voiced and i % 3 == 0:
            print(f"{t:7.2f}s | {str(note_name):>6} | {hz:8.2f} | {intensity:12.6f} | {register}")

    voiced_count = sum(1 for r in results if r['is_voiced'])
    print(f"\n[ANÁLISIS] Frames totales: {len(results)} | Con voz: {voiced_count}")
    return results


# ─────────────────────────────────────────────────────────────
# CÁLCULO DE MÉTRICAS
# ─────────────────────────────────────────────────────────────

def compute_metrics(frames: list) -> dict:
    """Calcula todas las métricas musicales a partir de los frames."""
    voiced = [r for r in frames if r['is_voiced'] and r['hz']]
    if not voiced:
        print("[MÉTRICAS] Sin frames con voz detectada.")
        return {}

    hz_vals    = [r['hz'] for r in voiced]
    notes      = [r['note'] for r in voiced]
    registers  = [r['register'] for r in voiced]
    intensities = [r['intensity'] for r in voiced]

    note_counts     = Counter(notes)
    register_counts = Counter(registers)

    lowest_note  = min(voiced, key=lambda x: x['hz'])
    highest_note = max(voiced, key=lambda x: x['hz'])
    avg_hz       = float(np.mean(hz_vals))
    vocal_range_st = 12 * np.log2(highest_note['hz'] / lowest_note['hz'])

    # Cambios de nota
    note_changes = sum(
        1 for a, b in zip(notes, notes[1:]) if a != b
    )

    # Momentos de alta intensidad (percentil 95)
    thresh = np.percentile(intensities, 95)
    highlights, last_t = [], -5.0
    for r in sorted(voiced, key=lambda x: x['time']):
        if r['intensity'] >= thresh and r['time'] - last_t > 2.0:
            highlights.append(r)
            last_t = r['time']

    metrics = {
        "most_common_note":       note_counts.most_common(1)[0][0],
        "lowest_note":            {"note": lowest_note['note'],  "hz": lowest_note['hz'],  "time": lowest_note['time']},
        "highest_note":           {"note": highest_note['note'], "hz": highest_note['hz'], "time": highest_note['time']},
        "avg_hz":                 round(avg_hz, 2),
        "vocal_range_semitones":  round(vocal_range_st, 1),
        "vocal_range_octaves":    round(vocal_range_st / 12, 2),
        "note_changes":           note_changes,
        "total_voiced_frames":    len(voiced),
        "total_frames":           len(frames),
        "register_distribution":  dict(register_counts),
        "dominant_register":      register_counts.most_common(1)[0][0],
        "top_notes":              note_counts.most_common(15),
        "max_intensity":          {
            "value": round(max(intensities), 4),
            "time":  max(voiced, key=lambda x: x['intensity'])['time'],
            "note":  max(voiced, key=lambda x: x['intensity'])['note']
        },
        "highlight_moments": [
            {"time": h['time'], "note": h['note'],
             "hz": h['hz'], "intensity": round(h['intensity'], 4)}
            for h in highlights[:8]
        ],
    }

    print("\n═══ MÉTRICAS FINALES ═══════════════════════════════")
    print(f"  Nota más frecuente   : {metrics['most_common_note']}")
    print(f"  Nota más grave       : {metrics['lowest_note']['note']} ({metrics['lowest_note']['hz']} Hz) @ {metrics['lowest_note']['time']}s")
    print(f"  Nota más aguda       : {metrics['highest_note']['note']} ({metrics['highest_note']['hz']} Hz) @ {metrics['highest_note']['time']}s")
    print(f"  Frecuencia promedio  : {metrics['avg_hz']} Hz")
    print(f"  Rango vocal          : {metrics['vocal_range_semitones']} semitonos = {metrics['vocal_range_octaves']} octavas")
    print(f"  Cambios de nota      : {metrics['note_changes']}")
    print(f"  Registro dominante   : {metrics['dominant_register']}")
    print(f"  Distribución         : {metrics['register_distribution']}")
    print("═══════════════════════════════════════════════════")
    return metrics


# ─────────────────────────────────────────────────────────────
# ENTRADA PRINCIPAL
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Pipeline de Análisis Vocal en Tiempo Real'
    )
    parser.add_argument('--audio',    help='Ruta a archivo WAV/MP3')
    parser.add_argument('--youtube',  help='URL de YouTube para descargar')
    parser.add_argument('--demo',     action='store_true', help='Usar audio sintético')
    parser.add_argument('--no-demucs',action='store_true', help='Omitir separación vocal')
    parser.add_argument('--out',      default='vocal_analysis/output', help='Directorio de salida')
    args = parser.parse_args()

    global OUTPUT_DIR
    OUTPUT_DIR = Path(args.out)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. OBTENER AUDIO
    audio_path = None

    if args.demo or (not args.audio and not args.youtube):
        synthetic = str(OUTPUT_DIR / 'bogdan_sos_synthetic.wav')
        audio_path = generate_synthetic_audio(synthetic, duration=90)

    elif args.youtube:
        try:
            import yt_dlp
            opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(OUTPUT_DIR / 'downloaded.%(ext)s'),
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
                'no_check_certificates': True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([args.youtube])
            audio_path = str(next(OUTPUT_DIR.glob('downloaded.wav')))
        except Exception as e:
            print(f"[ERROR] Descarga fallida: {e}")
            sys.exit(1)

    else:
        audio_path = args.audio
        if not os.path.exists(audio_path):
            print(f"[ERROR] Archivo no encontrado: {audio_path}")
            sys.exit(1)

    # 2. SEPARAR VOZ (Demucs)
    if not args.no_demucs:
        audio_path = separate_vocals_demucs(audio_path)

    # 3. ANALIZAR
    frames = analyze_audio(audio_path, realtime_display=True)

    # 4. GUARDAR FRAMES
    frames_path = OUTPUT_DIR / 'frame_analysis.json'
    with open(frames_path, 'w') as f:
        json.dump(frames, f, indent=2)
    print(f"\n[GUARDADO] Frames → {frames_path}")

    # 5. MÉTRICAS
    metrics = compute_metrics(frames)
    metrics_path = OUTPUT_DIR / 'metrics.json'
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"[GUARDADO] Métricas → {metrics_path}")

    # 6. ABRIR DASHBOARD
    dashboard = OUTPUT_DIR / 'dashboard.html'
    if dashboard.exists():
        print(f"\n[LISTO] Dashboard: {dashboard.resolve()}")
        print("         Abrir en navegador para ver el reporte completo.")
    else:
        print("\n[AVISO] dashboard.html no encontrado. Ejecutar generador por separado.")


if __name__ == '__main__':
    main()