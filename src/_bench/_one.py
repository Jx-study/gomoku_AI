
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
