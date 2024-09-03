import cv2
import numpy as np
import time
import os

# 常量設置
class const:
    MARGIN = 40       # 棋盤邊距
    GRID = 25         # 每個網格的大小
    NUM = 22          # 棋盤格子數量 (從0到22，總共23個點)
    LEN = 525         # 棋盤的總長度 (NUM-1) * GRID
    PIECE_RADIUS = 10 # 棋子的半徑
    WIN = 5           # 連成5子的勝利條件

# 棋子顏色
BLACK_COLOR = (0, 0, 0)
WHITE_COLOR = (255, 255, 255)

# 初始化棋盤圖像
def draw_board():
    img = np.zeros((700, 700, 3), dtype=np.uint8)
    img[:] = (118, 208, 255)  # 淡黃色背景

    # 繪製棋盤網格
    for i in range(const.NUM):
        # 繪製水平和垂直網格線
        cv2.line(img, (const.MARGIN, const.MARGIN + i * const.GRID), 
                 (const.MARGIN + const.LEN, const.MARGIN + i * const.GRID), (0, 0, 0), 1)
        cv2.line(img, (const.MARGIN + i * const.GRID, const.MARGIN), 
                 (const.MARGIN + i * const.GRID, const.MARGIN + const.LEN), (0, 0, 0), 1)
    return img

def draw_piece(img, row, col, color):
    x = const.MARGIN + col * const.GRID
    y = const.MARGIN + row * const.GRID
    cv2.circle(img, (x, y), const.PIECE_RADIUS, color, -1)

def update_board(img):
    cv2.imshow("Gomoku", img)
    cv2.waitKey(1)

def read_move_from_file():
    while True:
        if os.path.exists("a.txt"):
            try:
                with open("a.txt", "r") as f:
                    move = f.read().strip().split()
                os.remove("a.txt")
                return int(move[0]), int(move[1]), int(move[2])
            except (IndexError, ValueError, IOError):
                print("Error reading a.txt, retrying...")
                time.sleep(0.1)
        else:
            time.sleep(0.1)

def signal_next_turn():
    try:
        with open("b.txt", "w") as f:
            f.write("next")
    except IOError:
        print("Error writing to b.txt")

def update_text(img, pieces, text):
    # 重新绘制棋盘图像
    img[:] = draw_board()  # 调用draw_board函数获取棋盘图像
    
    # 重新绘制所有棋子
    for (row, col, color) in pieces:
        draw_piece(img, row, col, color)

    # 将文本按换行符拆分成多行
    lines = text.split('\n')
    y0, dy = 30, 30  # 初始y坐标和每行之间的间距
    
    for i, line in enumerate(lines):
        # 获取每行文字的尺寸 (宽度和高度)
        text_size = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 1, 1)[0]
        # 计算文字的起始x坐标，使其水平居中
        text_x = (img.shape[1] - text_size[0]) // 2
        # 计算y坐标位置
        text_y = y0 + i * dy
        
        # 在图像上绘制文字
        cv2.putText(img, line, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 1, cv2.LINE_AA)

def redraw_pieces(img, pieces):
    # 繪製所有棋子
    for (row, col, color) in pieces:
        draw_piece(img, row, col, color)

def main():
    cv2.namedWindow("Gomoku")
    img = draw_board()
    turn, player = 1, 1
    winner = "A"
    
    pieces = []  # 用于保存所有棋子的状态

    text = "Start gomoku game ^_^"
    update_text(img, pieces, text)
    update_board(img)
    time.sleep(2)
    
    text = "Please enter whether you want to\nplay Black(1) or White(2):"
    update_text(img, pieces, text)
    update_board(img)
    time.sleep(5)

    while True:
        # 更新文字以显示当前回合
        text = f"Turn: {turn} - Player {'Black' if player == 1 else 'White'}"
        update_text(img, pieces, text)  # 重新绘制棋盘、棋子和新的文字
        update_board(img)

        row, col, player = read_move_from_file()
        
        if row == -1 and col == -1:  # 结束游戏的信号
            if player == 2: 
                winner = "B"
            break
        
        color = BLACK_COLOR if player == 1 else WHITE_COLOR
        pieces.append((row, col, color))  # 保存棋子状态
        update_text(img, pieces, text)  # 更新棋子和文字
        update_board(img)
        
        signal_next_turn()
        turn += 1
        player = 3 - player  # 交换玩家
        
        # 处理键盘事件
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
    
    text = 'Winner ' + winner
    update_text(img, pieces, text)  # 更新最终文字
    update_board(img)
    
    while True:                      
        if cv2.waitKey(1000) == 27:
            break        
    cv2.destroyAllWindows()   

main()
