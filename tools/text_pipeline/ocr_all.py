import json,os,re,sys
os.environ['OMP_THREAD_LIMIT']='1'
import numpy as np,pytesseract
from PIL import Image
from multiprocessing import Pool
BANK='../../bank/'
G=json.load(open('geom.json'));D=json.load(open('parsed.json'))
def ocr(g,y0,y1):
    y0=max(0,y0);y1=min(g.shape[0],y1)
    im=Image.fromarray(g[y0:y1]).convert('L')
    im=im.resize((im.width*2,im.height*2),Image.LANCZOS)
    return pytesseract.image_to_string(im,config='--psm 6')
def trailing_text_start(bands):
    i=len(bands)
    while i>0:
        s,e,x0,x1=bands[i-1];h=e-s
        if (8<=h<=26 and x0<=28) or (h<7 and (x1-x0)<150):i-=1
        else:break
    return i
def work(q):
    geo=G[q];v=D[q];out={}
    if 'err' in geo:return q,out
    g=np.array(Image.open(BANK+'q/'+q+'.webp').convert('L'))
    if v['file']=='rw':
        if geo['fig']:
            bands=geo['bands'];pi=trailing_text_start(bands)
            out['pidx']=pi
            if pi<len(bands):
                out['pass']=ocr(g,bands[pi][0]-4,bands[-1][1]+4)
    else:
        if not geo['fig']:
            out['stem']=ocr(g,geo['stem'][0],geo['stem'][1])
        if 'opts' in geo and v['ans'] and re.search(r'(?m)^[A-D]\. ?\S',v['ans']):
            out['opts']=ocr(g,geo['opt_span'][0],geo['opt_span'][1])
    return q,out
if __name__=='__main__':
    qs=list(G)
    res={}
    with Pool(2) as p:
        for i,(q,o) in enumerate(p.imap_unordered(work,qs,chunksize=8)):
            res[q]=o
            if i%200==0:print(i,flush=True)
    json.dump(res,open('ocr.json','w'))
    print('done',len(res))
