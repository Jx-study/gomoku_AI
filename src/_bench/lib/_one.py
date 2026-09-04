
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
