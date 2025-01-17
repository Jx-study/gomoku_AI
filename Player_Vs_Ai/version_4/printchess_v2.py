from graphics import*
import time     # 延遲執行+記錄運行時間
import ctypes   # 調用C語言函式庫
import os, sys

# 定義常量+全域變數
class const:
    MARGIN = 100      # 棋盤邊距
    GRID = 30         # 每個網格的大小
    NUM = 22          # 棋盤格子數量 (從0到22，總共23個點)
    LEN = 630         # 棋盤的總長度 (NUM-1) * GRID
    PIECE_RADIUS = 10 # 棋子的半徑
    BOARD_MAX = 22
    MIDPOINT_X = 11
    MIDPOINT_Y = 11

# 定義游戲畫面
win = GraphWin(title="Gomoku", width = 800, height = 800)
txt_notice = Text(Point(400,50), "")
txt_notice.setTextColor(color_rgb(0,0,0))
txt_notice.setSize(30)
txt_notice.setFace('courier')
txt_notice.setStyle("bold")

txt_round = Text(Point(50,120), "")
txt_round.setSize(18)
txt_round.setFace('helvetica')

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
    txt_notice.draw(win)
    txt_round.draw(win)
    p_time.draw(win)
    # 中心點
    n_piece = Circle(Point(100+11*30, 100+11*30),7)
    n_piece.setFill('black')
    n_piece.draw(win)
    
def choose_player(window):
    # 在現有的視窗上顯示讓玩家選擇先手或後手的畫面
    # 背景
    background = Rectangle(Point(250, 250), Point(550, 450))
    background.setFill(color_rgb(255, 255, 255))
    background.draw(window)

    # 在視窗中央顯示提示文字
    message = Text(Point(400, 300), "Choose your role:")
    message.setTextColor(color_rgb(0, 0, 0))
    message.draw(window)

    # 建立選擇按鈕
    black_button = Rectangle(Point(300, 350), Point(400, 400))
    black_button.setFill(color_rgb(0, 0, 0))
    black_button.setOutline(color_rgb(255, 255, 255))
    black_text = Text(Point(350, 375), "Black")
    black_text.setTextColor(color_rgb(255, 255, 255))
    black_button.draw(window)
    black_text.draw(window)

    white_button = Rectangle(Point(400, 350), Point(500, 400))
    white_button.setFill(color_rgb(255, 255, 255))
    white_button.setOutline(color_rgb(0, 0, 0))
    white_text = Text(Point(450, 375), "White")
    white_button.draw(window)
    white_text.draw(window)

    # 等待玩家選擇
    point = window.getMouse()
    if black_button.getP1().getX() < point.getX() < black_button.getP2().getX() and \
       black_button.getP1().getY() < point.getY() < black_button.getP2().getY():
        player, ai = 1, 2
    elif white_button.getP1().getX() < point.getX() < white_button.getP2().getX() and \
         white_button.getP1().getY() < point.getY() < white_button.getP2().getY():
        player, ai = 2, 1
    else:
        # 如果玩家點擊了其他地方,則重新選擇
        background.undraw()
        message.undraw()
        black_button.undraw()
        black_text.undraw()
        white_button.undraw()
        white_text.undraw()
        return choose_player(window)

    # 隱藏選擇畫面
    background.undraw()
    message.undraw()
    black_button.undraw()
    black_text.undraw()
    white_button.undraw()
    white_text.undraw()

    return player, ai

# 提示詞
def notice(string: str):
    txt_notice.setText(string)
    win.update()

def restart():
    return
#----------------------------(游戲)----------------------------
# 初始化
def init():
    roundCounter = 1    # 局數計算
    board = [[0 for _ in range(const.BOARD_MAX)] for _ in range(const.BOARD_MAX)] # 初始化棋盤
    ai_lib.initZobristTable()
    ai_lib.initTranspositionTable()
    return roundCounter, board


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
    correct = True
    notice("Start gomoku game ^_^")
    time.sleep(1)
    while True:
        x, y = 0, 0
        start, end = 0, 0
        txt_round.setText("回合數:%d"%roundCounter)

        if(Round == ai):           # ai回合
            notice("AI正在下棋...")
            start = time.time()
            x, y = aiMove(board, ai, roundCounter)
            end = time.time()
        else:                      # 玩家回合
            if(roundCounter == 1  and correct):notice("第一手請落子在正中心位置")
            elif(roundCounter == 1  and correct == False): notice("麻煩第一手落子在中心")
            else: notice("玩家正在下棋...")
            start = time.time()
            point = win.getMouse()
            x = round((point.getX() - const.MARGIN) / const.GRID)
            y = round((point.getY() - const.MARGIN) / const.GRID)
            end = time.time()
            print(x,y)
            
        # 檢查落子是否合法
        if(roundCounter == 1 and (x != 11 or y != 11)): 
            correct = False
            continue
        
        if(check_valid_move(board, x, y, Round) == 1 and 0<x<22 and 0<y<22):
            board[y][x] = Round
            ai_lib.updateZobristKey(x, y, Round)    # 更新 Zobrist 键
            piece = Circle(Point(100+x*30, 100+y*30),15)
            txt_num = Text(Point(100+x*30, 100+y*30),"%d"%roundCounter)
            txt_num.setTextColor("red")
            p_time.setText("耗時%.2fs"%(end-start))

            if(Round == 1):
                piece.setFill('black')
            else:
                piece.setFill('white')
            piece.draw(win)
            txt_num.draw(win)
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
    player, ai = choose_player(win)
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

if __name__ == "__main__":
    main()