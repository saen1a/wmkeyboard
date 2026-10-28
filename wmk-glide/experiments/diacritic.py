import os
import sys, math, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows=load_dump('synth_base26_pred.tsv')
known={}
for line in open('data/de_150k.txt',encoding='utf-8'):
    p=line.split()
    if p: known[p[0].lower()]=int(p[1])
strokes=load_strokes('synth_run/base26.jsonl')
assert len(rows)==len(strokes)
def variants(w):
    opts=[]
    for ch in w:
        if ch=='a': opts.append(['a','ä'])
        elif ch=='o': opts.append(['o','ö'])
        elif ch=='u': opts.append(['u','ü'])
        elif ch=='s': opts.append(['s','ß'])
        else: opts.append([ch])
    out=[]
    for t in itertools.product(*opts):
        v=''.join(t)
        if v in known: out.append(v)
    return out
def pick(w, mode='freq'):
    vs=variants(w)
    if not vs: return w
    return max(vs,key=lambda v:known[v])
def acc(mode):
    hit=0
    for (target,pool),r in zip(rows,strokes):
        if not pool: continue
        w=pool[0][0]
        p=pick(w,mode)
        # a variant may be a different word; only replace if it is a twin of w
        if p.replace('ä','a').replace('ö','o').replace('ü','u').replace('ß','s') != w.replace('ä','a').replace('ö','o').replace('ü','u').replace('ß','s'):
            p=w
        hit+= p==target
    return 100*hit/len(rows)
base=100*sum(1 for (t,p),r in zip(rows,strokes) if p and p[0][0]==t)/len(rows)
print('base26 top1',base)
print('freq restore',acc('freq'))
