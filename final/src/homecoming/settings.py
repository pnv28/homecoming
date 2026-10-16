from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'runtime'
MAP_ROOT = ROOT / 'precomputed/maps'
STEP_4 = ROOT / 'precomputed/outputs/step_4/current'
STEP_3 = ROOT / 'precomputed/outputs/step_3/current'
DEEPSEEK_BASE = 'https://api.deepseek.com'
MODEL = 'deepseek-flash'
MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 12

for directory in (RUNTIME, RUNTIME / 'route_cache', RUNTIME / 'map_cache'):
    directory.mkdir(parents=True, exist_ok=True)
