# Diesel Engine Simulator V6 — Toyota 2KD-FTV + Kubota RD85

Aplikasi Streamlit Community Cloud; model **fisika 0D + torsi target**, tanpa Machine Learning dan tanpa dataset eksperimen PNM.

## Menu mesin

- **Toyota 2KD-FTV**: 2WD awal (65 kW @ 3800 rpm) dan 4WD awal (75 kW @ 3600 rpm). Model ada dalam `physics.py`, berasal dari V5.
- **Kubota RD85 DI**: satu silinder, bore × stroke 88 × 84 mm, kapasitas ~511 cc, daya maks 8,5 HP @ 2200 rpm, torsi maks 3,40 kgf·m @ 1600 rpm. Model ada dalam `rd85_physics.py`, menggunakan kerangka 0D yang sama dengan perbedaan geometri, jumlah silinder, dan envelope torsi. Informasi ini diambil dari file `Optimasi_Formulasi_PPO_RD85.html` yang disediakan pengguna. **CR=18, connecting rod=130 mm, SOI=-15°CA dan beberapa koefisien pembakaran masih ASUMSI, bukan hasil ukur.** RD85 di sini diasumsikan tanpa turbo.

## Tiga jenis campuran

1. **B0 (Pertadex) + B100 (biodiesel)**, B0–B100.
2. **B0 (Pertadex) + PPO**, P0–P100.
3. **B0 (Pertadex) + PPO + B50 (premix)**. Tiga slider B0/PPO/B50 berjumlah **tepat 100% volume**, termasuk saat salah satunya digeser ke 0% atau 100%. Saat salah satu slider digeser, dua yang lain mengikuti **proporsi sebelum perubahan**. Contoh awal **30% B0 + 50% PPO + 20% B50**.

B50 pada pilihan ketiga adalah **produk premix 50% biodiesel**, bukan B100. Karena B50 menjadi salah satu *komponen dasar*, seluruh sifatnya bisa diedit sebagai bahan bakar tersendiri.

Sifat campuran: densitas = campuran berdasarkan volume (asumsi volume aditif); LHV dan C/H/O = pembobotan berdasarkan fraksi massa; viskositas = VBN blending; CN = proxy fraksi volume; flash point = perkiraan, **bukan verifikasi keamanan campuran**. Seluruh persentase yang tampil adalah **volume**, bukan massa.

## Menu dan keluaran

- **Ringkasan**: torsi, daya, BMEP, BTE, BSFC, laju bahan bakar, indeks emisi.
- **Performa**: kurva RPM, konsumsi kg/jam dan L/jam, energi kimia.
- **Indikator emisi**: NOx dan smoke **indeks relatif B0=100**, CO₂ ideal neraca karbon; bukan emisi aktual ppm, HSU atau PM.
- **Pembakaran 0D**: kurva tekanan, temperatur, fraksi terbakar, ignition delay, CA50.
- **Fuel properties**: tabel properti, grafik komposisi, sumber/asumsi.
- **Ekspor & metode**: CSV grafik, riwayat sesi, fuel properties.

## Batasan penting

- **Mode kendali satu-satunya adalah Torsi Target per RPM**. Daya/torsi B0 dan campuran dapat hampir sama akibat target yang sama. Ini bukan prediksi independen daya maksimum saat bahan bakar diganti.
- **Tidak ada pembacaan atau tampilan data PNM**. Tidak ada dependensi `data/pnm_b0_b50.csv`.
- File HTML RD85 memuat *test bed virtual*, data sintetis, regresi Scheffé, dan optimasi. **Bagian-bagian sintetis dan regresi tersebut tidak dipakai sebagai hasil eksperimen maupun model prediksi aplikasi ini.** Hanya data geometri/parameter acuan dan pendekatan analisis pembakaran yang dirujuk.
- Torsi antar titik rating, thermodynamic coefficients, boost surrogate Toyota, dan emisi adalah estimasi; belum kalibrasi/perbandingan dengan data tekanan silinder aktual.
- PPO P100 adalah **skenario matematis**, bukan rekomendasi operasional. Perlu pemeriksaan kompatibilitas mesin, kualitas bahan bakar, stabilitas, flash point terukur, dan keselamatan.

## Jalankan lokal (opsional)

```bash
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Menjalankan pengujian otomatis

```bash
python -m unittest discover -s tests -p 'test_v6.py' -v
```

`tests/smoke_ui_stub.py` menguji pembuatan grafik dengan antarmuka Streamlit *tiruan*; bukan pengujian browser nyata.

## Deploy ke Streamlit Community Cloud

1. Upload **seluruh file** `streamlit_app.py`, `physics.py`, `rd85_physics.py`, `blend_controls.py`, dan `requirements.txt` ke **root** repository GitHub; jangan unggah ZIP sebagai satu file.
2. Buka Streamlit Community Cloud, pilih repository dan entry point `streamlit_app.py`.
3. Commit; tunggu build; bila masih menampilkan V5 pilih **Manage app → Reboot app**.
4. Uji RD85 → campuran ternary → 30/50/20 → Run, kemudian Toyota 2WD/4WD.

Acuan utama: J. B. Heywood, *Internal Combustion Engine Fundamentals*; file pengguna `Optimasi_Formulasi_PPO_RD85.html`; model Toyota versi sebelumnya.
