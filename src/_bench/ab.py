import ctypes, time, sys
BM=22; CB=(ctypes.c_int*BM)*BM
def load(p):
    l=ctypes.CDLL(p); l.initZobristTable(); l.aiRound.restype=None
    l.aiRound.argtypes=[ctypes.POINTER(CB),ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
    return l
POS={
 "quiet-8":[(11,11,1),(12,12,2),(9,12,1),(13,10,2),(10,14,1),(14,9,2),(8,9,1),(12,15,2)],
 "quiet-12":[(11,11,1),(12,12,2),(9,12,1),(13,10,2),(10,14,1),(14,9,2),(8,9,1),(12,15,2),(15,13,1),(7,8,2),(16,12,1),(6,14,2)],
 "quiet-16":[(11,11,1),(12,12,2),(9,12,1),(13,10,2),(10,14,1),(14,9,2),(8,9,1),(12,15,2),(15,13,1),(7,8,2),(16,12,1),(6,14,2),(9,16,1),(17,9,2),(5,11,1),(15,16,2)],
}
# add the original benchmark's endGame-heavy scenarios too
import benchmark_ai as b
for n,m in b.DISTINCT_SCENARIOS: POS[n]=m
def run(lib,mv,ai=2):
    bd=[[0]*BM for _ in range(BM)]
    for x,y,p in mv: bd[y][x]=p
    c=CB()
    for i in range(BM):
        for j in range(BM): c[i][j]=bd[i][j]
    bx=ctypes.c_int(); by=ctypes.c_int()
    t=time.perf_counter(); lib.aiRound(ctypes.byref(c),ai,len(mv)+1,ctypes.byref(bx),ctypes.byref(by))
    return time.perf_counter()-t,(bx.value,by.value)
# 用法: python ab.py <baseline.dll> [<new.dll>]
#   baseline 通常用 git 取出的舊版編譯而成，例如：
#   git show <commit>:src/ai.c > old.c && gcc -shared -o old.dll -fPIC old.c
BASE = sys.argv[1] if len(sys.argv) > 1 else './ai_baseline.dll'
NEW  = sys.argv[2] if len(sys.argv) > 2 else '../ai.dll'
base=load(BASE); new=load(NEW)
print(f"{'pos':12}{'before':>9}{'after':>9}{'speedup':>9}  {'move_before':>13}{'move_after':>13}  same")
tb=ta=0
for n,mv in POS.items():
    b1,m1=run(base,mv); b2,m2=run(new,mv); tb+=b1; ta+=b2
    print(f"{n:12}{b1:8.3f}s{b2:8.3f}s{(b1/b2 if b2 else 0):8.1f}x  {str(m1):>13}{str(m2):>13}  {'OK' if m1==m2 else '**DIFF**'}")
print(f"\nTOTAL  before={tb:.3f}s  after={ta:.3f}s  speedup={tb/ta:.1f}x")
