"""Model termodinamika 0D satu-zona, Toyota 2KD-FTV 2WD / 4WD awal.

Basis: Heywood, Internal Combustion Engine Fundamentals; adaptasi dari
ppo_blend_physics.py milik pengguna (PPO starter, 28 September 2026).
- Integrasi Heun (RK2) pada persamaan energi, bukan Euler.
- Bahan bakar B0/B100 diasumsikan dua endpoint; data sifat bahan bakar dari
  tabel penelitian pengguna adalah REFERENSI LAIN, bukan sampel PNM.
- LHV default adalah ASUMSI, bukan 'calorific value' tabel yang belum diverifikasi.
- Cetane *index* tabel sebagai PROXY CN eksploratif, bukan pengukuran CN.
- Korelasi emisi hanya INDEKS RELATIF, bukan prediksi NOx ppm/FSN terukur.
- Lima mode: fixed_torque, fixed_injection, fixed_mass_cycle,
  fixed_fuel_flow dan fixed_volume_cycle (mm³/siklus/silinder).
- Dua keluarga skenario utama: B0/B100 dan P0/P100 berbasis B0/PPO.
- Properti B0, B100, PPO, serta campuran akhir dapat diisi secara manual.
  PPO ilustratif bukan rekomendasi penggunaan langsung pada kendaraan.
- RPM > 2250 berasal dari asumsi model & spesifikasi pabrikan; BUKAN
  ekstrapolasi data performa PNM yang hanya tersedia hingga 2250 rpm.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np

# 2KD-FTV 2WD/4WD awal: spesifikasi berbeda untuk rated power dan torsi.
N_CYL = 4
BORE_M = 0.092
STROKE_M = 0.0938
CR = 18.5
ROD_M = 0.150  # ASUMSI, panjang connecting rod belum diketahui
V_CYL = math.pi * BORE_M**2 * STROKE_M / 4
V_TOTAL = N_CYL * V_CYL
R_AIR = 287.0
THETA = np.arange(-150.0, 130.0 + 0.5, 0.5)
DT = 0.5

# Properti fisik dari tabel literatur pengguna; calorific D240 sengaja TIDAK
# diubah menjadi LHV. Data CI hanya dipakai sebagai PROXY CN secara eksplisit.
REFERENCE_FUELS = {
    0: dict(density=833.1, viscosity=4.69, ci=48, flash=61.5, calorific_reported=59.79),
    50: dict(density=853.6, viscosity=5.09, ci=59, flash=82.5, calorific_reported=51.26),
    55: dict(density=855.9, viscosity=5.10, ci=58, flash=85.5, calorific_reported=48.73),
    100: dict(density=875.5, viscosity=5.77, ci=67, flash=164.5, calorific_reported=45.23),
}

@dataclass(frozen=True)
class EngineProfile:
    key: str
    label: str
    rated_power_kw: float
    rated_rpm: int
    max_torque_nm: float
    torque_plateau_start_rpm: int
    torque_plateau_end_rpm: int
    torque_1000_nm: float  # ASUMSI — bentuk envelope, bukan titik pengukuran
    torque_3800_nm: float | None  # ASUMSI di atas rated rpm khusus 4WD
    boost_pr_max_assumed: float  # ASUMSI surrogate turbo, bukan ECU/turbo map


# Angka rating/plateau: Toyota, New Features – 2KD-FTV Engine, hal. 19.
# Endpoint 1000 rpm dan 3800 rpm (4WD), bentuk interpolasi dan boost adalah
# ASUMSI pemodelan agar kurva dapat dihitung; bukan data pabrikan per RPM.
ENGINE_PROFILES: dict[str, EngineProfile] = {
    '2wd': EngineProfile('2wd', '2WD awal', 65.0, 3800, 192.0,
                         1200, 3000, 165.0, None, 1.65),
    '4wd': EngineProfile('4wd', '4WD awal (High Version)', 75.0, 3600, 260.0,
                         1600, 2400, 195.0, 178.0, 1.80),
}


def get_engine_profile(variant: str = '2wd') -> EngineProfile:
    try:
        return ENGINE_PROFILES[variant]
    except KeyError as exc:
        raise ValueError(f"Varian mesin tidak dikenal: {variant!r}; pilihan 2wd atau 4wd") from exc


@dataclass(frozen=True)
class FuelComponent:
    """Sifat komponen pada suhu referensi (density @15°C, viskositas @40°C).

    Cetane adalah CN jika diukur; bila masih berasal dari cetane index,
    harus ditandai sebagai proxy pada UI. LHV adalah *lower* heating value.
    """
    density_kg_m3: float
    viscosity_cst: float
    lhv_mj_kg: float
    cetane_proxy: float
    flash_c: float
    C_pct: float
    H_pct: float
    O_pct: float


# Titik awal: referensi tabel pengguna dan asumsi starter kit (bukan sertifikat kualitas).
DEFAULT_B0 = FuelComponent(833.1, 4.69, 43.0, 48.0, 61.5, 86.5, 13.5, 0.0)
DEFAULT_B100 = FuelComponent(875.5, 5.77, 40.0, 67.0, 164.5, 77.0, 12.0, 11.0)
DEFAULT_PPO = FuelComponent(805.0, 1.70, 43.6, 45.0, 45.0, 86.0, 14.0, 0.0)


def validate_fuel(f: FuelComponent, name: str = "bahan bakar") -> None:
    """Validasi numerik; bukan uji kesesuaian terhadap spesifikasi BBM."""
    vals = tuple(vars(f).values())
    if not all(math.isfinite(v) for v in vals):
        raise ValueError(f"{name}: semua properti harus bernilai finite")
    if not 500 <= f.density_kg_m3 <= 1200:
        raise ValueError(f"{name}: density di luar rentang pemeriksaan 500–1200 kg/m³")
    if not 0.21 <= f.viscosity_cst <= 100:
        raise ValueError(f"{name}: viskositas di luar rentang pemeriksaan 0,21–100 cSt")
    if not 15 <= f.lhv_mj_kg <= 55:
        raise ValueError(f"{name}: LHV di luar rentang pemeriksaan 15–55 MJ/kg")
    if not 10 <= f.cetane_proxy <= 100:
        raise ValueError(f"{name}: CN/proxy di luar rentang 10–100")
    if not -50 <= f.flash_c <= 300:
        raise ValueError(f"{name}: flash point di luar rentang pemeriksaan")
    if any(not 0 <= v <= 100 for v in (f.C_pct, f.H_pct, f.O_pct)):
        raise ValueError(f"{name}: nilai C,H,O harus dalam % massa 0–100")
    if not 90 <= f.C_pct + f.H_pct + f.O_pct <= 100.01:
        raise ValueError(f"{name}: jumlah C+H+O harus 90–100% massa; sisanya boleh N/S/abu")


def component_as_properties(f: FuelComponent, origin: str) -> dict:
    validate_fuel(f, origin)
    afr = (11.48*f.C_pct + 34.34*f.H_pct - 4.3*f.O_pct)/100
    if afr <= 0:
        raise ValueError('AFR stoikiometrik tidak valid')
    return dict(density_kg_m3=f.density_kg_m3, viscosity_cst=f.viscosity_cst,
                lhv_mj_kg=f.lhv_mj_kg, cetane_proxy=f.cetane_proxy,
                flash_c=f.flash_c, C_pct=f.C_pct, H_pct=f.H_pct,
                O_pct=f.O_pct, afr_st=afr, origin=origin,
                cetane_proxy_basis='CN / proxy sesuai masukan')


def mix_fuels(components: list[FuelComponent], volume_fractions: list[float],
              origin: str) -> dict:
    """Mixing: rho basis volume; LHV/C/H/O basis massa; Refutas viskositas.
    CN diaproksimasi linier berdasar volume; flash bukan jaminan keselamatan.
    """
    for i, f in enumerate(components):
        validate_fuel(f, f'komponen {i+1}')
    v=np.asarray(volume_fractions, dtype=float)
    if len(components)!=len(v) or np.any(v < 0) or not np.isfinite(v).all() or abs(float(v.sum())-1)>1e-8:
        raise ValueError('Fraksi volume harus nonnegatif dan total 100%.')
    if sum(v > 1e-12)==1:
        idx=int(np.argmax(v))
        return component_as_properties(components[idx], origin)
    rho=np.array([f.density_kg_m3 for f in components])
    density=float(v@rho)
    w=v*rho/density
    lhv=float(w@np.array([f.lhv_mj_kg for f in components]))
    C,H,O=[float(w@np.array([getattr(f,k+'_pct') for f in components])) for k in ('C','H','O')]
    visc=float(math.exp(math.exp((w@np.array([_vbn(f.viscosity_cst) for f in components])-10.975)/14.534))-.8)
    CN=float(v@np.array([f.cetane_proxy for f in components]))
    # Wickey–Chittenden pendekatan prediksi flash; bukan nilai flash point terukur.
    TF=np.array([f.flash_c*9/5+32 for f in components])
    bi=10**(-6.1188+2414/(TF+230.56))
    mix_b=float(v@bi)
    flashF=2414/(math.log10(mix_b)+6.1188)-230.56
    flash=(flashF-32)*5/9
    afr_st=(11.48*C+34.34*H-4.3*O)/100
    return dict(density_kg_m3=density,viscosity_cst=visc,lhv_mj_kg=lhv,
                cetane_proxy=CN,flash_c=float(flash),C_pct=C,H_pct=H,O_pct=O,
                afr_st=afr_st,origin=origin,
                cetane_proxy_basis='interpolasi fraksi volume; hanya proxy',
                mass_fractions=tuple(map(float,w)))


@dataclass(frozen=True)
class Settings:
    variant: str = "2wd"
    rpm: int = 2000
    load_pct: float = 50.0
    b_pct: float = 50.0
    mode: str = "fixed_torque"  # fixed_torque | fixed_injection | fixed_mass_cycle | fixed_fuel_flow
    fixed_mg_cycle_cyl: float = 30.0  # mg/injection-cycle/cylinder, BOTH fuels, all RPM
    fixed_fuel_kg_h: float = 9.0      # kg/h total engine, BOTH fuels, all RPM
    fixed_volume_mm3_cycle_cyl: float = 30.0  # mm³/siklus/silinder, sama kedua bahan bakar
    lhv_b0: float = 43.0   # ASUMSI sementara MJ/kg
    lhv_b100: float = 40.0 # ASUMSI sementara MJ/kg
    cn_override: float | None = None
    pressure_ratio_max: float | None = None  # None -> default ASUMSI spesifik profil 2WD/4WD
    intake_temp_k: float = 305.0      # K
    soi_deg: float = -6.0             # SOI main, ASUMSI (°CA ATDC)
    pilot_enabled: bool = True        # strategi pilot ASSUMSI, verifikasi ECU
    fuel_scheme: str = 'biodiesel'     # biodiesel | ppo
    ppo_pct: float = 0.0              # untuk scheme=ppo
    b50_pct: float = 0.0              # legacy: sisa volume = B0 (mode PPO+B0+B50)
    b0_fuel: FuelComponent | None = None
    b100_fuel: FuelComponent | None = None
    ppo_fuel: FuelComponent | None = None
    scenario_fuel_override: FuelComponent | None = None  # properti campuran akhir terukur


def _vbn(v: float) -> float:
    return 14.534 * math.log(math.log(v + .8)) + 10.975


def fuel_properties(b_pct: float, lhv_b0: float = 43., lhv_b100: float = 40.,
                    cn_override: float | None = None,
                    b0_fuel: FuelComponent | None = None,
                    b100_fuel: FuelComponent | None = None) -> dict:
    """B0+B100 campuran fraksi VOLUME, end-member bisa diisi manual.

    Bila tidak ada input manual, titik 0/50/55/100 dari tabel literatur
    dipertahankan untuk kompatibilitas V3; LHV tidak diambil dari calorific
    value literatur yang basis HHV/LHV-nya belum jelas. Perubahan input manual
    menggunakan mixing rules pada semua konsentrasi sehingga hasil berubah.
    """
    if not 0 <= b_pct <= 100:
        raise ValueError('Biodiesel B harus 0–100% volume')
    f0=b0_fuel or FuelComponent(*[DEFAULT_B0.density_kg_m3,DEFAULT_B0.viscosity_cst,
                                  lhv_b0,DEFAULT_B0.cetane_proxy,DEFAULT_B0.flash_c,
                                  DEFAULT_B0.C_pct,DEFAULT_B0.H_pct,DEFAULT_B0.O_pct])
    f100=b100_fuel or FuelComponent(DEFAULT_B100.density_kg_m3,DEFAULT_B100.viscosity_cst,
                                    lhv_b100,DEFAULT_B100.cetane_proxy,DEFAULT_B100.flash_c,
                                    DEFAULT_B100.C_pct,DEFAULT_B100.H_pct,DEFAULT_B100.O_pct)
    result=mix_fuels([f0,f100],[1-b_pct/100,b_pct/100],
                     'B0+B100: aturan pencampuran komponen')
    result['b_pct']=float(b_pct)
    result['p_pct']=0.0
    result['recipe']=f'B{b_pct:g} = {100-b_pct:g}%vol B0 + {b_pct:g}%vol B100'
    result['reported_calorific_mj_kg']=None
    # Historical output default preserved: tabel B0/B50/B55/B100 dari sumber literatur.
    using_reference=(b0_fuel is None or b0_fuel==DEFAULT_B0) and (b100_fuel is None or b100_fuel==DEFAULT_B100)
    if using_reference and b_pct in REFERENCE_FUELS:
        ref=REFERENCE_FUELS[int(b_pct)]
        result.update(density_kg_m3=ref['density'],viscosity_cst=ref['viscosity'],
                      cetane_proxy=float(ref['ci']),flash_c=ref['flash'],
                      reported_calorific_mj_kg=ref['calorific_reported'],
                      origin='sifat fisik tabel penelitian lain; LHV asumsi model',
                      cetane_proxy_basis='cetane index penelitian lain (proxy)')
    if cn_override is not None:
        result['cetane_proxy']=float(cn_override)
        result['cetane_proxy_basis']='override CN/proxy pengguna'
    return result


def ppo_b0_properties(ppo_pct:float,lhv_b0:float,lhv_b100:float,
                      cn_override:float|None=None,
                      b0_fuel:FuelComponent|None=None,
                      ppo_fuel:FuelComponent|None=None) -> dict:
    """Campuran P0..P100 = B0 + PPO, basis % volume.

    PPO bukan jenis tunggal bahan bakar; data manual sebaiknya berasal dari
    sampel laboratorium. Default PPO hanya contoh starter pengguna.
    """
    if not 0 <= ppo_pct <= 100:
        raise ValueError('PPO P harus 0–100% volume')
    f0=b0_fuel or FuelComponent(DEFAULT_B0.density_kg_m3,DEFAULT_B0.viscosity_cst,
                                 lhv_b0,DEFAULT_B0.cetane_proxy,DEFAULT_B0.flash_c,
                                 DEFAULT_B0.C_pct,DEFAULT_B0.H_pct,DEFAULT_B0.O_pct)
    ppo=ppo_fuel or DEFAULT_PPO
    result=mix_fuels([f0,ppo],[1-ppo_pct/100,ppo_pct/100],
                     'PPO+B0: aturan campuran; PPO default ilustratif' if ppo_fuel is None
                     else 'PPO+B0: masukan properti komponen')
    result.update(b_pct=0.0,p_pct=float(ppo_pct),
                  recipe=f'P{ppo_pct:g} = {100-ppo_pct:g}%vol B0 + {ppo_pct:g}%vol PPO',
                  reported_calorific_mj_kg=None)
    if cn_override is not None:
        result['cetane_proxy']=float(cn_override)
        result['cetane_proxy_basis']='override CN/proxy pengguna'
    return result


def ppo_recipe_properties(ppo_pct:float,b50_pct:float,lhv_b0:float,lhv_b100:float,
                          cn_override:float|None=None,
                          b0_fuel:FuelComponent|None=None,
                          b100_fuel:FuelComponent|None=None,
                          ppo_fuel:FuelComponent|None=None) -> dict:
    """Mode PPO + B0 + B50 V3 (opsi lanjutan) tetap tersedia."""
    if ppo_pct<0 or b50_pct<0 or ppo_pct+b50_pct>100:
        raise ValueError('PPO + B50 harus <= 100%, sisanya B0')
    f0=b0_fuel or FuelComponent(DEFAULT_B0.density_kg_m3,DEFAULT_B0.viscosity_cst,
                                 lhv_b0,DEFAULT_B0.cetane_proxy,DEFAULT_B0.flash_c,
                                 DEFAULT_B0.C_pct,DEFAULT_B0.H_pct,DEFAULT_B0.O_pct)
    f100=b100_fuel or FuelComponent(DEFAULT_B100.density_kg_m3,DEFAULT_B100.viscosity_cst,
                                     lhv_b100,DEFAULT_B100.cetane_proxy,DEFAULT_B100.flash_c,
                                     DEFAULT_B100.C_pct,DEFAULT_B100.H_pct,DEFAULT_B100.O_pct)
    fppo=ppo_fuel or DEFAULT_PPO
    # B50 diwakili oleh properti hasil pencampuran B0+B100; bukan nilai bahan murni.
    b50=fuel_properties(50,lhv_b0,lhv_b100,b0_fuel=f0,b100_fuel=f100)
    f50=FuelComponent(b50['density_kg_m3'],b50['viscosity_cst'],b50['lhv_mj_kg'],
                      b50['cetane_proxy'],b50['flash_c'],b50['C_pct'],b50['H_pct'],b50['O_pct'])
    result=mix_fuels([fppo,f0,f50],[ppo_pct/100,(100-ppo_pct-b50_pct)/100,b50_pct/100],
                     'PPO+B0+B50: pendekatan model (opsi lanjutan)')
    result.update(b_pct=float(0.5*b50_pct), p_pct=float(ppo_pct),
                  reported_calorific_mj_kg=None,
                  recipe=f'PPO {ppo_pct:g}% + B0 {100-ppo_pct-b50_pct:g}% + B50 {b50_pct:g}% volume')
    if cn_override is not None:
        result['cetane_proxy']=float(cn_override)
        result['cetane_proxy_basis']='override CN/proxy pengguna'
    return result

@lru_cache(maxsize=1)
def geometry():
    a = STROKE_M / 2
    R = ROD_M / a
    th = np.deg2rad(THETA)
    s = a * (R + 1 - np.cos(th) - np.sqrt(R*R - np.sin(th)**2))
    vc = V_CYL / (CR-1)
    v = vc + np.pi / 4 * BORE_M**2 * s
    area = 2 * math.pi / 4 * BORE_M**2 + math.pi * BORE_M * (s + vc/(math.pi/4*BORE_M**2))
    return v, area


def full_load_torque(rpm: float, variant: str = '2wd') -> float:
    """Envelope nominal INTERPOLASI, bukan hasil uji torsi per titik RPM.

    Anchors terverifikasi: rating daya, torsi maksimum, dan rentang plateau.
    2WD: 192 Nm @ 1200–3000; 65 kW @ 3800.
    4WD: 260 Nm @ 1600–2400; 75 kW @ 3600.
    Pada 4WD 3600–3800, endpoint 178 Nm adalah asumsi dan DILABELI
    di atas RPM rated; model hanya eksploratif di area itu.
    """
    profile = get_engine_profile(variant)
    n = float(rpm)
    t_rated = profile.rated_power_kw * 1000 * 60 / (2 * math.pi * profile.rated_rpm)
    if n < profile.torque_plateau_start_rpm:
        return float(np.interp(n, [1000, profile.torque_plateau_start_rpm],
                               [profile.torque_1000_nm, profile.max_torque_nm]))
    if n <= profile.torque_plateau_end_rpm:
        return profile.max_torque_nm
    if n <= profile.rated_rpm:
        return float(np.interp(n, [profile.torque_plateau_end_rpm, profile.rated_rpm],
                               [profile.max_torque_nm, t_rated]))
    if profile.torque_3800_nm is not None:
        return float(np.interp(n, [profile.rated_rpm, 3800],
                               [t_rated, profile.torque_3800_nm]))
    # 2WD: di atas rated tidak digunakan oleh sweep default.
    return t_rated


def cv(T):
    """Fungsi kalor spesifik sederhana, J/(kg K), bukan data kimia rinci."""
    return 690.0 + 0.22*np.clip(T,200,4000)


def u_specific(T):
    """Integral cv dT, J/kg (referensi arbitrer nol pada T=0)."""
    return 690.0*T + 0.11*T*T


def wiebe(theta, soc, dur, m, a=6.9):
    return 1-np.exp(-a*np.maximum((theta-soc)/max(dur,0.1),0)**(m+1))


def ignition_delay(cn, T, p_bar, piston_speed):
    # Hardenberg-Hase, menurut starter kit pengguna; p harus > 12.4 bar.
    EA = 618840. / (cn+25)
    expo = EA*(1/(8.3143*T) - 1/17190) + (21.2/max(p_bar-12.4,0.1))**.63
    return float((.36+.22*piston_speed)*math.exp(min(expo,10.0)))


def simulate_cycle(settings: Settings, b_pct: float, rpm: float, m_f_fixed: float | None = None, recipe: bool = False):
    """Jalankan kasus steady-state; bila m_f_fixed=None, iterasi untuk torque target.
    Output berupa angka per silinder dan trace sudut engkol yang konsisten.
    """
    if recipe and settings.fuel_scheme=='ppo_b0':
        prop=ppo_b0_properties(settings.ppo_pct,settings.lhv_b0,settings.lhv_b100,
                               settings.cn_override,settings.b0_fuel,settings.ppo_fuel)
        b_pct=prop['b_pct']
    elif recipe and settings.fuel_scheme=='ppo':
        prop=ppo_recipe_properties(settings.ppo_pct,settings.b50_pct,
                                   settings.lhv_b0,settings.lhv_b100,settings.cn_override,
                                   settings.b0_fuel,settings.b100_fuel,settings.ppo_fuel)
        b_pct=prop['b_pct']
    else:
        prop=fuel_properties(b_pct,settings.lhv_b0,settings.lhv_b100,
                             settings.cn_override if recipe and b_pct != 0 else None,
                             settings.b0_fuel,settings.b100_fuel)
    if recipe and settings.scenario_fuel_override is not None:
        # Nilai terukur campuran akhir, bukan mixing rule; b_pct/p_pct tetap hanya label.
        manual=component_as_properties(settings.scenario_fuel_override,
                                       'properti campuran akhir manual (diutamakan)')
        prop.update(manual)
        prop['reported_calorific_mj_kg']=None
        prop['manual_final_blend']=True
        prop['cetane_proxy_basis']='CN / proxy campuran akhir dari input manual'
        if settings.cn_override is not None:
            prop['cetane_proxy']=float(settings.cn_override)
            prop['cetane_proxy_basis']='override CN dari kotak lanjutan'

    profile = get_engine_profile(settings.variant)
    n = float(rpm)
    t_target = full_load_torque(n, settings.variant) * settings.load_pct/100
    bmep_target = 4*math.pi*t_target/V_TOTAL/1e5
    load = settings.load_pct/100.
    # Conventional turbo dengan map PR surrogate, bukan compressor map terukur.
    pr_max = (settings.pressure_ratio_max if settings.pressure_ratio_max is not None
              else profile.boost_pr_max_assumed)
    if not 1 <= pr_max <= 2.5:
        raise ValueError('Rasio tekanan turbo maksimum harus antara 1 dan 2,5.')
    PR = 1+(pr_max-1)*load**1.2*min(n/profile.rated_rpm,1.0)**.6
    T2 = settings.intake_temp_k*(1+(PR**.286-1)/.7)
    p_ivc = .98*PR*1e5
    T_ivc = T2+15+20*load
    V, area = geometry()
    m_gas = p_ivc*V[0]/(R_AIR*T_ivc)
    m_air = .96*m_gas
    Sp = 2*STROKE_M*n/60
    p_tdc = p_ivc/1e5*(V[0]/V_CYL*(CR-1))**1.35
    T_tdc = T_ivc*(V[0]/V_CYL*(CR-1))**.35
    ID = ignition_delay(prop['cetane_proxy'], T_tdc,p_tdc,Sp)
    ID *= (prop['viscosity_cst']/3)**.08
    ID *= 1+1.5*max(0,51-prop['cetane_proxy'])/10*(1-load)**2
    if settings.pilot_enabled:
        ID = 1+0.45*ID  # koreksi fenomenologis; pilot belum dibuktikan pada unit ini.
    soi = settings.soi_deg +4*(1-load)
    soc = soi+ID
    id_ms = ID/(6*n)*1000
    max_fuel = 1.05*m_air/prop['afr_st']

    def integrate(mf, traces=False):
        mf = max(float(mf),1e-9)
        phi = mf*prop['afr_st']/m_air
        beta = 1-0.926*max(phi,.05)**.37/max(id_ms,.05)**.26
        beta = float(np.clip(beta,.02,.90)) * (.5 if settings.pilot_enabled else 1)
        diff = (30+60*phi)*(n/2000)**.35*(60/110)**.3*(prop['viscosity_cst']/3)**.1*(1-.01*prop['O_pct'])
        xb = beta*wiebe(THETA,soc,7.,2.)+(1-beta)*wiebe(THETA,soc+2,diff,.9)
        lean = 1-min(phi/.5,1)
        theta_q = 5+15*load+(8 if settings.pilot_enabled else 0)
        eta_c = float(np.clip((.995-.030*id_ms*lean)/(1+math.exp(min((soc-theta_q)/1.5,20))),.65,.997))
        Q = eta_c*mf*prop['lhv_mj_kg']*1e6*xb
        temp = np.empty(len(THETA), dtype=float)
        pres = np.empty_like(temp)
        temp[0],pres[0] = T_ivc,p_ivc
        W,Qwall=0.0,0.0
        for i in range(len(THETA)-1):
            dV = V[i+1]-V[i]
            dQ = Q[i+1]-Q[i]
            # Hukum I: dU = Qcomb - Qwall - p dV; RK2 (Heun).
            def rhs(Tlocal,Vlocal,Alocal,dQ_slope,dV_slope):
                p_local=m_gas*R_AIR*Tlocal/Vlocal
                pmot=p_ivc*(V[0]/Vlocal)**1.35
                w = 2.28*Sp+0.00324*(V_CYL*T_ivc/(p_ivc*V[0]))*max(p_local-pmot,0)
                h=3.26*BORE_M**-.2*(p_local/1000)**.8*Tlocal**-.55*w**.8
                Qwall_slope=h*Alocal*(Tlocal-450)/(6*n)
                return (dQ_slope-Qwall_slope-p_local*dV_slope)/(m_gas*cv(Tlocal)),p_local,Qwall_slope
            k1,p1,qw1 = rhs(temp[i],V[i],area[i],dQ/DT,dV/DT)
            Tpred = max(180,temp[i]+DT*k1)
            k2,ppred,qw2 = rhs(Tpred,V[i+1],area[i+1],dQ/DT,dV/DT)
            temp[i+1] = max(180,temp[i]+DT*(k1+k2)/2)
            pres[i+1]=m_gas*R_AIR*temp[i+1]/V[i+1]
            W += 0.5*(pres[i]+pres[i+1])*dV
            Qwall += .5*(qw1+qw2)*DT
        imep = W/V_CYL/1e5
        pmax = max(pres)/1e5
        fmep = .5 + .004*pmax + .09*Sp + .0009*Sp**2  # Chen-Flynn-like, asumsi
        pmep=.05
        bmep = imep-fmep-pmep
        Qtotal = Q[-1]-Q[0]
        delta_u = m_gas*(u_specific(temp[-1])-u_specific(temp[0]))
        residual_pct=abs(Qtotal-W-Qwall-delta_u)/max(Qtotal,1e-8)*100
        return locals()

    requested_mf = m_f_fixed
    if m_f_fixed is None:
        lower = 1e-7
        upper = max_fuel
        cap = integrate(upper)
        lower_result = integrate(lower)
        capped=cap['bmep']<bmep_target
        if bmep_target < lower_result['bmep']:
            mf=lower
        elif capped:
            mf=upper
        else:
            for _ in range(16):
                mid=(lower+upper)/2
                if integrate(mid)['bmep']<bmep_target:
                    lower=mid
                else:
                    upper=mid
            mf=(lower+upper)/2
    else:
        mf=min(max(m_f_fixed,1e-7),max_fuel)
        capped=mf<m_f_fixed
    r=integrate(mf,True)
    # 4-stroke: setiap silinder 1 siklus/2 putaran.
    bmep=r['bmep']
    torque=bmep*1e5*V_TOTAL/(4*math.pi)
    power_kw=torque*2*math.pi*n/60/1000
    fuel_kg_h=mf*N_CYL*n/120*3600
    fuel_l_h=fuel_kg_h*1000/prop['density_kg_m3']
    fuel_volume_mm3_cycle_cyl=mf/prop['density_kg_m3']*1e9
    fuel_chemical_kw=fuel_kg_h*prop['lhv_mj_kg']/3.6
    bsfc=fuel_kg_h*1000/power_kw if power_kw>1e-5 else None
    bte=power_kw/(fuel_kg_h/3600*prop['lhv_mj_kg']*1000) if power_kw>0 else None
    lam=m_air/(mf*prop['afr_st'])
    # Indeks termal NOx (tanpa kalibrasi satuan); hanya relatif terhadap B0.
    T_unburn=T_ivc*(r['pres']/p_ivc)**(.35/1.35)
    T_b=np.minimum(T_unburn + prop['lhv_mj_kg']*1e6/(1+prop['afr_st'])/1600,2900)
    rate=np.sqrt(r['pres']/1e5)*np.exp(-69090/T_b)/np.sqrt(T_b)
    nox_raw=float(np.trapezoid(r['xb']*rate,THETA)/(6*n) * mf*(1+prop['afr_st']))
    # smoke hanya indeks empiris tanpa unit fisik.
    soot_raw=1.9*max(r['phi'],0)**2.5*(1-r['beta'])*max(1-prop['O_pct']/30,.05)*(prop['viscosity_cst']/3)**.25
    ca50 = float(THETA[np.argmax(r['xb']>=0.5)]) if np.any(r['xb']>=0.5) else None
    result={
        'variant':settings.variant, 'engine_profile':profile.label,
        'rpm':int(n), 'fuel_pct':float(b_pct),'torque_nm':float(torque),'power_kw':float(power_kw),
        'bmep_bar':float(bmep),'target_bmep_bar':float(bmep_target),'imep_bar':float(r['imep']),
        'fmep_bar':float(r['fmep']),'fuel_kg_h':float(fuel_kg_h),
        'fuel_l_h':float(fuel_l_h),'fuel_chemical_kw':float(fuel_chemical_kw),
        'fuel_volume_mm3_cycle_cyl':float(fuel_volume_mm3_cycle_cyl),
        'fuel_mg_cycle_cyl':float(mf*1e6),
        'requested_fuel_mg_cycle_cyl':float(requested_mf*1e6) if requested_mf is not None else None,
        'air_fuel_limit_mg_cycle_cyl':float(max_fuel*1e6),
        'requested_fuel_kg_h':float(requested_mf*N_CYL*n/120*3600) if requested_mf is not None else None,
        'fuel_capped_by_air':bool(capped) if requested_mf is not None else bool(capped),
        'bsfc_g_kwh':float(bsfc) if bsfc is not None else None,
        'bte_pct':float(100*bte) if bte is not None else None,
        'lambda_air':float(lam),'phi':float(r['phi']),
        'pmax_bar':float(r['pmax']),'ca50_deg':ca50,
        'soc_deg':float(soc),'ign_delay_deg':float(ID),
        'nox_raw':nox_raw,'smoke_raw':float(soot_raw),
        'co2_ideal_kg_h':float(fuel_kg_h*prop['C_pct']/100*44/12),
        'energy_residual_pct':float(r['residual_pct']),
        'turbo_pr_assumed':float(PR), 'turbo_pr_max_setting':float(pr_max),
        'fuel_lhv_mj_kg':float(prop['lhv_mj_kg']),
        'fuel_density_kg_m3':float(prop['density_kg_m3']),
        'fuel_family':settings.fuel_scheme if recipe else 'reference_b0',
        'fuel_p_pct':float(prop.get('p_pct',0.0)),
        'fuel_recipe':prop.get('recipe','B0 referensi'),
        'fuel_viscosity_cst':float(prop['viscosity_cst']),
        'cetane_proxy':float(prop['cetane_proxy']),
        'limited':bool(capped or abs(torque-t_target)/max(t_target,1)>.03) if m_f_fixed is None else bool(capped),
        'target_torque_nm':float(t_target),
        'fuel_properties':prop,
        'trace': [
            {'theta_deg':round(float(th),2),'pressure_bar':float(p)/1e5,
             'temperature_k':float(T), 'burned_fraction':float(xb)}
            for th,p,T,xb in zip(THETA,r['pres'],r['temp'],r['xb'])
        ]
    }
    return result


def run_sweep(settings: Settings) -> dict:
    profile = get_engine_profile(settings.variant)
    if settings.mode not in ('fixed_torque','fixed_injection','fixed_mass_cycle','fixed_fuel_flow','fixed_volume_cycle'):
        raise ValueError('mode tidak dikenal')
    if settings.mode=='fixed_mass_cycle' and not (0 < settings.fixed_mg_cycle_cyl <= 100):
        raise ValueError('Injeksi konstan harus 0 < mg/siklus/silinder <= 100')
    if settings.mode=='fixed_fuel_flow' and not (0 < settings.fixed_fuel_kg_h <= 100):
        raise ValueError('Laju bahan bakar konstan harus 0 < kg/jam <= 100')
    if settings.mode=='fixed_volume_cycle' and not (0 < settings.fixed_volume_mm3_cycle_cyl <= 150):
        raise ValueError('Volume injeksi konstan harus 0 < mm³/siklus/silinder <= 150')
    if settings.fuel_scheme not in ('biodiesel','ppo','ppo_b0'):
        raise ValueError('Jenis campuran tidak dikenal')
    if settings.fuel_scheme=='ppo' and settings.ppo_pct+settings.b50_pct>100:
        raise ValueError('PPO + B50 tidak boleh lebih dari 100%.')
    # Titik PNM (<=2250) + titik tambahan sampai rating pabrikan 3800.
    # Titik di atas 2250 belum tervalidasi oleh dataset PNM.
    speeds=sorted({1250,1500,1750,2000,2250,2500,2750,3000,3250,3400,3600,3800,
                   profile.torque_plateau_start_rpm, profile.torque_plateau_end_rpm,
                   profile.rated_rpm, settings.rpm})
    points=[]
    focus={}
    for rpm in speeds:
        # Definisi mode sengaja berbeda agar grafik fisik tidak salah ditafsirkan:
        # fixed_torque: B0 dan skenario mencari m_f berbeda untuk T target.
        # fixed_injection: B0 dicari pada T target per RPM, skenario pakai
        #                  massa B0 pada RPM itu (masih BERUBAH antarputaran).
        # fixed_mass_cycle: kedua bahan bakar menerima mg/cycle/cyl konstan.
        # fixed_fuel_flow: kedua bahan bakar menerima kg/h konstan;
        #                  mg/cycle/cyl turun ketika RPM naik.
        if settings.mode=='fixed_volume_cycle':
            volume_m3=settings.fixed_volume_mm3_cycle_cyl*1e-9
            b0_prop=fuel_properties(0,settings.lhv_b0,settings.lhv_b100,
                                    b0_fuel=settings.b0_fuel,b100_fuel=settings.b100_fuel)
            if settings.fuel_scheme=='ppo_b0':
                scenario_prop=ppo_b0_properties(settings.ppo_pct,settings.lhv_b0,settings.lhv_b100,
                                                settings.cn_override,settings.b0_fuel,settings.ppo_fuel)
            elif settings.fuel_scheme=='ppo':
                scenario_prop=ppo_recipe_properties(settings.ppo_pct,settings.b50_pct,
                                                    settings.lhv_b0,settings.lhv_b100,
                                                    settings.cn_override,settings.b0_fuel,
                                                    settings.b100_fuel,settings.ppo_fuel)
            else:
                scenario_prop=fuel_properties(settings.b_pct,settings.lhv_b0,settings.lhv_b100,
                                               settings.cn_override,settings.b0_fuel,settings.b100_fuel)
            if settings.scenario_fuel_override is not None:
                scenario_prop['density_kg_m3']=settings.scenario_fuel_override.density_kg_m3
            reference=simulate_cycle(settings,0,rpm,m_f_fixed=volume_m3*b0_prop['density_kg_m3'])
            scenario=simulate_cycle(settings,settings.b_pct,rpm,
                                    m_f_fixed=volume_m3*scenario_prop['density_kg_m3'],recipe=True)
        elif settings.mode=='fixed_mass_cycle':
            mf_spec=settings.fixed_mg_cycle_cyl*1e-6
            reference=simulate_cycle(settings,0,rpm,m_f_fixed=mf_spec)
            scenario=simulate_cycle(settings,settings.b_pct,rpm,m_f_fixed=mf_spec,
                                    recipe=True)
        elif settings.mode=='fixed_fuel_flow':
            mf_spec=settings.fixed_fuel_kg_h/3600/(N_CYL*rpm/120)
            reference=simulate_cycle(settings,0,rpm,m_f_fixed=mf_spec)
            scenario=simulate_cycle(settings,settings.b_pct,rpm,m_f_fixed=mf_spec,
                                    recipe=True)
        else:
            reference=simulate_cycle(settings,0,rpm)
            scenario=simulate_cycle(settings,settings.b_pct,rpm,
                                m_f_fixed=reference['fuel_mg_cycle_cyl']/1e6 if settings.mode=='fixed_injection' else None,
                                recipe=True)
        # Rating nameplate adalah TITIK ACUAN bukan validasi hasil fisika.
        rated_torque=full_load_torque(rpm,settings.variant)
        for output in (reference, scenario):
            output['rated_torque_nm']=rated_torque
            output['rated_power_kw']=rated_torque*2*math.pi*rpm/(60*1000)
            output['nominal_load_torque_nm']=rated_torque*settings.load_pct/100
            output['above_rated_torque']=output['torque_nm']>rated_torque*1.02
            output['outside_pnm_rpm']=rpm>2250
            output['above_rated_rpm']=rpm>profile.rated_rpm
            output['pnm_variant_verified']=False
        reference['series']='B0 REFERENSI'
        if settings.fuel_scheme=='ppo_b0':
            scenario['series']=f'P{settings.ppo_pct:g} (PPO+B0) SKENARIO'
        elif settings.fuel_scheme=='ppo':
            scenario['series']=(f'PPO{settings.ppo_pct:g}+B0{100-settings.ppo_pct-settings.b50_pct:g}'
                                f'+B50_{settings.b50_pct:g} SKENARIO')
        else:
            scenario['series']=f'B{settings.b_pct:g} SKENARIO'
        if settings.scenario_fuel_override is not None:
            scenario['series']+=' [PROPERTI MANUAL]'
        if settings.mode=='fixed_volume_cycle':
            for point in (reference,scenario):
                point['requested_fuel_volume_mm3_cycle_cyl']=settings.fixed_volume_mm3_cycle_cyl
                point['requested_fuel_l_h']=(settings.fixed_volume_mm3_cycle_cyl*1e-9*
                    point['fuel_density_kg_m3']*N_CYL*rpm/120*3600*1000/point['fuel_density_kg_m3'])
        else:
            for point in (reference,scenario):
                point['requested_fuel_volume_mm3_cycle_cyl']=None
                point['requested_fuel_l_h']=None
        reference['focus']=rpm==settings.rpm; scenario['focus']=rpm==settings.rpm
        ref_nox=max(reference['nox_raw'],1e-30)
        ref_soot=max(reference['smoke_raw'],1e-30)
        for p in (reference,scenario):
            p['nox_rel_pct']=100*p['nox_raw']/ref_nox
            p['smoke_rel_pct']=100*p['smoke_raw']/ref_soot
            points.append(p)
        if rpm==settings.rpm:
            focus={'reference':reference,'scenario':scenario}
    return {'settings':settings,'profile':profile,'points':points,'focus':focus,
            'rpm_grid':speeds,'pnm_rpm_max':2250,
            'rated_power_kw':profile.rated_power_kw,'rated_rpm':profile.rated_rpm}
