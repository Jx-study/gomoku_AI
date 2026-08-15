import ctypes, time, sys
import benchmark_ai as b

# 盤面以中心點的偏移表示，棋盤大小由 dll 的 getBoardMax() 決定
OFF={
 "quiet-8":[(0,0,1),(1,1,2),(-2,1,1),(2,-1,2),(-1,3,1),(3,-2,2),(-3,-2,1),(1,4,2)],
 "quiet-12":[(0,0,1),(1,1,2),(-2,1,1),(2,-1,2),(-1,3,1),(3,-2,2),(-3,-2,1),(1,4,2),(4,2,1),(-4,-3,2),(5,1,1),(-5,3,2)],
 "quiet-16":[(0,0,1),(1,1,2),(-2,1,1),(2,-1,2),(-1,3,1),(3,-2,2),(-3,-2,1),(1,4,2),(4,2,1),(-4,-3,2),(5,1,1),(-5,3,2),(-2,5,1),(6,-2,2),(-6,0,1),(4,5,2)],
}
def run(lib,mv,ai=2):
    BM=b.BOARD_MAX
    bd=[[0]*BM for _ in range(BM)]
    for x,y,p in mv: bd[y][x]=p
    c=b.CBoardType()
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
base=b.bind_lib(BASE); new=b.bind_lib(NEW)
c0=b.BOARD_MAX//2
POS={n:[(c0+dx,c0+dy,p) for dx,dy,p in off] for n,off in OFF.items()}
# add the original benchmark's endGame-heavy scenarios too
for n,m in b.scenarios(): POS[n]=m
print(f"{'pos':12}{'before':>9}{'after':>9}{'speedup':>9}  {'move_before':>13}{'move_after':>13}  same")
tb=ta=0
for n,mv in POS.items():
    b1,m1=run(base,mv); b2,m2=run(new,mv); tb+=b1; ta+=b2
    print(f"{n:12}{b1:8.3f}s{b2:8.3f}s{(b1/b2 if b2 else 0):8.1f}x  {str(m1):>13}{str(m2):>13}  {'OK' if m1==m2 else '**DIFF**'}")
print(f"\nTOTAL  before={tb:.3f}s  after={ta:.3f}s  speedup={tb/ta:.1f}x")
