# Toyota 2KD-FTV — Engine Simulator Online (Streamlit Community Cloud)

**Versi:** Cloud V1 · **Metode:** model termodinamika 0D berbasis persamaan fisika (tanpa ML) · **Mesin:** Toyota 2KD-FTV 2WD generasi awal.

Proyek ini disiapkan untuk dipublikasikan langsung melalui [Streamlit Community Cloud](https://share.streamlit.io/) (hosting Streamlit), bukan melalui Ubuntu Server, Grafana, Apache/Nginx, Docker, atau instalasi pada komputer pengguna.

## Isi proyek

```text
streamlit_app.py              # Entry point Streamlit Cloud
physics.py                    # Solver engine 0D, Heun/RK2, properties, kinerja
requirements.txt              # Dependensi otomatis terinstal di Cloud
.streamlit/config.toml        # Tema dan parameter app
.gitignore                    # Mengecualikan rahasia dan file sementara
data/pnm_b0_b50.csv           # Dataset PNM terpilih TANPA fuel consumption
tests/test_physics.py         # 7 uji model
verifikasi_paket.py           # Pemeriksaan cepat tanpa Streamlit
docs/CATATAN_METODE.md       # Asumsi dan keterbatasan
PANDUAN_DEPLOY_CLOUD.md       # Langkah upload GitHub → Streamlit Cloud
```

## Cara publikasi

1. **Ekstrak ZIP.** Pastikan `streamlit_app.py`, `requirements.txt`, `physics.py`, dan folder `data` berada di tingkat teratas proyek.
2. Buat repository **Private** di GitHub, misalnya `simulator-toyota-2kd-ftv`.
3. Unggah seluruh **isi folder hasil ekstrak** (bukan file ZIP-nya) ke repository GitHub. Pastikan folder `data` dan `.streamlit` ikut terunggah.
4. Buka https://share.streamlit.io/ lalu hubungkan akun GitHub. Untuk repository privat, izinkan akses Streamlit ke repository terkait.
5. Klik **Create app → Yup, I have an app**. Pilih repository, branch `main`, dan **Main file path: `streamlit_app.py`**.
6. Pada **Advanced settings**, pilih **Python 3.12**; tidak perlu `secrets.toml` atau environment variable.
7. Klik **Deploy**. Jika sukses, aplikasi berjalan di `https://<subdomain-yang-dipilih>.streamlit.app`.
8. Atur **Settings → Sharing → Only specific people can view this app**, lalu gunakan **Share → Invite** untuk memasukkan email anggota tim. Lakukan sebelum menyebarkan URL.

Baca [PANDUAN_DEPLOY_CLOUD.md](PANDUAN_DEPLOY_CLOUD.md) untuk instruksi terperinci dan masalah yang sering terjadi.

## Yang dapat disimulasikan

- Mode **fixed torque** atau **fixed injection quantity**.
- Variasi RPM, beban, B0–B100, parameter LHV, tekanan turbo, ignition timing, dan koreksi pilot-injection.
- Resep PPO-M + Pertamina Dex + B50 **sebagai skenario ilustratif**, bukan formulasi yang sudah aman/tervalidasi.
- Torsi, daya, BMEP, IMEP, BTE, BSFC, konsumsi bahan bakar **hasil model**.
- Profil tekanan dan temperatur silinder terhadap crank angle, fraksi terbakar, ignition delay, CA50.
- NOx/smoke **indeks relatif saja**, bukan ppm/emisi absolut.
- Grafik eksperimen PNM pada lima RPM untuk B0 dan B50, terpisah dari hasil model.
- Unduh ringkasan skenario, trace silinder, dan data PNM terpilih dalam CSV.

## Batasan ilmiah

- Semua angka keluaran pembakaran/performa simulator adalah **estimasi model**. LHV B0 43 MJ/kg dan B100 40 MJ/kg masih **asumsi**, bukan konversi langsung nilai kalor yang dilaporkan pada tabel penelitian lain.
- **Cetane index bukan cetane number**; angka cetane dipakai sebagai **proxy eksploratif** sampai tersedia pengukuran CN/DCN.
- Kurva torsi penuh dan rasio boost memakai pendekatan/parameter, bukan peta ECU atau compressor map aktual.
- Data performa PNM belum memiliki verifikasi kesetaraan beban; grafik PNM merupakan pembanding deskriptif, **bukan validasi kuantitatif** pada setpoint simulator.
- **Fuel consumption PNM dikecualikan secara eksplisit dari proyek ini.** Nilai BSFC, BTE, fuel kg/h adalah hasil fisika model, bukan hasil pengukuran PNM.
- Jangan gunakan hasil untuk diagnosis keselamatan mesin, penetapan emisi regulasi, atau keputusan pengujian bahan bakar tanpa validasi eksperimental.

## Privasi dan keterbatasan hosting

- Untuk akses hanya tim, gunakan **private repository + private app**. Kebijakan saat panduan ini dibuat (12 November 2026) menyatakan satu private app per akun Community Cloud; cek kebijakan terbaru sebelum menambah aplikasi privat.
- Jangan unggah kata sandi, token, atau data rahasia ke GitHub. Rahasia jika dibutuhkan kelak harus disimpan di Streamlit Cloud **Secrets**, bukan di kode.
- Community Cloud adalah hosting eksternal yang menurut dokumentasi Streamlit berada di AS. Pastikan publikasi dataset PNM dan data bahan bakar sudah sesuai izin pemilik data dan kebijakan institusi.
- Riwayat skenario pada `st.session_state` bersifat **sementara untuk sesi pengguna**, bukan database permanen. Hindari mengandalkannya untuk arsip penelitian.
- Tidak perlu server sendiri, Docker, database, PHP, Nginx, atau Apache. Server dapat tertidur/terbatas sumber daya sesuai kebijakan Community Cloud.

## Pengujian lokal opsional untuk admin/developer

Tidak diperlukan untuk publikasi. Jika hendak mengecek terlebih dahulu:

```bash
python verifikasi_paket.py
python -m unittest discover -s tests -v
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Rujukan teknis deployment

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
- https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
- https://docs.streamlit.io/deploy/streamlit-community-cloud/status
