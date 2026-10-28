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
bi=Counter()
for t in sent[:cut]:
    for a,b in zip(t,t[1:]): bi[(a,b)]+=1
uni=Counter()
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: uni[p[0].lower()]=int(p[1])
uni_top=[w for w,_ in uni.most_common(3)]
def evaluate(cap):
    d=defaultdict(list)
    for (a,b),c in Counter(dict(bi.most_common(cap))).items(): d[a].append((b,c))
    for a in d: d[a].sort(key=lambda x:-x[1])
    hit1=hit3=n=0
    for t in test:
        for i in range(1,len(t)):
            prev=t[i-1]; target=t[i]; n+=1
            cand=[w for w,_ in d.get(prev,[])[:3]] or uni_top
            hit1+=cand[0]==target; hit3+=target in cand
    print(cap,f'top1 {100*hit1/n:.2f} top3 {100*hit3/n:.2f}')
for cap in (50000,150000,300000,600000,1000000):
    evaluate(cap)
