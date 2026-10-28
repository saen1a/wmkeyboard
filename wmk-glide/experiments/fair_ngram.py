import os
import sys, math, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows=load_dump('pool32.tsv'); strokes=load_strokes('data/de_swipes.jsonl')
def key(r): return (r.get('sentence','')+'|'+str(r.get('session',''))).encode()
def is_test(r): return int(hashlib.sha256(key(r)).hexdigest()[:8],16)%5==0
train=[r for r in strokes if not is_test(r)]; test=[(i,r) for i,r in enumerate(strokes) if is_test(r)]
lm=LM(train)
sub=[(i,r,p1,p2) for i,r in test for p1,p2 in [context_of(r)] if p1 and rows[i][1]]
print('test n',len(sub))
def acc(fn):
    hit=0
    for i,r,p1,p2 in sub:
        pool=rows[i][1]; best=max(pool,key=lambda c: fn(c,p1,p2,pool))
        hit+=best[0]==rows[i][0]
    return 100*hit/len(sub)
print('baseline',acc(lambda c,p1,p2,pool:c[1]))
for name,tri in (('bi',False),('tri',True)):
    for w in (0.5,0.7,1.0,1.5):
        for cap in (3,4,999):
            def f(c,p1,p2,pool,w=w,cap=cap,tri=tri):
                if tri: ref=lm.logp3(pool[0][0],p2,p1); val=lm.logp3(c[0],p2,p1)
                else: ref=lm.logp2(pool[0][0],p1); val=lm.logp2(c[0],p1)
                return c[1]+max(-cap,min(cap,w*(val-ref)))
            a=acc(f)
            if a>69: print(name,w,cap,a)
