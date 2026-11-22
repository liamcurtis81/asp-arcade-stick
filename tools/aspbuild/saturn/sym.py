import sys,struct,bisect,subprocess,collections
binf,prof=sys.argv[1],sys.argv[2]
syms=[]
for l in subprocess.run(['arm-linux-gnueabi-nm','-n','-S',binf],capture_output=True,text=True).stdout.splitlines():
    p=l.split()
    if len(p)>=4 and p[2] in 'tTwW': syms.append((int(p[0],16),int(p[1],16),p[3]))
    elif len(p)==3 and p[1] in 'tT': syms.append((int(p[0],16),0,p[2]))
addrs=[s[0] for s in syms]
d=open(prof,'rb').read(); n=struct.unpack('<I',d[:4])[0]
pcs=struct.unpack('<%dI'%n,d[4:4+4*n]); tids=struct.unpack('<%dH'%n,d[4+4*n:4+6*n])
def name(pc):
    i=bisect.bisect_right(addrs,pc)-1
    if i>=0:
        a,sz,nm=syms[i]
        if pc<a+max(sz,1) or (sz==0 and pc-a<0x10000): return nm
    if 0x10000000<=pc: return '<recompiled SH-2 code / heap>'
    return '?%x'%pc
c=collections.Counter(); ct=collections.Counter(tids); bythread=collections.defaultdict(collections.Counter)
for pc,t in zip(pcs,tids):
    nm=name(pc); c[nm]+=1; bythread[t][nm]+=1
print('samples',n,'threads',dict(ct.most_common()))
for nm,k in c.most_common(45): print('%5.1f%% %s'%(100*k/n,nm))
for t,cc in bythread.items():
    print('--- thread',t, sum(cc.values()))
    for nm,k in cc.most_common(8): print('   %5.1f%% %s'%(100*k/sum(cc.values()),nm))
