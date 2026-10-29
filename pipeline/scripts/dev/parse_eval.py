import json, sys, collections, re, pickle
from earnings_tone import data
rows=[json.loads(l) for l in open(sys.argv[2])]
intro=re.compile(r"(first|next) question|question (comes|is) from|from the line of|you may (now )?go ahead|your line is",re.I)
st=collections.Counter(); per=[]
for r in rows:
    t=data._row_to_transcript(r)
    if t is None: st['dropped']+=1; continue
    T=t.turns; n=len(T); st['n']+=1
    qa=[i for i,x in enumerate(T) if x.section=='qa']; fq=qa[0] if qa else n
    if not qa: st['no_qa']+=1
    elif fq/n<0.15: st['split_first_15pct']+=1
    np_=len(t.qa_pairs())
    if np_==0: st['zero_pairs']+=1
    # first analyst-labelled speaker should be the person the operator first introduces
    sp=collections.defaultdict(set)
    for x in T: sp[x.speaker].add(x.role)
    an=[s for s,r in sp.items() if 'analyst' in r]; ex=[s for s,r in sp.items() if 'exec' in r]
    if not ex: st['no_exec']+=1
    if any(x.role=='analyst' and x.section=='prepared' for x in T): st['analyst_in_prepared']+=1
    # header ground truth (2018-era)
    sc=r['structured_content']; sc=json.loads(sc) if isinstance(sc,str) else sc
    hdr={h['speaker'].lower():h['text'].lower() for h in sc if h['speaker'].lower() in('executives','analysts')}
    if hdr:
        st['hdr_calls']+=1
        for x in T:
            if x.role=='operator': continue
            truth='analyst' if x.speaker.lower() in hdr.get('analysts','') and x.speaker.lower() not in hdr.get('executives','') else ('exec' if x.speaker.lower() in hdr.get('executives','') else None)
            if truth: st['hdr_turns']+=1; st['hdr_turns_wrong']+= truth!=x.role
    # answer share: share of QA exec words
    qaw=sum(len(x.text.split()) for x in T if x.section=='qa' and x.role=='exec')
    per.append(dict(sym=r['symbol'],date=r['date'],n=n,fq=fq,pairs=np_,an=an,ex=ex,qa_exec_words=qaw))
print(dict(st))
pickle.dump(per,open(sys.argv[1],"wb"))
