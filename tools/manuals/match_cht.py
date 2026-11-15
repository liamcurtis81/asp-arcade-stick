import json, os, re, sys
DB='/home/claude/moves/ldb/cht'
SYS={'sfcx':('sfc','Nintendo - Super Nintendo Entertainment System'),
     'fcx':('nes','Nintendo - Nintendo Entertainment System'),
     'mdx':('megadrive','Sega - Mega Drive - Genesis'),
     'gbax':('gba','Nintendo - Game Boy Advance'),
     'psxx':('psx','Sony - PlayStation')}
G=json.load(open('/home/claude/man/games.json'))
def base(s):
    s=re.sub(r'\[.*?\]','',s); s=re.sub(r'\(.*?\)','',s)
    s=s.replace('&','and').replace("'",'').lower()
    s=re.sub(r'^the\s+','',s); s=re.sub(r',\s*the\b','',s)
    return ' '.join(re.findall(r'[a-z0-9]+',s))
ROM={'ii':'2','iii':'3','iv':'4','v':'5','vi':'6'}
def base2(s):
    w=base(s.replace('&',' ')).split()
    w=[ROM.get(x,x) for x in w if x not in ('and','disneys','disney')]
    return ' '.join(w)
def regs(s): return ' '.join(re.findall(r'\((.*?)\)',s)).lower()
out={}; unmatched={}
for emu,(sysn,folder) in SYS.items():
    files=[f[:-4] for f in os.listdir(os.path.join(DB,folder)) if f.endswith('.cht')]
    idx={}
    for f in files:
        idx.setdefault(base(f),[]).append(f)
        idx.setdefault('~'+base2(f),[]).append(f)
    res={}; miss=[]
    for g in G[emu]:
        cands=[]
        for nm in g['title'].split('~'):
            b=base(nm)
            cands+=idx.get(b,[]) or idx.get('~'+base2(nm),[])
        if not cands:
            miss.append(g['title']); continue
        tr=regs(g['title'])
        def score(f):
            r=regs(f); s=0
            for i,reg in enumerate(['usa','europe','world','japan']):
                if reg in r: s+= (10-i)*(2 if reg in tr else 1)
            if 'rev' in r or 'beta' in r or 'proto' in r: s-=5
            if sysn=='gba' and 'code breaker' in r: s+=50
            if sysn=='gba' and ('action replay' in r or 'gameshark' in r): s-=50
            if sysn=='psx' and 'gameshark' in r: s+=50
            m=re.search(r'\d+',open(os.path.join(DB,folder,f+'.cht'),errors='ignore').readline()); n=int(m.group()) if m else 0
            return (s, n)
        best=max(cands,key=score)
        res[g['key']]=os.path.join(folder,best+'.cht')
    out[sysn]=res; unmatched[sysn]=miss
    print(sysn, len(res),'/',len(G[emu]))
json.dump(out,open('cht_map.json','w'),indent=1)
json.dump(unmatched,open('cht_unmatched.json','w'),indent=1)
