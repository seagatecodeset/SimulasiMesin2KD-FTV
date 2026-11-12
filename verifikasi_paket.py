"""Pemeriksaan cepat paket Streamlit Cloud tanpa harus menginstal Streamlit."""
from pathlib import Path
import ast
import csv

ROOT = Path(__file__).resolve().parent
NEEDED = [
    'streamlit_app.py', 'physics.py', 'requirements.txt',
    'data/pnm_b0_b50.csv', '.streamlit/config.toml',
    'tests/test_physics.py'
]
missing = [name for name in NEEDED if not (ROOT/name).is_file()]
if missing:
    raise SystemExit('File belum lengkap: ' + ', '.join(missing))
for name in ('streamlit_app.py', 'physics.py'):
    ast.parse((ROOT/name).read_text(encoding='utf-8'), filename=name)
with (ROOT/'data/pnm_b0_b50.csv').open(newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames or []
    data = list(reader)
assert 'fuel_consumption' not in '_'.join(headers).lower(), 'Kolom PNM fuel consumption terdeteksi'
assert 'torque_nm' in headers and 'power_kw' in headers
assert len(data) == 10, f'Jumlah pengamatan PNM tidak sesuai: {len(data)}'
from physics import Settings, run_sweep
result = run_sweep(Settings())
assert len(result['points']) >= 10
assert result['focus']['scenario']['energy_residual_pct'] < 1.0
print('OK: semua file Cloud ada, sintaks benar, PNM tanpa fuel consumption, solver berhasil.')
