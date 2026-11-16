"""Streamlit Cloud Toyota 2KD-FTV 2WD/4WD awal | Simulator 0-D non-ML.

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

from physics import (Settings, REFERENCE_FUELS, V_TOTAL, CR, BORE_M, STROKE_M,
                     ENGINE_PROFILES, get_engine_profile, full_load_torque, run_sweep)

ROOT = Path(__file__).resolve().parent
PNM_PATH = ROOT / "data" / "pnm_b0_b50.csv"
COLORS = {"B0": "#2563EB", "scenario": "#F97316", "pnmB0": "#2563EB", "pnmB50": "#0D9488"}

PNM_COLUMNS = [
    "fuel", "rpm", "torque_nm", "power_kw", "o2_pct", "co_ppm",
    "nox_ppm", "no_ppm", "no2_ppm", "co2_pct", "hc_ppm", "smoke_pct"
]
# Salinan data eksperimen yang sudah dipilih, TANPA fuel consumption PNM.
# Dipakai sebagai cadangan jika subfolder data/ belum tersalin ke GitHub.
PNM_FALLBACK_CSV = 'fuel,rpm,torque_nm,power_kw,o2_pct,co_ppm,nox_ppm,no_ppm,no2_ppm,co2_pct,hc_ppm,smoke_pct\nB0,1250,78.2830769,10.20917,12.1388889,291.8888889,318.2555556,276.7777778,42.7333333,8.8877778,322.6666667,2.69\nB0,1500,84.3895238,13.031369,11.48,214.5555556,349.7222222,310.3333333,39.6333333,9.36,203.4444444,3.18\nB0,1750,95.7559172,17.5630769,11.3888889,152.5555556,365.6555556,333.1111111,31.2555556,9.8011111,69.2222222,5.27\nB0,2000,96.2319412,20.1330588,11.3855556,128.5555556,332.8555556,318.0,15.4,9.6666667,127.8888889,4.46\nB0,2250,90.0845294,21.2278235,11.6811111,111.3333333,322.2444444,299.5555556,22.5333333,9.3744444,172.5555556,3.0\nB50,1250,75.1023952,10.0808383,12.3822222,318.1111111,321.7555556,273.5555556,49.0222222,8.7133333,116.1111111,3.02\nB50,1500,80.7427219,12.7134911,11.8944444,222.6666667,336.6222222,299.6666667,43.3777778,9.5077778,49.7777778,4.9\nB50,1750,96.3649133,17.6910983,10.7344444,176.8888889,383.6222222,363.1111111,29.6333333,10.4522222,190.2222222,3.59\nB50,2000,96.8346154,20.5504734,11.2733333,127.6666667,352.7777778,328.0,26.9,10.0333333,88.4444444,4.49\nB50,2250,93.9657396,22.1574556,11.6322222,112.6666667,346.9777778,328.1111111,21.2555556,9.5177778,161.1111111,2.72\n'

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
    """Membaca PNM dengan aman; simulator tidak berhenti jika berkas CSV belum di-upload.

    Hanya kolom yang diizinkan yang diteruskan ke dashboard. Data konsumsi PNM
    sengaja tidak dibaca, ditampilkan, atau dipakai dalam perhitungan.
    """
    try:
        if not PNM_PATH.is_file():
            raise FileNotFoundError(str(PNM_PATH))
        df = pd.read_csv(PNM_PATH)
        if not set(PNM_COLUMNS).issubset(df.columns):
            raise ValueError("Kolom CSV PNM tidak lengkap")
        df = df.loc[:, PNM_COLUMNS].copy()
        if df.empty:
            raise ValueError("CSV PNM kosong")
        return df, "file GitHub"
    except (OSError, ValueError, pd.errors.ParserError):
        # Ini salinan data hasil audit PNM yang sama, bukan dataset sintetis.
        fallback = pd.read_csv(io.StringIO(PNM_FALLBACK_CSV))
        return fallback.loc[:, PNM_COLUMNS].copy(), "salinan tertanam (fallback)"

@st.cache_data(show_spinner=False, ttl=3600, max_entries=12)
def model(settings: Settings):
    """Cache hasil solver antar rerun; hanya bergantung pada input simulasi."""
    return run_sweep(settings)


def line_chart(df, y, title, axis_label, percent=False, nominal=False, profile=None):
    fig = go.Figure()
    for series, group in df.groupby("series", sort=False):
        c = COLORS["B0"] if series == "B0 REFERENSI" else COLORS["scenario"]
        fig.add_trace(go.Scatter(x=group["rpm"],y=group[y], mode="lines+markers",
                                 name=series, line=dict(color=c,width=3), marker=dict(size=7),
                                 hovertemplate="RPM %{x}<br>Nilai %{y:.3f}<extra>%{fullData.name}</extra>"))
    # Referensi pabrikan: titik spesifikasi + envelope interpolasi sederhana.
    # Bukan titik uji Toyota pada setiap RPM.
    if nominal and y in ("torque_nm", "power_kw"):
        if profile is None:
            raise ValueError('Profil mesin wajib diberikan untuk grafik nominal.')
        unique=df.drop_duplicates("rpm").sort_values("rpm")
        nominal_col="rated_torque_nm" if y=="torque_nm" else "rated_power_kw"
        fig.add_trace(go.Scatter(x=unique["rpm"],y=unique[nominal_col],mode="lines",
                       name=f"Envelope {profile.label} — interpolasi asumsi (100% load)",
                       line=dict(color="#64748B",dash="dash",width=1.8)))
        if y=="power_kw":
            rating = f"{profile.rated_power_kw:g} kW @ {profile.rated_rpm:,} rpm"
            fig.add_trace(go.Scatter(x=[profile.rated_rpm],y=[profile.rated_power_kw],
                mode="markers+text",name=f"Rating Toyota {rating}",text=[rating],
                textposition="top left",marker=dict(size=10,symbol="diamond",color="#0F766E")))
    fig.add_vrect(x0=2250,x1=3850,fillcolor="#F59E0B",opacity=.055,line_width=0)
    if profile is not None and profile.rated_rpm < 3800:
        fig.add_vrect(x0=profile.rated_rpm,x1=3850,fillcolor="#DC2626",opacity=.065,line_width=0)
    fig.update_layout(title=title, xaxis_title="RPM",yaxis_title=axis_label,
                      legend=dict(orientation="h",y=-.30,x=0),margin=dict(l=30,r=10,t=55,b=75),height=355,
                      hovermode="x unified")
    if percent:
        fig.update_yaxes(ticksuffix="%")
    return fig


def variant_nominal_chart(field: str):
    """Komparasi envelope 2WD/4WD; hanya titik spesifikasi yang terverifikasi."""
    fig = go.Figure()
    speeds = list(range(1000,3801,100))
    for variant,color in (("2wd", "#2563EB"), ("4wd", "#EA580C")):
        profile = get_engine_profile(variant)
        t = [full_load_torque(n,variant) for n in speeds]
        values = (t if field == "torque_nm" else
                  [val*2*math.pi*n/60000 for val,n in zip(t,speeds)])
        fig.add_trace(go.Scatter(x=speeds,y=values,mode="lines",
            name=f"{profile.label} (envelope asumsi)",line=dict(color=color,width=2.6)))
        if field == "power_kw":
            fig.add_trace(go.Scatter(x=[profile.rated_rpm],y=[profile.rated_power_kw],
                mode="markers",name=f"Rating {profile.label}: {profile.rated_power_kw:g} kW @ {profile.rated_rpm}",
                marker=dict(color=color,size=10,symbol="diamond")))
    fig.add_vrect(x0=2250,x1=3850,fillcolor="#F59E0B",opacity=.05,line_width=0)
    fig.update_layout(title=("Perbandingan kurva nominal torsi — 2WD vs 4WD" if field=="torque_nm"
                             else "Perbandingan kurva nominal daya — 2WD vs 4WD"),
        xaxis_title="RPM",yaxis_title=("Torsi (Nm)" if field=="torque_nm" else "Daya (kW)"),
        height=350,hovermode="x unified",margin=dict(l=25,r=10,t=50,b=78),
        legend=dict(orientation="h",y=-.31,x=0))
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
    keys = ["variant","engine_profile","rpm","series","fuel_pct","torque_nm","power_kw","bmep_bar",
            "imep_bar","fmep_bar","bsfc_g_kwh","bte_pct","fuel_kg_h",
            "fuel_mg_cycle_cyl","lambda_air","pmax_bar","soc_deg","ca50_deg",
            "ign_delay_deg","nox_rel_pct","smoke_rel_pct","co2_ideal_kg_h",
            "energy_residual_pct","limited","rated_torque_nm","rated_power_kw",
            "nominal_load_torque_nm","requested_fuel_mg_cycle_cyl",
            "air_fuel_limit_mg_cycle_cyl","requested_fuel_kg_h",
            "fuel_capped_by_air","above_rated_torque","outside_pnm_rpm",
            "above_rated_rpm","pnm_variant_verified","turbo_pr_assumed","turbo_pr_max_setting"]
    return pd.DataFrame([{k: p.get(k) for k in keys} for p in results["points"]])


def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")


def fmt(v, unit="", decimals=2):
    if v is None or not np.isfinite(v):
        return "—"
    return f"{v:,.{decimals}f} {unit}".strip()

# ================ CONTROLS ================
st.sidebar.title("⚙️ Kendali Simulasi")
st.sidebar.caption("Toyota 2KD-FTV · 2.494 cc · CR 18,5:1 · **V3.1**")
variant_labels = {"2WD awal · 65 kW": "2wd", "4WD awal · 75 kW": "4wd"}
variant_label = st.sidebar.selectbox("Engine Variant", list(variant_labels),
                                     index=0, key="engine_variant_choice",
                                     help="Profil mesin mengikuti rating Toyota yang berbeda, bukan sekadar label penggerak roda.")
variant = variant_labels[variant_label]
selected_profile = get_engine_profile(variant)
st.sidebar.caption(f"**{selected_profile.rated_power_kw:g} kW @ {selected_profile.rated_rpm:,} rpm** · "
                   f"**{selected_profile.max_torque_nm:g} Nm @ "
                   f"{selected_profile.torque_plateau_start_rpm:,}–{selected_profile.torque_plateau_end_rpm:,} rpm**")
st.sidebar.caption("Atur input dan tekan Jalankan simulasi. Mengganti varian langsung memperbarui hasil.")
# V3.1: pilihan mode berada DI LUAR st.form supaya perubahan opsi
# langsung memperbarui penjelasan, tanpa menunggu tombol Jalankan simulasi.
mode_options={
    "Torsi target per RPM (default)":"fixed_torque",
    "Injeksi skenario = B0 pada masing-masing RPM":"fixed_injection",
    "Massa injeksi konstan pada seluruh RPM (mg/siklus/silinder)":"fixed_mass_cycle",
    "Laju aliran bahan bakar konstan pada seluruh RPM (kg/jam)":"fixed_fuel_flow",
}
mode_help={
    "fixed_torque": (
        "**Mode 1 — Torsi target per RPM**\n\n"
        "**Yang dijaga:** torsi target mengikuti persentase beban terhadap "
        "kurva torsi referensi varian mesin pada setiap RPM.\n\n"
        "**Cara kerja:** model mencari jumlah injeksi B0 dan bahan bakar skenario "
        "secara terpisah agar torsi target tercapai, jika memungkinkan.\n\n"
        "**Cocok untuk:** membandingkan kebutuhan bahan bakar, BSFC, dan BTE "
        "pada torsi yang sama. Kurva torsi/daya B0 dan B50 dapat hampir berhimpit."
    ),
    "fixed_injection": (
        "**Mode 2 — Massa skenario mengikuti B0 pada setiap RPM**\n\n"
        "**Yang dijaga:** massa injeksi B0 dan bahan bakar skenario "
        "**sama pada RPM yang sedang dihitung**.\n\n"
        "**Cara kerja:** model mencari injeksi B0 untuk torsi target di masing-masing RPM, "
        "lalu memakai massa yang sama untuk bahan bakar skenario. "
        "**Massa injeksi masih berubah antar-RPM**.\n\n"
        "**Cocok untuk:** membandingkan respons torsi/daya saat sifat bahan bakar "
        "diganti dengan suplai massa yang sama pada titik RPM tersebut."
    ),
    "fixed_mass_cycle": (
        "**Mode 3 — Massa injeksi per siklus konstan**\n\n"
        "**Yang dijaga:** massa injeksi dalam **mg/siklus/silinder** sama untuk "
        "B0, skenario, dan seluruh RPM.\n\n"
        "**Akibatnya:** total laju bahan bakar **kg/jam meningkat seiring RPM** "
        "(jika target injeksi tercapai). Misal 30 mg/siklus/silinder: "
        "7,20 kg/jam pada 2.000 RPM dan 12,24 kg/jam pada 3.400 RPM.\n\n"
        "**Cocok untuk:** analisis respons mesin terhadap RPM dengan massa per siklus tetap."
    ),
    "fixed_fuel_flow": (
        "**Mode 4 — Laju aliran bahan bakar konstan**\n\n"
        "**Yang dijaga:** laju total bahan bakar dalam **kg/jam** sama untuk B0, "
        "skenario, dan seluruh RPM.\n\n"
        "**Akibatnya:** massa injeksi **mg/siklus/silinder berkurang saat RPM naik**. "
        "Misal 6 kg/jam: 25 mg/siklus/silinder pada 2.000 RPM dan "
        "14,71 mg/siklus/silinder pada 3.400 RPM.\n\n"
        "**Cocok untuk:** simulasi suplai bahan bakar total yang dibatasi."
    ),
}
mode_label=st.sidebar.selectbox(
    "Mode pengendalian bahan bakar", list(mode_options), index=0,
    key="fuel_control_mode_choice",
    help="Pilih mode untuk langsung melihat keterangannya di bawah menu. "
         "Hasil simulasi baru dihitung setelah klik Jalankan simulasi.",
)
mode=mode_options[mode_label]
st.sidebar.info(mode_help[mode])
st.sidebar.caption(
    "Catatan: mode injeksi ini adalah skenario model, bukan pemetaan ECU "
    "common-rail Toyota yang telah diverifikasi. Jika suplai udara terbatas, "
    "injeksi aktual dapat lebih rendah daripada nilai yang diminta."
)

with st.sidebar.form("simulation_input"):
    rpm=st.number_input("Putaran mesin (rpm)",min_value=1000,max_value=3800,value=2000,step=50)
    load=st.slider("Beban relatif terhadap torsi referensi (%)", min_value=10,max_value=100,value=50,step=5,
                   help="Beban 100% mengacu pada envelope torsi profil 2WD/4WD yang dipilih, bukan data ECU aktual.")
    fixed_mg=30.0
    fixed_flow=6.0
    if mode=="fixed_mass_cycle":
        fixed_mg=st.number_input("Massa injeksi TETAP (mg/siklus/silinder)",
                       min_value=2.0,max_value=100.0,value=30.0,step=1.0)
    elif mode=="fixed_fuel_flow":
        fixed_flow=st.number_input("Laju massa bahan bakar TETAP (kg/jam total mesin)",
                       min_value=0.5,max_value=100.0,value=6.0,step=0.5)
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
                              max_value=2.2,value=selected_profile.boost_pr_max_assumed,
                              step=.05,key=f"boost_pr_{variant}",
                              help="Nilai 2WD dan 4WD merupakan asumsi model, bukan compressor map/hasil ECU.")
        intake_c=st.number_input("Temperatur udara masuk lingkungan (°C)",min_value=10,max_value=55,value=32,step=1)
        soi=st.number_input("Main SOI pada beban 100% (°CA ATDC)",min_value=-25.0,
                             max_value=10.0,value=-6.0,step=1.0)
        pilot=st.checkbox("Aktifkan koreksi pilot injection (asumsi)",value=True)
    submitted=st.form_submit_button("▶ Jalankan simulasi",type="primary",use_container_width=True)

settings=Settings(variant=variant,rpm=int(rpm),load_pct=float(load),b_pct=b_pct,mode=mode,
                  fixed_mg_cycle_cyl=float(fixed_mg),fixed_fuel_kg_h=float(fixed_flow),
                  lhv_b0=float(lhv0),lhv_b100=float(lhv100),
                  cn_override=float(cn) if cn_user else None,
                  pressure_ratio_max=float(prmax),intake_temp_k=float(intake_c)+273.15,
                  soi_deg=float(soi),pilot_enabled=bool(pilot),
                  fuel_scheme="biodiesel" if blend_mode.startswith("Biodiesel") else "ppo",
                  ppo_pct=ppo_pct,b50_pct=b50_pct)

if ("sim_result" not in st.session_state or submitted
    or st.session_state["sim_result"]["settings"].variant != variant):
    try:
        with st.spinner("Menghitung siklus 0D dengan integrator Heun RK2..."):
            sim=model(settings)
        st.session_state["sim_result"]=sim
        st.session_state["run_time"]=datetime.now().strftime("%d/%m/%Y %H:%M")
        hist=st.session_state.get("history",[])
        scenario=sim["focus"]["scenario"]
        hist.insert(0,{"waktu":st.session_state["run_time"],"variant":settings.variant,
                       "rpm":settings.rpm,
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
active_profile=sim["profile"]
ref=sim["focus"]["reference"]
sc=sim["focus"]["scenario"]
frame=clean_df(sim)
pnm, pnm_source=load_pnm()

st.markdown(f"""
<div class="hero">
  <small>ONLINE ENGINE LAB · PHYSICS-BASED MODEL</small>
  <h1>Toyota 2KD-FTV Engine Simulator</h1>
  <p>Simulasi interaktif Toyota 2KD-FTV {active_profile.label}:
     {active_profile.rated_power_kw:g} kW @ {active_profile.rated_rpm:,} rpm, tanpa machine learning.</p>
  <div class="hero-tags"><span>{active_profile.label}</span><span>4 silinder · 2.494 cc</span>
    <span>CR 18,5:1</span><span>Heun RK2</span><span>B0–B100</span><span>Cloud V3.1 · Dual Variant</span></div>
</div>
""",unsafe_allow_html=True)
if actual != settings:
    st.info("Input di sisi kiri telah berubah tetapi hasil masih berasal dari simulasi sebelumnya. Klik **Jalankan simulasi** untuk memperbarui.")

st.markdown(f"""<div class="appnote"><strong>Skenario:</strong> {sc['series']} ·
<strong>{active_profile.label}</strong> · <strong>{actual.rpm:,} rpm</strong> · <strong>{actual.load_pct:g}% beban</strong> ·
<strong>{next((label for label,value in {
 'Torsi target per RPM':'fixed_torque',
 'Injeksi skenario sama dengan B0 per RPM':'fixed_injection',
 'Massa injeksi sama untuk semua RPM':'fixed_mass_cycle',
 'Laju bahan bakar sama untuk semua RPM':'fixed_fuel_flow'
}.items() if value==actual.mode),'mode tak dikenal')}</strong>.
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
    st.caption(f"Profil aktif: **{active_profile.label}** · boost PR asumsi maksimum **{sc['turbo_pr_max_setting']:.2f}** · "
               "rating pabrikan adalah input acuan, bukan titik validasi independen.")
    if sc["limited"]:
        st.warning("Target simulasi tidak sepenuhnya tercapai atau jumlah bahan bakar dibatasi oleh asumsi udara/AFR. Periksa grafik jumlah injeksi dan pengaturan boost.")
    if actual.rpm>2250:
        st.info("RPM fokus di luar rentang data PNM (1.250–2.250 rpm). Hasil adalah model 0D, bukan validasi PNM.")
    if actual.rpm>active_profile.rated_rpm:
        st.warning("RPM fokus berada di atas rated power RPM profil yang dipilih. Envelope di area ini hanya asumsi dan tidak terverifikasi.")
    if sc["fuel_properties"].get("flash_c", 100) < 52:
        st.warning("Flash point campuran diperkirakan di bawah 52 °C. Ini hanya pemeriksaan ilustratif, bukan penetapan kelayakan bahan bakar. Jangan menguji campuran pada mesin tanpa evaluasi keselamatan dan mutu yang memadai.")
    col1,col2=st.columns(2)
    with col1:
        st.plotly_chart(line_chart(frame,"torque_nm","Torsi terhadap putaran","Torsi (Nm)",nominal=True,profile=active_profile),use_container_width=True)
    with col2:
        st.plotly_chart(line_chart(frame,"power_kw","Daya terhadap putaran","Daya (kW)",nominal=True,profile=active_profile),use_container_width=True)
    st.caption("Konsumsi bahan bakar, BSFC, dan BTE adalah hasil model. Fuel consumption PNM tidak dibaca. Identitas varian PNM belum dikonfirmasi sehingga PNM tidak digunakan untuk kalibrasi khusus 2WD/4WD.")

with tabs[1]:
    col1,col2=st.columns(2)
    for col,field,name,unit in ((col1,"bsfc_g_kwh","BSFC model","g/kWh"),
                                (col2,"bte_pct","BTE model","%")):
        with col: st.plotly_chart(line_chart(frame,field,name,unit),use_container_width=True)
    col1,col2=st.columns(2)
    with col1: st.plotly_chart(line_chart(frame,"fuel_kg_h","Konsumsi bahan bakar MODEL","kg/jam"),use_container_width=True)
    with col2: st.plotly_chart(line_chart(frame,"bmep_bar","BMEP model","bar"),use_container_width=True)
    st.info(f"**Profil {active_profile.label}:** rating Toyota "
            f"**{active_profile.rated_power_kw:g} kW pada {active_profile.rated_rpm:,} rpm**; "
            f"torsi maksimum {active_profile.max_torque_nm:g} Nm pada "
            f"{active_profile.torque_plateau_start_rpm:,}–{active_profile.torque_plateau_end_rpm:,} rpm. "
            "Kurva penghubung antartitik spesifikasi merupakan **interpolasi asumsi**, bukan dynotest Toyota.")
    if any(frame["above_rated_rpm"]):
        st.warning(f"{active_profile.label} memiliki titik sweep di atas rated RPM "
                   f"({active_profile.rated_rpm:,}). Titik tersebut untuk eksplorasi saja; "
                   "bukan klaim batas putaran maksimum/karakteristik ECU.")
    with st.expander("Bandingkan envelope nominal 2WD vs 4WD (bukan data dynotest)"):
        a,b=st.columns(2)
        with a: st.plotly_chart(variant_nominal_chart("torque_nm"),use_container_width=True)
        with b: st.plotly_chart(variant_nominal_chart("power_kw"),use_container_width=True)
        st.caption("Titik rating dan plateau berasal dari Toyota; nilai pada RPM lain adalah interpolasi/ekstrapolasi asumsi.")
    st.subheader("Audit definisi injeksi & kondisi operasi")
    st.caption("Grafik ini wajib diperiksa bersama kurva daya. 'Injeksi tetap' tidak selalu berarti laju bahan bakar tetap. Dua grafik berikut menggunakan massa injeksi AKTUAL sesudah pembatasan udara pada model.")
    c1,c2=st.columns(2)
    with c1: st.plotly_chart(line_chart(frame,"fuel_mg_cycle_cyl","Massa per siklus per silinder","mg/siklus/silinder"),use_container_width=True)
    with c2: st.plotly_chart(line_chart(frame,"fuel_kg_h","Laju massa total mesin (hasil model)","kg/jam"),use_container_width=True)
    capped=frame[frame["fuel_capped_by_air"]==True]  # noqa: E712
    exceeds=frame[frame["above_rated_torque"]==True]  # noqa: E712
    if len(exceeds):
        st.warning(f"Terdapat {len(exceeds)} titik yang menghasilkan torsi lebih dari 102% envelope nominal. Ini hasil skenario injeksi terbuka, bukan titik operasi yang sudah dijamin mampu dicapai ECU/mesin.")
    if len(capped):
        st.warning(f"Terdapat {len(capped)} titik yang dibatasi asumsi udara/AFR. Pada titik itu jumlah injeksi atau laju bahan bakar yang diminta TIDAK bisa dijaga konstan; lihat kolom 'requested' di CSV.")
    if actual.mode=='fixed_torque':
        st.info("**Torsi target per RPM:** besar torsi ditentukan dari persentase envelope nominal, kemudian massa injeksi dicari melalui iterasi. Kemiripan kurva B0–B50 adalah konsekuensi kontrol torsi, bukan prediksi efek bahan bakar terhadap daya maksimum.")
    elif actual.mode=='fixed_injection':
        st.info("**Skenario = B0 di masing-masing RPM:** jumlah injeksi B0 disetel ulang untuk setiap RPM agar mencapai torsi target; B50 menggunakan jumlah yang sama pada RPM tersebut. Karena itu massa injeksi TIDAK konstan sepanjang sweep RPM.")
    elif actual.mode=='fixed_mass_cycle':
        st.info(f"**Massa injeksi benar-benar konstan:** target {actual.fixed_mg_cycle_cyl:g} mg/siklus/silinder pada seluruh RPM untuk kedua bahan bakar. Jika tidak dibatasi udara, laju massa bahan bakar naik sebanding RPM. Setelan boost masih ditentukan oleh parameter beban, bukan ECU aktual.")
    else:
        st.info(f"**Laju bahan bakar benar-benar konstan:** target {actual.fixed_fuel_kg_h:g} kg/jam pada seluruh RPM untuk kedua bahan bakar. Massa per siklus turun ~1/RPM. Jika dibatasi udara, target aliran tidak akan tercapai pada beberapa titik.")
    st.caption("Rentang data PNM berhenti pada 2.250 rpm dan identitas varian PNM belum dipastikan. Titik model menggunakan profil 2WD/4WD terpilih beserta asumsi matematis masing-masing.")
    st.subheader("Tabel audit hasil versus envelope")
    audit_cols=["variant","series","rpm","torque_nm","power_kw","rated_torque_nm","rated_power_kw","fuel_mg_cycle_cyl","requested_fuel_mg_cycle_cyl","fuel_kg_h","requested_fuel_kg_h","fuel_capped_by_air","above_rated_torque","outside_pnm_rpm","above_rated_rpm","limited"]
    st.dataframe(frame[audit_cols].round(3),hide_index=True,use_container_width=True)

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
    if pnm_source != "file GitHub":
        st.warning("File `data/pnm_b0_b50.csv` belum ditemukan atau tidak sesuai di repository GitHub. Dashboard tetap berjalan dengan **salinan data PNM tertanam** yang identik dengan dataset hasil audit sebelumnya. Untuk memutakhirkan data PNM, unggah file CSV yang benar ke GitHub.")
    st.warning(f"**Status data PNM: varian mesin pengujian belum dikonfirmasi.** "
               f"Walaupun simulator sedang memilih **{active_profile.label}**, "
               "data PNM **belum dapat diasumsikan mewakili profil 2WD maupun 4WD**. "
               "Kondisi beban pengujian juga belum dipastikan. Grafik hanya pembanding deskriptif, "
               "bukan validasi langsung keluaran model pada varian terpilih.")
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
        st.write(f"Dataset PNM average.xlsx (hasil audit). Sumber yang dimuat: {pnm_source}.")
        st.write("Varian mesin dan kesetaraan beban PNM masih belum diketahui. Hanya dipakai kolom daya, torsi dan emisi. Data fuel consumption **tidak disimpan dan tidak dihitung**.")
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
        data=csv_bytes(frame),file_name=f"simulasi_2KD_FTV_{actual.variant}_V3.csv",mime="text/csv")
    tr=pd.DataFrame(sc["trace"])
    st.download_button("⬇ Unduh kurva silinder skenario (CSV)",
        data=csv_bytes(tr),file_name=f"simulasi_2KD_FTV_{actual.variant}_trace.csv",mime="text/csv")
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
- **Profil Engine Variant V3:** 2WD awal = 65 kW @ 3.800 rpm, 192 Nm @ 1.200–3.000 rpm; 4WD awal = 75 kW @ 3.600 rpm, 260 Nm @ 1.600–2.400 rpm. Geometri dan rasio kompresi sama menurut Toyota New Features (hal. 19).
- **Envelope full load:** nilai di antara plateau torsi dan rating daya dihitung dengan interpolasi linier ASUMSI. Endpoint 1.000 rpm untuk kedua varian serta area 4WD di atas 3.600 rpm juga ASUMSI, bukan titik pengujian; ECU dan sistem turbo masing-masing varian dapat berbeda.
- **Asumsi boost per varian:** PR maksimum 2WD 1,65 dan 4WD 1,80 hanyalah nilai awal skenario; bisa diubah di sidebar. Bukan peta tekanan boost mesin asli. Tanpa data ECU, pengubahan varian TIDAK otomatis memberikan model turbo/injeksi 4WD yang tervalidasi.
- **Mode injeksi:** `fixed_injection` lama berarti massa B50 = B0 *pada setiap RPM* (tidak tetap sepanjang sweep); `fixed_mass_cycle` menjaga mg/siklus/silinder; `fixed_fuel_flow` menjaga kg/jam. Ketiga konsep berbeda.
- **Turbo & pembatasan udara:** fraksi beban di mode fixed-fuel adalah input parameter boost yang belum ditutup dengan umpan balik output aktual. Saat suplai dipotong oleh batas AFR, mode "konstan" tidak lagi tercapai; dashboard memberi peringatan.
- **Rentang PNM:** hanya 1.250–2.250 rpm. **Identitas varian PNM belum terverifikasi** sehingga tidak diklaim cocok untuk 2WD atau 4WD. Data PNM TIDAK digunakan untuk menghitung kurva simulasi > 2.250 rpm; berlaku asumsi model dan profil rating Toyota yang dipilih. Mencapai titik rating pada mode torsi target BUKAN validasi independen.
- **Emisi:** NOx dan smoke hanya indeks relatif; CO₂ merupakan batas ideal neraca karbon, bukan emisi tailpipe.
- **Validasi:** data PNM punya RPM, torsi/daya dan emisi, tetapi belum ada kepastian kondisi beban maupun satuan fuel consumption. Karena itu tidak mengklaim model sudah tervalidasi.
- **Wilayah berlaku:** steady-state, dua profil 2KD-FTV 2WD/4WD generasi awal dan asumsi masing-masing; tidak untuk diagnosis kerusakan atau kepatuhan emisi.
""")
    st.caption("Referensi utama: J.B. Heywood, Internal Combustion Engine Fundamentals; kode starter PPO-M pengguna; dokumen spesifikasi Toyota 2KD-FTV 2WD awal; data PNM dan tabel fuel properties yang pengguna kirim.")

st.divider()
st.caption(f"Toyota 2KD-FTV {active_profile.label} · Engine Lab Cloud V3 | Hasil terakhir: {st.session_state.get('run_time','—')} | Non-ML · Streamlit Community Cloud · Penyimpanan hanya selama sesi")
