from graphics import*
import time     # 延遲執行+記錄運行時間
import ctypes   # 調用C語言函式庫
import os, sys

# 定義常量+全域變數
class const:
    MARGIN = 100       # 棋盤邊距
    GRID = 30         # 每個網格的大小
    NUM = 22          # 棋盤格子數量 (從0到22，總共23個點)
    LEN = 630         # 棋盤的總長度 (NUM-1) * GRID
    PIECE_RADIUS = 10 # 棋子的半徑
    BOARD_MAX = 22
    MIDPOINT_X = 11
    MIDPOINT_Y = 11

# 定義游戲畫面
win = GraphWin(title="Gomoku", width = 800, height = 800)
txt = Text(Point(400,50), "")
txt.setTextColor(color_rgb(0,0,0))
txt.setSize(30)
txt.setFace('courier')
txt.setStyle("bold")
txt_round = Text(Point(20,120), "")

p_time = Text(Point(50,600), "")
p_time.setTextColor(color_rgb(255,0,0))
p_time.setFace('courier')

# 加載共享庫
ai_lib = ctypes.CDLL('./ai.dll')

# 定義C函數的返回值和參數類型
ai_lib.initZobristTable.restype = None
ai_lib.initTranspositionTable.restype = None
ai_lib.aiRound.restype = None
ai_lib.aiRound.argtypes = [ctypes.POINTER(ctypes.c_int * const.BOARD_MAX * const.BOARD_MAX), 
                           ctypes.c_int, ctypes.c_int, 
                           ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
ai_lib.checkUnValid.restype = ctypes.c_int
ai_lib.checkUnValid.argtypes = [ctypes.POINTER(ctypes.c_int * const.BOARD_MAX * const.BOARD_MAX),
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int]
ai_lib.checkWin.restype = ctypes.c_int
ai_lib.checkWin.argtypes = [
    ctypes.POINTER(ctypes.c_int * const.BOARD_MAX * const.BOARD_MAX),  # 棋盘二维数组
    ctypes.c_int,  # minX
    ctypes.c_int,  # maxX
    ctypes.c_int,  # minY
    ctypes.c_int,  # maxY
    ctypes.c_int   # currentPlayer
]
ai_lib.updateZobristKey.restype = None
ai_lib.updateZobristKey.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]

# 定义 ctypes 二维数组的类型
CBoardType = (ctypes.c_int * const.BOARD_MAX) * const.BOARD_MAX


#---------------------------（游戲畫面+提示）-------------------------
# 游戲畫面
def drawWin():
    win.setBackground(color_rgb(255, 208, 118))
    
    # 判断运行环境，设置图片路径
    if getattr(sys, 'frozen', False):
        # 打包后的路径（PyInstaller）
        bundle_dir = sys._MEIPASS
    else:
        # 开发环境中的当前文件路径
        bundle_dir = os.path.abspath(os.path.dirname(__file__))

    # 获取图片的完整路径
    img_path = os.path.join(bundle_dir, "200w.gif")

    # 使用图像路径创建图片对象
    img = Image(Point(50, 50), img_path)
    img.draw(win)
    
    # 棋盤
    for i in range(const.NUM):
        # 繪製垂直線
        line = Line(Point(const.MARGIN + i * const.GRID, const.MARGIN), 
                    Point(const.MARGIN + i * const.GRID, const.MARGIN + const.LEN))
        line.draw(win)
        # 繪製水平線
        line = Line(Point(const.MARGIN, const.MARGIN + i * const.GRID), 
                    Point(const.MARGIN + const.LEN, const.MARGIN + i * const.GRID))
        line.draw(win)
    txt.draw(win)
    p_time.draw(win)
    # 中心點
    n_piece = Circle(Point(100+11*30, 100+11*30),7)
    n_piece.setFill('black')
    n_piece.draw(win)
    

# 提示詞
def notice(string: str):
    txt.setText(string)
    win.update()

def restart():
    return
#----------------------------(游戲)----------------------------
# 初始化
def init():
    Round = 1    # 局數計算
    board = [[0 for _ in range(const.BOARD_MAX)] for _ in range(const.BOARD_MAX)] # 初始化棋盤
    ai_lib.initZobristTable()
    ai_lib.initTranspositionTable()
    return Round, board

# 選先手
def chooseFisrt(point, player, ai):
    x = point.getX(); y = point.getY()
    

    return True

# 檢查指定位置落子後是否形成無效連線（禁手）
def check_valid_move(board, x, y, player):
    # 将 Python 的二维列表转换为 ctypes 二维数组
    c_board = CBoardType()
    for i in range(const.BOARD_MAX):
        for j in range(const.BOARD_MAX):
            c_board[i][j] = board[i][j]

    # 调用 C 函数
    result = ai_lib.checkUnValid(ctypes.byref(c_board), x, y, player)

    return result

# 檢查是否有人勝利
def checkWin(board, minX, maxX, minY, maxY, currentPlayer):
    # 将 Python 的二维列表转换为 ctypes 二维数组
    c_board = CBoardType()
    for i in range(const.BOARD_MAX):
        for j in range(const.BOARD_MAX):
            c_board[i][j] = board[i][j]

    # 调用 C 函数 checkWin
    result = ai_lib.checkWin(ctypes.byref(c_board), minX, maxX, minY, maxY, currentPlayer)
    
    return result

# Ai回合
def aiMove(board, ai, roundCounter):
    bestx = ctypes.c_int()
    besty = ctypes.c_int()

    # 将 Python 的二维列表转换为 ctypes 二维数组
    c_board = CBoardType()
    for i in range(const.BOARD_MAX):
        for j in range(const.BOARD_MAX):
            c_board[i][j] = board[i][j]

    # 调用 C 函数
    ai_lib.aiRound(ctypes.byref(c_board), ai, roundCounter, 
                   ctypes.byref(bestx), ctypes.byref(besty))

    # 从 ctypes 返回最佳位置
    print(f"Python AI Move: ({bestx.value}, {besty.value})")
    return bestx.value, besty.value

# 游戲流程
def game(board, roundCounter, player, ai):
    Round = 1   # 1=黑棋回合，2=白棋回合
    winner, chance = 0, 3
    notice("Start gomoku game ^_^")
    time.sleep(1)
    while True:
        x, y = 0, 0
        start, end = 0, 0

        if(Round == ai):           # ai回合
            notice("AI正在下棋...")
            start = time.time()
            x, y = aiMove(board, ai, roundCounter)
            end = time.time()
        else:                      # 玩家回合
            if(roundCounter == 1):notice("第一手請落子在正中心位置")
            else: notice("玩家正在下棋...")
            start = time.time()
            point = win.getMouse()
            x = round((point.getX() - const.MARGIN) / const.GRID)
            y = round((point.getY() - const.MARGIN) / const.GRID)
            end = time.time()
            print(x,y)

        # 檢查落子是否合法
        if(check_valid_move(board, x, y, Round) == 1 and 0<x<22 and 0<y<22):
            piece = Circle(Point(100+x*30, 100+y*30),15)
            board[y][x] = Round
            ai_lib.updateZobristKey(x, y, Round)    # 更新 Zobrist 键
            

            p_time.setText("耗時%.2fs"%(end-start))

            if(Round == 1):
                piece.setFill('black')
            else:
                piece.setFill('white')
            piece.draw(win)
            roundCounter += 1
            
        
        else:
            chance -= 1
            notice(f"你還有{chance}次機會")
            win.update()
            time.sleep(1)
            if(chance ==0):
                winner = 3 - Round
                break
            continue

        # 檢查是否(勝利)
        winner = checkWin(board, 0, const.BOARD_MAX-1, 0, const.BOARD_MAX-1, Round)
        if(winner == 0):
            Round = 3-Round     # 轉換回合
            time.sleep(1)
        else: 
            break

        win.update()  # 每回合结束后刷新窗口

    return winner, roundCounter

def main():
    roundCounter, board = init()
    drawWin()
    # 選擇先手
    player, ai = 1,2
    '''
    point = win.getMouse()
    while(not chooseFisrt(point, player, ai)):
        point = win.getMouse()  #除了點擊先手或退出，點擊其他界面無效
    chooseFisrt(point, player, ai)
    '''
    # 開始游戲
    result, roundCounter = game(board, roundCounter, player, ai)
    print(roundCounter)
    if(result == ai):
        count = (roundCounter // 2)
        notice(f"AI花了{count}手才勝利!")
    else:
        notice("恭喜玩家!")
    win.getMouse()
    win.close

main()

