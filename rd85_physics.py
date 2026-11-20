"""Model termodinamika 0D satu-zona, Kubota RD85 single cylinder (referensi HTML pengguna).

Basis: Heywood, Internal Combustion Engine Fundamentals; adaptasi dari
ppo_blend_physics.py milik pengguna (PPO starter, 28 September 2026).
- Integrasi Heun (RK2) pada persamaan energi, bukan Euler.
- Campuran B0+B100, B0+PPO, serta B0+PPO+B50 dengan fraksi volume terkunci 100%.
- Data properti dari literatur pengguna bukan kalibrasi/validasi mesin.
- LHV default adalah ASUMSI, bukan 'calorific value' tabel yang belum diverifikasi.
- Cetane *index* tabel sebagai PROXY CN eksploratif, bukan pengukuran CN.
- Korelasi emisi hanya INDEKS RELATIF, bukan prediksi NOx ppm/FSN terukur.
- Satu pengendalian: torsi target per RPM (fixed_torque).
- Input properti komponen serta campuran akhir dapat diubah manual.
- NOx dan smoke hanya INDEKS relatif; CO2 adalah neraca karbon ideal.
- RPM dan hubungan performa di luar titik rating bersifat skenario model.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np

# Kubota RD85 DI menurut acuan HTML; CR/rod length adalah asumsi, belum hasil ukur.
N_CYL = 1
BORE_M = 0.088
STROKE_M = 0.084
CR = 18.0  # ASUMSI menurut notebook RD85
ROD_M = 0.130  # ASUMSI menurut notebook RD85
V_CYL = math.pi * BORE_M**2 * STROKE_M / 4
V_TOTAL = N_CYL * V_CYL
R_AIR = 287.0
THETA = np.arange(-150.0, 130.0 + 0.5, 0.5)
DT = 0.5

# Properti fisik dari tabel literatur pengguna; calorific D240 sengaja TIDAK
# diubah menjadi LHV. Data CI hanya dipakai sebagai PROXY CN secara eksplisit.
REFERENCE_FUELS = {}  # RD85 tidak mengimpor tabel fuel properties 2KD/PNM


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


# Rating RD85 diambil dari file HTML Optimasi_Formulasi_PPO_RD85.
# 8,5 HP @ 2200 rpm; 3,40 kgf.m @ 1600 rpm (konversi 9,80665).
# Interpolasi torsi pada 1000 rpm adalah asumsi (24,5 Nm).
ENGINE_PROFILES: dict[str, EngineProfile] = {
    'rd85': EngineProfile('rd85', 'Kubota RD85 DI (asumsi pembakaran)',
                          8.5*0.7457, 2200, 3.4*9.80665,
                          1600, 1600, 24.5, None, 1.0),
}


def get_engine_profile(variant: str = '2wd') -> EngineProfile:
    try:
        return ENGINE_PROFILES[variant]
    except KeyError as exc:
        raise ValueError(f"Varian mesin tidak dikenal: {variant!r}; pilihan rd85") from exc


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
# PPO/RD85 HTML: Pertadex approx rho=835, CN=53, LHV=43, visc=3, flash=62.
# C/H/O are assumed in absence of laboratory ultimate analysis.
DEFAULT_B0 = FuelComponent(835.0, 3.00, 43.0, 53.0, 62.0, 86.5, 13.5, 0.0)
DEFAULT_B100 = FuelComponent(875.5, 5.77, 40.0, 67.0, 164.5, 77.0, 12.0, 11.0)
DEFAULT_PPO = FuelComponent(805.0, 2.00, 43.6, 42.0, 48.0, 86.0, 14.0, 0.0)
# B50 mengikuti contoh sifat pada notebook RD85; rho, CN, LHV, visc, flash
# adalah nilai REFERENSI notebook, bukan sampel/kalibrasi mesin yang terukur.
# C/H adalah ASUMSI untuk melengkapi mass balance (O=5.6%).
DEFAULT_B50 = FuelComponent(861.0, 3.55, 39.95, 54.7, 92.0, 82.0, 12.4, 5.6)


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
    variant: str = 'rd85'
    rpm: int = 2000
    load_pct: float = 50.0
    b_pct: float = 50.0
    mode: str = 'fixed_torque'  # Hanya mode ini didukung
    lhv_b0: float = 43.0       # asumsi sementara MJ/kg
    lhv_b100: float = 40.0     # asumsi sementara MJ/kg
    cn_override: float | None = None
    pressure_ratio_max: float | None = 1.0
    intake_temp_k: float = 305.0
    soi_deg: float = -15.0
    pilot_enabled: bool = False
    fuel_scheme: str = 'biodiesel'  # biodiesel | ppo_b0 | ternary
    ppo_pct: float = 0.0
    b0_pct: float = 100.0  # untuk ternary
    b50_pct: float = 0.0  # untuk ternary
    b50_fuel: FuelComponent | None = None
    b0_fuel: FuelComponent | None = None
    b100_fuel: FuelComponent | None = None
    ppo_fuel: FuelComponent | None = None
    scenario_fuel_override: FuelComponent | None = None


def _vbn(v: float) -> float:
    return 14.534 * math.log(math.log(v + .8)) + 10.975


def fuel_properties(b_pct: float, lhv_b0: float = 43., lhv_b100: float = 40.,
                    cn_override: float | None = None,
                    b0_fuel: FuelComponent | None = None,
                    b100_fuel: FuelComponent | None = None) -> dict:
    """B0+B100 campuran fraksi VOLUME, end-member bisa diisi manual.

    Nilai densitas, viskositas, dan cetane index pada B0/B50/B55/B100
    bisa memakai sumber sifat bahan bakar penelitian lain (bukan pengujian mesin).
    LHV tidak diambil dari calorific value yang basis HHV/LHV-nya belum jelas.
    Nilai manual dari pengguna diprioritaskan bila diberikan.
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
    # Pada RD85 REFERENCE_FUELS kosong; tidak mengimpor tabel 2KD/PNM.
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



def ternary_properties(b0_pct: float, ppo_pct: float, b50_pct: float,
                       b0_fuel: FuelComponent | None = None,
                       ppo_fuel: FuelComponent | None = None,
                       b50_fuel: FuelComponent | None = None,
                       cn_override: float | None = None) -> dict:
    """B0 (Pertadex) + PPO + B50, persentase VOLUME berjumlah 100.

    B50 adalah KOMPONEN AKHIR (bahan bakar premix), bukan B100.
    Perhitungan LHV/C/H/O basis massa, densitas basis volume.
    Viskositas dan CN adalah estimasi mixing-rule; tidak menyatakan stabilitas.
    """
    x = [float(b0_pct), float(ppo_pct), float(b50_pct)]
    if not all(math.isfinite(v) and v >= 0 and v <= 100 for v in x):
        raise ValueError('Semua fraksi ternary wajib antara 0 dan 100%.')
    if abs(sum(x)-100) > 1e-8:
        raise ValueError('Total B0 + PPO + B50 harus tepat 100% volume.')
    prop = mix_fuels([b0_fuel or DEFAULT_B0, ppo_fuel or DEFAULT_PPO,
                      b50_fuel or DEFAULT_B50], [v/100 for v in x],
                      'B0 + PPO + B50: campuran 3 komponen, basis volume')
    prop.update(b_pct=0.0, p_pct=float(ppo_pct),
                b0_pct=float(b0_pct), b50_pct=float(b50_pct),
                recipe=(f'{b0_pct:g}%vol B0 (Pertadex) + '
                        f'{ppo_pct:g}%vol PPO + {b50_pct:g}%vol B50'),
                reported_calorific_mj_kg=None)
    if cn_override is not None:
        prop['cetane_proxy'] = float(cn_override)
        prop['cetane_proxy_basis'] = 'override manual pengguna'
    return prop

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
    """Envelope RD85, memakai titik 1600 dan 2200 RPM dari referensi.

    Torsi pada 1000 RPM diasumsikan 24,5 Nm; antara titik diinterpolasi.
    Tidak merepresentasikan kurva hasil pengujian penuh RD85.
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
    # Di atas 2200 RPM tidak digunakan oleh sweep RD85.
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


def simulate_cycle(settings: Settings, b_pct: float, rpm: float, recipe: bool = False):
    """Siklus 0D steady state dengan iterasi massa injeksi ke torsi target."""
    if recipe and settings.fuel_scheme=='ternary':
        prop=ternary_properties(settings.b0_pct,settings.ppo_pct,settings.b50_pct,
                               settings.b0_fuel,settings.ppo_fuel,settings.b50_fuel,
                               settings.cn_override)
        b_pct=0.0
    elif recipe and settings.fuel_scheme=='ppo_b0':
        prop=ppo_b0_properties(settings.ppo_pct,settings.lhv_b0,settings.lhv_b100,
                               settings.cn_override,settings.b0_fuel,settings.ppo_fuel)
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
    # RD85 referensi naturally-aspirated: PR = 1.0, tanpa boost turbo.
    # Tetapkan PR maks=1 (mode sederhana ini tidak memakai peta aliran udara).
    pr_max = (settings.pressure_ratio_max if settings.pressure_ratio_max is not None
              else profile.boost_pr_max_assumed)
    if not 1 <= pr_max <= 2.5:
        raise ValueError('Rasio tekanan turbo maksimum harus antara 1 dan 2,5.')
    PR = 1.0
    T2 = settings.intake_temp_k
    p_ivc = .98*PR*1e5
    T_ivc = T2+10+15*load
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

    lower = 1e-7
    upper = max_fuel
    cap = integrate(upper)
    lower_result = integrate(lower)
    capped = cap['bmep'] < bmep_target
    if bmep_target < lower_result['bmep']:
        mf = lower
    elif capped:
        mf = upper
    else:
        for _ in range(16):
            mid = (lower+upper)/2
            if integrate(mid)['bmep'] < bmep_target:
                lower = mid
            else:
                upper = mid
        mf = (lower+upper)/2
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
        'air_fuel_limit_mg_cycle_cyl':float(max_fuel*1e6),
        'fuel_capped_by_air':bool(capped),
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
        'fuel_b0_pct':float(prop.get('b0_pct', 100.0-prop.get('p_pct',0.0) if settings.fuel_scheme=='ppo_b0' else 100.0-b_pct)),
        'fuel_b50_pct':float(prop.get('b50_pct',0.0)),
        'fuel_recipe':prop.get('recipe','B0 referensi'),
        'fuel_viscosity_cst':float(prop['viscosity_cst']),
        'cetane_proxy':float(prop['cetane_proxy']),
        'limited':bool(capped or abs(torque-t_target)/max(t_target,1)>.03),
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
    """Jalankan torsi target untuk B0 referensi dan satu skenario campuran."""
    profile = get_engine_profile(settings.variant)
    if settings.mode != 'fixed_torque':
        raise ValueError('Hanya pengendalian torsi target per RPM yang tersedia.')
    if settings.fuel_scheme not in ('biodiesel', 'ppo_b0', 'ternary'):
        raise ValueError('Campuran tersedia: B0+B100, B0+PPO, B0+PPO+B50.')
    if not (1000 <= settings.rpm <= 2200 and 0 < settings.load_pct <= 100):
        raise ValueError('RD85: RPM simulasi dibatasi 1000–2200; beban 0–100%.')
    if not (0 <= settings.b_pct <= 100 and 0 <= settings.ppo_pct <= 100):
        raise ValueError('Persentase campuran harus 0–100% volume.')
    if settings.fuel_scheme == 'ternary':
        if abs(settings.b0_pct+settings.ppo_pct+settings.b50_pct-100) > 1e-8:
            raise ValueError('Total campuran ternary harus tepat 100%.')
    speeds = sorted({1000, 1200, 1400, 1500, 1600, 1800, 2000, 2200,
                     profile.torque_plateau_start_rpm, profile.rated_rpm, settings.rpm})
    points = []
    focus = {}
    for rpm in speeds:
        reference = simulate_cycle(settings, 0, rpm)
        scenario = simulate_cycle(settings, settings.b_pct, rpm, recipe=True)
        rated_torque = full_load_torque(rpm, settings.variant)
        for output in (reference, scenario):
            output['rated_torque_nm'] = rated_torque
            output['rated_power_kw'] = rated_torque*2*math.pi*rpm/60000
            output['nominal_load_torque_nm'] = rated_torque*settings.load_pct/100
            output['above_rated_torque'] = output['torque_nm']>rated_torque*1.02
            output['above_rated_rpm'] = rpm>profile.rated_rpm
        reference['series'] = 'B0 REFERENSI'
        scenario['series'] = (
            f'B0 {settings.b0_pct:g}% + PPO {settings.ppo_pct:g}% + B50 {settings.b50_pct:g}%'
            if settings.fuel_scheme=='ternary'
            else (f'P{settings.ppo_pct:g} (B0+PPO) SKENARIO'
                  if settings.fuel_scheme=='ppo_b0'
                  else f'B{settings.b_pct:g} (B0+B100) SKENARIO'))
        if settings.scenario_fuel_override is not None:
            scenario['series'] += ' [PROPERTI MANUAL]'
        reference['focus'] = scenario['focus'] = (rpm == settings.rpm)
        ref_nox = max(reference['nox_raw'], 1e-30)
        ref_soot = max(reference['smoke_raw'], 1e-30)
        for pt in (reference, scenario):
            pt['nox_rel_pct'] = 100*pt['nox_raw']/ref_nox
            pt['smoke_rel_pct'] = 100*pt['smoke_raw']/ref_soot
            points.append(pt)
        if rpm == settings.rpm:
            focus = {'reference': reference, 'scenario': scenario}
    return {'settings':settings, 'profile':profile, 'points':points,
            'focus':focus, 'rpm_grid':speeds,
            'rated_power_kw':profile.rated_power_kw,'rated_rpm':profile.rated_rpm}
