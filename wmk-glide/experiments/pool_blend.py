import os
import sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows=load_dump(sys.argv[1]); strokes=load_strokes(sys.argv[2]); lm=LM(strokes)
sub=subset(rows,strokes)
print('n',len(sub))
def acc(fn):
    hit=0
    for i,r,p1,p2 in sub:
        pool=rows[i][1]; best=max(pool,key=lambda c: fn(c,r,p1,p2,i))
        hit+=best[0]==rows[i][0]
    return 100*hit/len(sub)
base=sum(1 for i,r,p1,p2 in sub if rows[i][1][0][0]==rows[i][0])
print('baseline %.2f'%(100*base/len(sub)))
for P in (4,8,12,16,24,32):
    for w,cap in ((0.7,3.0),(1.0,3.0),(1.5,3.0),(1.0,999.0)):
        def fn(c,r,p1,p2,i,P=P,w=w,cap=cap):
            pool=rows[i][1][:P]; ref=lm.logp2(pool[0][0],p1)
            return c[1]+max(-cap,min(cap,w*(lm.logp2(c[0],p1)-ref)))
        # need pool limited; redo inside
        hit=0
        for i,r,p1,p2 in sub:
            pool=rows[i][1][:P]; ref=lm.logp2(pool[0][0],p1)
            best=max(pool,key=lambda c: c[1]+max(-cap,min(cap,w*(lm.logp2(c[0],p1)-ref))))
            hit+=best[0]==rows[i][0]
        print(f'P={P:2} w={w} cap={cap}: {100*hit/len(sub):.2f}')
