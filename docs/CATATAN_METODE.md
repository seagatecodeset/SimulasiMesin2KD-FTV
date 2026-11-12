# Catatan metodologi dan jejak sumber — simulator 2KD-FTV

## Yang berasal dari dokumen/masukan pengguna

- Mesin Toyota 2KD-FTV **2WD generasi awal**: bore 92 mm, stroke 93,8 mm, CR 18,5:1; rating referensi 65 kW @3800 rpm, torsi 192 Nm pada rentang 1200–3000 rpm (sumber spesifikasi Toyota yang sudah dibahas pada percakapan).
- Slide "Tahap 1: Bangun Mesin Virtual": sembilan langkah, 0D engine cycle, ignition delay Hardenberg–Hase, Wiebe, Woschni, NOx ratio, motoring dan neraca energi.
- Kode `ppo_blend_physics.py` dari `Optimasi_Campuran_PPO.zip`: model campuran dan konsep siklus 0D; implementasi dalam proyek ini telah diubah ke integrator Heun.
- `Dataset PNM average.xlsx`: lima titik RPM × B0/B50, data torsi/daya dan emisi. `data/pnm_b0_b50.csv` sengaja **tanpa fuel consumption**.
- Tabel fuel properties pengguna berasal dari penelitian lain (B0/B50/B55/B100): density, viscosity, calorific value, cetane index, flash point.

## Asumsi model (bukan terukur)

- Connecting rod = 150 mm; awal/akhir siklus tertutup θ = -150° sampai +130°.
- Turbine/compressor pressure ratio adalah fungsi aproksimasi RPM dan beban (bukan map kompresor Toyota).
- Intake gas temperature, residual charge, wall temperature, pilot injection correction, SOI default.
- LHV default B0 43 dan B100 40 MJ/kg; elemental composition dan efisiensi pembakaran berupa parameter eksploratif.
- FMEP menggunakan fungsi tekanan puncak dan mean piston speed mirip Chen–Flynn dengan koefisien dugaan.
- Power/torsi envelope idealisasi rating 2WD awal, bukan hasil aktual dari semua putaran.

## Mengapa tidak ada RMSE terhadap PNM saat ini?

PNM tidak mencantumkan kondisi beban/test protocol yang cukup untuk memastikan setiap titik setara dengan setelan simulasi. Memaksa perbandingan dan menghasilkan RMSE saat ini memberikan kesan validasi yang tidak sah. Setelah ada beban terukur atau tata cara uji, barulah lakukan prediksi di titik operasi sepadan dan kuantifikasi kesalahan.

## Perhitungan numerik

- Motoring adiabatik dengan γ konstan dibandingkan dengan pV^γ = konstanta.
- Uji residual energi: Qpembakaran = W + Qdinding + ΔU pada batas volume yang dimodelkan.
- Tes motor dan energi mengecek konsistensi integrator, **tidak mengonfirmasi ketepatan submodel kimia pembakaran atau emisi**.

## Sumber utama untuk pembaca

- Heywood, John B., *Internal Combustion Engine Fundamentals*, edisi kedua, McGraw-Hill, 2018.
- Dokumen Toyota 2KD-FTV (New Features) yang diberikan dalam pembahasan sebelumnya: https://toyotamanuals.gitlab.io/pz471-zx006-ca/htmlweb/ncf/ncf210e/m_nf_0018.pdf
- Pedoman instalasi Streamlit: https://docs.streamlit.io/get-started/installation/command-line
- Data numerik pengguna yang menyertai percakapan (PNM dan fuel properties).
