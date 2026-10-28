import os
import sys, math
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
print('n',len(rows),'known',len(known),'full',len(full))
def splits(w):
    out=[]
    for i in range(3,len(w)-2):
        a,b=w[:i],w[i:]
        if a in known and b in known:
            out.append((a,b,math.log1p(known[a]),math.log1p(known[b])))
    return out
def best_split(w):
    ss=splits(w)
    if not ss: return None
    # prefer the split with the highest min part frequency
    return max(ss,key=lambda x:min(x[2],x[3]))
def score(c,w=0.0,cap=3.0,mode='bonus'):
    word,s=c
    if word in known: return s
    bs=best_split(word)
    if bs is None: return s-10.0 if mode=='drop' else s
    fullf=full.get(word)
    fl=math.log1p(fullf) if fullf else 0.0
    if mode=='bonus':
        return s+min(cap,w*fl)
    if mode=='drop':
        return s if fullf else s-10.0
    if mode=='replace':
        # use the full-list frequency instead of the part min
        return s - (1.0 if fullf else 0.0) # placeholder
    return s
def acc(w=0.0,cap=3.0,mode='bonus'):
    hit=0
    for target,pool in rows:
        if not pool: continue
        best=max(pool,key=lambda c: score(c,w,cap,mode))
        hit+=best[0]==target
    return 100*hit/len(rows)
print('baseline %.2f'%acc())
for mode in ('bonus','drop'):
    for cap in (1.0,2.0,3.0,5.0):
        for w in (0.1,0.2,0.3,0.5,0.75,1.0):
            a=acc(w,cap,mode)
            if a>74.6: print(f'{mode} w={w} cap={cap}: {a:.2f}')
