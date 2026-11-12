"""Model termodinamika 0D satu-zona, Toyota 2KD-FTV 2WD awal.

Basis: Heywood, Internal Combustion Engine Fundamentals; adaptasi dari
ppo_blend_physics.py milik pengguna (PPO starter, 28 September 2026).
- Integrasi Heun (RK2) pada persamaan energi, bukan Euler.
- Bahan bakar B0/B100 diasumsikan dua endpoint; data sifat bahan bakar dari
  tabel penelitian pengguna adalah REFERENSI LAIN, bukan sampel PNM.
- LHV default adalah ASUMSI, bukan 'calorific value' tabel yang belum diverifikasi.
- Cetane *index* tabel sebagai PROXY CN eksploratif, bukan pengukuran CN.
- Korelasi emisi hanya INDEKS RELATIF, bukan prediksi NOx ppm/FSN terukur.
- Mode fixed_torque mencari massa bahan bakar, fixed_injection mempertahankan
  massa bahan bakar B0 pada RPM + beban target yang sama.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np

# 2KD-FTV 2WD awal, referensi 65 kW @ 3800; 192 Nm @ 1200..3000 rpm.
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
class Settings:
    rpm: int = 2000
    load_pct: float = 50.0
    b_pct: float = 50.0
    mode: str = "fixed_torque"  # fixed_torque | fixed_injection
    lhv_b0: float = 43.0   # ASUMSI sementara MJ/kg
    lhv_b100: float = 40.0 # ASUMSI sementara MJ/kg
    cn_override: float | None = None
    pressure_ratio_max: float = 1.65  # ASUMSI conventional turbo
    intake_temp_k: float = 305.0      # K
    soi_deg: float = -6.0             # SOI main, ASUMSI (°CA ATDC)
    pilot_enabled: bool = True        # strategi pilot ASSUMSI, verifikasi ECU
    fuel_scheme: str = 'biodiesel'     # biodiesel | ppo
    ppo_pct: float = 0.0              # untuk scheme=ppo
    b50_pct: float = 0.0              # sisa dari 100% adalah Pertamina Dex (B0)


def _vbn(v: float) -> float:
    return 14.534 * math.log(math.log(v + .8)) + 10.975


def fuel_properties(b_pct: float, lhv_b0: float = 43., lhv_b100: float = 40.,
                    cn_override: float | None = None) -> dict:
    """Campur B0/B100 berdasarkan volume; parameter referensi exact dipakai apa adanya.
    Density = linear volume; LHV dan unsur = linear mass; viscosity = Refutas.
    Cetane index diinterpolasi piecewise dari literatur, sebagai proxy CN eksploratif.
    """
    if not 0 <= b_pct <= 100:
        raise ValueError("Persen biodiesel harus 0-100.")
    x = b_pct / 100
    rho0, rho100 = REFERENCE_FUELS[0]['density'], REFERENCE_FUELS[100]['density']
    density = (1 - x) * rho0 + x * rho100
    mass_b100 = x * rho100 / density
    lhv = (1 - mass_b100) * lhv_b0 + mass_b100 * lhv_b100
    viscosity = math.exp(math.exp(( (1-mass_b100)*_vbn(4.69) + mass_b100*_vbn(5.77) - 10.975)/14.534))-.8
    points = np.array(sorted(REFERENCE_FUELS))
    ci = float(np.interp(b_pct, points, [REFERENCE_FUELS[int(p)]['ci'] for p in points]))
    flash = float(np.interp(b_pct, points, [REFERENCE_FUELS[int(p)]['flash'] for p in points]))
    source = 'mixing_rules + literatur CI' 
    # Tepat pada komposisi yang dilaporkan, pakai pengukuran densitas/visko tabel.
    for k in REFERENCE_FUELS:
        if abs(b_pct-k)<1e-9:
            density = REFERENCE_FUELS[k]['density']
            viscosity = REFERENCE_FUELS[k]['viscosity']
            flash = REFERENCE_FUELS[k]['flash']
            source = 'sifat fisik literatur; LHV provisional'
    C = (1-mass_b100)*86.5 + mass_b100*77.0  # persen massa ASUMSI
    H = (1-mass_b100)*13.5 + mass_b100*12.0
    O = (1-mass_b100)*0.0 + mass_b100*11.0
    afr_st = 11.48*C/100 + 34.34*H/100 - 4.3*O/100
    return dict(b_pct=b_pct, density_kg_m3=density, viscosity_cst=viscosity,
                lhv_mj_kg=lhv, cetane_proxy=float(cn_override) if cn_override is not None else ci,
                cetane_proxy_basis='override pengguna' if cn_override is not None else 'proxy cetane index literatur',
                reported_calorific_mj_kg=REFERENCE_FUELS[int(b_pct)]['calorific_reported'] if b_pct in REFERENCE_FUELS else None,
                flash_c=flash, C_pct=C, H_pct=H, O_pct=O, afr_st=afr_st, origin=source)


def ppo_recipe_properties(ppo_pct:float,b50_pct:float,lhv_b0:float,lhv_b100:float,
                          cn_override:float|None=None) -> dict:
    """PPO-M/Dex/B50: properti PPO-M ILUSTRATIF dari starter kit pengguna.
    Komposisi dinyatakan %volume dan disyaratkan jumlah 100. Ini BUKAN
    formulasi tervalidasi/aman untuk dipakai langsung pada kendaraan.
    """
    if ppo_pct<0 or b50_pct<0 or ppo_pct+b50_pct>100:
        raise ValueError('PPO + B50 harus <= 100%, Dex adalah sisanya.')
    x1=ppo_pct/100
    x3=b50_pct/100
    x2=1-x1-x3
    b0=fuel_properties(0,lhv_b0,lhv_b100)
    b50=fuel_properties(50,lhv_b0,lhv_b100)
    # PPO-M sumber: kode contoh pengguna, nilai ilustratif, bukan hasil uji lab.
    ppo=dict(density_kg_m3=805.,lhv_mj_kg=43.6,viscosity_cst=1.70,
             cetane_proxy=45.,flash_c=45.,C_pct=86.,H_pct=14.,O_pct=0.)
    comps=[ppo,b0,b50]
    v=np.array([x1,x2,x3],dtype=float)
    rho=np.array([p['density_kg_m3'] for p in comps])
    density=float(v@rho)
    w=v*rho/density
    LHV=float(w@np.array([p['lhv_mj_kg'] for p in comps]))
    C,H,O=[float(w@np.array([p[k+'_pct'] for p in comps])) for k in ('C','H','O')]
    visc=float(math.exp(math.exp((w@np.array([_vbn(p['viscosity_cst']) for p in comps])-10.975)/14.534))-.8)
    CI=float(v@np.array([p['cetane_proxy'] for p in comps]))
    # Wickey-Chittenden: eksperimental blend flash, berlaku sebagai estimasi saja.
    TF=np.array([p['flash_c']*9/5+32 for p in comps])
    bi=10**(-6.1188+2414/(TF+230.56))
    flashF=2414/(math.log10(float(v@bi))+6.1188)-230.56
    flash=(flashF-32)*5/9
    afr_st=11.48*C/100+34.34*H/100-4.3*O/100
    return dict(b_pct=50*x3,density_kg_m3=density,viscosity_cst=visc,
         lhv_mj_kg=LHV,cetane_proxy=float(cn_override) if cn_override is not None else CI,
         cetane_proxy_basis='override pengguna' if cn_override is not None else 'proxy CI + PPO-M ilustratif',
         reported_calorific_mj_kg=None, flash_c=flash,C_pct=C,H_pct=H,O_pct=O,
         afr_st=afr_st,origin='campuran PPO-M ilustratif; B0/B50 literatur',
         recipe=f'PPO-M {ppo_pct:g}% + Dex {100-ppo_pct-b50_pct:g}% + B50 {b50_pct:g}%')


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


def full_load_torque(rpm: float) -> float:
    """Profil envelope ASUMSI: 192 Nm @1200..3000, 65 kW @3800."""
    t3800 = 65000 * 60 / (2*math.pi*3800)
    if rpm < 1200:
        return float(np.interp(rpm,[1000,1200],[165,192]))
    if rpm <= 3000:
        return 192.0
    return float(np.interp(rpm,[3000,3800],[192,t3800]))


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
    if recipe and settings.fuel_scheme=='ppo':
        prop=ppo_recipe_properties(settings.ppo_pct,settings.b50_pct,
                                   settings.lhv_b0,settings.lhv_b100,settings.cn_override)
        b_pct=prop['b_pct']  # fraksi biodiesel efektif di bahan bakar (bukan PPO).
    else:
        prop = fuel_properties(b_pct, settings.lhv_b0, settings.lhv_b100,
                               settings.cn_override if b_pct != 0 else None)
    n = float(rpm)
    t_target = full_load_torque(n) * settings.load_pct/100
    bmep_target = 4*math.pi*t_target/V_TOTAL/1e5
    load = settings.load_pct/100.
    # Conventional turbo dengan map PR surrogate, bukan compressor map terukur.
    PR = 1+(settings.pressure_ratio_max-1)*load**1.2*(n/3800)**.6
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
        'rpm':int(n), 'fuel_pct':float(b_pct),'torque_nm':float(torque),'power_kw':float(power_kw),
        'bmep_bar':float(bmep),'target_bmep_bar':float(bmep_target),'imep_bar':float(r['imep']),
        'fmep_bar':float(r['fmep']),'fuel_kg_h':float(fuel_kg_h), 'fuel_mg_cycle_cyl':float(mf*1e6),
        'bsfc_g_kwh':float(bsfc) if bsfc is not None else None,
        'bte_pct':float(100*bte) if bte is not None else None,
        'lambda_air':float(lam),'phi':float(r['phi']),
        'pmax_bar':float(r['pmax']),'ca50_deg':ca50,
        'soc_deg':float(soc),'ign_delay_deg':float(ID),
        'nox_raw':nox_raw,'smoke_raw':float(soot_raw),
        'co2_ideal_kg_h':float(fuel_kg_h*prop['C_pct']/100*44/12),
        'energy_residual_pct':float(r['residual_pct']),
        'fuel_lhv_mj_kg':float(prop['lhv_mj_kg']),
        'fuel_density_kg_m3':float(prop['density_kg_m3']),
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
    if settings.mode not in ('fixed_torque','fixed_injection'):
        raise ValueError('mode tidak dikenal')
    if settings.fuel_scheme not in ('biodiesel','ppo'):
        raise ValueError('Jenis campuran tidak dikenal')
    if settings.fuel_scheme=='ppo' and settings.ppo_pct+settings.b50_pct>100:
        raise ValueError('PPO + B50 tidak boleh lebih dari 100%.')
    speeds=sorted({1250,1500,1750,2000,2250,settings.rpm})
    points=[]
    focus={}
    for rpm in speeds:
        # Referensi pada beban yang sama; untuk mode fixed_injection
        # skenario memakai jumlah bahan bakar B0, bukan torsi tetap.
        reference=simulate_cycle(settings,0,rpm)
        scenario=simulate_cycle(settings,settings.b_pct,rpm,
                                m_f_fixed=reference['fuel_mg_cycle_cyl']/1e6 if settings.mode=='fixed_injection' else None,
                                recipe=settings.fuel_scheme=='ppo')
        reference['series']='B0 REFERENSI'
        scenario['series']=(f'PPO{settings.ppo_pct:g}+Dex{100-settings.ppo_pct-settings.b50_pct:g}+B50_{settings.b50_pct:g} SKENARIO'
                            if settings.fuel_scheme=='ppo' else f'B{settings.b_pct:g} SKENARIO')
        reference['focus']=rpm==settings.rpm; scenario['focus']=rpm==settings.rpm
        ref_nox=max(reference['nox_raw'],1e-30)
        ref_soot=max(reference['smoke_raw'],1e-30)
        for p in (reference,scenario):
            p['nox_rel_pct']=100*p['nox_raw']/ref_nox
            p['smoke_rel_pct']=100*p['smoke_raw']/ref_soot
            points.append(p)
        if rpm==settings.rpm:
            focus={'reference':reference,'scenario':scenario}
    return {'settings':settings,'points':points,'focus':focus,'rpm_grid':speeds}
