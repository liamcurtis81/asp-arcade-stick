import json,re,difflib,unicodedata
idx=json.load(open('/mnt/user-data/uploads/Downloads/asp_manual_index.json'))
games=json.load(open('games.json'))
def norm(s):
    s=unicodedata.normalize('NFKD',s)
    s=re.sub(r'\.(pdf|smc|nes|zip)$','',s,flags=re.I)
    s=re.sub(r'[\(\[][^\)\]]*[\)\]]','',s)          # regions, flags
    s=s.lower().replace('&',' and ')
    s=re.sub(r"\b(disney's|disneys|disney)\b",'',s)
    s=re.sub(r"'s\b|’s\b",'s',s)
    s=re.sub(r'\b(\w+) s\b',r'\1s',s)               # "Bonk s" -> "Bonks"
    m=re.match(r'^(.*), (the|a)\b(.*)$',s)
    if m: s=m.group(2)+' '+m.group(1)+m.group(3)
    s=re.sub(r'[^a-z0-9]+',' ',s)
    s=re.sub(r'\b(the|a)\b',' ',s)
    rom={'i':'1','ii':'2','iii':'3','iv':'4','v':'5','vi':'6','vii':'7','viii':'8'}
    toks=s.split()
    toks=[rom.get(t,t) if k>0 else t for k,t in enumerate(toks)]
    s=' '.join(toks)
    s=s.replace('megaman','mega man').replace('chip n dale','chipn dale').replace('chipn dale','chip n dale')
    s=re.sub(r' 1$','',s)
    return s
src={'sfcx':['kirklands_manual_labor_-_super_nintendo_-_usa_-_2k_version','snes_manual_archive'],
     'gbax':['kirklands-manual-labor-nintendo-game-boy-advance-usa-4k-version'],
     'mdx':['SEGAGenesisMegaDriveManuals'],'fcx':['rx2MRPnes1250pxPDF']}
out={}
for emu,items in src.items():
    res=[]
    cands=[]
    for it in items:
        for n,sz in idx[it]['files']:
            reg=' '.join(re.findall(r'\(([^)]*)\)',n))
            cands.append((norm(n),n,it,sz,reg))
    names=[c[0] for c in cands]
    for g in games[emu]:
        t=g['title'] if emu=='mdx' else g['key']
        q=norm(t)
        exact=[c for c in cands if c[0]==q]
        if exact:
            # prefer USA, then first item
            exact.sort(key=lambda c:(items.index(c[2]), 0 if 'USA' in c[4] else 1 if 'Europe' in c[4] or 'UK' in c[4] else 2))
            best=exact[0]; score=1.0
        else:
            m=difflib.get_close_matches(q,names,n=1,cutoff=0.0)
            best=cands[names.index(m[0])] if m else None
            score=difflib.SequenceMatcher(None,q,m[0]).ratio() if m else 0
        res.append({'key':g['key'],'title':t,'q':q,'file':best[1] if best else None,'item':best[2] if best else None,'size':best[3] if best else 0,'score':round(score,2)})
    out[emu]=res
json.dump(out,open('match.json','w'),indent=1)
for emu,r in out.items():
    ok=sum(1 for x in r if x['score']==1); print(emu,len(r),'exact',ok)
