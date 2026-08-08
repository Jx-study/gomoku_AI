import ctypes, time, subprocess, sys, json
# Run each DLL in a FRESH process per position to eliminate cross-call TT/Zobrist state
CODE = r'''
import ctypes, time, sys, json
BM=22; CB=(ctypes.c_int*BM)*BM
dll, key = sys.argv[1], sys.argv[2]
POS={
 "quiet-8":[(11,11,1),(12,12,2),(9,12,1),(13,10,2),(10,14,1),(14,9,2),(8,9,1),(12,15,2)],
 "quiet-12":[(11,11,1),(12,12,2),(9,12,1),(13,10,2),(10,14,1),(14,9,2),(8,9,1),(12,15,2),(15,13,1),(7,8,2),(16,12,1),(6,14,2)],
 "quiet-16":[(11,11,1),(12,12,2),(9,12,1),(13,10,2),(10,14,1),(14,9,2),(8,9,1),(12,15,2),(15,13,1),(7,8,2),(16,12,1),(6,14,2),(9,16,1),(17,9,2),(5,11,1),(15,16,2)],
}
mv=POS[key]
l=ctypes.CDLL(dll); l.initZobristTable(); l.aiRound.restype=None
l.aiRound.argtypes=[ctypes.POINTER(CB),ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
bd=[[0]*BM for _ in range(BM)]
for x,y,p in mv: bd[y][x]=p
c=CB()
for i in range(BM):
    for j in range(BM): c[i][j]=bd[i][j]
bx=ctypes.c_int(); by=ctypes.c_int()
t=time.perf_counter(); l.aiRound(ctypes.byref(c),2,len(mv)+1,ctypes.byref(bx),ctypes.byref(by)); el=time.perf_counter()-t
print(json.dumps({"t":el,"m":[bx.value,by.value]}))
'''
# 用法: python ab_fresh.py <baseline.dll> [<new.dll>]
BASE = sys.argv[1] if len(sys.argv) > 1 else './ai_baseline.dll'
NEW  = sys.argv[2] if len(sys.argv) > 2 else '../ai.dll'
open('_one.py','w').write(CODE)
print(f"{'pos':10}{'before':>9}{'after':>9}  {'move_before':>13}{'move_after':>13}  same")
for key in ["quiet-8","quiet-12","quiet-16"]:
    r=[]
    for dll in [BASE, NEW]:
        out=subprocess.run([sys.executable,'_one.py',dll,key],capture_output=True,text=True)
        r.append(json.loads(out.stdout.strip().splitlines()[-1]))
    same = 'OK' if r[0]["m"]==r[1]["m"] else '**DIFF**'
    print(f"{key:10}{r[0]['t']:8.3f}s{r[1]['t']:8.3f}s  {str(tuple(r[0]['m'])):>13}{str(tuple(r[1]['m'])):>13}  {same}")
