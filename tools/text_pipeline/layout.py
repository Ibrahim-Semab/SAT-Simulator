import numpy as np, json, re
from PIL import Image
BANK='../../bank/'
def bands_of(g,thr=200,gap=1):
    ink=g<thr
    rows=ink.any(axis=1)
    out=[];s=None
    for y,v in enumerate(rows):
        if v and s is None:s=y
        if not v and s is not None:out.append([s,y]);s=None
    if s is not None:out.append([s,len(rows)])
    m=[]
    for b in out:
        if m and b[0]-m[-1][1]<gap:m[-1][1]=b[1]
        else:m.append(b)
    res=[]
    for s,e in m:
        cols=np.where(ink[s:e].any(axis=0))[0]
        res.append((s,e,int(cols[0]),int(cols[-1])))
    return res
def load(qid):
    return np.array(Image.open(BANK+'q/'+qid+'.webp').convert('L'))
# templates from b86123af
def make_tpl():
    g=load('b86123af');B=bands_of(g)
    nar=[b for b in B if b[2]<=27 and b[3]-b[2]<75 and b[0]>150]
    q,a=nar[0],nar[1]
    return {'q':g[q[0]:q[1],q[2]:q[3]+1].astype(int),'a':g[a[0]:a[1],a[2]:a[3]+1].astype(int)},(q,a)
TPL,_dbg=make_tpl()
import os
TPL['r']=np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)),'tpl_rationale.npy'))
def match(g,b,tpl):
    s,e,x0,x1=b;th,tw=tpl.shape
    if abs((e-s)-th)>1 or abs((x1-x0+1)-tw)>1 or x0>30:return False
    tm=tpl<160;best=0
    for dy in(-1,0,1):
        for dx in(-1,0,1):
            ys,xs=s+dy,x0+dx
            if ys<0 or xs<0:continue
            c=g[ys:ys+th,xs:xs+tw]
            if c.shape!=tpl.shape:continue
            cm=c<160;u=(cm|tm).sum()
            if u:best=max(best,(cm&tm).sum()/u)
    return best>0.55
def analyse(qid):
    g=load(qid);H,W=g.shape;B=bands_of(g)
    while B and match(g,B[-1],TPL['r']):B=B[:-1]      # trailing 'Rationale' heading
    r={'w':W,'h':H}
    qi=next((i for i,b in enumerate(B) if b[0]>100 and match(g,b,TPL['q'])),None)
    if qi is None:r['err']='no Question label';return r,g,B
    ai=next((i for i,b in enumerate(B) if i>qi and match(g,b,TPL['a'])),None)
    r['qi']=qi;r['ai']=ai
    r['stem_bands']=B[qi+1:(ai if ai is not None else len(B))]
    r['opt_bands']=B[ai+1:] if ai is not None else []
    r['label_bottom']=B[qi][1]
    return r,g,B
if __name__=='__main__':
    print(_dbg)
    import csv
    rows=list(csv.DictReader(open(BANK+'index.csv',encoding='utf-8-sig')))
    fails=[];noA=[]
    for row in rows:
        r,g,B=analyse(row['Question ID'])
        if 'err' in r:fails.append((row['Question ID'],r['err']))
        elif r['ai'] is None and row['Response Type'].startswith('Multiple'):noA.append(row['Question ID'])
        elif r['ai'] is not None and row['Response Type'].startswith('Student'):noA.append(row['Question ID']+'(spr-with-answer)')
    print(len(rows),'fails',len(fails),fails[:5],'noAnswer-label MCQ',len(noA),noA[:8])
