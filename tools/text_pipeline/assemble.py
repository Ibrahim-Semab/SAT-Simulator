import json,re,csv,collections,statistics,sys
BANK='../../bank/'
G=json.load(open('geom.json'));D=json.load(open('parsed.json'));O=json.load(open('ocr.json'))
import os
HY=json.load(open('hybrid.json')) if os.path.exists('hybrid.json') else {}
FULL=144
def norm(s):return (s or '').replace('\x02','-').replace('\xa0',' ').replace('‑','-')
def toks(s):return collections.Counter(re.findall(r'[a-z0-9]+',norm(s).lower()))
def flat_offsets(lines):
    out='';offs=[]
    for l in lines:
        l=l.strip()
        if out=='' and not offs:offs.append(0);out=l
        else:
            out+='' if out.endswith(('-','—')) else ' '
            offs.append(len(out));out+=l
    return out,offs
def join_lines(lines):return flat_offsets(lines)[0]
START=re.compile(r'(?:Which (?:choice|finding|quotation|statement|detail|sentence|of the following|option)|Based on the (?:text|texts|data|graph|table|information|passage|notes|poem)|According to (?:the|both) |As used in the text|What (?:does|is|would|will|can)|How (?:does|would|do|did)|Why (?:does|would|is|did)|In (?:the|this) (?:text|context|poem))')
def find_prompt(flat):
    best=None
    for m in START.finditer(flat):
        p=m.start()
        pre=flat[:p].rstrip()
        if p==0 or re.search(r'[.?!”"’:_)\]]$',pre):
            if '?' in flat[p:]:best=p
    if best is None:
        qi=flat.rfind('?')
        if qi<0:return None
        b=max((m.end() for m in re.finditer(r'[.!?”"’]\s+(?=[A-Z“"])',flat[:qi])),default=0)
        best=b
    pre=flat[:best].rstrip()
    ends=[m.end() for m in re.finditer(r'[.!?”"’]\s+(?=[A-Z“"])',pre)]
    s=ends[-1] if ends else 0
    if re.match(r'(?:The|A) (?:student|writer)\b',pre[s:]):best=s
    return best
def build_paras(lines,allow_bullets=True):
    paras=[];cur=[];bullets=False
    def flush():
        nonlocal cur
        if cur:paras.append(('• ' if bullets else '')+join_lines(cur));cur=[]
    n=len(lines)
    for i,l in enumerate(lines):
        L=l.strip()
        if not L:continue
        if re.fullmatch(r'Text [12]',L):
            flush();paras.append('# '+L);continue
        nxt=lines[i+1].strip() if i+1<n else None
        cur.append(L)
        end=nxt is None
        if not end:
            if bullets:
                end=bool(re.search(r'[.?!”"’)]$',L)) and bool(re.match(r'[A-Z0-9“"‘(]',nxt))
            elif re.fullmatch(r'_+',L):end=True
            elif re.fullmatch(r'_+',nxt):end=False
            elif re.fullmatch(r'Text [12]',nxt):end=True
            elif len(L)<FULL*.9 and re.search(r'[.?!:”"’)]$',L) and re.match(r'[A-Z0-9“"‘(_]',nxt):end=True
        if end:
            flush()
            if allow_bullets and re.search(r'notes:$',L):bullets=True
    flush()
    return paras
def verse(lines):
    ls=[l.strip() for l in lines if l.strip()]
    if len(ls)>=4 and statistics.median(len(l) for l in ls)<72:
        head=[];body=ls
        if re.match(r'The following text',ls[0]):head=[ls[0]];body=ls[1:]
        return head+['\n'.join(body)]
    return None
def parse_opts(a):
    if a is None:return None
    parts=re.split(r'(?m)^([A-D])\. ?',a)
    labs=parts[1::2];txt=[join_lines(norm(t).split('\n')) if t.strip() else '' for t in parts[2::2]]
    return txt if labs==['A','B','C','D'] else None
def clean_lines(s):return norm(s).rstrip('\n').split('\n')
def split_prompt(lines,hdr):
    flat,offs=flat_offsets(lines)
    p=find_prompt(flat)
    if p is None:return lines,None
    i=max(j for j,o in enumerate(offs) if o<=p)
    pre=lines[:i]
    pref=flat[offs[i]:p].strip()
    if pref:pre=pre+[pref]
    return pre,flat[p:].strip()
def extras(ocr,txt):
    diff=toks(ocr)-toks(txt)
    return sum(c for t,c in diff.items() if len(t)<=3 or any(ch.isdigit() for ch in t))
MARK=re.compile(r'\s[,.?;:](?!\d)|\(\s|\s\)|\bthe value of\s*[.?]|\b(and|or)\s*[,.]|,\s*(and|or)\s+(is|are|be)\b')
def stem_ok_math(q,v,geo,oc):
    txt=norm(v['stem'])
    if MARK.search(txt):return False
    if 'err' in geo:return True       # no image to compare, text is all we have
    if geo['fig']:return False
    if 'stem' not in oc:return False
    return extras(oc['stem'],txt)==0
def opts_ok_math(q,v,geo,oc):
    ot=parse_opts(v['ans'])
    if not ot or any(not o for o in ot):return False
    if MARK.search(' '.join(ot)):return False
    if 'opts' not in oc:return False
    return extras(oc['opts'],norm(v['ans']))==0
def rect_x(geo,w):return [18,max(w-14,100)]
def fig_split(q,geo,lines):
    """math figure stem -> figure crop + hybrid text for the trailing text lines"""
    import numpy as np
    from PIL import Image
    from hybrid import hybrid,ocr_words,nw
    from ocr_all import trailing_text_start
    bands=geo['bands'];pi=trailing_text_start(bands)
    if pi>=len(bands) or pi==0:return None
    g=np.array(Image.open(BANK+'q/'+q+'.webp').convert('L'))
    rect=[bands[pi][0]-4,geo['stem'][1]]
    W=ocr_words(g,rect[0],rect[1])
    if not W:return None
    oc=collections.Counter(nw(w['t']) for w in W if nw(w['t']))
    best=None
    for t in range(len(lines)):
        tt=collections.Counter(x for x in re.findall(r'[a-z0-9]+',norm(' '.join(lines[t:])).lower()))
        miss=sum((tt-oc).values());extra=sum(c for k,c in (oc-tt).items() if len(k)>3 and not any(ch.isdigit() for ch in k))
        sc=2*miss+extra
        if best is None or sc<best[0]:best=(sc,t)
    sc,t=best
    paras=[norm(x) for x in build_paras(lines[t:],False)]
    if not paras:return None
    res,info=hybrid(g,rect,paras)
    if not res or info['cov']>0.02:return None
    return {'fg':[geo['stem'][0],bands[pi][0]-3],'P':res}
def rw_fallback(q,geo,mcq,ot):
    o={'si':geo['stem']}
    if mcq and ot and all(ot):o['o']=ot
    return o
def build(q,meta):
    v=D[q];geo=G[q];oc=O.get(q,{});w=geo['w'];rec={'mode':{}}
    mcq=meta['Response Type'].startswith('Multiple')
    lines=clean_lines(v['stem'])
    ot=parse_opts(v['ans']) if mcq else None
    out={}
    if v['file']=='rw':
        fg=None;note=[]
        if geo['fig'] and 'err' not in geo:
            bands=geo['bands'];pi=oc.get('pidx',len(bands));ps=oc.get('pass')
            if pi>=len(bands) or not ps:return rw_fallback(q,geo,mcq,ot),'rw-fig:no-passage'
            best=None
            for t in range(len(lines)):
                tt=join_lines(lines[t:]);a=toks(ps);b=toks(tt)
                sc=sum((a-b).values())+sum((b-a).values())
                if best is None or sc<best[0]:best=(sc,t)
            sc,t=best
            n=sum(toks(ps).values())
            if sc>max(6,0.12*n):return rw_fallback(q,geo,mcq,ot),'rw-fig:ocr-mismatch(%d/%d)'%(sc,n)
            out['fg']=[geo['stem'][0],bands[pi][0]-3];lines=lines[t:]
        under='underlined' in norm(v['stem'])
        pre,prompt=split_prompt(lines,v['hdr'])
        if under and 'err' not in geo and not geo['fig']:
            from underline import underlined_ranges
            import numpy as np
            from PIL import Image
            pa=geo['para_at'];bands=geo['bands'];done=False
            if prompt and pa:
                k=len(bands)-pa[-1]
                if 1<=k<=5 and 60*(k-1)<len(prompt)<=175*k:
                    g=np.array(Image.open(BANK+'q/'+q+'.webp').convert('L'))
                    P=[norm(x) for x in build_paras(pre)]
                    ur=underlined_ranges(g,[geo['stem'][0],bands[pa[-1]][0]-3],P)
                    if ur:
                        out['P']=P;out['U']=ur;out['PR']=norm(prompt);done=True
                    else:
                        out['si']=[geo['stem'][0],bands[pa[-1]][0]-3];out['PR']=prompt;done=True
            if not done:
                out['si']=geo['stem']
        elif under and geo['fig']:
            return rw_fallback(q,geo,mcq,ot),'rw-fig+underline'
        else:
            vs=verse(pre)
            P=vs if vs else build_paras(pre)
            out['P']=[norm(x) for x in P]
            if prompt:out['PR']=norm(prompt)
            else:return {},'rw:no-prompt'
    else:
        h=HY.get(q)
        if stem_ok_math(q,v,geo,oc):
            out['P']=[norm(x) for x in build_paras(lines,False)]
        elif h and h.get('res') and h['info'].get('cov',1)<=0.02:
            out['P']=h['res']
        elif 'err' in geo:return out,'math:no-image-no-text'
        else:
            out['si']=geo['stem']
            if geo['fig']:
                r=fig_split(q,geo,lines)
                if r:out.pop('si');out.update(r)
    if mcq:
        if ot is None:return {},'opts:parse'
        if v['file']=='rw' or opts_ok_math(q,v,geo,oc):
            if any(not o for o in ot):return {},'rw-opts-empty'
            out['o']=ot
        else:
            out['o']=[[r[0],r[1],r[2],r[3]] for r in geo['opts']]
    return out,None
def write_meta(rows,res,path):
    old=json.loads(open('old_meta.js',encoding='utf8').read()[len('window.BANK='):].rstrip().rstrip(';'))
    om={x['id']:x for x in old};out=[]
    for r in rows:
        q=r['Question ID'];b=om[q]
        rec={k:b[k] for k in ('w','h','id','s','a','d','k','l','m','src','p','ep')}
        if r['Response Type'].startswith('Student') and D[q]['corr']:rec['a']=norm(D[q]['corr'])   # CSV dropped leading decimal points
        rec.update(res[q]);out.append(rec)
    open(path,'w',encoding='utf8').write('window.BANK='+json.dumps(out,ensure_ascii=False,separators=(',',':'))+';\n')
    return out
if __name__=='__main__':
    rows=list(csv.DictReader(open(BANK+'index.csv',encoding='utf-8-sig')))
    res={};fails=[];stat=collections.Counter()
    for r in rows:
        q=r['Question ID']
        o,err=build(q,r)
        if err:fails.append((q,err))
        if not o or ('o' not in o and r['Response Type'].startswith('Multiple')):
            print('UNBUILDABLE',q,err);continue
        res[q]=o
        kind=('text' if 'P' in o else 'img')
        stat[(D[q]['file'],kind,'img-inline' if 'P' in o and any('[[' in p for p in o['P']) else '',('otext' if 'o' not in o else (all(isinstance(x,str) for x in o['o']) and 'otext' or 'oimg')))]+=1
    json.dump(res,open('assembled.json','w'),ensure_ascii=False)
    write_meta(rows,res,'meta_new.js')
    print(len(res),'built;',len(fails),'fell back');print(collections.Counter(e.split('(')[0] for q,e in fails))
    for k in sorted(stat):print(k,stat[k])
