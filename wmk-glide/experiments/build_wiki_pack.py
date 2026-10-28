import os
import re, gzip, pickle
from collections import Counter
# Vocabulary from de_full (the pack gates on the full list)
known=set()
for line in open('data/de_full.txt',encoding='utf-8'):
    p=line.split()
    if p: known.add(p[0].lower())
# generic tokenizer: letters incl. umlauts/ß, apostrophe/hyphen inside; lower; strip edges
tok=re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)
bi=Counter(); tri=Counter()
n=0
for line in open('data/wiki/deu_wikipedia_2021_1M/deu_wikipedia_2021_1M-sentences.txt',encoding='utf-8'):
    parts=line.split('\t',1)
    text=parts[1] if len(parts)==2 else parts[0]
    ws=[]
    for m in tok.finditer(text.lower().replace('’',"'")):
        w=m.group(0)
        if w in known: ws.append(w)
        else: ws.append(None)
    # count adjacent known pairs; a None breaks
    for a,b in zip(ws,ws[1:]):
        if a and b: bi[(a,b)]+=1
    for a,b,c in zip(ws,ws[1:],ws[2:]):
        if a and b and c: tri[(a,b,c)]+=1
    n+=1
    if n%200000==0: print(n,len(bi),len(tri))
print('sentences',n,'bigrams',len(bi),'trigrams',len(tri))
bi=dict(bi.most_common(150000)); tri=dict(tri.most_common(75000))
pickle.dump((bi,tri),open('wiki_pack.pkl','wb'))
print('kept',len(bi),len(tri))
