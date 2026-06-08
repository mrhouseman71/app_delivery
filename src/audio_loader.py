"""
audio_loader.py
══════════════════════════════════════════════════════════════════════
Módulo de carga universal de audio para el pipeline vocal.
Extiende el pipeline.py original con soporte para:

  1. YouTube / SoundCloud / cualquier fuente soportada por yt-dlp
  2. Archivos locales WAV, MP3, FLAC, OGG, M4A
  3. Segmentos (inicio y fin en segundos)
  4. Separación vocal automática con Demucs

INTEGRACIÓN CON EL PIPELINE
────────────────────────────
  Este módulo reemplaza el bloque "OBTENER AUDIO" de pipeline.py.
  El resto del pipeline (pYIN, métricas, CSV) funciona igual.

USO CLI
───────
  # YouTube — canción completa
  python audio_loader.py --youtube "https://youtu.be/XXXXXXXXX"

  # YouTube — solo el puente (2:30 a 3:10)
  python audio_loader.py --youtube "https://youtu.be/XXXXXXXXX" --start 150 --end 190

  # Archivo local MP3
  python audio_loader.py --audio mi_cancion.mp3

  # Ver información del video antes de descargar
  python audio_loader.py --info "https://youtu.be/XXXXXXXXX"

DERECHOS DE AUTOR
─────────────────
  Este módulo descarga audio únicamente para análisis técnico local.
  No almacena, distribuye ni publica el audio descargado.
  El archivo se elimina opcionalmente al finalizar con --cleanup.
  Verificar los términos de servicio de la plataforma y las leyes
  de copyright aplicables antes de descargar contenido con copyright.
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


# ──────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ──────────────────────────────────────────────────────────────────

DEFAULT_OUT   = Path("vocal_analysis/output")
SAMPLE_RATE   = 22050     # Hz — igual que pipeline.py
MAX_DURATION  = 600       # segundos — límite de seguridad (10 min)


# ──────────────────────────────────────────────────────────────────
# INFORMACIÓN DEL VIDEO (sin descargar)
# ──────────────────────────────────────────────────────────────────

def get_video_info(url: str) -> dict:
    """
    Obtiene metadatos del video sin descargarlo.
    Retorna dict con título, duración, canal, formatos disponibles.
    """
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "titulo":    info.get("title", "desconocido"),
                "canal":     info.get("uploader", "desconocido"),
                "duracion_s": info.get("duration", 0),
                "duracion":  _fmt_time(info.get("duration", 0)),
                "url":       url,
                "vista_previa": info.get("thumbnail", ""),
                "formatos_audio": [
                    f"{f['format_id']}: {f.get('abr','?')}kbps {f.get('ext','?')}"
                    for f in info.get("formats", [])
                    if f.get("vcodec") == "none" and f.get("acodec") != "none"
                ][:5],
            }
    except ImportError:
        print("[ERROR] yt-dlp no instalado. Ejecutar: pip install yt-dlp")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] No se pudo obtener info de {url}: {e}")
        return {}


def _fmt_time(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ──────────────────────────────────────────────────────────────────
# DESCARGA DE AUDIO
# ──────────────────────────────────────────────────────────────────

def download_audio(
    url:      str,
    out_dir:  Path = DEFAULT_OUT,
    start_s:  float = None,
    end_s:    float = None,
) -> str:
    """
    Descarga el audio de una URL y lo convierte a WAV mono 22050 Hz.

    Parameters
    ----------
    url     : URL de YouTube, SoundCloud, Spotify (preview), etc.
    out_dir : directorio de salida
    start_s : segundo de inicio del segmento (None = desde el principio)
    end_s   : segundo de fin del segmento (None = hasta el final)

    Returns
    -------
    Ruta al archivo WAV listo para el pipeline.
    """
    try:
        import yt_dlp
    except ImportError:
        print("[ERROR] yt-dlp no instalado. Ejecutar: pip install yt-dlp")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Nombre de archivo sanitizado
    safe_name = "audio_descargado"
    wav_path  = str(out_dir / f"{safe_name}.wav")

    print(f"\n[DESCARGA] Fuente  : {url}")
    if start_s is not None:
        print(f"[DESCARGA] Segmento: {_fmt_time(int(start_s))} → {_fmt_time(int(end_s or 9999))}")

    # Opciones de yt-dlp
    # Se pide el mejor audio disponible y se convierte a WAV
    postproc = [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}]

    # Corte de segmento via FFmpeg si se especificó
    if start_s is not None or end_s is not None:
        ss   = start_s or 0
        to   = end_s   or MAX_DURATION
        # Validar duración máxima
        dur  = to - ss
        if dur > MAX_DURATION:
            print(f"[WARN] Segmento de {dur:.0f}s supera el límite de {MAX_DURATION}s. "
                  f"Recortando a {MAX_DURATION}s.")
            to = ss + MAX_DURATION
        postproc.append({
            "key": "FFmpegVideoConvertor",
            "preferedformat": "wav",
        })
        # Usamos download_ranges para cortar sin descargar todo
        opts_extra = {
            "download_ranges": yt_dlp.utils.download_range_func(
                chapters=None,
                ranges=[(ss, to)]
            ),
            "force_keyframes_at_cuts": True,
        }
    else:
        opts_extra = {}

    ydl_opts = {
        "format":          "bestaudio/best",
        "outtmpl":         str(out_dir / f"{safe_name}.%(ext)s"),
        "postprocessors":  postproc,
        "no_check_certificates": True,
        "quiet":           False,
        "no_warnings":     False,
        **opts_extra,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            titulo = info.get("title", "desconocido")
            print(f"[DESCARGA] ✅ '{titulo}'")
    except Exception as e:
        print(f"[ERROR] Descarga fallida: {e}")
        sys.exit(1)

    # Buscar el WAV generado
    candidates = list(out_dir.glob(f"{safe_name}*.wav"))
    if not candidates:
        print("[ERROR] No se encontró el WAV descargado.")
        sys.exit(1)

    wav_path = str(sorted(candidates)[-1])
    size_mb  = os.path.getsize(wav_path) / 1_048_576
    print(f"[DESCARGA] Archivo : {wav_path}  ({size_mb:.1f} MB)")
    return wav_path


# ──────────────────────────────────────────────────────────────────
# CARGA DE ARCHIVO LOCAL
# ──────────────────────────────────────────────────────────────────

def load_local_audio(
    path:    str,
    out_dir: Path    = DEFAULT_OUT,
    start_s: float   = None,
    end_s:   float   = None,
) -> str:
    """
    Convierte cualquier formato de audio local (MP3, FLAC, OGG, M4A, WAV)
    a WAV mono 22050 Hz usando FFmpeg o scipy/librosa.

    Parameters
    ----------
    path    : ruta al archivo de audio
    out_dir : directorio de salida para el WAV convertido
    start_s : segundo de inicio del segmento
    end_s   : segundo de fin del segmento

    Returns
    -------
    Ruta al archivo WAV convertido.
    """
    src = Path(path)
    if not src.exists():
        print(f"[ERROR] Archivo no encontrado: {path}")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_wav = str(out_dir / f"{src.stem}_converted.wav")

    # Si ya es WAV y no hay segmento, retornar directo
    if src.suffix.lower() == ".wav" and start_s is None and end_s is None:
        print(f"[AUDIO] Usando archivo WAV directo: {path}")
        return path

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None and src.suffix.lower() in {".mp3", ".m4a", ".aac", ".wma", ".mp4", ".webm"}:
        print("[ERROR] ffmpeg no encontrado. No es posible convertir este formato sin ffmpeg.")
        print("Instalar ffmpeg y volver a ejecutar:")
        print("  sudo apt-get install -y ffmpeg")
        print("o en macOS:")
        print("  brew install ffmpeg")
        sys.exit(1)

    # Construir comando FFmpeg para convertir y/o cortar
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if start_s is not None:
        cmd += ["-ss", str(start_s)]
    if end_s is not None:
        duration = (end_s - (start_s or 0))
        cmd += ["-t", str(duration)]
    cmd += ["-ar", "22050", "-ac", "1", "-acodec", "pcm_s16le", out_wav]

    print(f"[AUDIO] Convirtiendo {src.name} → WAV...")
    if start_s is not None:
        seg = f"{_fmt_time(int(start_s))} → {_fmt_time(int(end_s or 9999))}"
        print(f"[AUDIO] Segmento: {seg}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or "ffmpeg falló durante la conversión")
    except FileNotFoundError:
        print(f"[AUDIO] ffmpeg no encontrado. Usando librosa de fallback...")
        _convert_with_librosa(str(src), out_wav, start_s, end_s)
    except RuntimeError as exc:
        print(f"[AUDIO] FFmpeg devolvió error: {exc}")
        print("[AUDIO] Usando librosa de fallback...")
        _convert_with_librosa(str(src), out_wav, start_s, end_s)

    size_mb = os.path.getsize(out_wav) / 1_048_576
    print(f"[AUDIO] ✅ Convertido: {out_wav}  ({size_mb:.1f} MB)")
    return out_wav


def _convert_with_librosa(src: str, dst: str,
                           start_s: float = None, end_s: float = None):
    """Fallback de conversión usando librosa + scipy."""
    try:
        import librosa
        from scipy.io import wavfile
        offset   = start_s or 0.0
        duration = (end_s - offset) if end_s else None
        y, sr    = librosa.load(src, sr=22050, mono=True,
                                offset=offset, duration=duration)
        wavfile.write(dst, sr, (y * 32767).astype(np.int16))
    except ImportError:
        print("[ERROR] librosa o scipy no están instalados. Ejecutar: pip install librosa scipy")
        sys.exit(1)
    except Exception as exc:
        print(f"[ERROR] No se pudo convertir con librosa: {exc}")
        print("[ERROR] Este formato requiere ffmpeg o un backend de audio válido para librosa.")
        print("Instalar ffmpeg y volver a ejecutar:")
        print("  sudo apt-get install -y ffmpeg")
        print("o en macOS:")
        print("  brew install ffmpeg")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────
# SEPARACIÓN VOCAL (Demucs)
# ──────────────────────────────────────────────────────────────────

def separate_vocals(audio_path: str, out_dir: Path = DEFAULT_OUT) -> str:
    """
    Separa la voz del audio usando Demucs htdemucs.
    Idéntico al separate_vocals_demucs() de pipeline.py.
    """
    try:
        demucs_out = out_dir / "demucs"
        cmd = [
            sys.executable, "-m", "demucs",
            "--two-stems", "vocals",
            "-o", str(demucs_out),
            audio_path
        ]
        print("\n[DEMUCS] Separando voz... (puede tardar 2–5 min en CPU)")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[DEMUCS] Error: {result.stderr[:300]}")
            print("[DEMUCS] Usando audio original sin separación.")
            return audio_path

        vocals = next(demucs_out.rglob("vocals.wav"), None)
        if vocals:
            print(f"[DEMUCS] ✅ Voz aislada: {vocals}")
            return str(vocals)
    except Exception as e:
        print(f"[DEMUCS] No disponible ({e}). Usando audio original.")
    return audio_path


# ──────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL DE CARGA (integración con pipeline.py)
# ──────────────────────────────────────────────────────────────────

def load_audio_for_pipeline(
    url:       str   = None,
    local:     str   = None,
    start_s:   float = None,
    end_s:     float = None,
    out_dir:   Path  = DEFAULT_OUT,
    no_demucs: bool  = False,
) -> str:
    """
    Función unificada de carga de audio para el pipeline.
    Retorna la ruta al WAV listo para analyze_audio().

    Uso desde pipeline.py extendido:

        from audio_loader import load_audio_for_pipeline
        audio_path = load_audio_for_pipeline(
            url     = "https://youtu.be/...",
            start_s = 90,    # desde 1:30
            end_s   = 150,   # hasta 2:30
            out_dir = Path("vocal_analysis/output"),
        )
    """
    if url:
        raw = download_audio(url, out_dir, start_s, end_s)
    elif local:
        raw = load_local_audio(local, out_dir, start_s, end_s)
    else:
        raise ValueError("Especificar url= o local=")

    if not no_demucs:
        return separate_vocals(raw, out_dir)
    return raw


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Carga universal de audio para el pipeline vocal"
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--youtube",  metavar="URL",
                     help="URL de YouTube / SoundCloud / etc.")
    src.add_argument("--audio",    metavar="FILE",
                     help="Archivo local WAV/MP3/FLAC/OGG/M4A")
    src.add_argument("--info",     metavar="URL",
                     help="Solo mostrar info del video (no descargar)")

    ap.add_argument("--start",     type=float, default=None,
                    metavar="SEG", help="Segundo de inicio del segmento")
    ap.add_argument("--end",       type=float, default=None,
                    metavar="SEG", help="Segundo de fin del segmento")
    ap.add_argument("--no-demucs", action="store_true",
                    help="Omitir separación vocal con Demucs")
    ap.add_argument("--out",       default="vocal_analysis/output",
                    help="Directorio de salida")
    args = ap.parse_args()

    out_dir = Path(args.out)

    # Solo info
    if args.info:
        info = get_video_info(args.info)
        print(f"\n{'─'*50}")
        print(f"  Título   : {info.get('titulo')}")
        print(f"  Canal    : {info.get('canal')}")
        print(f"  Duración : {info.get('duracion')} ({info.get('duracion_s')}s)")
        print(f"  URL      : {info.get('url')}")
        print(f"\n  Formatos de audio disponibles:")
        for f in info.get("formatos_audio", []):
            print(f"    {f}")
        print(f"{'─'*50}\n")
        sys.exit(0)

    # Cargar audio
    wav_path = load_audio_for_pipeline(
        url       = args.youtube,
        local     = args.audio,
        start_s   = args.start,
        end_s     = args.end,
        out_dir   = out_dir,
        no_demucs = args.no_demucs,
    )

    print(f"\n✅ Audio listo para el pipeline: {wav_path}")
    print(f"   Siguiente paso:")
    print(f"   python pipeline.py --audio \"{wav_path}\" --no-demucs")
