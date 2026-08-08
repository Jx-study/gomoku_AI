import ctypes, sys
BM=22; CB=(ctypes.c_int*BM)*BM
mv=[(11,11,1),(12,12,2),(9,12,1),(13,10,2),(10,14,1),(14,9,2),(8,9,1),(12,15,2)]
def board_c(moves):
    bd=[[0]*BM for _ in range(BM)]
    for x,y,p in moves: bd[y][x]=p
    c=CB()
    for i in range(BM):
        for j in range(BM): c[i][j]=bd[i][j]
    return c
# 用法: python zob_key_probe.py [<dll> ...]（預設檢查 ../ai.dll）
DLLS = sys.argv[1:] or ['../ai.dll']
for name,dll in [(d, d) for d in DLLS]:
    l=ctypes.CDLL(dll); l.initZobristTable(); l.initTranspositionTable()
    l.aiRound.restype=None
    l.aiRound.argtypes=[ctypes.POINTER(CB),ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]
    l.updateZobristKey.restype=None; l.updateZobristKey.argtypes=[ctypes.c_int]*3
    l.computeZobristKey.restype=ctypes.c_ulonglong
    l.computeZobristKey.argtypes=[ctypes.POINTER(CB)]
    key=ctypes.c_ulonglong.in_dll(l,"currentZobristKey")
    c=board_c(mv)
    truth=l.computeZobristKey(ctypes.byref(c))
    print(f"\n{name}")
    print(f"  before any call: currentZobristKey=0x{key.value:016x}  (true key=0x{truth:016x})  match={key.value==truth}")
    bx=ctypes.c_int(); by=ctypes.c_int()
    l.aiRound(ctypes.byref(c),2,len(mv)+1,ctypes.byref(bx),ctypes.byref(by))
    print(f"  after aiRound : currentZobristKey=0x{key.value:016x}  match_truth={key.value==truth}")
    for (x,y,p) in mv[-2:]: l.updateZobristKey(x,y,0)
    print(f"  after buggy undo XORs: currentZobristKey=0x{key.value:016x}  match_truth={key.value==truth}")
    l.aiRound(ctypes.byref(board_c(mv)),2,len(mv)+1,ctypes.byref(bx),ctypes.byref(by))
    print(f"  after next search    : currentZobristKey=0x{key.value:016x}  match_truth={key.value==truth}  <-- fixed版應為 True")
