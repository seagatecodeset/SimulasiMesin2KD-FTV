# Update simulator Streamlit Cloud V5 ke V6

**Tidak perlu membuat aplikasi Streamlit Cloud baru.**

## 1. Backup

Simpan salinan kode saat ini dari repository GitHub, atau catat nomor commit terakhir agar dapat dikembalikan jika perlu.

## 2. Unggah file

Dari `PATCH_V5_KE_V6_2KD_RD85_Streamlit.zip`, ekstrak dan unggah **ke folder utama/root repository**:

- `streamlit_app.py` — **replace** V5.
- `physics.py` — **replace** V5 (menambah ternary untuk Toyota).
- `rd85_physics.py` — **baru**, simulasi RD85.
- `blend_controls.py` — **baru**, pengunci 3 slider.
- `requirements.txt` — sama/aman digunakan.

Pastikan tidak ada file bernama `physics (1).py`, dan semua nama menggunakan huruf kecil sama persis. Pilih **Commit changes**.

## 3. Restart aplikasi

Pada Streamlit Community Cloud: **Manage app → Reboot app** jika tampilan masih V5. Pastikan sidebar menunjukkan **V6**.

## 4. Cek wajib

1. **Pilih simulator mesin**: Toyota 2KD-FTV (2WD dan 4WD) atau Kubota RD85.
2. **Campuran 1**: B0 + B100, contoh B35.
3. **Campuran 2**: B0 + PPO, contoh P30.
4. **Campuran 3**: B0 + PPO + B50, contoh **B0=30, PPO=50, B50=20**; total yang muncul harus **100%**.
5. Geser PPO menjadi 70%: B0 dan B50 harus otomatis turun secara proporsional, total tetap 100%.
6. Pastikan hasil RD85 berubah dengan RPM, dan data torsi/daya untuk RD85 tidak disamakan dengan Toyota.
7. Cek tab Ringkasan, Performa, Indikator emisi, Pembakaran 0D, Fuel properties, Ekspor.
8. Data eksperimen PNM tidak boleh tampil.

## 5. Pemecahan masalah

- **`ModuleNotFoundError: rd85_physics` atau `blend_controls`**: file baru belum diunggah ke root repository.
- **`cannot import ...`**: ganti `physics.py` dan `streamlit_app.py` **bersamaan**, lalu reboot aplikasi.
- **Perubahan belum tampak**: periksa branch yang dipakai Streamlit, status commit GitHub, lalu reboot.
- **Input properti gagal**: periksa satuan density (kg/m³), LHV (MJ/kg), dan C+H+O (90–100% massa).
- **Hasil B0 dan campuran punya torsi hampir sama**: normal untuk metode torsi target, jika tidak dibatasi model udara.

## Catatan penggunaan ilmiah

Data RD85 dalam HTML memuat contoh sintetis untuk pendidikan/optimasi. Simulator V6 **tidak mengklaim** angka itu sebagai pengukuran asli. Karakteristik PPO bersifat sensitif terhadap proses pirolisis dan perlu pengujian laboratorium. B50 adalah premix, bukan bahan bakar B100.
