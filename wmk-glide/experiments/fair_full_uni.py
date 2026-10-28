import os
import sys, math, hashlib
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows=load_dump('pool32.tsv'); strokes=load_strokes('data/de_swipes.jsonl')
# full unigram
full=Counter()
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: full[p[0].lower()]=int(p[1])
total=sum(full.values()); vocab=len(full)
def key(r): return (r.get('sentence','')+'|'+str(r.get('session',''))).encode()
def is_test(r): return int(hashlib.sha256(key(r)).hexdigest()[:8],16)%5==0
train=[r for r in strokes if not is_test(r)]; test=[(i,r) for i,r in enumerate(strokes) if is_test(r)]
# corpus bigrams from train
bi=Counter(); prev=Counter(); tri=Counter(); prev2=Counter(); uni_c=Counter()
for r in train:
    t=[x for x in tokens(r.get('sentence','')) if x]
    for w in t: uni_c[w]+=1
    for a,b in zip(t,t[1:]): bi[(a,b)]+=1; prev[a]+=1
    for a,b,c in zip(t,t[1:],t[2:]): tri[(a,b,c)]+=1; prev2[(a,b)]+=1
def pu(w): return (full[w]+1)/(total+vocab)
def l1(w): return math.log(pu(w))
def l2(w,p):
    u=pu(w)
    if not p or prev[p]==0: return math.log(u)
    pb=(bi[(p,w)]+0.3*u*prev[p])/(prev[p]+0.3)
    return math.log(0.7*pb+0.3*u)
def l3(w,p2,p1):
    base=l2(w,p1)
    if not p2 or prev2[(p2,p1)]==0: return base
    pt=(tri[(p2,p1,w)]+0.3*math.exp(base)*prev2[(p2,p1)])/(prev2[(p2,p1)]+0.3)
    return math.log(0.6*pt+0.4*math.exp(base))
sub=[(i,r,p1,p2) for i,r in test for p1,p2 in [context_of(r)] if p1 and rows[i][1]]
print('test',len(sub))
def acc(tri_use,w,cap):
    hit=0
    for i,r,p1,p2 in sub:
        pool=rows[i][1]; lp=(lambda x:l3(x,p2,p1)) if tri_use else (lambda x:l2(x,p1))
        ref=lp(pool[0][0]); best=max(pool,key=lambda c:c[1]+max(-cap,min(cap,w*(lp(c[0])-ref))))
        hit+=best[0]==rows[i][0]
    return 100*hit/len(sub)
print('baseline',acc(False,0,0))
for tri_use in (False,True):
    for w in (0.5,0.7,1.0,1.5,2.0):
        for cap in (3,4,999):
            a=acc(tri_use,w,cap)
            if a>69: print('tri' if tri_use else 'bi',w,cap,a)
