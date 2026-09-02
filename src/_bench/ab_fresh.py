import ctypes, time, subprocess, sys, json
# Run each DLL in a FRESH process per position to eliminate cross-call TT/Zobrist state
CODE = r'''
import ctypes, time, sys, json
dll, key = sys.argv[1], sys.argv[2]
l=ctypes.CDLL(dll)
l.getBoardMax.restype=ctypes.c_int
BM=l.getBoardMax()          # 棋盤大小以 dll 為準（ai.c 是唯一定義處）
CB=(ctypes.c_int*BM)*BM
# 盤面以中心點的偏移表示，換棋盤大小不必重寫
OFF={
 "quiet-8":[(0,0,1),(1,1,2),(-2,1,1),(2,-1,2),(-1,3,1),(3,-2,2),(-3,-2,1),(1,4,2)],
 "quiet-12":[(0,0,1),(1,1,2),(-2,1,1),(2,-1,2),(-1,3,1),(3,-2,2),(-3,-2,1),(1,4,2),(4,2,1),(-4,-3,2),(5,1,1),(-5,3,2)],
 "quiet-16":[(0,0,1),(1,1,2),(-2,1,1),(2,-1,2),(-1,3,1),(3,-2,2),(-3,-2,1),(1,4,2),(4,2,1),(-4,-3,2),(5,1,1),(-5,3,2),(-2,5,1),(6,-2,2),(-6,0,1),(4,5,2)],
}
c0=BM//2
mv=[(c0+dx,c0+dy,p) for dx,dy,p in OFF[key]]
l.initZobristTable(); l.aiRound.restype=None
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
open('_one.py','w',encoding='utf-8').write(CODE)

# 棋盤大小不同的兩顆 dll 比走法毫無意義（各自在不同大小的棋盤上算），
# 但每個 worker 只看得到自己那顆，所以守衛必須在這裡做
def board_max(dll):
    l = ctypes.CDLL(dll)
    try:
        l.getBoardMax.restype = ctypes.c_int
        return l.getBoardMax()
    except AttributeError:
        sys.exit(f"error: {dll} 沒有 export getBoardMax()，無法得知它編譯時用的棋盤大小。\n"
                 f"       不確定兩顆 dll 在同樣大小的棋盤上比較時，數據沒有意義。\n"
                 f"       請改用有 getBoardMax() 的版本當基準。")
bm_base, bm_new = board_max(BASE), board_max(NEW)
if bm_base != bm_new:
    sys.exit(f"error: 兩顆 dll 的棋盤大小不同（{bm_base} vs {bm_new}），無法對比")

print(f"{'pos':10}{'before':>9}{'after':>9}  {'move_before':>13}{'move_after':>13}  same")
for key in ["quiet-8","quiet-12","quiet-16"]:
    r=[]
    for dll in [BASE, NEW]:
        out=subprocess.run([sys.executable,'_one.py',dll,key],capture_output=True,text=True,encoding='utf-8')
        r.append(json.loads(out.stdout.strip().splitlines()[-1]))
    same = 'OK' if r[0]["m"]==r[1]["m"] else '**DIFF**'
    print(f"{key:10}{r[0]['t']:8.3f}s{r[1]['t']:8.3f}s  {str(tuple(r[0]['m'])):>13}{str(tuple(r[1]['m'])):>13}  {same}")
