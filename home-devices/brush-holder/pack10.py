import random, math, sys
B=[(8.1,8.1,'B1'),(11.9,11.9,'B2'),(21.9,10,'B3'),(23.75,9.5,'B4'),(30.5,8.3,'B5'),(34.2,8.9,'B6'),
   (28,10,'B7'),(38,6.95,'B8'),(46.8,19,'B9'),(37,12.3,'B10'),(55,16.8,'B11')]
def cw(s): return 34 if s>14 else (27 if s>10.5 else 24)
C=3.0; HEAD=float(sys.argv[2]); DY=float(sys.argv[1]); DEP=29
def place(r,stemlim):
    xs=[0.0]
    for p,b in zip(r,r[1:]): xs.append(xs[-1]+max((p[0]+b[0])/2+C,(cw(p[1])+cw(b[1]))/2+1.2))
    lo,hi=-1e9,1e9
    for (h,s,_),x in zip(r,xs):
        lo=max(lo,-HEAD+h/2-x,-86+cw(s)/2-x,-stemlim-x); hi=min(hi,HEAD-h/2-x,86-cw(s)/2-x,stemlim-x)
    if lo>hi: return None
    return [x+(lo+hi)/2 for x in xs], hi-lo
def ok(f,b,xf,xb):
    sl=1e9
    for (hf,sf,_),x1 in zip(f,xf):
        for (hb,sb,_),x2 in zip(b,xb):
            d=math.hypot(x1-x2,DY)-((hf+hb)/2+C); sl=min(sl,d)
            if d<0: return None
            if abs(x1-x2)<(cw(sf)+cw(sb))/2+1 and DY<2*DEP-10.2+1.2: return None
    return sl
random.seed(11); res=[]
for it in range(800000):
    s=B[:]; random.shuffle(s); k=random.randint(4,7); f,b=s[:k],s[k:]
    if max(h for h,_,_ in b)>38.5: continue
    pf=place(f,99); 
    if pf is None: continue
    pb=place(b,74)
    if pb is None: continue
    sl=ok(f,b,pf[0],pb[0])
    if sl is None: continue
    res.append((round(min(pf[1],pb[1],sl),2),max(h for h,_,_ in b),[(n,h,s_,round(x,1)) for (h,s_,n),x in zip(f,pf[0])],[(n,h,s_,round(x,1)) for (h,s_,n),x in zip(b,pb[0])]))
res.sort(key=lambda t:(t[1],-t[0]))
seen=set()
for t in res:
    key=(tuple(x[0] for x in t[2]),tuple(x[0] for x in t[3]))
    if key in seen: continue
    seen.add(key); print(t)
    if len(seen)>4: break
print(len(res))
