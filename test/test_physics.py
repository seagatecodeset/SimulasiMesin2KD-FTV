import sys
import math
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import numpy as np
from physics import (Settings,REFERENCE_FUELS,geometry,V_CYL,V_TOTAL,BORE_M,STROKE_M,
                     CR,THETA,fuel_properties,run_sweep,simulate_cycle)

class TestEnginePhysics(unittest.TestCase):
    def test_geometry(self):
        V,_=geometry()
        self.assertAlmostEqual(V_TOTAL*1e6,2494.0,delta=2)
        self.assertAlmostEqual(float(V[np.argmin(abs(THETA))]),V_CYL/(CR-1),places=12)
        # Kurva hanya dari IVC -150° sampai EVO +130°, jadi tidak mencapai BDC 180°.
        self.assertGreater(float(V[0]),float(V[np.argmin(abs(THETA))]))
        self.assertLess(float(max(V)),V_CYL*CR/(CR-1))

    def test_fuel_reference(self):
        for k,p in REFERENCE_FUELS.items():
            a=fuel_properties(k)
            self.assertAlmostEqual(a['density_kg_m3'],p['density'])
            self.assertAlmostEqual(a['viscosity_cst'],p['viscosity'])
            self.assertAlmostEqual(a['cetane_proxy'],p['ci'])
            self.assertEqual(a['reported_calorific_mj_kg'],p['calorific_reported'])
        self.assertAlmostEqual(fuel_properties(0)['lhv_mj_kg'],43)
        self.assertAlmostEqual(fuel_properties(100)['lhv_mj_kg'],40)
        self.assertNotEqual(fuel_properties(0)['lhv_mj_kg'],REFERENCE_FUELS[0]['calorific_reported'])

    def test_rk2_motoring_adiabatic(self):
        # Uji independen order-2, gas ideal gamma konstan, tanpa pembakaran & Qwall.
        V,_=geometry()
        gamma=1.35
        T0=337.8;p0=108440;m=p0*V[0]/(287*T0)
        cv=287/(gamma-1)
        T=np.zeros_like(V);T[0]=T0
        for i in range(len(V)-1):
            dv=V[i+1]-V[i]
            k1=-(m*287*T[i]/V[i])*dv/(m*cv)
            k2=-(m*287*(T[i]+k1)/V[i+1])*dv/(m*cv)
            T[i+1]=T[i]+(k1+k2)/2
        i=np.argmin(abs(THETA))
        p_tdc=m*287*T[i]/V[i]
        analytic=p0*(V[0]/V[i])**gamma
        self.assertLess(abs(p_tdc/analytic-1)*100,1.0)

    def test_energy_residual_all_fuels(self):
        for blend in (0,20,35,50,55,75,100):
            for rpm in (1250,2000,2250,3400):
                for load in (25,50,75):
                    with self.subTest(blend=blend,rpm=rpm,load=load):
                        result=simulate_cycle(Settings(rpm=rpm,load_pct=load,b_pct=blend),blend,rpm)
                        self.assertTrue(math.isfinite(result['power_kw']))
                        self.assertGreater(result['pmax_bar'],1)
                        self.assertLess(result['energy_residual_pct'],1)
                        self.assertGreaterEqual(result['bsfc_g_kwh'],0)
                        self.assertGreaterEqual(result['bte_pct'],0)
                        self.assertLess(result['bte_pct'],100)

    def test_no_pnm_consumption_and_fixed_injection(self):
        s=Settings(rpm=2000,load_pct=50,b_pct=50,mode='fixed_injection')
        results=run_sweep(s)
        ref=results['focus']['reference'];alt=results['focus']['scenario']
        self.assertAlmostEqual(ref['fuel_mg_cycle_cyl'],alt['fuel_mg_cycle_cyl'],places=3)
        self.assertNotAlmostEqual(ref['power_kw'],alt['power_kw'],places=4)
        for pt in results['points']:
            self.assertNotIn('pnm_fuel_consumption',pt)

    def test_ppo_illustrative_scenario(self):
        s=Settings(fuel_scheme='ppo',ppo_pct=30,b50_pct=20,mode='fixed_injection')
        data=run_sweep(s)
        scen=data['focus']['scenario']
        self.assertIn('PPO30',scen['series'])
        self.assertTrue(scen['power_kw']>0)
        self.assertLess(scen['energy_residual_pct'],1)
        self.assertAlmostEqual(scen['fuel_pct'],10) # 20% B50 -> 10% FAME efektif
        with self.assertRaises(ValueError):
            run_sweep(Settings(fuel_scheme='ppo',ppo_pct=80,b50_pct=40))

    def test_fixed_torque(self):
        for blend in (0,50,100):
            run=run_sweep(Settings(rpm=2000,load_pct=50,b_pct=blend,mode='fixed_torque'))
            ref=run['focus']['reference'];alt=run['focus']['scenario']
            self.assertAlmostEqual(alt['torque_nm'],ref['torque_nm'],delta=0.1)

if __name__=='__main__':unittest.main()
