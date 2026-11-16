# Memperbaiki FileNotFoundError di Streamlit Community Cloud

Versi aplikasi ini memperbaiki error `FileNotFoundError` yang timbul pada baris `pnm=load_pnm()` saat membaca `data/pnm_b0_b50.csv`.

## Pembaruan V3: ganti kedua file inti

1. Buka repository GitHub tempat aplikasi Streamlit sudah di-deploy.
2. Ganti `streamlit_app.py` dan `physics.py` sekaligus dengan file V3 dari paket ini.
3. **Commit changes** ke branch yang digunakan Streamlit (`main` jika mengikuti panduan). Jangan mencampur UI V3 dengan physics V2.
4. Streamlit Community Cloud umumnya memperbarui aplikasi setelah GitHub di-commit. Bila perlu, buka Manage app → Reboot app.
5. Buka kembali aplikasi. Jika CSV tidak tersedia, dashboard tetap berjalan menggunakan salinan PNM yang sudah disematkan (10 baris; tanpa kolom fuel consumption). Tab Data eksperimen memberi peringatan bahwa fallback dipakai.

## Perbaikan struktur GitHub yang benar (direkomendasikan)

Pastikan `data/pnm_b0_b50.csv` ikut di-commit ke path persis itu. Perhatikan huruf kecil karena server Streamlit menggunakan Linux. Jika lengkap, aplikasi akan mengambil data langsung dari file GitHub dan tidak memakai fallback.

```text
repository/
├── streamlit_app.py
├── physics.py
├── requirements.txt
└── data/
    └── pnm_b0_b50.csv
```

GitHub **tidak** otomatis mengekstrak ZIP: Anda harus mengunggah isi ZIP dengan foldernya, bukan file ZIP saja.

## Catatan Python 3.14

Python 3.14 pada traceback bukan penyebab FileNotFoundError ini. Untuk konsistensi uji, Python 3.12 direkomendasikan saat *deploy ulang* (Advanced settings). Menurut dokumentasi Streamlit, versi Python aplikasi yang sudah ter-deploy **tidak dapat diubah langsung**; Anda perlu menghapus dan men-deploy ulang jika hendak menggantinya. Tidak perlu melakukan ini untuk menyelesaikan error data PNM.

## Pemisahan data dan keluaran

- Simulasi fisika tetap 0D / non-ML.
- Fallback adalah salinan hasil audit PNM asli (RPM, torsi, daya, O2, CO, NOx, NO, NO2, CO2, HC, smoke).
- **Kolom fuel consumption PNM tetap tidak ada dan tidak dipakai**.
- BSFC, BTE, dan fuel consumption yang tampil berasal dari model fisika, bukan pengukuran PNM.
- Perbandingan PNM belum merupakan validasi penuh: **varian mesin 2WD/4WD serta kesetaraan kondisi beban pengujian belum diketahui**.

## Tautan resmi

- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python
