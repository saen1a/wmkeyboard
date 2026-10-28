import os
import bz2, gzip, re, random, math
from collections import Counter, defaultdict
# vocab de_full
known=set()
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: known.add(p[0].lower())
tok=re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)
def tokens(text):
    return [w for m in tok.finditer(text.lower().replace('’',"'")) if (w:=m.group(0)) in known]
sent=[]
with bz2.open('data/deu_sentences.tsv.bz2','rt',encoding='utf-8',errors='replace') as f:
    for line in f:
        p=line.rstrip('\n').split('\t',2)
        if len(p)>=3:
            t=tokens(p[2])
            if len(t)>=2: sent.append(t)
print('sentences',len(sent))
random.Random(1).shuffle(sent)
cut=int(len(sent)*0.8); train=sent[:cut]; test=sent[cut:]
def counts(items):
    bi=Counter(); tri=Counter()
    for t in items:
        for a,b in zip(t,t[1:]): bi[(a,b)]+=1
        for a,b,c in zip(t,t[1:],t[2:]): tri[(a,b,c)]+=1
    return bi,tri
bi_t,tr_t=counts(train)
print('tatoeba train bigrams',len(bi_t),'trigrams',len(tr_t))
# cap
bi_t=dict(bi_t.most_common(150000)); tr_t=dict(tr_t.most_common(75000))
# web pack
bi_w=Counter(); tr_w=Counter()
for line in gzip.open('data/de_bigrams.txt.gz','rt',encoding='utf-8'):
    p=line.rstrip('\n').rsplit(' ',1)
    if len(p)==2:
        ws=p[0].split()
        if len(ws)==2: bi_w[(ws[0],ws[1])]+=int(p[1])
for line in gzip.open('data/de_trigrams.txt.gz','rt',encoding='utf-8'):
    p=line.rstrip('\n').rsplit(' ',1)
    if len(p)==2:
        ws=p[0].split()
        if len(ws)==3: tr_w[(ws[0],ws[1],ws[2])]+=int(p[1])
# unigram de_full
uni=Counter()
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: uni[p[0].lower()]=int(p[1])
def nexts(bi):
    d=defaultdict(list)
    for (a,b),c in bi.items(): d[a].append((b,c))
    for a in d: d[a].sort(key=lambda x:-x[1])
    return d
uni_top=[w for w,_ in uni.most_common(3)]
def evaluate(bi,label,top=3):
    nx=nexts(bi); hit1=hit3=n=0
    for t in test:
        for i in range(1,len(t)):
            prev=t[i-1]; target=t[i]; n+=1
            cand=[w for w,_ in nx.get(prev,[])[:top]]
            if not cand: cand=uni_top
            hit1+=cand[0]==target; hit3+=target in cand
    print(label,f'n={n} top1 {100*hit1/n:.2f} top3 {100*hit3/n:.2f}')
evaluate(bi_w,'web/news pack')
evaluate(bi_t,'tatoeba pack')
# combined
combo=Counter(bi_w)
for k,c in bi_t.items(): combo[k]+=c
combo=dict(combo.most_common(150000))
evaluate(combo,'web+tatoeba (cap 150k)')
