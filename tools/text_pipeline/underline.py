import re,numpy as np
from difflib import SequenceMatcher
from hybrid import ocr_words,nw
def underlined_ranges(g,rect,para_text):
    """para_text: list of paragraph strings (passage). returns list of [pi,start,end] char ranges or None"""
    y0,y1=rect
    W=ocr_words(g,y0,y1)
    if not W:return None
    ink=g<170
    runm=np.zeros_like(ink)
    reg=ink[max(0,y0-2):y1+12]
    for yy in range(reg.shape[0]):
        row=reg[yy];x=0;n=len(row)
        while x<n:
            if row[x]:
                e=x
                while e<n and row[e]:e+=1
                if e-x>=20:runm[max(0,y0-2)+yy,x:e]=True
                x=e
            else:x+=1
    flags=[]
    for w in W:
        x0,x1=int(w['x0']),int(w['x1']);yb=int(w['y1'])
        strip=runm[max(0,yb-5):yb+9,x0:x1+1]
        flags.append(strip.size>0 and strip.any(axis=0).mean()>=0.5)
    tw=[];pos=[]
    for pi,p in enumerate(para_text):
        for m in re.finditer(r'\S+',p):tw.append(m.group());pos.append((pi,m.start(),m.end()))
    A=[(nw(w),i) for i,w in enumerate(tw) if nw(w)];B=[(nw(x['t']),j) for j,x in enumerate(W) if nw(x['t'])]
    sm=SequenceMatcher(None,[a for a,_ in A],[b for b,_ in B],autojunk=False)
    matched=0;ul=[]
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag=='equal':
            for k in range(i2-i1):
                matched+=1
                if flags[B[j1+k][1]]:ul.append(A[i1+k][1])
    if matched<0.9*len(A):return None
    ul=sorted(set(ul))
    if not ul:return None
    # merge consecutive txt words (allow gaps of unmatched/punctuation words)
    rng=[]
    for i in ul:
        pi,s,e=pos[i]
        if rng and rng[-1][0]==pi and i-rng[-1][3]<=40:rng[-1][2]=e;rng[-1][3]=i
        else:rng.append([pi,s,e,i])
    return [[a,b,c] for a,b,c,_ in rng]
