import os
import sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
known={}; full={}
for line in open('data/de_150k.txt',encoding='utf-8'):
    p=line.split()
    if p: known[p[0].lower()]=int(p[1])
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: full[p[0].lower()]=int(p[1])
def ev(path,w,cap,drop):
    rows=load_dump(path); hit=0; n=0
    for target,pool in rows:
        if not pool: continue
        def sc(c):
            word,s=c
            if word in known: return s
            f=full.get(word)
            if f is None: return s-100 if drop else s
            return s+min(cap,w*math.log1p(f))
        best=max(pool,key=sc); hit+=best[0]==target; n+=1
    return 100*hit/n
for path in ('pool_j3_de.tsv','pool_j5_de.tsv','pool_j8_de.tsv','pool_guard32.tsv'):
    print(path,'baseline',ev(path,0,0,False))
    best=(0,None)
    for drop in (False,True):
        for cap in (0.5,1,2,3,5):
            for w in (0.05,0.1,0.2,0.3,0.5,0.75,1.0):
                a=ev(path,w,cap,drop)
                if a>best[0]: best=(a,(drop,cap,w))
    print('  best',best)
