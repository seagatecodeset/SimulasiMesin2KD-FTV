# Panduan Publikasi — Toyota 2KD-FTV Engine Simulator pada Streamlit Community Cloud

**Tujuan:** aplikasi online untuk tim penelitian, tanpa server pribadi dan tanpa Docker. **Tanggal panduan:** 12 November 2026.

## A. Sebelum mulai

Perlu akun **GitHub** dan akun **Streamlit Community Cloud**. Pengguna akhir cukup browser. Pekerjaan ini **belum menerbitkan URL online otomatis**; pemilik akun harus mengunggah proyek ke GitHub lalu menekan Deploy di Streamlit Cloud karena tindakan ini memerlukan login dan izin pengguna.

**Saran keamanan:** karena ada data eksperimen PNM, gunakan **GitHub Private repository** dan **Streamlit Private app**; minta persetujuan yang relevan sebelum menempatkan dataset di hosting eksternal. Streamlit Cloud menyatakan infrastruktur aplikasinya berada di AS.

## B. Cara paling mudah: unggah melalui website GitHub

1. Buka https://github.com/ dan login. Klik **New repository**.
2. Isi nama misalnya **`simulator-toyota-2kd-ftv`**, pilih **Private**, lalu **Create repository**.
3. Ekstrak ZIP yang Anda terima ke folder biasa.
4. Dari repository baru, pilih **uploading an existing file** / **Add file → Upload files**. Unggah **seluruh isi folder**, bukan ZIP tunggal. Jika browser tidak mau mengunggah folder secara utuh, gunakan GitHub Desktop / git CLI agar subfolder tetap terjaga.
5. Pastikan struktur di root GitHub seperti ini:

   ```text
   simulator-toyota-2kd-ftv/
   ├── streamlit_app.py
   ├── physics.py
   ├── requirements.txt
   ├── data/pnm_b0_b50.csv
   ├── .streamlit/config.toml
   ├── tests/test_physics.py
   ├── docs/CATATAN_METODE.md
   ├── verifikasi_paket.py
   └── README.md
   ```

6. Klik **Commit changes**. Periksa kembali bahwa tidak ada `secrets.toml`, password, maupun file internal lain yang tidak boleh dipublikasikan. Jangan mengunggah folder `.venv`.

**Alternatif praktis untuk banyak file:** pasang GitHub Desktop, pilih **File → Add local repository** atau buat repository dari folder yang telah diekstrak, lalu **Publish repository** dengan opsi **Keep this code private**.

## C. Deploy ke Streamlit Community Cloud

1. Buka https://share.streamlit.io/ dan masuk menggunakan akun yang telah terhubung dengan GitHub.
2. Pastikan izin akses repository **Private** sudah diberikan kepada Streamlit saat diminta. Bila repo tidak terlihat, periksa pengaturan koneksi GitHub dan hak admin pada repository.
3. Klik **Create app**, pilih **Yup, I have an app**.
4. Isi **Repository**: `nama-akun-github/simulator-toyota-2kd-ftv`.
5. **Branch**: `main`.
6. **Main file path**: `streamlit_app.py`.
7. **App URL (optional)**: misalnya `2kd-ftv-engine-lab` jika masih tersedia; alamat akhirnya menjadi `https://2kd-ftv-engine-lab.streamlit.app` (hanya contoh, belum diterbitkan).
8. Klik **Advanced settings**: pilih **Python 3.12**. `Secrets`: kosong, karena aplikasi tidak membutuhkan API key atau password aplikasi.
9. Klik **Deploy** dan perhatikan log apabila terjadi error.
10. Setelah terbuka, lakukan simulasi default: 2.000 rpm, beban 50%, B50, lalu coba halaman Pembakaran dan Data PNM. Pastikan grafis dan tombol CSV bekerja.

## D. Membatasi akses hanya untuk tim

1. Dari Streamlit Cloud, buka **App settings → Sharing**.
2. Pilih **Only specific people can view this app**. Jangan memilih public/searchable.
3. Klik **Share**, masukkan email anggota tim, klik **Invite**.
4. Uji dengan satu akun anggota tim terlebih dahulu. Jangan menganggap repository Private otomatis cukup tanpa memastikan pengaturan aplikasi juga Private.
5. Kebijakan resmi yang dicek 12 November 2026 membatasi **satu private app per akun**. Jika membutuhkan banyak aplikasi privat, evaluasi paket/platform yang sesuai.

## E. Cara memperbarui aplikasi

Edit file di GitHub (`streamlit_app.py`, `physics.py`, atau `data/...`) dan commit ke branch `main`. Community Cloud mendeteksi perubahan dari GitHub dan memperbarui aplikasi. Perubahan dependensi di `requirements.txt` dapat menyebabkan proses instalasi ulang paket.

## F. Masalah umum

| Masalah | Pemeriksaan dan solusi |
|---|---|
| `ModuleNotFoundError: physics` | Pastikan `physics.py` dan `streamlit_app.py` sejajar pada root repo. |
| `No module named plotly` atau `numpy` | Periksa `requirements.txt` di root GitHub dan ulangi deployment/reboot. |
| `FileNotFoundError: data/pnm_b0_b50.csv` | Pastikan folder `data` dan CSV ikut di-commit (jangan hanya unggah skrip utama). |
| Repo privat tidak muncul | Hubungkan GitHub dengan izin akses repo private; pastikan hak admin ke repo. |
| `streamlit_app.py` not found | Set `Main file path` tepat `streamlit_app.py`, branch `main`. |
| Aplikasi tidak tampak bagi rekan tim | Periksa bahwa email mereka tercantum sebagai viewer di `Share`/`Sharing`. |
| App lambat saat menghitung | Jalankan beberapa skenario secara bergantian. Solver memang numerik; telah diberi caching 12 input terakhir. Community Cloud memiliki batas sumber daya. |
| App tidur setelah tidak dipakai | Buka lagi URL aplikasi; ini perilaku hosting Cloud dan bukan kerusakan perhitungan. |
| Klik download lalu riwayat hilang | `st.session_state` bukan penyimpanan permanen. Unduh CSV sebelum menutup sesi. |

## G. Periksa keluaran ilmiah

- Plot PNM mengandung RPM, torsi, daya, dan emisi **saja**. Tidak ada kolom fuel consumption dari uji PNM.
- BSFC/BTE/konsumsi yang tampil selalu diberi label **model**, bukan pengukuran PNM.
- Fuel properties berasal dari penelitian lain yang menggunakan tipe mesin sama; status **LHV provisional** dan **cetane index proxy** tetap perlu dicermati.
- NOx dan smoke dari simulator merupakan **indeks relatif**, bukan emisi dengan satuan ppm atau opacity aktual.
- Torsi full-load dalam simulator adalah **envelope asumsi** mesin 2KD-FTV 2WD generasi awal; belum mencerminkan ECU aktual tiap unit.

## H. Dokumentasi resmi

- Deploy: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Dependensi: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- Privasi dan viewers: https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
- Status dan batasan hosting: https://docs.streamlit.io/deploy/streamlit-community-cloud/status
