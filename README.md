# Toyota 2KD-FTV Engine Simulator — Streamlit Cloud V3 (2WD / 4WD)

**Rilis:** 16 November 2026. **Model:** termodinamika 0D satu zona dengan integrator Heun (RK2), tanpa machine learning. **Hosting:** Streamlit Community Cloud melalui GitHub, tidak memerlukan server sendiri.

## Profil mesin

| Parameter | 2WD awal | 4WD awal (High Version) |
| --- | ---: | ---: |
| Rated power | 65 kW @ 3.800 rpm | 75 kW @ 3.600 rpm |
| Max torque | 192 Nm @ 1.200–3.000 rpm | 260 Nm @ 1.600–2.400 rpm |
| Bore / stroke | 92 / 93,8 mm | 92 / 93,8 mm |
| Displacement | 2.494 cm³ | 2.494 cm³ |
| Compression ratio | 18,5:1 | 18,5:1 |
| Max turbo PR *model* (editable) | **1,65 asumsi** | **1,80 asumsi** |

**Sumber parameter rating dan geometri:** Toyota, *New Features – 2KD-FTV Engine*, halaman 19:
https://toyotamanuals.gitlab.io/pz471-zx006-ca/htmlweb/ncf/ncf210e/m_nf_0018.pdf

**PENTING:** bentuk envelope torsi antar-anchor, nilai torsi 1.000 rpm, dan ekstrapolasi torsi 4WD antara 3.600–3.800 rpm merupakan **asumsi**, bukan data pabrikan. Turbo PR maksimal, injeksi pilot, temperatur, LHV, pembakaran dan kerugian mesin adalah pendekatan ilustratif yang memerlukan kalibrasi. Varian 2WD/4WD di sini merepresentasikan konfigurasi/rating mesin menurut dokumen Toyota; bukan efek mekanis drivetrain 2WD/4WD.

## Fitur V3

- **Engine Variant** pada sidebar, beralih langsung antara profil **2WD** dan **4WD**.
- Mengubah varian otomatis mengubah titik rating, plateau torque, BMEP target, turbo PR default, label grafik, flag di atas rated RPM, dan metadata ekspor.
- Grafik overlay envelope nominal per varian plus perbandingan 2WD dan 4WD (terpisah dari kurva simulasi aktual).
- **Empat mode V2 dipertahankan**: `fixed_torque`, `fixed_injection`, `fixed_mass_cycle`, `fixed_fuel_flow`.
- Simulasi B0–B100 dan PPO-M/Dex/B50 *ilustratif*, tabel properti bahan bakar, tekanan silinder, temperatur gas, CA50, BTE/BSFC model, indeks NOx/smoke relatif, riwayat per sesi dan ekspor CSV.
- Dataset eksperimen PNM B0/B50 untuk 1.250–2.250 rpm ditampilkan sebagai **referensi deskriptif**. Varian mesin yang diuji belum dapat dipastikan; karena itu PNM **tidak otomatis berlaku** bagi 2WD atau 4WD. Kondisi beban pun belum terverifikasi.
- Kolom **fuel consumption PNM tetap dikecualikan**, sehingga angka konsumsi, BSFC dan BTE dalam dashboard berasal dari model, bukan data tersebut.

## Struktur berkas

```text
streamlit_app.py              dashboard Cloud (entry point)
physics.py                    engine model 0D + EngineProfile 2wd/4wd
requirements.txt              dependensi
.streamlit/config.toml        konfigurasi tema
.gitignore                    pengecualian file sementara
data/pnm_b0_b50.csv           data PNM tanpa fuel consumption
tests/test_physics.py         tujuh uji dasar V2
tests/test_modes_v2.py        lima uji mode V2
tests/test_variants_v3.py     tujuh uji profil/fitur V3
tests/test_pnm_fallback.py    pengujian CSV cadangan
tests/smoke_ui_stub.py       uji smoke UI berbasis objek pengganti, tanpa instalasi Streamlit
PANDUAN_UPDATE_V3.md          cara update GitHub → Streamlit
PANDUAN_DEPLOY_CLOUD.md       cara deploy baru
verifikasi_paket.py           cek paket/solver lokal
```

## Pembaruan cepat aplikasi online

1. Cadangkan `physics.py` dan `streamlit_app.py` versi sebelumnya dari repository GitHub Anda.
2. Ganti **kedua berkas** tersebut dengan versi V3 di root repository GitHub, jangan hanya salah satunya.
3. Disarankan unggah pula `tests/test_variants_v3.py`, `README.md`, dan `PANDUAN_UPDATE_V3.md`.
4. **Commit changes** pada branch yang digunakan Streamlit Cloud (biasanya `main`).
5. Buka aplikasi Streamlit yang sudah online dan pilih `Engine Variant` di sidebar. Jika masih menampilkan V2, gunakan `Manage app → Reboot app` dan pastikan commit telah selesai.

Tidak perlu aplikasi baru, token, Docker, PHP, atau server institusi.

## Tes sebelum diunggah (opsional)

```bash
python verifikasi_paket.py
python -m unittest discover -s tests -v
```

Instal dependensi Streamlit jika ingin menguji UI lokal:

```bash
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Batasan ilmiah

Hasil mode target torsi mengikuti envelope yang **dimasukkan** dari rating pabrikan. Mencapai tepat 65 kW @ 3.800 atau 75 kW @ 3.600 pada mode ini bukan pembuktian prediksi fisika independen. Model fisika tidak memiliki seluruh peta ECU, rail injection, turbocharger, EGR, intercooler dan aftertreatment yang divalidasi pada kedua varian. Hasil tidak untuk sertifikasi emisi, diagnosis keselamatan, atau perancangan injeksi nyata. Grafik NOx/smoke hanya indeks relatif; bukan data terukur dalam ppm/%HSU.

**Sumber studi sifat bahan bakar** merupakan penelitian lain pada tipe 2KD-FTV dan harus diperlakukan sebagai data referensi. Nilai kalor ASTM D240 dan cetane index masih memerlukan pemeriksaan HHV/LHV dan cetane number/DCN.
