import os
import json, math, re
from collections import Counter, defaultdict

def tokens(s):
    return [re.sub(r"[^\wäöüß]", "", t.lower()) for t in s.split()]

def load_dump(path):
    rows=[]
    for line in open(path,encoding='utf-8'):
        line=line.rstrip('\n')
        if not line: continue
        f=line.split('\t'); pool=[]
        for part in f[4].split('|'):
            if not part: continue
            w,sep,s=part.rpartition(':')
            if sep and s: pool.append((w,float(s)))
        rows.append((f[0],pool))
    return rows

def load_strokes(path):
    out=[]
    for line in open(path,encoding='utf-8'):
        r=json.loads(line); w=r['word'].lower()
        if len(w)>=2 and w.isalpha(): out.append(r)
    return out

class LM:
    def __init__(self, strokes):
        self.uni=Counter(); self.bi=Counter(); self.tri=Counter(); self.prev=Counter(); self.prev2=Counter()
        self.cache=[]  # per stroke: set of words earlier in the sentence
        for r in strokes:
            t=[x for x in tokens(r.get('sentence','')) if x]
            for w in t: self.uni[w]+=1
            for a,b in zip(t,t[1:]):
                self.bi[(a,b)]+=1; self.prev[a]+=1
            for a,b,c in zip(t,t[1:],t[2:]):
                self.tri[(a,b,c)]+=1; self.prev2[(a,b)]+=1
            self.cache.append(set(t))
        self.total=sum(self.uni.values()); self.vocab=len(self.uni)
        self.lam=0.7
    def pu(self,w): return (self.uni[w]+1)/(self.total+self.vocab)
    def logp1(self,w): return math.log(self.pu(w))
    def logp2(self,w,p):
        pu=self.pu(w)
        if not p or self.prev[p]==0: return math.log(pu)
        pb=(self.bi[(p,w)]+0.3*pu*self.prev[p])/(self.prev[p]+0.3)
        return math.log(self.lam*pb+(1-self.lam)*pu)
    def logp3(self,w,p2,p1):
        pu=self.pu(w)
        if not p1: return math.log(pu)
        base=self.logp2(w,p1)
        if not p2 or self.prev2[(p2,p1)]==0:
            return base
        pt=(self.tri[(p2,p1,w)]+0.3*math.exp(base)*self.prev2[(p2,p1)])/(self.prev2[(p2,p1)]+0.3)
        return math.log(0.6*pt+0.4*math.exp(base))

def context_of(r):
    t=[x for x in tokens(r.get('sentence','')) if x]
    i=r.get('word_idx',0)
    p1=t[i-1] if i-1>=0 and i-1<len(t) else None
    p2=t[i-2] if i-2>=0 and i-2<len(t) else None
    return p1,p2

def subset(rows, strokes):
    out=[]
    for i,r in enumerate(strokes):
        p1,p2=context_of(r)
        if p1 and rows[i][1]: out.append((i,r,p1,p2))
    return out
