import os
import sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows=load_dump(sys.argv[1]); strokes=load_strokes(sys.argv[2]); lm=LM(strokes)
sub=subset(rows,strokes)
print('n',len(sub))
def run(scorefn, P=8):
    hit=0
    for i,r,p1,p2 in sub:
        pool=rows[i][1][:P]
        best=max(pool,key=lambda c: scorefn(c,r,p1,p2,i,pool))
        hit+=best[0]==rows[i][0]
    return 100*hit/len(sub)
print('baseline',run(lambda c,*a: c[1]))
for w in (0.3,0.5,0.7,1.0,1.5):
    for cap in (1.5,2,2.5,3,4,999):
        def f(c,r,p1,p2,i,pool,w=w,cap=cap):
            ref=lm.logp2(pool[0][0],p1)
            return c[1]+max(-cap,min(cap,w*(lm.logp2(c[0],p1)-ref)))
        a=run(f)
        print(f'bi w={w} cap={cap}: {a:.2f}')
print('--- trigram ---')
for w in (0.3,0.5,0.7,1.0,1.5):
    for cap in (2,3,4,999):
        def f(c,r,p1,p2,i,pool,w=w,cap=cap):
            ref=lm.logp3(pool[0][0],p2,p1)
            return c[1]+max(-cap,min(cap,w*(lm.logp3(c[0],p2,p1)-ref)))
        print(f'tri w={w} cap={cap}: {run(f):.2f}')
print('--- mix bi+tri ---')
for b in (0.3,0.5,0.7):
    for t in (0.3,0.5,0.7):
        for cap in (3,4,999):
            def f(c,r,p1,p2,i,pool,b=b,t=t,cap=cap):
                refb=lm.logp2(pool[0][0],p1); reft=lm.logp3(pool[0][0],p2,p1)
                return c[1]+max(-cap,min(cap,b*(lm.logp2(c[0],p1)-refb)+t*(lm.logp3(c[0],p2,p1)-reft)))
            a=run(f)
            if a>82.5: print(f'mix b={b} t={t} cap={cap}: {a:.2f}')
