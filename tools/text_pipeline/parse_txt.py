import re, json, sys, csv, glob
A='source/'
FILES={'rw':A+'9720ccd7-Reading___Writing_All_Q_A_compressed.pdf.txt','mh':A+'3bcd709c-Math_Hard_compressed.pdf.txt','me':A+'b838c32a-Math_Easy_Medium_compressed.pdf.txt'}
def parse(path):
    t=open(path,encoding='utf8').read()
    parts=re.split(r'(?m)^Question ID: ([0-9a-f]{8})\s*$',t)
    out={}
    for i in range(1,len(parts),2):
        qid,body=parts[i],parts[i+1]
        m=re.search(r'(?ms)^Question\n(.*?)(?:^Answer\n(.*?))?^(?:Correct Answer: ?(.*?)\n)?Rationale\n',body)
        if not m: out[qid]={'err':'noparse','raw':body[:300]};continue
        stem,ans,corr=m.group(1),m.group(2),m.group(3)
        out[qid]={'stem':stem.rstrip('\n'),'ans':ans,'corr':(corr or '').strip(),'hdr':body[:body.find('Question\n')]}
    return out
if __name__=='__main__':
    allq={}
    for k,p in FILES.items():
        d=parse(p); print(k,len(d),'err',sum('err' in v for v in d.values()))
        for q,v in d.items(): v['file']=k; allq[q]=v
    print(len(allq))
    json.dump(allq,open('parsed.json','w'))
    rows=list(csv.DictReader(open('../../bank/index.csv',encoding='utf-8-sig')))
    miss=[r['Question ID'] for r in rows if r['Question ID'] not in allq]
    print('csv rows',len(rows),'missing from txt',len(miss),miss[:5])
    bad=0
    for r in rows:
        v=allq.get(r['Question ID'])
        if v and 'err' not in v and v['corr']!=r['Correct Answer'].strip(): bad+=1; 
        if v and 'err' not in v and v['corr']!=r['Correct Answer'].strip() and bad<6: print('ans mismatch',r['Question ID'],repr(v['corr']),r['Correct Answer'])
    print('answer mismatches',bad)
