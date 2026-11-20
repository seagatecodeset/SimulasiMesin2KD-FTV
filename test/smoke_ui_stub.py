"""Pemeriksaan antarmuka menggunakan pengganti Streamlit, BUKAN browser nyata."""
import runpy, sys, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class FakeStreamlit(types.ModuleType):
    def __init__(self, engine, scheme):
        super().__init__('streamlit')
        self.engine=engine;self.scheme=scheme
        self.sidebar=self
        self.session_state={}
        self.chart_count=0;self.error_count=0;self.tab_labels=[]
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def set_page_config(self,**kw): pass
    def markdown(self,*a,**kw): pass
    def caption(self,*a,**kw): pass
    def write(self,*a,**kw): pass
    def title(self,*a,**kw): pass
    def subheader(self,*a,**kw): pass
    def divider(self,*a,**kw): pass
    def info(self,*a,**kw): pass
    def warning(self,*a,**kw): pass
    def success(self,*a,**kw): pass
    def dataframe(self,*a,**kw): pass
    def metric(self,*a,**kw): pass
    def error(self,*a,**kw): self.error_count+=1
    def plotly_chart(self,chart,**kw):
        assert chart.data
        self.chart_count+=1
    def download_button(self,*a,**kw): return False
    def cache_data(self,*a,**kw): return lambda fn:fn
    def form(self,*a,**kw):return self
    def expander(self,*a,**kw):return self
    def spinner(self,*a,**kw):return self
    def columns(self,n,**kw):return [self]*(n if isinstance(n,int) else len(n))
    def tabs(self,labels):self.tab_labels=labels;return [self]*len(labels)
    def selectbox(self,label,options,**kw):
        if label=='Engine Variant':return next(x for x in options if '2WD' in x)
        return options[0]
    def radio(self,label,options,**kw):
        if label=='Pilih simulator mesin':
            return options[1] if self.engine=='rd85' else options[0]
        if label=='Jenis campuran bahan bakar':
            return options[{'biodiesel':0,'ppo_b0':1,'ternary':2}[self.scheme]]
        return options[0]
    def number_input(self,label,*a,**kw):
        return kw.get('value',a[2] if len(a)>=3 else kw.get('min_value',0))
    def slider(self,label,*a,**kw):
        if 'key' in kw and kw['key'] in self.session_state:
            return self.session_state[kw['key']]
        return kw.get('value',a[2] if len(a)>=3 else kw.get('min_value',0))
    def checkbox(self,label,**kw):return kw.get('value',False)
    def form_submit_button(self,*a,**kw): return False
    def stop(self):raise RuntimeError('st.stop')

for engine,scheme in [('2wd','biodiesel'),('2wd','ternary'),('rd85','ppo_b0'),('rd85','ternary')]:
    fake=FakeStreamlit(engine,scheme)
    sys.modules['streamlit']=fake
    runpy.run_path(str(ROOT/'streamlit_app.py'),run_name='__main__')
    st=fake.session_state['v6_result']['settings']
    assert st.variant==engine,(engine,st.variant)
    assert st.fuel_scheme==scheme,(scheme,st.fuel_scheme)
    if scheme=='ternary': assert (st.b0_pct,st.ppo_pct,st.b50_pct)==(30,50,20)
    assert fake.chart_count>=15, fake.chart_count
    assert fake.error_count==0
    assert len(fake.tab_labels)==6
    assert not any('pnm' in x.lower() for x in fake.tab_labels)
    print('OK UI stub',engine,scheme,'charts',fake.chart_count)
