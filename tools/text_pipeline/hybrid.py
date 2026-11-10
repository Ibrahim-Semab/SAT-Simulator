import os,re
os.environ.setdefault('OMP_THREAD_LIMIT','1')
import numpy as np,pytesseract
from pytesseract import Output
from PIL import Image
from difflib import SequenceMatcher
BANK='../../bank/'
MATHCH=re.compile(r'^[=+\-−×÷<>≤≥()|/^*%°,.]+$')
def nw(s):return ''.join(re.findall(r'[a-z0-9]+',s.lower()))
def ocr_words(g,y0,y1,x0=0,x1=None,scale=2):
    x1=x1 or g.shape[1]
    y0=max(0,y0);y1=min(g.shape[0],y1)
    im=Image.fromarray(g[y0:y1,x0:x1]).convert('L')
    im=im.resize((im.width*scale,im.height*scale),Image.LANCZOS)
    d=pytesseract.image_to_data(im,config='--psm 6',output_type=Output.DICT)
    out=[]
    for i,t in enumerate(d['text']):
        t=t.strip()
        if not t or float(d['conf'][i])<0:continue
        l,tp,w,h=d['left'][i],d['top'][i],d['width'][i],d['height'][i]
        out.append(dict(t=t,x0=x0+l/scale,y0=y0+tp/scale,x1=x0+(l+w)/scale,y1=y0+(tp+h)/scale,ln=(d['block_num'][i],d['par_num'][i],d['line_num'][i])))
    return out
def ink_outside(g,words,y0,y1,pad=5):
    reg=(g[y0:y1]<190)
    mask=np.zeros_like(reg)
    for w in words:
        a=max(0,int(w['y0']-y0-pad));b=min(reg.shape[0],int(w['y1']-y0+pad)+1)
        c=max(0,int(w['x0']-pad));d=min(reg.shape[1],int(w['x1']+pad)+1)
        mask[a:b,c:d]=True
    tot=reg.sum()
    return (reg&~mask).sum()/max(1,tot)
def hybrid(g,stem_rect,paras):
    """paras: list of paragraph strings (txt). returns (list of paragraph strings with [[y0,y1,x0,x1]] image markers, info) or (None,reason)"""
    y0,y1=stem_rect
    W=ocr_words(g,y0,y1)
    if not W:return None,'no-ocr'
    tw=[];pid=[]
    for pi,p in enumerate(paras):
        for w in p.split():tw.append(w);pid.append(pi)
    A=[(nw(w),i) for i,w in enumerate(tw) if nw(w)]
    B=[(nw(x['t']),j) for j,x in enumerate(W) if nw(x['t'])]
    sm=SequenceMatcher(None,[a for a,_ in A],[b for b,_ in B],autojunk=False)
    drop=set();groups=[]   # (anchor_txt_word_idx_after (-1=start), [ocr idx range])
    for tag,i1,i2,j1,j2 in sm.get_opcodes():
        if tag=='equal' or tag=='delete':continue
        if tag=='replace':
            a=[x for x,_ in A[i1:i2]];b=[x for x,_ in B[j1:j2]]
            ii1,ii2,jj1,jj2=i1,i2,j1,j2
            changed=True
            while changed and ii1<ii2 and jj1<jj2:
                changed=False
                for ka in range(1,ii2-ii1+1):
                    for kb in range(1,jj2-jj1+1):
                        if ''.join(x for x,_ in A[ii1:ii1+ka])==''.join(x for x,_ in B[jj1:jj1+kb]):
                            ii1+=ka;jj1+=kb;changed=True;break
                        if ''.join(x for x,_ in A[ii2-ka:ii2])==''.join(x for x,_ in B[jj2-kb:jj2]):
                            ii2-=ka;jj2-=kb;changed=True;break
                    if changed:break
            if jj1>=jj2:
                continue            # everything benign
            for k in range(ii1,ii2):drop.add(A[k][1])
            anchor=A[ii1-1][1] if ii1>0 else -1
            groups.append((anchor,B[jj1][1],B[jj2-1][1]));continue
        else:
            anchor=A[i1-1][1] if i1>0 else -1
        groups.append((anchor,B[j1][1],B[j2-1][1]))
    # build groups of ocr word indexes, extend with adjacent math punctuation
    segs=[]
    for anchor,ja,jb in groups:
        while ja>0 and nw(W[ja-1]['t'])=='' and MATHCH.match(W[ja-1]['t']) and W[ja-1]['ln']==W[ja]['ln']:ja-=1
        while jb<len(W)-1 and nw(W[jb+1]['t'])=='' and MATHCH.match(W[jb+1]['t']) and W[jb+1]['ln']==W[jb]['ln']:jb+=1
        idx=list(range(ja,jb+1))
        # split by line
        cur=[idx[0]]
        for j in idx[1:]:
            if W[j]['ln']==W[cur[-1]]['ln']:cur.append(j)
            else:segs.append((anchor,cur));cur=[j]
        segs.append((anchor,cur))
    def rr(s):
        return [min(W[j]['x0'] for j in s),min(W[j]['y0'] for j in s),max(W[j]['x1'] for j in s),max(W[j]['y1'] for j in s)]
    def near(a,b,m=7):
        return not(a[2]+m<b[0] or b[2]+m<a[0] or a[3]+m<b[1] or b[3]+m<a[1])
    textln0={W[j]['ln'] for j in range(len(W)) if nw(W[j]['t'])}
    merged=True
    while merged:
        merged=False
        for i in range(len(segs)):
            for k in range(i+1,len(segs)):
                if W[segs[i][1][0]]['ln']!=W[segs[k][1][0]]['ln'] and near(rr(segs[i][1]),rr(segs[k][1])):
                    # stacked parts of one formula: keep the anchor of the part that sits in a line of text
                    ai,aj=segs[i][0],segs[k][0]
                    ln_i=any(nw(W[j]['t']) and j not in set(x for _,s in segs for x in s) for j in range(len(W)) if W[j]['ln']==W[segs[i][1][0]]['ln'])
                    anc=ai if ln_i else aj
                    segs[i]=(anc,sorted(set(segs[i][1])|set(segs[k][1])));del segs[k];merged=True;break
            if merged:break
    mathidx={j for _,s in segs for j in s}
    # lines that have any text word (for block vs inline)
    textln={W[j]['ln'] for j in range(len(W)) if j not in mathidx and nw(W[j]['t'])}
    # coverage check
    cov=ink_outside(g,W,y0,y1)
    pad=3
    def rect(s):
        return [int(min(W[j]['y0'] for j in s))-pad,int(max(W[j]['y1'] for j in s))+pad,int(min(W[j]['x0'] for j in s))-pad,int(max(W[j]['x1'] for j in s))+pad]
    # emit
    out=[[]]; 
    by_anchor={}
    for a,s in segs:by_anchor.setdefault(a,[]).append(s)
    by_anchor_set=set(by_anchor)
    def emit_segs(a):
        for s in by_anchor.get(a,[]):
            r=rect(s);m='[[%d,%d,%d,%d]]'%tuple(max(0,v) for v in r)
            if not any(W[j]['ln'] in textln for j in s):
                if out[-1]:out.append([])
                out[-1].append(m);out.append([])
            else:out[-1].append(m)
    emit_segs(-1)
    cur_p=pid[0] if pid else 0
    skip_punct=set()
    last_anchor_punct={}
    for a,ss in by_anchor.items():
        last_anchor_punct[a]=set(''.join(re.findall(r'[.,?;:!]+$',W[ss[-1][-1]]['t'])))
    skip_punct=last_anchor_punct.get(-1,set())
    for i,w in enumerate(tw):
        if pid[i]!=cur_p:
            if out[-1]:out.append([])
            cur_p=pid[i]
        if i not in drop:
            if nw(w)=='' and skip_punct and all(c in skip_punct for c in w):
                skip_punct=set()
            else:
                skip_punct=set();out[-1].append(w)
        emit_segs(i)
        if i in by_anchor_set:skip_punct=last_anchor_punct.get(i,set())
    def jn(p):
        o=''
        for t in p:
            if o and not re.fullmatch(r'[.,?!;:)\]”’"%]+',t) and not o.endswith(('(','“','‘','$')):o+=' '
            o+=t
        return o
    res=[jn(p) for p in out if p]
    return res,dict(cov=round(cov,4),nseg=len(segs),dropped=len(drop))
