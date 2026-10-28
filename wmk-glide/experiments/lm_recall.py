import os
import sys, math, heapq
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows=load_dump(sys.argv[1]); strokes=load_strokes(sys.argv[2]); lm=LM(strokes)
sub=subset(rows,strokes)
# unigram top list
uni_top=[w for w,_ in lm.uni.most_common(2000)]
def topn(p2,p1,n=200):
    cand={}
    def put(w,s):
        if s>cand.get(w,-1e9): cand[w]=s
    for w in uni_top: put(w,lm.logp3(w,p2,p1))
    for (a,b),c in lm.bi.items():
        if a==p1: put(b,lm.logp3(b,p2,p1))
    for (a,b,c),cnt in lm.tri.items():
        if a==p2 and b==p1: put(c,lm.logp3(c,p2,p1))
    return [w for w,_ in sorted(cand.items(),key=lambda x:-x[1])[:n]]
for N in (10,25,50,100,200):
    in_lm=0; in_top=0; notpool_top=0
    for i,r,p1,p2 in sub:
        target=rows[i][0]; words=[w for w,_ in rows[i][1]]
        top=topn(p2,p1,N)
        if target in top: in_top+=1
        if target not in words and target in top: notpool_top+=1
        if target in top and target not in words: pass
    print(f'N={N}: target in LM top-N {in_top}/{len(sub)} ({100*in_top/len(sub):.1f}%), not in decoder pool but in top-N {notpool_top} ({100*notpool_top/len(sub):.1f}%)')
# how many targets are outside the pool at all
out=sum(1 for i,r,p1,p2 in sub if rows[i][0] not in [w for w,_ in rows[i][1]])
print('target outside pool',out,100*out/len(sub))
