import os
import sys, math, json, hashlib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

rows=load_dump(sys.argv[1]); strokes=load_strokes(sys.argv[2]); P=int(sys.argv[3]) if len(sys.argv)>3 else 32
# full list frequencies
full={}
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: full[p[0].lower()]=int(p[1])
known=set()
for line in open('data/de_150k.txt',encoding='utf-8'):
    p=line.split()
    if p: known.add(p[0].lower())

def sent_key(r):
    return r.get('sentence','') + '|' + str(r.get('session',''))
def is_test(r):
    h=hashlib.sha256(sent_key(r).encode()).hexdigest()
    return int(h[:8],16)%5==0

train=[(i,r) for i,r in enumerate(strokes) if not is_test(r) and context_of(r)[0] and rows[i][1]]
test =[(i,r) for i,r in enumerate(strokes) if     is_test(r) and context_of(r)[0] and rows[i][1]]
# LM built on train only
lm=LM([strokes[i] for i,_ in train])
print('train',len(train),'test',len(test))

def feats(i,r,p1,p2,c,lead):
    ds=c[1]-lead[1]
    d1=lm.logp1(c[0])-lm.logp1(lead[0])
    d2=lm.logp2(c[0],p1)-lm.logp2(lead[0],p1)
    d3=lm.logp3(c[0],p2,p1)-lm.logp3(lead[0],p2,p1)
    earlier=set(tokens(r.get('sentence',''))[:r.get('word_idx',0)])
    cache=1.0 if c[0] in earlier else 0.0
    ln=len(c[0])/10.0
    comp=0.0 if c[0] in known else 1.0
    fl=math.log1p(full.get(c[0],0))/10.0
    um=1.0 if any(ch in c[0] for ch in 'äöüß') else 0.0
    return np.array([ds,d1,d2,d3,cache,ln,comp,fl,um],dtype=float)

def make(items):
    X=[]; Y=[]; groups=[]
    for i,r in items:
        pool=rows[i][1][:P]
        lead=pool[0]
        p1,p2=context_of(r)
        X.append(np.stack([feats(i,r,p1,p2,c,lead) for c in pool]))
        Y.append(next(j for j,c in enumerate(pool) if c[0]==rows[i][0]) if any(c[0]==rows[i][0] for c in pool) else -1)
        groups.append(i)
    return X,Y,groups
Xtr,Ytr,_=make(train); Xte,Yte,_=make(test)
print('pool coverage train %.2f test %.2f'%(100*np.mean([y>=0 for y in Ytr]),100*np.mean([y>=0 for y in Yte])))
# baseline: argmax decoder score (index 0), only where target in pool
print('baseline train %.2f test %.2f'%(100*np.mean([y==0 for y in Ytr]),100*np.mean([y==0 for y in Yte])))
# conditional logit
nfeat=Xtr[0].shape[1]
theta=np.zeros(nfeat)
lr=0.2; l2=1e-3
for step in range(1500):
    grad=np.zeros(nfeat); loss=0.0
    for X,y in zip(Xtr,Ytr):
        if y<0: continue
        z=X@theta; z-=z.max(); p=np.exp(z); p/=p.sum()
        loss-=math.log(p[y]+1e-12)
        g=p; g[y]-=1.0
        grad+=X.T@g
    grad/=len(Xtr)
    grad+=l2*theta
    theta-=lr*grad
    if step%300==0: print('step',step,'loss',loss/len(Xtr),'theta',np.round(theta,3))
print('theta',theta)
def acc(X,Y):
    hit=0; n=0
    for Xg,y in zip(X,Y):
        if y<0: continue
        n+=1; hit+=int(np.argmax(Xg@theta)==y)
    return 100*hit/n
print('logit test %.2f (n=%d)'%(acc(Xte,Yte),sum(1 for y in Yte if y>=0)))
# cap blend baseline on test, fitted on train? use 0.7/3
def capacc(items,w=0.7,cap=3.0):
    hit=0;n=0
    for i,r in items:
        pool=rows[i][1][:P]; p1,p2=context_of(r); ref=lm.logp2(pool[0][0],p1)
        best=max(pool,key=lambda c: c[1]+max(-cap,min(cap,w*(lm.logp2(c[0],p1)-ref))))
        hit+=best[0]==rows[i][0]; n+=1
    return 100*hit/n
print('cap test %.2f'%capacc(test))
