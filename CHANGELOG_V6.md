# Perubahan V5 → V6

| Fitur | V5 | V6 |
|---|---|---|
| Mesin | Toyota 2KD 2WD/4WD | Toyota 2KD 2WD/4WD + **Kubota RD85** |
| Campuran | B0+B100, B0+PPO | B0+B100, B0+PPO, **B0+PPO+B50** |
| Slider tiga komponen | Tidak ada | **Tiga slider selalu berjumlah 100%** dengan proporsi penyeimbangan |
| Properti B50 premix | Tidak tersedia | Editor mandiri + nilai awal dari referensi HTML RD85 |
| Mode pengendalian | Torsi target | Tetap torsi target |
| Data PNM | Tidak dipakai | Tetap tidak dipakai |
| Model emisi | Indeks relatif | Tetap indeks relatif (belum validasi) |
| Hasil ekspor | CSV | CSV plus komposisi ternary dan identitas engine |

## Verifikasi

- Uji matematika, fraksi 100%, P0/B0, nilai ekstrem dan manual properties.
- Uji titik operasi beberapa RPM pada RD85.
- Uji pembuatan 6 tab dengan stub Streamlit untuk kedua jenis mesin.
- Belum dilakukan deployment ke Streamlit Cloud di akun pengguna.
