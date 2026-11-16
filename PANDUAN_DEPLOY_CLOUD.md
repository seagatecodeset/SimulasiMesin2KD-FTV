# Deploy baru V3 pada Streamlit Community Cloud

1. Buka ZIP V3 dan unggah isi folder (bukan ZIP) ke repository GitHub. Struktur root harus berisi `streamlit_app.py`, `physics.py`, `requirements.txt`, folder `data/`, dan folder `.streamlit/`.
2. Kunjungi https://share.streamlit.io/ → Create app → pilih repository, branch `main`, dan main file `streamlit_app.py`.
3. Pada Advanced Settings, pilih Python 3.12 jika tersedia. Tidak perlu database atau secrets untuk simulasi ini.
4. Deploy, lalu buka URL yang dihasilkan. Pilih Engine Variant di sidebar.
5. Agar dapat diakses umum, atur pengaturan Sharing/Visibility aplikasi menjadi Public. Pastikan izin penggunaan/publikasi data PNM dan literatur telah dipenuhi.
6. Jika butuh update dari V2, baca `PANDUAN_UPDATE_V3.md`.

Dokumentasi: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app
