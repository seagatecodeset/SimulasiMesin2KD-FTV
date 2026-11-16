# Panduan memperbarui Streamlit Cloud dari V2 ke V3

### A. File yang wajib diganti

**`physics.py`** dan **`streamlit_app.py`** harus diganti **bersamaan**. Keduanya menggunakan struktur `Settings.variant` dan profil mesin baru, sehingga mencampur V2/V3 dapat menimbulkan error.

### B. Langkah pada GitHub

1. Ekstrak ZIP V3.
2. Buka repository GitHub tempat aplikasi Streamlit berada (misalnya `simulasimesin2kd-ftv`).
3. Untuk file `physics.py` dan `streamlit_app.py` di root repo, pilih file → ikon pensil (*Edit*) → tempel isi file versi V3 → **Commit changes**. Alternatif: unggah kedua file via **Add file → Upload files** dan lakukan commit, lalu pastikan GitHub benar-benar mengganti file lama, bukan membuat duplikat.
4. Unggah `tests/test_variants_v3.py` ke folder `tests` jika ingin audit otomatis; perbarui README dan catatan metode jika diperlukan.
5. **Jangan ubah lokasi `data/pnm_b0_b50.csv`.** Fallback tetap tersedia bila CSV tidak ditemukan.
6. Buka https://share.streamlit.io/ → pilih aplikasi yang sama. Tunggu GitHub sync atau gunakan **Manage app → Reboot app**.
7. Pastikan pada sidebar muncul **V3**, pilihan **Engine Variant: 2WD/4WD**, dan judul hero sesuai pilihan.

### C. Skenario pengujian penerimaan

| Skenario | Apa yang harus terlihat |
| --- | --- |
| 2WD, torsi target, 100%, 3.800 rpm, B0 | ≈ 65 kW; plateau 192 Nm @ 1.200–3.000 rpm |
| 4WD, torsi target, 100%, 3.600 rpm, B0 | ≈ 75 kW; plateau 260 Nm @ 1.600–2.400 rpm |
| 4WD, torsi target, 100%, 3.800 rpm | Diberi peringatan **di atas RPM rated**; hasil bersifat asumsi |
| Kedua profil, fixed_mass_cycle 20 mg/siklus/silinder | mg/siklus konstan jika tidak kena batas udara |
| Kedua profil, fixed_fuel_flow 5 kg/jam | laju kg/jam konstan jika tidak kena batas udara |
| Kunjungi tab PNM | Peringatan: **varian PNM belum dikonfirmasi** |
| Download CSV | Kolom `variant`, `engine_profile`, `above_rated_rpm`, `pnm_variant_verified`, tanpa data fuel consumption PNM |

Angka pada dua baris pertama adalah hasil **mode target** yang menggunakan rating pabrikan sebagai anchor, bukan hasil validasi independen.

### D. Jika terjadi error

- `ImportError: get_engine_profile`: `physics.py` masih V2; ganti dengan V3.
- `unexpected keyword argument 'variant'`: `physics.py` masih V2, sedangkan `streamlit_app.py` sudah V3.
- Tampilan masih V2: periksa branch dan commit di GitHub, lalu lakukan reboot aplikasi.
- Data PNM tidak muncul: periksa `data/pnm_b0_b50.csv`; aplikasi tetap punya fallback bawaan.
- Performa simulasi melenceng: periksa apakah varian, boost PR, beban, dan mode injeksi sudah sesuai. Jangan mengubah koefisien korelasi tanpa data pembanding.

### E. Catatan

Pada setiap varian berlaku geometri yang sama menurut Toyota; perbedaan yang dimodelkan saat ini adalah rating/torsi nominal dan asumsi boost. Perbedaan ECU serta sistem hardware 4WD belum sepenuhnya dimodelkan. Jika tim punya peta rail pressure, boost/MAF, atau dynotest 4WD, data itu dapat digunakan pada kalibrasi tahap berikutnya.
