"""Streamlit Cloud Toyota 2KD-FTV 2WD awal | Simulator 0-D non-ML.

App ini tidak membaca kolom fuel consumption dataset PNM.
Data PNM berasal dari uji yang belum dikonfirmasi kesetaraan bebannya.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import io
import json
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from physics import Settings, REFERENCE_FUELS, V_TOTAL, CR, BORE_M, STROKE_M, run_sweep

ROOT = Path(__file__).resolve().parent
PNM_PATH = ROOT / "data" / "pnm_b0_b50.csv"
COLORS = {"B0": "#2563EB", "scenario": "#F97316", "pnmB0": "#2563EB", "pnmB50": "#0D9488"}

st.set_page_config(page_title="2KD-FTV Engine Lab | Online Simulator", page_icon="⚙️",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
  .block-container {padding-top:1.2rem;max-width:1460px;padding-bottom:2.5rem}
  .hero {background:linear-gradient(112deg,#0F2942 0%,#13475D 55%,#0E766B 100%);color:white;
         border-radius:18px;padding:1.55rem 1.9rem;margin-bottom:1.05rem;box-shadow:0 7px 18px rgba(15,41,66,.12)}
  .hero small {display:block;font-size:.7rem;font-weight:800;letter-spacing:.13em;color:#8DE6D3;text-transform:uppercase}
  .hero h1 {font-size:2.1rem;line-height:1.15;color:white;margin:.55rem 0 .5rem}
  .hero p {margin:0;color:#DCEFF2;font-size:.93rem;line-height:1.6}
  .hero-tags {display:flex;gap:.4rem;flex-wrap:wrap;margin-top:1rem}
  .hero-tags span {border:1px solid rgba(255,255,255,.32);border-radius:999px;
                   padding:.27rem .65rem;font-size:.75rem;color:white;background:rgba(255,255,255,.08)}
  .appnote {background:#EAF8F5;border-left:4px solid #0D9488;color:#103D3A;
            padding:.72rem 1.05rem;border-radius:9px;margin:.8rem 0}
  [data-testid="stMetric"] {background:white;border:1px solid #E2E8F0;border-radius:12px;
          padding:1rem 1.05rem;box-shadow:0 2px 6px rgba(35,64,90,.035)}
  [data-testid="stMetricLabel"] {font-weight:600}
  .muted {color:#718096;font-size:.86rem}
  @media(max-width:640px){.hero{padding:1.1rem 1.05rem}.hero h1{font-size:1.6rem}}
</style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def load_pnm():
    df = pd.read_csv(PNM_PATH)
    # Daftar putih kolom; fuel consumption PNM sengaja dikecualikan seluruhnya.
    allowed = ["fuel", "rpm", "torque_nm", "power_kw", "o2_pct", "co_ppm",
               "nox_ppm", "no_ppm", "no2_ppm", "co2_pct", "hc_ppm", "smoke_pct"]
    assert set(df.columns).issubset(set(allowed)), "Kolom di CSV PNM tidak sesuai daftar putih."
    return df[allowed].copy()

@st.cache_data(show_spinner=False, ttl=3600, max_entries=12)
def model(settings: Settings):
    """Cache hasil solver antar rerun; hanya bergantung pada input simulasi."""
    return run_sweep(settings)


def line_chart(df, y, title, axis_label, percent=False):
    fig = go.Figure()
    for series, group in df.groupby("series", sort=False):
        c = COLORS["B0"] if series == "B0 REFERENSI" else COLORS["scenario"]
        fig.add_trace(go.Scatter(x=group["rpm"],y=group[y], mode="lines+markers",
                                 name=series, line=dict(color=c,width=3), marker=dict(size=7),
                                 hovertemplate="RPM %{x}<br>Nilai %{y:.3f}<extra>%{fullData.name}</extra>"))
    fig.update_layout(title=title, xaxis_title="RPM",yaxis_title=axis_label,
                      legend=dict(orientation="h",y=-.30,x=0),margin=dict(l=30,r=10,t=55,b=75),height=355,
                      hovermode="x unified")
    if percent:
        fig.update_yaxes(ticksuffix="%")
    return fig


def trace_chart(ref, sc, field, name, yaxis, fill=False):
    fig = go.Figure()
    for sample, color in ((ref,COLORS["B0"]),(sc,COLORS["scenario"])):
        df=pd.DataFrame(sample["trace"])
        fig.add_trace(go.Scatter(x=df["theta_deg"],y=df[field],
                                 mode="lines",name=sample["series"],
                                 line=dict(color=color,width=2.6)))
    fig.add_vline(x=0,line_dash="dot",line_color="gray",opacity=.7)
    fig.update_layout(title=name,xaxis_title="Crank angle (°CA, TDC = 0)",
                      yaxis_title=yaxis,height=365,margin=dict(l=25,r=10,t=50,b=80),
                      legend=dict(orientation="h",y=-.32,x=0),hovermode="x unified")
    return fig


def experiment_chart(pnm, variable, label):
    fig=go.Figure()
    for fuel,color in (("B0",COLORS["pnmB0"]),("B50",COLORS["pnmB50"])):
        sub=pnm[pnm["fuel"]==fuel].sort_values("rpm")
        fig.add_trace(go.Scatter(x=sub["rpm"],y=sub[variable],name=f"PNM {fuel}",
                    mode="lines+markers",line=dict(color=color,width=3),marker=dict(size=8)))
    fig.update_layout(title=f"Hasil eksperimen PNM — {label}",xaxis_title="RPM",yaxis_title=label,
                      height=400,margin=dict(l=25,r=10,t=60,b=70),hovermode="x unified",
                      legend=dict(orientation="h",x=0,y=-.28))
    return fig


def clean_df(results):
    keys = ["rpm","series","fuel_pct","torque_nm","power_kw","bmep_bar",
            "imep_bar","fmep_bar","bsfc_g_kwh","bte_pct","fuel_kg_h",
            "fuel_mg_cycle_cyl","lambda_air","pmax_bar","soc_deg","ca50_deg",
            "ign_delay_deg","nox_rel_pct","smoke_rel_pct","co2_ideal_kg_h",
            "energy_residual_pct","limited"]
    return pd.DataFrame([{k: p.get(k) for k in keys} for p in results["points"]])


def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")


def fmt(v, unit="", decimals=2):
    if v is None or not np.isfinite(v):
        return "—"
    return f"{v:,.{decimals}f} {unit}".strip()

# ================ CONTROLS ================
st.sidebar.title("⚙️ Kendali Simulasi")
st.sidebar.caption("Atur parameter lalu tekan Jalankan simulasi")
st.sidebar.caption("2KD-FTV 2WD awal · 2.494 cc · CR 18,5:1")
with st.sidebar.form("simulation_input"):
    rpm=st.number_input("Putaran mesin (rpm)",min_value=1000,max_value=3800,value=2000,step=50)
    load=st.slider("Beban relatif terhadap torsi referensi (%)", min_value=10,max_value=100,value=50,step=5,
                   help="Beban 100% mengacu pada envelope torsi teoritis varian 2WD awal, bukan data ECU.")
    mode_label=st.radio("Mode simulasi",options=["Torsi target tetap","Jumlah injeksi tetap"],
                        help="Mode injeksi tetap menahan jumlah bahan bakar B0 pada RPM dan beban referensi.")
    mode="fixed_torque" if mode_label=="Torsi target tetap" else "fixed_injection"
    blend_mode=st.radio("Jenis campuran",["Biodiesel B0–B100","PPO-M + Dex + B50 (ilustratif)"],index=0)
    b_pct=50.0
    ppo_pct=0.0
    b50_pct=0.0
    if blend_mode=="Biodiesel B0–B100":
        b_pct=float(st.slider("Kadar biodiesel (% volume)",0,100,50,5))
    else:
        ppo_pct=float(st.slider("PPO-M (% volume)",0,100,30,5))
        max_b50=int(100-ppo_pct)
        b50_pct=float(st.slider("B50 (% volume)",0,max_b50,min(20,max_b50),5)) if max_b50 > 0 else 0.0
        st.caption(f"Sisa Pertamina Dex = {100-ppo_pct-b50_pct:.0f}% volume; sifat PPO-M ilustratif.")

    with st.expander("Asumsi bahan bakar & mesin (lanjutan)"):
        lhv0=st.number_input("LHV B0 (MJ/kg) — asumsi",min_value=35.0,max_value=48.0,value=43.0,step=.2)
        lhv100=st.number_input("LHV B100 (MJ/kg) — asumsi",min_value=32.0,max_value=46.0,value=40.0,step=.2)
        cn_user=st.checkbox("Tentukan cetane number skenario secara manual",value=False)
        cn=st.number_input("CN skenario",min_value=25.0,max_value=90.0,value=55.0,step=1.0,
                           disabled=not cn_user)
        prmax=st.number_input("Rasio tekanan turbo maksimum (asumsi)",min_value=1.0,
                              max_value=2.2,value=1.65,step=.05)
        intake_c=st.number_input("Temperatur udara masuk lingkungan (°C)",min_value=10,max_value=55,value=32,step=1)
        soi=st.number_input("Main SOI pada beban 100% (°CA ATDC)",min_value=-25.0,
                             max_value=10.0,value=-6.0,step=1.0)
        pilot=st.checkbox("Aktifkan koreksi pilot injection (asumsi)",value=True)
    submitted=st.form_submit_button("▶ Jalankan simulasi",type="primary",use_container_width=True)

settings=Settings(rpm=int(rpm),load_pct=float(load),b_pct=b_pct,mode=mode,
                  lhv_b0=float(lhv0),lhv_b100=float(lhv100),
                  cn_override=float(cn) if cn_user else None,
                  pressure_ratio_max=float(prmax),intake_temp_k=float(intake_c)+273.15,
                  soi_deg=float(soi),pilot_enabled=bool(pilot),
                  fuel_scheme="biodiesel" if blend_mode.startswith("Biodiesel") else "ppo",
                  ppo_pct=ppo_pct,b50_pct=b50_pct)

if "sim_result" not in st.session_state or submitted:
    try:
        with st.spinner("Menghitung siklus 0D dengan integrator Heun RK2..."):
            sim=model(settings)
        st.session_state["sim_result"]=sim
        st.session_state["run_time"]=datetime.now().strftime("%d/%m/%Y %H:%M")
        hist=st.session_state.get("history",[])
        scenario=sim["focus"]["scenario"]
        hist.insert(0,{"waktu":st.session_state["run_time"],"rpm":settings.rpm,
                       "load_pct":settings.load_pct,"jenis":scenario["series"],
                       "mode":settings.mode,"torque_nm":scenario["torque_nm"],
                       "power_kw":scenario["power_kw"],"bte_pct":scenario["bte_pct"],
                       "bsfc_g_kwh":scenario["bsfc_g_kwh"]})
        st.session_state["history"]=hist[:25]
    except (ValueError,OverflowError,FloatingPointError) as exc:
        st.error(f"Simulasi gagal: {exc}")
        st.stop()

sim=st.session_state["sim_result"]
actual=sim["settings"]
ref=sim["focus"]["reference"]
sc=sim["focus"]["scenario"]
frame=clean_df(sim)
pnm=load_pnm()

st.markdown("""
<div class="hero">
  <small>ONLINE ENGINE LAB · PHYSICS-BASED MODEL</small>
  <h1>Toyota 2KD-FTV Engine Simulator</h1>
  <p>Simulasi interaktif performa dan pembakaran mesin diesel 2WD generasi awal.
     Berbasis persamaan termodinamika 0D dan data referensi, tanpa machine learning.</p>
  <div class="hero-tags"><span>4 silinder · 2.494 cc</span><span>CR 18,5:1</span>
    <span>Heun RK2</span><span>B0–B100</span><span>Cloud Edition</span></div>
</div>
""",unsafe_allow_html=True)
if actual != settings:
    st.info("Input di sisi kiri telah berubah tetapi hasil masih berasal dari simulasi sebelumnya. Klik **Jalankan simulasi** untuk memperbarui.")

st.markdown(f"""<div class="appnote"><strong>Skenario:</strong> {sc['series']} ·
<strong>{actual.rpm:,} rpm</strong> · <strong>{actual.load_pct:g}% beban</strong> ·
<strong>{'torsi target tetap' if actual.mode=='fixed_torque' else 'jumlah injeksi tetap'}</strong>.
Hasil ini adalah <strong>estimasi model</strong>, belum dikalibrasi penuh dengan mesin aktual.</div>""",unsafe_allow_html=True)

tabs=st.tabs(["📊 Ringkasan", "⚡ Kurva performa", "🔥 Pembakaran 0D",
              "🧪 Data eksperimen PNM", "🛢️ Properti bahan bakar", "📁 Ekspor & metode"])

with tabs[0]:
    a,b,c,d=st.columns(4)
    a.metric("Torsi skenario",fmt(sc["torque_nm"],"Nm"),
             fmt(sc["torque_nm"]-ref["torque_nm"],"Nm"))
    b.metric("Daya skenario",fmt(sc["power_kw"],"kW"),
             fmt(sc["power_kw"]-ref["power_kw"],"kW"))
    c.metric("BSFC model",fmt(sc["bsfc_g_kwh"],"g/kWh"))
    d.metric("BTE model",fmt(sc["bte_pct"],"%"))
    a,b,c,d=st.columns(4)
    a.metric("BMEP model",fmt(sc["bmep_bar"],"bar"))
    b.metric("Puncak tekanan",fmt(sc["pmax_bar"],"bar"))
    c.metric("Ignition delay",fmt(sc["ign_delay_deg"],"°CA"))
    d.metric("Residual energi",fmt(sc["energy_residual_pct"],"%",4))
    if sc["limited"]:
        st.warning("Target simulasi tidak sepenuhnya tercapai atau suplai bahan bakar dibatasi model. Periksa RPM, beban, dan parameter.")
    if sc["fuel_properties"].get("flash_c", 100) < 52:
        st.warning("Flash point campuran diperkirakan di bawah 52 °C. Ini hanya pemeriksaan ilustratif, bukan penetapan kelayakan bahan bakar. Jangan menguji campuran pada mesin tanpa evaluasi keselamatan dan mutu yang memadai.")
    col1,col2=st.columns(2)
    with col1:
        st.plotly_chart(line_chart(frame,"torque_nm","Torsi terhadap putaran","Torsi (Nm)"),use_container_width=True)
    with col2:
        st.plotly_chart(line_chart(frame,"power_kw","Daya terhadap putaran","Daya (kW)"),use_container_width=True)
    st.caption("Konsumsi bahan bakar, BSFC, dan BTE di sini SEMUANYA hasil model. Kolom fuel consumption PNM tidak dibaca.")

with tabs[1]:
    col1,col2=st.columns(2)
    for col,field,name,unit in ((col1,"bsfc_g_kwh","BSFC model","g/kWh"),
                                (col2,"bte_pct","BTE model","%")):
        with col: st.plotly_chart(line_chart(frame,field,name,unit),use_container_width=True)
    col1,col2=st.columns(2)
    with col1: st.plotly_chart(line_chart(frame,"fuel_kg_h","Konsumsi bahan bakar MODEL","kg/jam"),use_container_width=True)
    with col2: st.plotly_chart(line_chart(frame,"bmep_bar","BMEP model","bar"),use_container_width=True)
    st.info("Mode **torsi target tetap** akan menghasilkan torsi dan daya hampir sama antara B0 dan campuran jika model dapat mencapai target. Perubahan terutama terlihat pada kebutuhan injeksi dan efisiensi. Gunakan **jumlah injeksi tetap** untuk melihat respons torsi/daya akibat perubahan bahan bakar.")

with tabs[2]:
    c1,c2=st.columns(2)
    with c1: st.plotly_chart(trace_chart(ref,sc,"pressure_bar","Tekanan di dalam silinder","bar"),use_container_width=True)
    with c2: st.plotly_chart(trace_chart(ref,sc,"temperature_k","Temperatur gas rata-rata silinder","K"),use_container_width=True)
    c1,c2=st.columns(2)
    with c1: st.plotly_chart(trace_chart(ref,sc,"burned_fraction","Fraksi pembakaran kumulatif","fraksi 0–1"),use_container_width=True)
    with c2:
        st.subheader("Parameter pembakaran")
        st.dataframe(pd.DataFrame([
            {"Parameter":"Ignition delay (°CA)","B0":ref["ign_delay_deg"],"Skenario":sc["ign_delay_deg"]},
            {"Parameter":"SOC (°CA ATDC)","B0":ref["soc_deg"],"Skenario":sc["soc_deg"]},
            {"Parameter":"CA50 (°CA ATDC)","B0":ref["ca50_deg"],"Skenario":sc["ca50_deg"]},
            {"Parameter":"IMEP (bar)","B0":ref["imep_bar"],"Skenario":sc["imep_bar"]},
            {"Parameter":"FMEP (bar)","B0":ref["fmep_bar"],"Skenario":sc["fmep_bar"]},
            {"Parameter":"Neraca energi residual (%)","B0":ref["energy_residual_pct"],"Skenario":sc["energy_residual_pct"]},
        ]).set_index("Parameter"),use_container_width=True)
        st.caption("Model satu-zona IVC→EVO; bukan hasil pengukuran tekanan silinder atau simulasi CFD.")
    st.subheader("Indikator emisi dari model (bukan ppm atau %HSU)")
    c1,c2,c3=st.columns(3)
    c1.metric("NOx relatif terhadap B0",fmt(sc["nox_rel_pct"],"%"))
    c2.metric("Smoke index relatif terhadap B0",fmt(sc["smoke_rel_pct"],"%"))
    c3.metric("CO₂ stoikiometrik ideal",fmt(sc["co2_ideal_kg_h"],"kg/jam"))
    st.warning("NOx dan smoke hanya indikator tren model; **tidak** boleh dibandingkan langsung dengan ppm NOx atau persentase smoke dari pengujian PNM. CO₂ ideal menganggap semua karbon menjadi CO₂.")

with tabs[3]:
    st.info("Data eksperimen PNM berisi 5 RPM × 2 bahan bakar. **Beban pengujian belum dipastikan**, sehingga grafik ini hanya pembanding deskriptif, bukan validasi kuantitatif langsung pada beban simulasi.")
    var_options={
       "Torsi (Nm)":"torque_nm", "Daya (kW)":"power_kw", "NOx (ppm)":"nox_ppm",
       "CO (ppm)":"co_ppm", "CO₂ (%vol)":"co2_pct", "HC (ppm)":"hc_ppm",
       "O₂ (%vol)":"o2_pct", "Smoke (% laporan)":"smoke_pct",
    }
    choice=st.selectbox("Parameter eksperimen",options=list(var_options))
    st.plotly_chart(experiment_chart(pnm,var_options[choice],choice),use_container_width=True)
    c1,c2=st.columns([2,1])
    with c1:
        pivot=pnm.pivot(index="rpm",columns="fuel",values=var_options[choice]).reset_index()
        if "B0" in pivot and "B50" in pivot:
            pivot["Δ B50 vs B0 (%)"]=np.where(pivot["B0"]!=0,(pivot["B50"]-pivot["B0"])/pivot["B0"]*100,np.nan)
        st.dataframe(pivot,hide_index=True,use_container_width=True)
    with c2:
        st.markdown("**Asal data**")
        st.write("Dataset PNM average.xlsx (ringkasan data yang sudah diaudit sebelumnya).")
        st.write("Hanya dipakai kolom daya, torsi dan emisi. Data fuel consumption **tidak disimpan dan tidak dihitung**.")
    st.download_button("⬇ Unduh data eksperimen PNM (tanpa fuel consumption)",
        data=csv_bytes(pnm),file_name="data_PNM_B0_B50_tanpa_fuel_consumption.csv",mime="text/csv")

with tabs[4]:
    st.subheader("Properti skenario dari aturan campuran")
    props=sc["fuel_properties"]
    units={"density_kg_m3":"Density (kg/m³)","viscosity_cst":"Kinematic viscosity (mm²/s)",
           "lhv_mj_kg":"LHV model (MJ/kg)","cetane_proxy":"CN proxy untuk ignition delay",
           "flash_c":"Flash point (°C) — perkiraan", "afr_st":"AFR stoikiometrik (kg/kg)",
           "C_pct":"C (% massa) — asumsi", "H_pct":"H (% massa) — asumsi", "O_pct":"O (% massa) — asumsi"}
    dfprop=pd.DataFrame([{"Sifat":units[k],"Nilai":props.get(k)} for k in units])
    st.dataframe(dfprop,hide_index=True,use_container_width=True)
    st.caption(f"Basis: {props.get('origin','—')} · CN: {props.get('cetane_proxy_basis','—')}")
    st.subheader("Tabel sumber fuel properties dari penelitian lain")
    fd=pd.DataFrame([{"Biodiesel (%)":k,"Density @15°C (kg/m³)":v["density"],
                  "Viscosity @40°C (mm²/s)":v["viscosity"],
                  "Calorific value dilaporkan (MJ/kg)":v["calorific_reported"],
                  "Cetane index (bukan CN)":v["ci"],"Flash point (°C)":v["flash"]}
                 for k,v in REFERENCE_FUELS.items()])
    st.dataframe(fd,hide_index=True,use_container_width=True)
    st.warning("Nilai kalor literatur, terutama B0 = 59,79 MJ/kg, belum terverifikasi sebagai LHV/HHV dan tidak otomatis dipakai. LHV model menggunakan asumsi yang dapat diubah di sidebar. Cetane INDEX hanya dipakai sebagai proxy eksploratif.")

with tabs[5]:
    st.subheader("Ekspor hasil simulasi")
    st.download_button("⬇ Unduh ringkasan seluruh RPM (CSV)",
        data=csv_bytes(frame),file_name="simulasi_2KD_FTV_ringkasan.csv",mime="text/csv")
    tr=pd.DataFrame(sc["trace"])
    st.download_button("⬇ Unduh kurva silinder skenario (CSV)",
        data=csv_bytes(tr),file_name="simulasi_2KD_FTV_trace_silinder.csv",mime="text/csv")
    history=pd.DataFrame(st.session_state.get("history",[]))
    st.subheader("Riwayat simulasi di sesi browser ini")
    st.dataframe(history,hide_index=True,use_container_width=True)
    if not history.empty:
        st.download_button("⬇ Unduh riwayat skenario (CSV)",
            data=csv_bytes(history),file_name="riwayat_skenario_2KD_FTV.csv",mime="text/csv")
    st.subheader("Batasan dan dasar matematis")
    st.markdown("""
- **Geometri:** crank-slider, volume dan luas permukaan ruang bakar berdasarkan bore, stroke, CR. Panjang connecting rod **150 mm diasumsikan**.
- **Pengisian udara:** boost conventional turbo memakai rumus surrogate fungsi RPM/beban, **bukan compressor map hasil ukur**; tidak menggunakan intercooler.
- **Ignition delay:** Hardenberg–Hase + koreksi fenomenologis viskositas/pilot. CN dari cetane index adalah **proxy**, bukan pengukuran cetane number.
- **Pembakaran:** dua fungsi Wiebe (premixed dan diffusion); asumsi model empiris.
- **Termodinamika:** satu-zona hukum I, perpindahan panas Woschni, integrator Heun/RK2 0,5°CA.
- **Kinerja:** IMEP → dikurangi FMEP (mirip Chen–Flynn) dan PMEP → BMEP, torsi, daya, BSFC dan BTE **hasil model**.
- **Emisi:** NOx dan smoke hanya indeks relatif; CO₂ merupakan batas ideal neraca karbon, bukan emisi tailpipe.
- **Validasi:** data PNM punya RPM, torsi/daya dan emisi, tetapi belum ada kepastian kondisi beban maupun satuan fuel consumption. Karena itu tidak mengklaim model sudah tervalidasi.
- **Wilayah berlaku:** steady-state, rentang dan metode asumsi pada profil 2KD-FTV 2WD generasi awal; tidak untuk diagnosis kerusakan atau kepatuhan emisi.
""")
    st.caption("Referensi utama: J.B. Heywood, Internal Combustion Engine Fundamentals; kode starter PPO-M pengguna; dokumen spesifikasi Toyota 2KD-FTV 2WD awal; data PNM dan tabel fuel properties yang pengguna kirim.")

st.divider()
st.caption(f"Toyota 2KD-FTV · Engine Lab Cloud | Hasil terakhir: {st.session_state.get('run_time','—')} | Non-ML · Streamlit Community Cloud · Penyimpanan hanya selama sesi")
