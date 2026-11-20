"""Kunci komposisi 3 slider: bilangan bulat 0-100, jumlah selalu 100.

Pada setiap perubahan satu slider, nilai slider yang diubah dipertahankan.
Dua komponen lainnya disesuaikan dengan mempertahankan rasio lamanya.
Fungsi ini tidak bergantung pada Streamlit, sehingga dapat diuji otomatis.
"""
from __future__ import annotations

COMPONENTS = ('b0', 'ppo', 'b50')


def rebalance_blend(values: dict[str, int], changed: str) -> dict[str, int]:
    if changed not in COMPONENTS:
        raise ValueError(f'Komponen tidak dikenal: {changed}')
    if any(k not in values for k in COMPONENTS):
        raise ValueError('Data harus berisi b0, ppo, b50')
    if any(not isinstance(values[k], int) or not 0 <= values[k] <= 100 for k in COMPONENTS):
        raise ValueError('Fraksi harus bilangan bulat 0–100')
    remaining = 100 - values[changed]
    others = [k for k in COMPONENTS if k != changed]
    old_total = values[others[0]] + values[others[1]]
    if old_total:
        first = round(remaining * values[others[0]] / old_total)
    else:
        # Saat keduanya 0, alokasikan ke komponen pertama (diterangkan di UI).
        first = remaining
    return {changed: values[changed], others[0]: first, others[1]: remaining - first}
