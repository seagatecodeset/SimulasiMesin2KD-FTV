"""Regresi matematika/UX komposisi V6 tanpa ketergantungan Streamlit UI."""
import unittest
import math
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import physics as toy
import rd85_physics as rd
from blend_controls import rebalance_blend


class BlendLockTests(unittest.TestCase):
    def test_rebalance_example(self):
        x={'b0':30,'ppo':50,'b50':20}
        self.assertEqual(sum(x.values()),100)
        for key,target in [('b0',70),('ppo',90),('b50',100),('b0',0),('ppo',0)]:
            new=rebalance_blend({**x,key:target},key)
            self.assertEqual(new[key],target)
            self.assertEqual(sum(new.values()),100)
            self.assertTrue(all(0<=z<=100 for z in new.values()))
    def test_single_component_and_edges(self):
        for values in ({'b0':100,'ppo':0,'b50':0},{'b0':0,'ppo':0,'b50':100},
                       {'b0':0,'ppo':100,'b50':0},{'b0':30,'ppo':50,'b50':20}):
            for key in values:
                for val in (0,1,13,50,99,100):
                    new=rebalance_blend({**values,key:val},key)
                    self.assertEqual(sum(new.values()),100)
                    self.assertEqual(new[key],val)
    def test_invalid_blend(self):
        for val in (-1,101):
            with self.assertRaises(ValueError):
                rebalance_blend({'b0':val,'ppo':0,'b50':100},'b0')


class FuelTests(unittest.TestCase):
    def test_ternary_exact_composition(self):
        for m in (toy,rd):
            a=m.ternary_properties(30,50,20)
            self.assertAlmostEqual(a['density_kg_m3'],.3*m.DEFAULT_B0.density_kg_m3+
                                   .5*m.DEFAULT_PPO.density_kg_m3+.2*m.DEFAULT_B50.density_kg_m3)
            self.assertIn('50%vol PPO',a['recipe'])
            self.assertEqual(a['b50_pct'],20)
    def test_ternary_endpoints(self):
        for m in (toy,rd):
            for a,b,c,base in ((100,0,0,m.DEFAULT_B0), (0,100,0,m.DEFAULT_PPO),
                               (0,0,100,m.DEFAULT_B50)):
                x=m.ternary_properties(a,b,c)
                self.assertAlmostEqual(x['lhv_mj_kg'],base.lhv_mj_kg)
                self.assertAlmostEqual(x['density_kg_m3'],base.density_kg_m3)
    def test_invalid_fractions_never_silently_normalized(self):
        for m in (toy,rd):
            with self.assertRaisesRegex(ValueError,'100'):
                m.ternary_properties(30,60,20)
            with self.assertRaisesRegex(ValueError,'100'):
                m.ternary_properties(20,30,40)
    def test_manual_override_affects_mix(self):
        for m in (toy,rd):
            edited=m.FuelComponent(870,4,40,51,75,84,12,4)
            a=m.ternary_properties(30,50,20)
            b=m.ternary_properties(30,50,20,ppo_fuel=edited)
            self.assertNotAlmostEqual(a['density_kg_m3'],b['density_kg_m3'])
            self.assertNotAlmostEqual(a['lhv_mj_kg'],b['lhv_mj_kg'])


class EngineTests(unittest.TestCase):
    def test_engine_geometry(self):
        self.assertEqual(rd.N_CYL,1)
        self.assertAlmostEqual(rd.V_TOTAL*1e6,510.94,delta=0.1)
        self.assertEqual(toy.N_CYL,4)
        self.assertAlmostEqual(toy.V_TOTAL*1e6,2494.0,delta=1)
        self.assertAlmostEqual(rd.get_engine_profile('rd85').rated_power_kw,6.339,places=2)
    def test_only_fixed_torque(self):
        for m,v in ((toy,'2wd'),(rd,'rd85')):
            with self.assertRaisesRegex(ValueError,'Hanya pengendalian'):
                m.run_sweep(m.Settings(variant=v,mode='fixed_injection'))
    def test_all_fuel_families_all_engines(self):
        for m,v,n in ((toy,'2wd',2000),(toy,'4wd',2000),(rd,'rd85',1600)):
            for fam,kwargs in (('biodiesel',{'b_pct':50}),('ppo_b0',{'ppo_pct':50}),
                               ('ternary',{'b0_pct':30,'ppo_pct':50,'b50_pct':20})):
                with self.subTest(engine=v,blend=fam):
                    res=m.run_sweep(m.Settings(variant=v,rpm=n,load_pct=50,
                                               fuel_scheme=fam,**kwargs))
                    a,b=res['focus']['reference'],res['focus']['scenario']
                    self.assertLess(abs(a['torque_nm']-b['torque_nm']),0.5)
                    self.assertTrue(all(math.isfinite(b[k]) for k in ('power_kw','fuel_kg_h','bte_pct','bsfc_g_kwh')))
                    self.assertLess(b['energy_residual_pct'],1)
                    self.assertEqual(a['nox_rel_pct'],100)
                    self.assertEqual(len(res['points']),2*len(res['rpm_grid']))
                    if fam=='ternary':
                        self.assertEqual(b['fuel_b50_pct'],20)
    def test_no_pnm_or_regression_in_app(self):
        app=(ROOT/'streamlit_app.py').read_text()
        for bad in ('pnm_b0_b50.csv','PNM_FALLBACK_CSV','scheffe(','sklearn'):
            self.assertNotIn(bad,app)
        self.assertIn('v6_ternary_b50',app)
        self.assertIn('on_change=on_ternary_change',app)

if __name__=='__main__':
    unittest.main()
