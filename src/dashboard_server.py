"""Simple dashboard server for live audio demo.

Sirve el contenido estático del repositorio y expone /download?url=<youtube_url>
para que el dashboard pueda descargar audio de YouTube y reproducirlo.
"""

import json
import os
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / 'vocal_analysis' / 'output'
DOWNLOAD_NAME = 'downloaded.wav'
COOKIES_FILE = ROOT / '.cookies.txt'


def load_cookies_from_file():
    """Load cookies from .cookies.txt if it exists."""
    if COOKIES_FILE.exists():
        return COOKIES_FILE.read_text().strip()
    return None


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/download':
            self.handle_download(parsed.query)
        else:
            return super().do_GET()

    def handle_download(self, query):
        params = urllib.parse.parse_qs(query)
        url = params.get('url', [None])[0]
        if not url:
            return self.respond_json({'success': False, 'error': 'Missing url parameter'}, status=400)
        if yt_dlp is None:
            return self.respond_json({'success': False, 'error': 'yt_dlp is not installed'}, status=500)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            outtmpl = str(OUTPUT_DIR / 'downloaded.%(ext)s')
            opts = {
                'format': 'bestaudio/best,best',
                'outtmpl': outtmpl,
                'noplaylist': True,
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'wav',
                        'preferredquality': '192',
                    }
                ],
            }
            cookie_browser = params.get('cookies_from_browser', [None])[0]
            cookie_file = params.get('cookies', [None])[0]
            
            # Priority 1: explicit browser name from URL parameter
            if cookie_browser:
                browser = cookie_browser.strip().lower()
                if browser not in yt_dlp.SUPPORTED_BROWSERS:
                    raise RuntimeError('Browser "{}" no soportado. Usa uno de: {}'.format(browser, ', '.join(sorted(yt_dlp.SUPPORTED_BROWSERS))))
                opts['cookies_from_browser'] = browser
            else:
                # Priority 2: try to use installed browser for JS challenge solving
                # Brave, Firefox and Chrome are most reliable
                opts['cookies_from_browser'] = 'brave'
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            downloaded_path = OUTPUT_DIR / DOWNLOAD_NAME
            if not downloaded_path.exists():
                raise RuntimeError('No WAV file was generated')
            response = {'success': True, 'file': f'/vocal_analysis/output/{DOWNLOAD_NAME}'}
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except Exception as exc:
            error_msg = str(exc)
            self.wfile.write(json.dumps({'success': False, 'error': error_msg}).encode('utf-8'))

    def respond_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))


def run(port: int = 8000):
    os.chdir(ROOT)
    server = ThreadingHTTPServer(('0.0.0.0', port), DashboardHandler)
    print(f'Serving dashboard and static files at http://localhost:{port}')
    print('Use /download?url=<youtube URL> to download YouTube audio as WAV')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped')


if __name__ == '__main__':
    run()
