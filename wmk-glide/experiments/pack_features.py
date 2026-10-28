import os
import sys, math, gzip
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows=load_dump('pool32.tsv'); strokes=load_strokes('data/de_swipes.jsonl')
bi=Counter(); tri=Counter(); left=Counter(); left2=Counter()
for line in gzip.open('data/de_bigrams.txt.gz','rt',encoding='utf-8'):
    p=line.rstrip('\n').rsplit(' ',1)
    if len(p)!=2: continue
    phrase,c=p; ws=phrase.split()
    if len(ws)==2: bi[(ws[0],ws[1])]+=int(c); left[ws[0]]+=int(c)
for line in gzip.open('data/de_trigrams.txt.gz','rt',encoding='utf-8'):
    p=line.rstrip('\n').rsplit(' ',1)
    if len(p)!=2: continue
    phrase,c=p; ws=phrase.split()
    if len(ws)==3: tri[(ws[0],ws[1],ws[2])]+=int(c); left2[(ws[0],ws[1])]+=int(c)
uni=Counter()
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: uni[p[0].lower()]=int(p[1])
tot=sum(uni.values()); V=len(uni)
def bucket(w):
    f=uni[w]
    return 0 if f>=100000 else 1 if f>=10000 else 2 if f>=1000 else 3 if f>=100 else 4
cb=Counter()
for (a,b),c in bi.items(): cb[(a,bucket(b))]+=c
sub=[(i,r,p1,p2) for i,r in enumerate(strokes) for p1,p2 in [context_of(r)] if p1 and rows[i][1]]
def term(w,c,cap):
    v=w*math.log1p(c); return cap if v>cap else v
def ev(w2=0.8,w3=0.3,ws=0.0,wc=0.0,scale=50.0,alpha=0.1):
    hit=0;n=0
    for i,r,p1,p2 in sub:
        pool=rows[i][1]; scored=[]
        for idx,(word,s) in enumerate(pool):
            c2=bi.get((p1,word),0); c3=tri.get((p2,p1,word),0) if p2 else 0
            p2p=(c2+alpha*(uni[word]+1)/(tot+V)*left[p1])/(left[p1]+alpha) if left[p1] else (uni[word]+1)/(tot+V)
            p3p=(c3+alpha*p2p*left2[(p2,p1)])/(left2[(p2,p1)]+alpha) if p2 and left2[(p2,p1)] else p2p
            e=term(w2,p2p*scale,1.2)+term(w3,p3p*scale,1.5)
            if ws and p2:
                e+=term(ws,bi.get((p2,word),0)/scale,1.0)
            if wc:
                cl=bucket(word); cbc=cb.get((p1,cl),0)
                e+=term(wc,cbc/left[p1],1.0) if left[p1] else 0
            scored.append((word,-idx+e))
        best=max(scored,key=lambda x:x[1])[0]
        hit+=best==rows[i][0]; n+=1
    return 100*hit/n
print('n',len(sub))
for ws in (0,0.1,0.2,0.3,0.5):
    for wc in (0,0.1,0.2,0.3):
        print('skip',ws,'class',wc,round(ev(ws=ws,wc=wc),2))
