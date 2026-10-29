import json, sys, re, collections
from earnings_tone import data
rows=[json.loads(l) for l in open(sys.argv[1])]
ts=[]
stats=collections.Counter()
for r in rows:
    t=data._row_to_transcript(r)
    if t is None: stats['dropped']+=1; continue
    turns=t.turns; n=len(turns)
    qa=[i for i,x in enumerate(turns) if x.section=='qa']
    first_qa=qa[0] if qa else n
    split_i=first_qa-1  # matched turn
    frac=first_qa/n
    roles=collections.Counter((x.section,x.role) for x in turns)
    pairs=len(t.qa_pairs())
    stats['n']+=1
    if frac<0.15: stats['split_in_first_15pct']+=1
    if not qa: stats['no_qa']+=1
    if pairs==0: stats['zero_pairs']+=1
    if roles[('prepared','exec')]<=1: stats['<=1 prepared exec turn']+=1
    ts.append((r['symbol'],r['year'],r['quarter'],n,first_qa,round(frac,2),pairs,dict(roles),turns[split_i].speaker if 0<=split_i<n else None, turns[split_i].text[:140] if 0<=split_i<n else None))
print(stats)
import random; random.seed(1)
for x in random.sample(ts,8): print(x,"\n")
json.dump(ts, open(sys.argv[2],'w'), default=str)
