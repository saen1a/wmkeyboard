import os
import sys, json, hashlib, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
all_strokes=load_strokes('data/de_swipes.jsonl')
def key(r): return (r.get('sentence','')+'|'+str(r.get('session',''))).encode()
def is_test(r): return int(hashlib.sha256(key(r)).hexdigest()[:8],16)%5==0
train=[r for r in all_strokes if not is_test(r)]
test=[r for r in all_strokes if is_test(r)]
lm=LM(train)
uni_top=[w for w,_ in lm.uni.most_common(5000)]
def topn(p2,p1,n=50):
    cand={}
    def put(w,s):
        if s>cand.get(w,-1e9): cand[w]=s
    for w in uni_top: put(w,lm.logp3(w,p2,p1))
    for (a,b),c in lm.bi.items():
        if a==p1: put(b,lm.logp3(b,p2,p1))
    for (a,b,c),cnt in lm.tri.items():
        if a==p2 and b==p1: put(c,lm.logp3(c,p2,p1))
    return sorted(cand.items(),key=lambda x:-x[1])[:n]
with open('test_extra50_lp.jsonl','w',encoding='utf-8') as fe:
    for r in test:
        p1,p2=context_of(r)
        if not p1: continue
        top=topn(p2,p1,50)
        mx=top[0][1]
        fe.write(json.dumps([[w, s-mx] for w,s in top],ensure_ascii=False)+'\n')
print('done')
