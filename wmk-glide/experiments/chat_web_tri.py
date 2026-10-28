import os
import bz2, gzip, re, random
from collections import Counter, defaultdict
known=set()
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: known.add(p[0].lower())
tok=re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)
def tokens(text): return [w for m in tok.finditer(text.lower().replace('’',"'")) if (w:=m.group(0)) in known]
sent=[]
with bz2.open('data/deu_sentences.tsv.bz2','rt',encoding='utf-8',errors='replace') as f:
    for line in f:
        p=line.rstrip('\n').split('\t',2)
        if len(p)>=3:
            t=tokens(p[2])
            if len(t)>=2: sent.append(t)
random.Random(1).shuffle(sent); cut=int(len(sent)*0.8); test=sent[cut:]
bi=Counter(); tri=Counter()
for line in gzip.open('data/de_bigrams.txt.gz','rt',encoding='utf-8'):
    p=line.rstrip('\n').rsplit(' ',1)
    if len(p)==2:
        ws=p[0].split()
        if len(ws)==2: bi[(ws[0],ws[1])]+=int(p[1])
for line in gzip.open('data/de_trigrams.txt.gz','rt',encoding='utf-8'):
    p=line.rstrip('\n').rsplit(' ',1)
    if len(p)==2:
        ws=p[0].split()
        if len(ws)==3: tri[(ws[0],ws[1],ws[2])]+=int(p[1])
uni=Counter()
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: uni[p[0].lower()]=int(p[1])
uni_top=[w for w,_ in uni.most_common(3)]
def nx(bi):
    d=defaultdict(list)
    for (a,b),c in bi.items(): d[a].append((b,c))
    for a in d: d[a].sort(key=lambda x:-x[1])
    return d
bix=nx(bi); trix=defaultdict(list)
for (a,b,c),cnt in tri.items(): trix[(a,b)].append((c,cnt))
for k in trix: trix[k].sort(key=lambda x:-x[1])
for use_tri in (False,True):
    hit1=hit3=n=0
    for t in test:
        for i in range(1,len(t)):
            prev=t[i-1]; target=t[i]; p2=t[i-2] if i>=2 else None; n+=1
            cand=[w for w,_ in trix.get((p2,prev),[])[:3]] if use_tri and p2 else []
            if not cand: cand=[w for w,_ in bix.get(prev,[])[:3]]
            if not cand: cand=uni_top
            hit1+=cand[0]==target; hit3+=target in cand
    print('web tri' if use_tri else 'web bi',f'top1 {100*hit1/n:.2f} top3 {100*hit3/n:.2f}')
