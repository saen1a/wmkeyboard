import os
import sys, math, gzip, pickle
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows=load_dump('pool32.tsv'); strokes=load_strokes('data/de_swipes.jsonl')
def load_pack(bi_path,tri_path):
    bi=Counter(); tri=Counter()
    for line in gzip.open(bi_path,'rt',encoding='utf-8'):
        p=line.rstrip('\n').rsplit(' ',1)
        if len(p)!=2: continue
        ws=p[0].split()
        if len(ws)==2: bi[(ws[0],ws[1])]+=int(p[1])
    for line in gzip.open(tri_path,'rt',encoding='utf-8'):
        p=line.rstrip('\n').rsplit(' ',1)
        if len(p)!=2: continue
        ws=p[0].split()
        if len(ws)==3: tri[(ws[0],ws[1],ws[2])]+=int(p[1])
    return bi,tri
web=load_pack('data/de_bigrams.txt.gz','data/de_trigrams.txt.gz')
wiki=pickle.load(open('wiki_pack.pkl','rb'))
uni=Counter()
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: uni[p[0].lower()]=int(p[1])
tot=sum(uni.values()); V=len(uni)
sub=[(i,r,p1,p2) for i,r in enumerate(strokes) for p1,p2 in [context_of(r)] if p1 and rows[i][1]]
def evaluate(bi,tri,label):
    left=Counter(); left2=Counter()
    for (a,b),c in bi.items(): left[a]+=c
    for (a,b,d),c in tri.items(): left2[(a,b)]+=c
    def term(w,c,cap):
        v=w*math.log1p(c); return cap if v>cap else v
    hit=0
    for i,r,p1,p2 in sub:
        pool=rows[i][1]; scored=[]
        for idx,(word,s) in enumerate(pool):
            c2=bi.get((p1,word),0); c3=tri.get((p2,p1,word),0) if p2 else 0
            base=(uni[word]+1)/(tot+V)
            p2p=(c2+0.1*base*left[p1])/(left[p1]+0.1) if left[p1] else base
            p3p=(c3+0.1*p2p*left2[(p2,p1)])/(left2[(p2,p1)]+0.1) if p2 and left2[(p2,p1)] else p2p
            e=term(0.8,p2p*50,1.2)+term(0.3,p3p*50,1.5)
            scored.append((word,-idx+e))
        hit+=max(scored,key=lambda x:x[1])[0]==rows[i][0]
    print(label,round(100*hit/len(sub),2))
print('n',len(sub))
evaluate(*web,'web/news')
evaluate(*wiki,'wiki')
# combined, then cap to 150k/75k by count
for w in (0.5,1.0,2.0):
    bi=Counter(web[0]); tri=Counter(web[1])
    for k,c in wiki[0].items(): bi[k]+=c*w
    for k,c in wiki[1].items(): tri[k]+=c*w
    bi=dict(bi.most_common(150000)); tri=dict(tri.most_common(75000))
    evaluate(bi,tri,f'web+wiki*{w} capped')
# larger combined cap
for cap in (300000,600000):
    bi=Counter(web[0]); tri=Counter(web[1])
    for k,c in wiki[0].items(): bi[k]+=c
    for k,c in wiki[1].items(): tri[k]+=c
    bi=dict(bi.most_common(cap)); tri=dict(tri.most_common(cap//2))
    evaluate(bi,tri,f'web+wiki cap {cap}')
