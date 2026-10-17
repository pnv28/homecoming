from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
# systemd reads the root-only production file into the service environment.
# Local runs load a readable .env directly. Existing environment values win.
if os.access(ROOT / '.env', os.R_OK):
    load_dotenv(ROOT / '.env', override=False, interpolate=False)
RUNTIME = ROOT / 'runtime'
MAP_ROOT = ROOT / 'precomputed/maps'
STEP_4 = ROOT / 'precomputed/outputs/step_4/current'
STEP_3 = ROOT / 'precomputed/outputs/step_3/current'
DEEPSEEK_BASE = 'https://api.deepseek.com'
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '').strip()
MODEL = os.environ.get('DEEPSEEK_MODEL', '').strip() or 'deepseek-flash'
MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 12

for directory in (RUNTIME, RUNTIME / 'route_cache', RUNTIME / 'map_cache'):
    directory.mkdir(parents=True, exist_ok=True)
