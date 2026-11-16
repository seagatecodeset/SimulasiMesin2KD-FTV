"""Pemeriksaan cepat paket Streamlit Cloud tanpa harus menginstal Streamlit."""
from pathlib import Path
import ast
import csv

ROOT = Path(__file__).resolve().parent
NEEDED = [
    'streamlit_app.py', 'physics.py', 'requirements.txt',
    'data/pnm_b0_b50.csv', '.streamlit/config.toml',
    'tests/test_physics.py', 'tests/test_modes_v2.py', 'tests/test_variants_v3.py'
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
from physics import Settings, run_sweep, get_engine_profile, full_load_torque
for variant, rated_kw, rated_rpm in [('2wd',65,3800), ('4wd',75,3600)]:
    prof=get_engine_profile(variant)
    assert prof.rated_power_kw == rated_kw
    assert prof.rated_rpm == rated_rpm
    result=run_sweep(Settings(variant=variant, rpm=rated_rpm, load_pct=100))
    assert len(result['points']) >= 10
    assert result['focus']['scenario']['energy_residual_pct'] < 1.0
    assert abs(result['focus']['reference']['power_kw']-rated_kw)<0.4
    assert not any(p['pnm_variant_verified'] for p in result['points'])
print('OK V3: file Cloud lengkap; PNM tanpa fuel consumption; kedua profil 2WD/4WD diuji.')
