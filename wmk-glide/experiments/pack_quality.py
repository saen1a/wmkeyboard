import os
import sys, math, gzip, hashlib
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
def pu(w): return (uni[w]+1)/(tot+V)
# coverage
sub=[]
for i,r in enumerate(strokes):
    p1,p2=context_of(r)
    if p1 and rows[i][1]: sub.append((i,r,p1,p2))
cov_pair=sum(1 for i,r,p1,p2 in sub if (p1,rows[i][0]) in bi)
cov_tri=sum(1 for i,r,p1,p2 in sub if p2 and (p2,p1,rows[i][0]) in tri)
cov_tgt=sum(1 for i,r,p1,p2 in sub if uni[rows[i][0]]>0)
cov_ctx=sum(1 for i,r,p1,p2 in sub if left[p1]>0)
print(f'n={len(sub)} pair in pack {cov_pair} ({100*cov_pair/len(sub):.1f}%), tri {cov_tri} ({100*cov_tri/len(sub):.1f}%), target in unigram {cov_tgt} ({100*cov_tgt/len(sub):.1f}%), context in pack {cov_ctx} ({100*cov_ctx/len(sub):.1f}%)')
# rank rerank variants
def term(w,c,cap):
    v=w*math.log1p(c)
    return cap if v>cap else v
def ev(kind,w2=0.45,w3=0.6,scale=50.0,alpha=0.3):
    hit=0;n=0
    for i,r,p1,p2 in sub:
        pool=rows[i][1]
        scored=[]
        for idx,(word,s) in enumerate(pool):
            c2=bi.get((p1,word),0); c3=tri.get((p2,p1,word),0) if p2 else 0
            if kind=='raw':
                e=term(w2,c2/scale,1.2)+term(w3,c3/scale,1.5)
            elif kind=='prob':
                p2p=(c2/left[p1]) if left[p1] else pu(word)
                p3p=(c3/left2[(p2,p1)]) if p2 and left2[(p2,p1)] else p2p
                e=term(w2,p2p*scale,1.2)+term(w3,p3p*scale,1.5)
            elif kind=='backoff':
                base=pu(word)
                p2p=(c2+alpha*base*left[p1])/(left[p1]+alpha) if left[p1] else base
                p3p=(c3+alpha*p2p*left2[(p2,p1)])/(left2[(p2,p1)]+alpha) if p2 and left2[(p2,p1)] else p2p
                e=term(w2,p2p*scale,1.2)+term(w3,p3p*scale,1.5)
            else: e=0
            scored.append((word,-idx+e))
        best=max(scored,key=lambda x:x[1])[0]
        hit+=best==rows[i][0]; n+=1
    return 100*hit/n
base=100*sum(1 for i,r,p1,p2 in sub if rows[i][1][0][0]==rows[i][0])/len(sub)
print('baseline',round(base,2))
for kind in ('raw','prob','backoff'):
    best=(0,None)
    for w2 in (0.2,0.45,0.8):
        for w3 in (0.3,0.6,1.0):
            for sc in (5,20,50,200):
                for a in ((0.1,0.3,1.0) if kind=='backoff' else (0.3,)):
                    x=ev(kind,w2,w3,sc,a)
                    if x>best[0]: best=(x,(w2,w3,sc,a))
    print(kind,'best',round(best[0],2),best[1])
