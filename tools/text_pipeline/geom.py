import json,statistics,csv,sys
import numpy as np
from layout import *
def is_fig(sb):
    return any((b[1]-b[0])>26 for b in sb) or any((b[1]-b[0])<7 and (b[3]-b[2])>300 for b in sb)
def label_end_x(g,band):
    s,e,x0,x1=band
    ink=(g[s:e]<200).any(axis=0)
    xs=np.where(ink)[0]
    # glyph clusters; label "A." is the first cluster(s) before a gap >=5px
    prev=xs[0];end=xs[0]
    for x in xs[1:]:
        if x-prev>=5:break
        prev=x
    # 'A.'-'D.' always end by x=35; a short answer ("B. 0") sits <5px after the label and would be swallowed
    return min(int(prev),35)
def geometry(qid,mode):
    r,g,B=analyse(qid);H,W=g.shape
    sb=r['stem_bands']
    out={'id':qid,'w':W,'h':H,'fig':bool(sb) and is_fig(sb),'nb':len(sb)}
    if not sb: out['err']='no stem';return out
    out['stem']=[max(0,sb[0][0]-4),min(H,sb[-1][1]+4)]
    gaps=[sb[i+1][0]-sb[i][1] for i in range(len(sb)-1)]
    med=statistics.median(gaps) if gaps else 0
    out['para_at']=[i+1 for i,gp in enumerate(gaps) if gp>med+9]   # band index starting a new paragraph
    out['bands']=[list(b) for b in sb]
    if mode=='MCQ':
        ob=r['opt_bands']
        starts=[b for b in ob if b[2]<=28]
        if len(starts)!=4:out['err']='opt starts %d'%len(starts);return out
        rects=[]
        for i,st in enumerate(starts):
            nxt=starts[i+1][0] if i<3 else 10**9
            mine=[b for b in ob if st[0]<=b[0]<nxt]
            lx=label_end_x(g,st)
            rects.append([max(0,st[0]-4),min(H,mine[-1][1]+4),lx+6,min(W,max(b[3] for b in mine)+8)])
        out['opts']=rects
        out['opt_span']=[rects[0][0],rects[-1][1]]
    return out
if __name__=='__main__':
    rows=list(csv.DictReader(open(BANK+'index.csv',encoding='utf-8-sig')))
    res={};errs=[]
    for row in rows:
        m='MCQ' if row['Response Type'].startswith('Multiple') else 'SPR'
        o=geometry(row['Question ID'],m)
        res[row['Question ID']]=o
        if 'err' in o:errs.append((row['Question ID'],o['err']))
    json.dump(res,open('geom.json','w'))
    print(len(res),'errors',errs[:10],len(errs))
