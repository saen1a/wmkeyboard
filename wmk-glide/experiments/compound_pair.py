import os
import sys, math, pickle, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows=load_dump(sys.argv[1]); strokes=load_strokes(sys.argv[2])
known={}; full={}
for line in open('data/de_150k.txt',encoding='utf-8'):
    p=line.split()
    if p: known[p[0].lower()]=int(p[1])
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: full[p[0].lower()]=int(p[1])
print('loaded',len(known),len(full))
cache='pairs.pkl'
if os.path.exists(cache):
    pair_max=pickle.load(open(cache,'rb'))
else:
    pair_max={}
    for w,f in full.items():
        if w in known: continue
        for i in range(3,len(w)-2):
            a,b=w[:i],w[i:]
            if a in known and b in known:
                k=(a,b)
                if f>pair_max.get(k,0): pair_max[k]=f
    pickle.dump(pair_max,open(cache,'wb'))
print('pairs',len(pair_max))
def split_best(w):
    best=None
    for i in range(3,len(w)-2):
        a,b=w[:i],w[i:]
        if a in known and b in known:
            pc=pair_max.get((a,b),0)
            if best is None or pc>best[0]: best=(pc,a,b)
    return best
def score(c,w=0.0,cap=3.0,use='pair'):
    word,s=c
    if word in known: return s
    b=split_best(word)
    if not b: return s-10
    pc,a,bb=b
    val=math.log1p(pc) if use=='pair' else math.log1p(full.get(word,0))
    return s+min(cap,w*val)
def acc(w=0.0,cap=3.0,use='pair'):
    hit=0
    for target,pool in rows:
        if not pool: continue
        best=max(pool,key=lambda c: score(c,w,cap,use))
        hit+=best[0]==target
    return 100*hit/len(rows)
print('baseline %.2f'%acc())
for use in ('pair','full'):
    for cap in (1,2,3,5):
        for w in (0.1,0.2,0.3,0.5,0.75,1.0):
            a=acc(w,cap,use)
            if a>74.6: print(f'{use} w={w} cap={cap}: {a:.2f}')
