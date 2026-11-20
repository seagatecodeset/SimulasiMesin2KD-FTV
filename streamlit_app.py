"""V6 diesel simulator — Toyota 2KD-FTV dan Kubota RD85.

Tiga campuran: B0+B100, B0+PPO, B0+PPO+B50 (selalu 100% volume).
Hanya mode torsi target, tanpa eksperimen PNM atau prediksi ML.
NOx/smoke = indeks relatif, CO2 ideal = neraca karbon, bukan emisi terukur.
"""
from __future__ import annotations

from datetime import datetime
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import physics as toyota_model
import rd85_physics as kubota_model
from blend_controls import rebalance_blend
from physics import Settings, FuelComponent, DEFAULT_B0, DEFAULT_B100, DEFAULT_PPO, DEFAULT_B50

st.set_page_config(
    page_title="Diesel Engine Simulator | Toyota 2KD-FTV + Kubota RD85 V6",
    page_icon="⚙️", layout="wide", initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.block-container{padding-top:1.2rem;max-width:1480px;padding-bottom:2.2rem}
.hero{background:linear-gradient(115deg,#10263e,#12566d 57%,#11866d);
      color:white;border-radius:18px;padding:1.5rem 1.8rem;margin-bottom:1.1rem;
      box-shadow:0 9px 22px rgba(10,40,70,.15)}
.hero small{font-size:.75rem;font-weight:800;letter-spacing:.12em;color:#a4f2e5}
.hero h1{color:white;font-size:2.15rem;margin:.45rem 0}
.hero p{color:#e3f0f5;margin:.3rem 0;font-size:.96rem}
.hero-tags{display:flex;gap:.45rem;flex-wrap:wrap;margin-top:.85rem}
.hero-tags span{border-radius:999px;border:1px solid rgba(255,255,255,.3);
 padding:.26rem .65rem;font-size:.73rem;background:rgba(255,255,255,.1)}
.info-band{border-radius:10px;border-left:4px solid #0d9488;background:#eaf8f5;
 color:#153f3b;padding:.7rem .95rem;margin:.55rem 0 1rem}
[data-testid="stMetric"]{border:1px solid #dce7ee;border-radius:12px;
 padding:.8rem .9rem;background:rgba(225,236,242,.12)}
@media(max-width:640px){.hero{padding:1rem}.hero h1{font-size:1.55rem}}
</style>
""", unsafe_allow_html=True)

BLUE = "#2563eb"
ORANGE = "#f97316"

@st.cache_data(show_spinner=False, ttl=3600, max_entries=15)
def compute(settings: Settings):
    if settings.variant == "rd85":
        return kubota_model.run_sweep(settings)
    return toyota_model.run_sweep(settings)


def fmt(x, unit="", decimals=2):
    if x is None or not np.isfinite(x):
        return "—"
    return f"{x:,.{decimals}f} {unit}".strip()


def to_csv(df):
    return df.to_csv(index=False).encode("utf-8-sig")


def flatten_output(result):
    columns = [
        "variant", "engine_profile", "rpm", "series", "fuel_family", "fuel_pct",
        "fuel_b0_pct", "fuel_b50_pct",
        "fuel_p_pct", "fuel_recipe", "target_torque_nm", "torque_nm", "power_kw",
        "bmep_bar", "imep_bar", "fmep_bar", "bsfc_g_kwh", "bte_pct",
        "fuel_kg_h", "fuel_l_h", "fuel_chemical_kw", "fuel_mg_cycle_cyl",
        "fuel_volume_mm3_cycle_cyl", "fuel_density_kg_m3", "fuel_lhv_mj_kg",
        "lambda_air", "pmax_bar", "soc_deg", "ca50_deg", "ign_delay_deg",
        "nox_rel_pct", "smoke_rel_pct", "co2_ideal_kg_h", "energy_residual_pct",
        "rated_torque_nm", "rated_power_kw", "nominal_load_torque_nm",
        "fuel_capped_by_air", "above_rated_torque", "above_rated_rpm", "limited",
        "turbo_pr_assumed", "turbo_pr_max_setting"
    ]
    return pd.DataFrame([{key: point.get(key) for key in columns}
                         for point in result["points"]])


def trend_chart(data, y, title, y_label, profile=None, nominal=False):
    fig=go.Figure()
    for series, group in data.groupby("series", sort=False):
        color=BLUE if series == "B0 REFERENSI" else ORANGE
        fig.add_trace(go.Scatter(
            x=group["rpm"], y=group[y], name=series, mode="lines+markers",
            line=dict(color=color, width=3), marker=dict(size=6),
            hovertemplate="%{x} RPM<br>%{y:.3f}<extra>%{fullData.name}</extra>"
        ))
    if nominal and profile and y in ("torque_nm", "power_kw"):
        unique=data.drop_duplicates("rpm").sort_values("rpm")
        col="rated_torque_nm" if y=="torque_nm" else "rated_power_kw"
        fig.add_trace(go.Scatter(x=unique["rpm"], y=unique[col], mode="lines",
            line=dict(color="#64748b", dash="dash",width=1.5),
            name="Envelope nominal (interpolasi asumsi)"))
        if y == "power_kw":
            fig.add_trace(go.Scatter(
                x=[profile.rated_rpm], y=[profile.rated_power_kw],
                mode="markers", marker=dict(size=10,symbol="diamond",color="#059669"),
                name="Rating daya pabrikan"))
    if profile and profile.rated_rpm < 3800 and profile.key != "rd85":
        fig.add_vrect(x0=profile.rated_rpm,x1=3850,
                      fillcolor="#ef4444",opacity=.055,line_width=0)
    fig.update_layout(title=title,xaxis_title="Putaran mesin (RPM)",yaxis_title=y_label,
                      height=350,margin=dict(l=25,r=12,t=52,b=80),
                      legend=dict(orientation="h",x=0,y=-.29),hovermode="x unified")
    return fig


def crank_chart(ref, scenario, field, title, yunit):
    fig=go.Figure()
    for point, color in ((ref, BLUE),(scenario, ORANGE)):
        tr=pd.DataFrame(point["trace"])
        fig.add_trace(go.Scatter(x=tr["theta_deg"],y=tr[field],mode="lines",
                                 line=dict(color=color,width=2.5),name=point["series"]))
    fig.add_vline(x=0,line_dash="dot",line_color="gray")
    fig.update_layout(title=title,xaxis_title="Sudut engkol (°CA, TMA = 0)",
        yaxis_title=yunit,height=355,margin=dict(l=25,r=12,t=52,b=80),
        legend=dict(orientation="h",x=0,y=-.29),hovermode="x unified")
    return fig


def fuel_editor(label, prefix, default: FuelComponent) -> FuelComponent:
    """Editor dalam form; masukan baru dihitung ketika Jalankan ditekan."""
    with st.expander(label,expanded=False):
        st.caption("Isi dari pengujian/COA bila tersedia. Nilai awal bukan seluruhnya data terukur.")
        kw={
            "density_kg_m3":st.number_input("Density @15 °C (kg/m³)",500.,1200.,float(default.density_kg_m3),step=1.,key=f"{prefix}_rho"),
            "viscosity_cst":st.number_input("Viskositas @40 °C (mm²/s)",.21,100.,float(default.viscosity_cst),step=.1,key=f"{prefix}_visc"),
            "lhv_mj_kg":st.number_input("LHV (MJ/kg; bukan HHV)",15.,55.,float(default.lhv_mj_kg),step=.2,key=f"{prefix}_lhv"),
            "cetane_proxy":st.number_input("Cetane number / proxy",10.,100.,float(default.cetane_proxy),step=1.,key=f"{prefix}_cn"),
            "flash_c":st.number_input("Flash point (°C)",-50.,300.,float(default.flash_c),step=1.,key=f"{prefix}_flash"),
            "C_pct":st.number_input("Karbon C (% massa)",0.,100.,float(default.C_pct),step=.5,key=f"{prefix}_c"),
            "H_pct":st.number_input("Hidrogen H (% massa)",0.,100.,float(default.H_pct),step=.5,key=f"{prefix}_h"),
            "O_pct":st.number_input("Oksigen O (% massa)",0.,100.,float(default.O_pct),step=.5,key=f"{prefix}_o")
        }
        st.caption("Jumlah C+H+O diharapkan 90–100% massa. Data PPO awal hanya ilustrasi.")
    return FuelComponent(**kw)


# ========= Sidebar: model selection and fixed-torque method =========
st.sidebar.title("⚙️ Pengaturan Simulasi")
st.sidebar.caption("**V6** · Toyota 2KD-FTV & Kubota RD85 · Physics-based 0D")
engine_label=st.sidebar.radio("Pilih simulator mesin", [
    "Toyota 2KD-FTV", "Kubota RD85 (1 silinder)"
],key="v6_engine_family")
is_rd85=engine_label.startswith("Kubota")
model=kubota_model if is_rd85 else toyota_model
if is_rd85:
    variant="rd85"
    st.sidebar.caption("**Kubota RD85 DI** · 88 × 84 mm · ~511 cc · "
                       "8,5 HP @ 2.200 RPM · 33,3 Nm @ 1.600 RPM")
    st.sidebar.warning("RD85: CR=18, connecting rod=130 mm, SOI=-15°CA, "
                       "FMEP dan karakteristik udara adalah **asumsi** dari bahan acuan. "
                       "Bukan data tekanan silinder atau emisi terukur.")
else:
    variant_choices={"2WD awal — 65 kW":"2wd", "4WD awal — 75 kW":"4wd"}
    variant_name=st.sidebar.selectbox("Engine Variant",list(variant_choices),key="v6_engine_variant")
    variant=variant_choices[variant_name]
profile=model.get_engine_profile(variant)
st.sidebar.caption(f"**{profile.rated_power_kw:.2f} kW @ {profile.rated_rpm:,} RPM** · "
                   f"{profile.max_torque_nm:.1f} Nm @ "
                   f"{profile.torque_plateau_start_rpm:,} RPM")
st.sidebar.info("**Metode tetap: Torsi Target per RPM.** "
                "Massa injeksi B0 dan campuran dicari agar torsi target sama; "
                "torsi/daya cenderung serupa ketika target tercapai. "
                "Yang perlu dibandingkan adalah kebutuhan bahan bakar, BTE, BSFC, "
                "pembakaran dan indeks emisi relatif.")
blend_labels=[
    "1 · B0 (Pertadex) + B100 (Biodiesel)",
    "2 · B0 (Pertadex) + PPO",
    "3 · B0 (Pertadex) + PPO + B50 (ternary)"
]
blend_label=st.sidebar.radio("Jenis campuran bahan bakar",blend_labels,key="v6_blend_family")
fuel_scheme=("biodiesel" if blend_label==blend_labels[0] else
             "ppo_b0" if blend_label==blend_labels[1] else "ternary")

# Tiga slider harus berada DI LUAR st.form agar nilainya segera saling mengunci.
blend_keys={"b0":"v6_ternary_b0","ppo":"v6_ternary_ppo","b50":"v6_ternary_b50"}
for component,default in (("b0",30),("ppo",50),("b50",20)):
    if blend_keys[component] not in st.session_state:
        st.session_state[blend_keys[component]]=default

def on_ternary_change(changed: str) -> None:
    values={c:int(st.session_state[k]) for c,k in blend_keys.items()}
    updated=rebalance_blend(values,changed)
    for c,k in blend_keys.items():
        st.session_state[k]=updated[c]

b0_pct=100.0; ppo_pct=0.0; b50_pct=0.0; b_pct=0.0
if fuel_scheme=="ternary":
    st.sidebar.markdown("**Komposisi campuran (% volume)**")
    st.sidebar.caption("Geser salah satu komponen; dua lainnya otomatis menyesuaikan "
                       "secara proporsional. Total selalu **100%**.")
    for component,label in (("b0","B0 / Pertadex"),("ppo","PPO"),("b50","B50 / Biodiesel 50%")):
        st.sidebar.slider(label,0,100,step=1,key=blend_keys[component],
                          on_change=on_ternary_change,args=(component,))
    b0_pct=float(st.session_state[blend_keys["b0"]])
    ppo_pct=float(st.session_state[blend_keys["ppo"]])
    b50_pct=float(st.session_state[blend_keys["b50"]])
    st.sidebar.success(f"B0 {b0_pct:.0f}% + PPO {ppo_pct:.0f}% + B50 {b50_pct:.0f}% "
                       f"= **{b0_pct+ppo_pct+b50_pct:.0f}%**")
    st.sidebar.caption("B50 dihitung sebagai komponen **premix** yang sudah jadi. "
                       "Angka ini bukan B100. Tidak ada komponen yang boleh melebihi total.")
with st.sidebar.expander("✍️ Fuel Properties Manual",expanded=False):
    edit_components=st.checkbox("Edit properti komponen bahan bakar",key="v6_edit_components")
    edit_final=st.checkbox("Override properti campuran akhir hasil lab",key="v6_edit_final")

with st.sidebar.form(f"v6_simulation_form_{variant}"):
    default_rpm=1600 if is_rd85 else 2000
    rpm_max=2200 if is_rd85 else 3800
    rpm=int(st.number_input("RPM fokus",min_value=1000,max_value=rpm_max,
                             value=default_rpm,step=50,key=f"v6_rpm_{variant}"))
    load=int(st.slider("Beban (% dari torsi nominal)",10,100,50,5,
        help="Beban = fraksi torsi nominal envelope model, bukan pengukuran load ECU.",
        key=f"v6_load_{variant}"))
    if fuel_scheme=="biodiesel":
        b_pct=float(st.slider("B100 dalam B0 (% volume)",0,100,50,5,key="v6_binary_b"))
        b0_pct=100-b_pct
        st.caption(f"B{b_pct:g}: {b0_pct:g}%vol Pertadex + {b_pct:g}%vol B100")
    elif fuel_scheme=="ppo_b0":
        ppo_pct=float(st.slider("PPO dalam B0 (% volume)",0,100,50,5,key="v6_binary_p"))
        b0_pct=100-ppo_pct
        st.caption(f"P{ppo_pct:g}: {b0_pct:g}%vol Pertadex + {ppo_pct:g}%vol PPO")
    else:
        st.caption("Komposisi ternary diatur melalui tiga slider di atas; "
                   "perhitungan menggunakan jumlah terkunci 100%.")
    f0=f100=fppo=f50=None
    default_b0=model.DEFAULT_B0
    default_b100=model.DEFAULT_B100
    default_ppo=model.DEFAULT_PPO
    default_b50=model.DEFAULT_B50
    if edit_components:
        st.markdown("**Properti komponen (manual)**")
        f0=fuel_editor("B0 (Pertadex)",f"v6_{variant}_b0",default_b0)
        if fuel_scheme=="biodiesel":
            f100=fuel_editor("B100 (Biodiesel)",f"v6_{variant}_b100",default_b100)
        elif fuel_scheme=="ppo_b0":
            fppo=fuel_editor("PPO",f"v6_{variant}_ppo",default_ppo)
        else:
            fppo=fuel_editor("PPO",f"v6_{variant}_ppo",default_ppo)
            f50=fuel_editor("B50 (komponen premix)",f"v6_{variant}_b50",default_b50)
    final_fuel=(fuel_editor("Campuran akhir terukur",f"v6_{variant}_final",default_b0)
                if edit_final else None)
    with st.expander("Asumsi mesin & pembakaran (lanjutan)"):
        cn_override_enabled=st.checkbox("Override CN/proxy skenario",value=False)
        cn=st.number_input("CN/proxy skenario",10.,100.,55.,step=1.,disabled=not cn_override_enabled)
        if is_rd85:
            pr=1.0
            st.caption("RD85 referensi tanpa turbo; pressure ratio = 1,0.")
        else:
            pr=st.number_input("Rasio tekanan turbo maks. (ASUMSI)",1.,2.2,
                               float(profile.boost_pr_max_assumed),step=.05,key=f"v6_pr_{variant}")
        temp_c=st.number_input("Temperatur lingkungan (°C)",10,55,32,step=1)
        soi=st.number_input("SOI utama (°CA ATDC; asumsi)",-25.,10.,
                            -15. if is_rd85 else -6.,step=1.,key=f"v6_soi_{variant}")
        pilot=st.checkbox("Koreksi injeksi pilot (asumsi)",value=not is_rd85,
                          key=f"v6_pilot_{variant}")
    submitted=st.form_submit_button("▶ Jalankan Simulasi",type="primary",use_container_width=True)

settings=Settings(variant=variant,rpm=rpm,load_pct=float(load),mode="fixed_torque",
    fuel_scheme=fuel_scheme,b_pct=b_pct,ppo_pct=ppo_pct,b0_pct=b0_pct,b50_pct=b50_pct,
    cn_override=float(cn) if cn_override_enabled else None,
    pressure_ratio_max=float(pr),intake_temp_k=float(temp_c)+273.15,
    soi_deg=float(soi),pilot_enabled=bool(pilot),b0_fuel=f0,b100_fuel=f100,
    ppo_fuel=fppo,b50_fuel=f50,scenario_fuel_override=final_fuel)

if ("v6_result" not in st.session_state or submitted or
    st.session_state["v6_result"]["settings"].variant != variant):
    try:
        with st.spinner("Menghitung siklus termodinamika 0D (Heun RK2)..."):
            sim=compute(settings)
        st.session_state["v6_result"]=sim
        st.session_state["v6_time"]=datetime.now().strftime("%d/%m/%Y %H:%M")
        history=st.session_state.get("v6_history",[])
        pt=sim["focus"]["scenario"]
        history.insert(0,{"waktu":st.session_state["v6_time"],
            "mesin":variant,"rpm":rpm,"beban_pct":load,
            "bahan_bakar":pt["series"],"daya_kw":pt["power_kw"],
            "torsi_nm":pt["torque_nm"],"bsfc_g_kwh":pt["bsfc_g_kwh"],
            "bte_pct":pt["bte_pct"],"nox_rel_pct":pt["nox_rel_pct"],
            "smoke_rel_pct":pt["smoke_rel_pct"]})
        st.session_state["v6_history"]=history[:20]
    except (ValueError,OverflowError,ZeroDivisionError,FloatingPointError) as exc:
        st.error(f"Simulasi gagal: {exc}")
        st.stop()

sim=st.session_state["v6_result"]
active=sim["settings"]
engine=sim["profile"]
ref=sim["focus"]["reference"]
sc=sim["focus"]["scenario"]
frame=flatten_output(sim)

engine_title="Kubota RD85" if active.variant=="rd85" else "Toyota 2KD-FTV"
engine_specs=("~511 cc · 1 silinder · CR 18,0 (asumsi)" if active.variant=="rd85"
              else "2.494 cc · 4 silinder · CR 18,5")
st.markdown(f"""
<div class="hero"><small>PHYSICS-BASED DIESEL ENGINE SIMULATOR · V6</small>
<h1>{engine_title} — Engine Simulator</h1>
<p>Model 0D steady-state untuk {engine.label}. Tiga pilihan resep:
B0+B100, B0+PPO, B0+PPO+B50. Simulasi torsi target dengan persamaan termodinamika,
tanpa machine learning.</p>
<div class="hero-tags"><span>{engine.label}</span><span>{engine_specs}</span>
<span>Torsi Target</span><span>3 Keluarga Campuran</span><span>Heun RK2</span><span>V6</span></div></div>
""",unsafe_allow_html=True)
if active != settings:
    st.info("Input di panel kiri sudah berubah. Klik **Jalankan Simulasi** agar hasil diperbarui.")
st.markdown(f"""<div class="info-band"><strong>Simulasi aktif:</strong> {sc['series']} ·
<strong>{engine.label}</strong> · <strong>{active.rpm:,} RPM</strong> ·
<strong>beban {active.load_pct:g}%</strong> · metode torsi target.
Seluruh grafik adalah <strong>hasil model matematis</strong>, bukan pengukuran mesin.</div>""",
unsafe_allow_html=True)

pages=st.tabs(["📊 Ringkasan", "⚡ Performa", "🌫️ Indikator emisi",
               "🔥 Pembakaran 0D", "🛢️ Fuel properties", "📁 Ekspor & metode"])

with pages[0]:
    a,b,c,d=st.columns(4)
    a.metric("Torsi skenario",fmt(sc["torque_nm"],"Nm"),fmt(sc["torque_nm"]-ref["torque_nm"],"Nm"))
    b.metric("Daya skenario",fmt(sc["power_kw"],"kW"),fmt(sc["power_kw"]-ref["power_kw"],"kW"))
    c.metric("BSFC model",fmt(sc["bsfc_g_kwh"],"g/kWh"))
    d.metric("BTE model",fmt(sc["bte_pct"],"%"))
    a,b,c,d=st.columns(4)
    a.metric("BMEP",fmt(sc["bmep_bar"],"bar"))
    b.metric("Bahan bakar",fmt(sc["fuel_kg_h"],"kg/jam"))
    c.metric("NOx relatif B0",fmt(sc["nox_rel_pct"],"%"))
    d.metric("Smoke relatif B0",fmt(sc["smoke_rel_pct"],"%"))
    st.info("**Mengapa torsi dan daya B0–campuran hampir sama?** Model mencari "
            "massa injeksi berbeda untuk mencapai **torsi target yang sama**. "
            "Ini konsekuensi metode pengendalian, bukan bukti bahwa jenis bahan bakar "
            "tidak memengaruhi performa. Amati BSFC, BTE, kebutuhan energi, dan indikator emisi.")
    if sc["limited"] or ref["limited"]:
        st.warning("Pada salah satu bahan bakar, batas suplai udara/energi membuat "
                   "torsi target tidak sepenuhnya tercapai. Perbandingan tidak lagi pada torsi identik.")
    c1,c2=st.columns(2)
    with c1:
        st.plotly_chart(trend_chart(frame,"power_kw","Kurva daya vs RPM","Daya (kW)",engine,True),use_container_width=True)
    with c2:
        st.plotly_chart(trend_chart(frame,"bsfc_g_kwh","BSFC pada torsi target","BSFC (g/kWh)"),use_container_width=True)

with pages[1]:
    st.subheader("Perbandingan kinerja pada kondisi torsi target")
    for y1,title1,unit1,y2,title2,unit2 in [
        ("torque_nm","Torsi","Nm","power_kw","Daya","kW"),
        ("bmep_bar","BMEP","bar","bte_pct","BTE","%"),
        ("bsfc_g_kwh","BSFC","g/kWh","fuel_kg_h","Laju massa bahan bakar","kg/jam"),
        ("fuel_l_h","Laju volume bahan bakar","L/jam","fuel_chemical_kw","Energi kimia masuk","kW")]:
        c1,c2=st.columns(2)
        with c1: st.plotly_chart(trend_chart(frame,y1,title1,unit1,engine,y1 in ('torque_nm','power_kw')),use_container_width=True)
        with c2: st.plotly_chart(trend_chart(frame,y2,title2,unit2,engine,y2 in ('torque_nm','power_kw')),use_container_width=True)
    st.caption("Torsi referensi mengikuti envelope yang diinterpolasi dari titik rating; "
               "nilai pada RPM selain titik pabrikan merupakan asumsi pemodelan.")
    if frame["limited"].any():
        st.warning("Terdapat titik yang dibatasi oleh model suplai udara; lihat kolom 'limited' pada tabel.")
    st.dataframe(frame[["variant","series","rpm","target_torque_nm","torque_nm","power_kw",
        "bmep_bar","bte_pct","bsfc_g_kwh","fuel_kg_h","fuel_l_h","limited"]].round(3),
        hide_index=True,use_container_width=True)

with pages[2]:
    st.subheader("Indikator emisi dari model — tidak setara dengan emisi terukur")
    c1,c2,c3=st.columns(3)
    c1.metric("NOx relatif B0",fmt(sc["nox_rel_pct"],"%"))
    c2.metric("Smoke relatif B0",fmt(sc["smoke_rel_pct"],"%"))
    c3.metric("CO₂ ideal neraca karbon",fmt(sc["co2_ideal_kg_h"],"kg/jam"))
    st.warning("**NOx dan smoke merupakan indeks relatif berbasis model, dengan B0 = 100% "
               "pada RPM dan beban yang sama; bukan NOx (ppm), smoke (%HSU), atau PM (g/kWh).** "
               "CO₂ mengasumsikan seluruh karbon bahan bakar teroksidasi menjadi CO₂; "
               "bukan pengukuran tailpipe. Model belum menyediakan prediksi CO atau HC yang tervalidasi.")
    a,b=st.columns(2)
    with a: st.plotly_chart(trend_chart(frame,"nox_rel_pct","Indeks NOx relatif B0","% dari B0"),use_container_width=True)
    with b: st.plotly_chart(trend_chart(frame,"smoke_rel_pct","Indeks smoke relatif B0","% dari B0"),use_container_width=True)
    st.plotly_chart(trend_chart(frame,"co2_ideal_kg_h","Laju CO₂ teoritis maksimum (neraca karbon)","kg/jam"),use_container_width=True)
    st.caption("Angka relatif di bawah 100% berarti indeks lebih rendah daripada B0, "
               "tetapi belum membuktikan penurunan emisi aktual mesin.")

with pages[3]:
    a,b=st.columns(2)
    with a: st.plotly_chart(crank_chart(ref,sc,"pressure_bar","Tekanan silinder (0D)","bar"),use_container_width=True)
    with b: st.plotly_chart(crank_chart(ref,sc,"temperature_k","Temperatur silinder (0D)","K"),use_container_width=True)
    a,b=st.columns(2)
    with a: st.plotly_chart(crank_chart(ref,sc,"burned_fraction","Fraksi terbakar kumulatif","fraksi"),use_container_width=True)
    with b:
        st.subheader("Parameter pembakaran pada RPM fokus")
        data=[("Ignition delay (°CA)","ign_delay_deg"),("SOC (°CA ATDC)","soc_deg"),
              ("CA50 (°CA ATDC)","ca50_deg"),("IMEP (bar)","imep_bar"),
              ("FMEP (bar)","fmep_bar"),("Puncak tekanan (bar)","pmax_bar"),
              ("Residual energi (%)","energy_residual_pct")]
        st.dataframe(pd.DataFrame([{"Parameter":label,"B0":ref[k],"Skenario":sc[k]}
                                   for label,k in data]),hide_index=True,use_container_width=True)
        st.caption("Model satu-zona IVC–EVO, bukan data tekanan silinder terukur.")

with pages[4]:
    st.subheader("Properti campuran yang digunakan model")
    prop=sc["fuel_properties"]
    prop_ref=ref["fuel_properties"]
    units={"density_kg_m3":"Density (kg/m³)","viscosity_cst":"Viskositas kinematik (mm²/s)",
           "lhv_mj_kg":"LHV (MJ/kg)","cetane_proxy":"CN/proxy",
           "flash_c":"Flash point (°C) — prediksi campuran", "afr_st":"AFR stoikiometrik (kg/kg)",
           "C_pct":"C (% massa)","H_pct":"H (% massa)","O_pct":"O (% massa)"}
    st.dataframe(pd.DataFrame([{"Parameter":label,"B0 referensi":prop_ref.get(key),
                               "Campuran skenario":prop.get(key)} for key,label in units.items()]),
                 hide_index=True,use_container_width=True)
    st.caption(f"Resep: {prop.get('recipe','—')}. Basis: {prop.get('origin','—')}.")
    # Representasi komposisi aktif. Label B50 pada ternary = komponen premix.
    if active.fuel_scheme == "ternary":
        composition={"Pertadex B0":active.b0_pct,
                     "PPO":active.ppo_pct,"B50 (premix)":active.b50_pct}
    elif active.fuel_scheme == "biodiesel":
        composition={"Pertadex B0":100-active.b_pct,"B100":active.b_pct}
    else:
        composition={"Pertadex B0":100-active.ppo_pct,"PPO":active.ppo_pct}
    comp_items={k:v for k,v in composition.items() if v>0}
    st.plotly_chart(go.Figure(go.Pie(labels=list(comp_items),values=list(comp_items.values()),
        hole=.55,textinfo="label+percent")).update_layout(
        title="Komposisi campuran (% volume)",height=320,
        margin=dict(l=15,r=15,t=45,b=15)),use_container_width=True)
    with st.expander("Sumber dan status properti bahan bakar"):
        if active.variant=="rd85":
            rows=[
                {"Bahan bakar":"Pertadex B0", "Density (kg/m³)":835,
                 "Viskositas (mm²/s)":3.00,"LHV (MJ/kg)":43.00,
                 "CN/proxy":53.0,"Flash (°C)":62.0},
                {"Bahan bakar":"PPO", "Density (kg/m³)":805,
                 "Viskositas (mm²/s)":2.00,"LHV (MJ/kg)":43.60,
                 "CN/proxy":42.0,"Flash (°C)":48.0},
                {"Bahan bakar":"B50 premix", "Density (kg/m³)":861,
                 "Viskositas (mm²/s)":3.55,"LHV (MJ/kg)":39.95,
                 "CN/proxy":54.7,"Flash (°C)":92.0}
            ]
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            st.warning("**Sumber RD85:** file Optimasi_Formulasi_PPO_RD85.html. "
                       "Nilai Pertadex dan PPO adalah tipikal/ilustratif; sebagian "
                       "B50 mengacu pada data yang dinyatakan dalam notebook. "
                       "C/H/O untuk pelengkap model masih asumsi. "
                       "Model test-bed sintetis dalam HTML bukan data validasi.")
        else:
            rows=[{"Biodiesel (%)":pct,"Density @15°C (kg/m³)":d["density"],
                "Viskositas @40°C (mm²/s)":d["viscosity"],
                "Calorific value dilaporkan (MJ/kg)":d["calorific_reported"],
                "Cetane index":d["ci"],"Flash point (°C)":d["flash"]}
                  for pct,d in model.REFERENCE_FUELS.items()]
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            st.warning("Nilai kalor literatur belum dikonfirmasi HHV/LHV dan "
                       "tidak otomatis menjadi LHV model. Cetane index adalah proxy. "
                       "B50 premix ternary default memakai contoh pada referensi RD85 "
                       "dan boleh diganti menggunakan data laboratorium.")
    st.caption("Properti komponen, termasuk B50 premix, dan campuran akhir dapat diubah di sidebar. "
               "Input manual baru berlaku setelah tombol Jalankan Simulasi ditekan.")

with pages[5]:
    st.subheader("Ekspor hasil simulasi")
    st.download_button("⬇ Unduh hasil seluruh RPM (CSV)",to_csv(frame),
                       file_name=f"simulasi_{active.variant}_V6.csv",mime="text/csv")
    st.download_button("⬇ Unduh tekanan & pembakaran RPM fokus (CSV)",
        to_csv(pd.DataFrame(sc["trace"])),file_name=f"kurva_{active.variant}_V6.csv",mime="text/csv")
    fuel_rows=[]
    for label,item in (("B0",active.b0_fuel or model.DEFAULT_B0),
                       ("B100",active.b100_fuel or model.DEFAULT_B100),
                       ("PPO",active.ppo_fuel or model.DEFAULT_PPO),
                       ("B50",active.b50_fuel or model.DEFAULT_B50),
                       ("Campuran akhir hasil model",None),
                       ("Campuran akhir terukur manual",active.scenario_fuel_override)):
        if item is not None:
            fuel_rows.append({"Komponen":label,**vars(item)})
        elif label=="Campuran akhir hasil model":
            fuel_rows.append({"Komponen":label, **{k:prop.get(k) for k in vars(model.DEFAULT_B0)}})
    st.download_button("⬇ Unduh fuel properties (CSV)",to_csv(pd.DataFrame(fuel_rows)),
                       file_name=f"fuel_properties_{active.variant}_V6.csv",mime="text/csv")
    hist=pd.DataFrame(st.session_state.get("v6_history",[]))
    st.subheader("Riwayat skenario (hanya sesi browser)")
    st.dataframe(hist,hide_index=True,use_container_width=True)
    if not hist.empty:
        st.download_button("⬇ Unduh riwayat skenario (CSV)",to_csv(hist),
                           file_name="riwayat_simulasi_V6.csv",mime="text/csv")
    st.subheader("Dasar model dan batasan")
    st.markdown("""
- **Hanya metode torsi target per RPM:** B0 dan skenario diiterasi hingga torsi acuan sama, jika tidak dibatasi udara. Kesamaan daya/torsi adalah akibat pengendalian ini.
- **Tiga keluarga bahan bakar:** B0+B100, B0+PPO, serta B0+PPO+B50 (semuanya basis % volume). Ketiga slider ternary selalu terkunci dengan total tepat 100%. LHV/C/H/O dihitung dari fraksi massa.
- **Geometri:** Toyota 2KD-FTV bore 92 mm, stroke 93,8 mm, CR 18,5, rod 150 mm asumsi. RD85 bore 88 mm, stroke 84 mm, 1 silinder, CR 18, rod 130 mm, SOI -15° asumsi dari notebook referensi.
- **Model pembakaran:** ignition delay Hardenberg–Hase yang dimodifikasi, dua fungsi Wiebe, kalor dinding Woschni, integrator Heun RK2 0,5°CA.
- **Udara & kontrol:** Toyota memakai surrogate boost; RD85 memakai PR=1 (tanpa boost). Kurva torsi antar-rating merupakan interpolasi asumsi, bukan dynotest.
- **BTE/BSFC:** estimasi model, bukan data konsumsi terukur. Properti bahan bakar dan konstanta korelasi memerlukan verifikasi.
- **Emisi:** NOx dan smoke hanya indeks relatif terhadap B0; CO₂ merupakan batas neraca karbon ideal. Tidak ada klaim prediksi konsentrasi emisi aktual atau kelayakan emisi.
- **PPO:** sifat bawaan ilustratif. Kelayakan, keamanan, stabilitas pencampuran, dan pengaruh terhadap injektor harus dinilai terpisah.
- **Keberlakuan:** skenario steady-state Toyota 2KD-FTV 2WD/4WD awal dan Kubota RD85 DI. Referensi HTML RD85 memuat data sintetis dan optimasi Scheffé; bagian tersebut sengaja tidak menjadi data validasi model ini. Bukan alat sertifikasi ataupun pengganti pengujian mesin.
""")
    st.caption("Acuan: J. B. Heywood, Internal Combustion Engine Fundamentals; "
               "dokumen teknis Toyota 2KD-FTV; Optimasi_Formulasi_PPO_RD85.html (geometri dan asumsi RD85, bukan data uji).")

st.divider()
st.caption(f"{engine_title} {engine.label} · V6 · Metode torsi target · "
           f"Pembaruan hasil: {st.session_state.get('v6_time','—')} · "
           "Physics-based · Streamlit Cloud · Tidak menyimpan data di server")
