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
class GameHistory:
    def __init__(self):
        self.board = [[0 for _ in range(const.BOARD_MAX)] for _ in range(const.BOARD_MAX)]
        self.moves_history = []     # 儲存落子記錄
        self.piece_objects = []     # 棋子圖形
        self.number_objects = []    # 棋子回合數提示

    def add_move(self, x, y, player, piece, number):
        self.board[y][x] = player
        self.moves_history.append((x, y, player))
        self.piece_objects.append(piece)
        self.number_objects.append(number)

    def undo_last_move(self):
        if not self.moves_history:
            return False
        
        # 移除最後兩個個棋子和數字的圖形
        for i in range (2):
            x, y, player = self.moves_history.pop()
            self.board[y][x] = 0
            self.piece_objects[-1].undraw()
            self.piece_objects.pop()
            self.number_objects[-1].undraw()
            self.number_objects.pop()
            
            ai_lib.updateZobristKey(x, y, 0)         # 更新 Zobrist key

        return True

    def clear_board(self):
        self.board = [[0 for _ in range(const.BOARD_MAX)] for _ in range(const.BOARD_MAX)]
        for piece in self.piece_objects:
            piece.undraw()
        for number in self.number_objects:
            number.undraw()
        self.moves_history.clear()
        self.piece_objects.clear()
        self.number_objects.clear()
    
    def get_board_state(self):
        return self.board

class GameWindow:
    def __init__(self):
        self.win = GraphWin(title="Gomoku", width=800, height=800)
        self.txt_notice = None
        self.txt_round = None
        self.txt_time = None
        self.restart_button = None
        self.undo_button = None

    def create_text(self, point, size, color, face, style):
        txt = Text(point, "")
        txt.setSize(size)
        txt.setTextColor(color_rgb(*color))
        txt.setFace(face)
        txt.setStyle(style if style in ['bold', 'italic', 'underline', 'normal'] else 'normal')
        return txt

    def create_button(self, x1, y1, x2, y2, text, bg_color, text_color):
        button = Rectangle(Point(x1, y1), Point(x2, y2))
        button.setFill(bg_color)
        button.setOutline(text_color)
        button.draw(self.win)
        label = Text(Point((x1 + x2) / 2, (y1 + y2) / 2), text)
        label.setTextColor(text_color)
        label.draw(self.win)
        return button, label

    def init_window(self):
        self.win.setBackground(color_rgb(255, 208, 118))
        
        # 文字提示
        self.txt_notice = self.create_text(Point(400, 50), 30, (0, 0, 0), 'courier', 'bold')
        self.txt_round = self.create_text(Point(50, 120), 18, (0, 0, 0), 'helvetica', 'normal')
        self.txt_time = self.create_text(Point(50, 600), 12, (255, 0, 0), 'courier', 'normal')
        
        # 加載圖片
        if getattr(sys, 'frozen', False):
            bundle_dir = sys._MEIPASS
        else:
            bundle_dir = os.path.abspath(os.path.dirname(__file__))
        img_path = os.path.join(bundle_dir, "200w.gif")
        img = Image(Point(50, 50), img_path)
        img.draw(self.win)
        
        # 繪製棋盤線
        for i in range(const.NUM):
            Line(Point(const.MARGIN + i * const.GRID, const.MARGIN),
                 Point(const.MARGIN + i * const.GRID, const.MARGIN + const.LEN)).draw(self.win)
            Line(Point(const.MARGIN, const.MARGIN + i * const.GRID),
                 Point(const.MARGIN + const.LEN, const.MARGIN + i * const.GRID)).draw(self.win)
        
        # 繪製文字
        self.txt_notice.draw(self.win)
        self.txt_round.draw(self.win)
        self.txt_time.draw(self.win)
        
        # 中心點
        center_x = const.MARGIN + (const.NUM // 2) * const.GRID
        center_y = const.MARGIN + (const.NUM // 2) * const.GRID
        n_piece = Circle(Point(center_x, center_y), 7)
        n_piece.setFill('black')
        n_piece.draw(self.win)
        
        # 創建按鈕
        self.restart_button, _ = self.create_button(290, 750, 390, 790, "Restart", "red", "white")
        self.undo_button, _ = self.create_button(410, 750, 510, 790, "Undo", "green", "white")

    def get_click(self):
        return self.win.getMouse()

    def check_button_click(self, point):
        if (self.restart_button.getP1().getX() < point.getX() < self.restart_button.getP2().getX() and
            self.restart_button.getP1().getY() < point.getY() < self.restart_button.getP2().getY()):
            return "restart"
        
        if (self.undo_button.getP1().getX() < point.getX() < self.undo_button.getP2().getX() and
            self.undo_button.getP1().getY() < point.getY() < self.undo_button.getP2().getY()):
            return "undo"
        return None

    def create_piece(self, x, y, is_black):
        piece = Circle(Point(100+x*30, 100+y*30), 15)
        piece.setFill('black' if is_black else 'white')
        piece.draw(self.win)
        return piece

    def create_number(self, x, y, number):
        txt_num = Text(Point(100+x*30, 100+y*30), str(number))
        txt_num.setTextColor("red")
        txt_num.draw(self.win)
        return txt_num

    def update_notice(self, message):
        self.txt_notice.setText(message)
        self.win.update()

    def update_round(self, round_num):
        self.txt_round.setText(f"回合數:{round_num}")

    def update_time(self, time_spent):
        self.txt_time.setText(f"耗時{time_spent:.2f}s")

    def close(self):
        self.win.close()

#----------------------------(游戲)----------------------------
class GomokuGame:
    def __init__(self):
        self.window = GameWindow()
        self.board = GameHistory()
        self.roundCounter = 1

        # 初始化 AI
        ai_lib.initZobristTable()
        ai_lib.initTranspositionTable()

    def start(self):
        self.window.init_window()
        player, ai = self.choose_player()
        self.game(player, ai)
        self.window.close()

    # 重置遊戲狀態，保留現有物件，不重新初始化。
    def reset_game_state(self):
        self.board.clear_board()
        self.roundCounter = 1
        ai_lib.initZobristTable()  
        ai_lib.initTranspositionTable()  
        self.window.update_notice("重新開始遊戲")

    # 在現有的視窗上顯示讓玩家選擇先手或後手的畫面
    def choose_player(self):
        # 背景
        background = Rectangle(Point(250, 250), Point(550, 450))
        background.setFill(color_rgb(255, 255, 255))
        background.draw(self.window.win)

        # 在視窗中央顯示提示文字
        message = Text(Point(400, 300), "Choose your role:")
        message.setTextColor(color_rgb(0, 0, 0))
        message.draw(self.window.win)

        # 建立選擇按鈕
        black_button = Rectangle(Point(300, 350), Point(400, 400))
        black_button.setFill(color_rgb(0, 0, 0))
        black_button.setOutline(color_rgb(255, 255, 255))
        black_text = Text(Point(350, 375), "Black")
        black_text.setTextColor(color_rgb(255, 255, 255))
        black_button.draw(self.window.win)
        black_text.draw(self.window.win)

        white_button = Rectangle(Point(400, 350), Point(500, 400))
        white_button.setFill(color_rgb(255, 255, 255))
        white_button.setOutline(color_rgb(0, 0, 0))
        white_text = Text(Point(450, 375), "White")
        white_text.setTextColor(color_rgb(0, 0, 0))
        white_button.draw(self.window.win)
        white_text.draw(self.window.win)

        # 等待玩家選擇
        while True:
            point = self.window.get_click()
            if black_button.getP1().getX() < point.getX() < black_button.getP2().getX() and \
            black_button.getP1().getY() < point.getY() < black_button.getP2().getY():
                player, ai = 1, 2
                break
            elif white_button.getP1().getX() < point.getX() < white_button.getP2().getX() and \
                white_button.getP1().getY() < point.getY() < white_button.getP2().getY():
                player, ai = 2, 1
                break

        # 清理選擇畫面
        background.undraw()
        message.undraw()
        black_button.undraw()
        black_text.undraw()
        white_button.undraw()
        white_text.undraw()

        return player, ai

    # 將 Python 的二維列表轉換為 ctypes 二維陣列
    def convert_to_c_board(self):
        c_board = CBoardType()
        board_state = self.board.get_board_state()
        for i in range(const.BOARD_MAX):
            for j in range(const.BOARD_MAX):
                c_board[i][j] = board_state[i][j]
        return c_board

    # 檢查指定位置落子後是否形成無效連線（禁手）OR 開局規則下法
    def check_valid_move(self, x, y, player):
        if self.roundCounter == 1 and (x != 11 or y != 11):
            return False
        
        c_board = self.convert_to_c_board()
        return (ai_lib.checkUnValid(ctypes.byref(c_board), x, y, player) == 1 and 0 < x < 22 and 0 < y < 22)

    # 檢查是否有人勝利
    def check_win(self, player):
        c_board = self.convert_to_c_board()
        result = ai_lib.checkWin(ctypes.byref(c_board), 0, const.BOARD_MAX-1, 0, const.BOARD_MAX-1, player) != 0
        return result

    # Ai回合
    def ai_move(self, ai):
        bestx = ctypes.c_int()
        besty = ctypes.c_int()

        c_board = self.convert_to_c_board()
        ai_lib.aiRound(ctypes.byref(c_board), ai, self.roundCounter, ctypes.byref(bestx), ctypes.byref(besty))

        print(f"Python AI Move: ({bestx.value}, {besty.value})")
        return bestx.value, besty.value

    # 處理玩家游戲行為選擇：重新開始/悔棋/其他
    def operation_button(self, point, player, ai):
        clicked_button = self.window.check_button_click(point)
        if clicked_button == "restart":
            self.reset_game_state()  # 重置遊戲狀態
            player, ai = self.choose_player()  # 重新選擇玩家角色
            return self.game(player, ai)  # 重新開始遊戲
        elif clicked_button == "undo":
            if self.board.undo_last_move():
                if self.roundCounter > 2:
                    self.roundCounter -= 2
                return True  # 成功悔棋，返回遊戲
            else:
                self.window.update_notice("沒有可以悔棋的步數")
        elif clicked_button == "exit":
            self.window.update_notice("遊戲結束，再見!")
            return False  # 結束遊戲
        else:
            return False  # 點擊其他地方，退出

    def game(self, player, ai):
        current_player = 1  # 1=黑棋回合，2=白棋回合
        chance = 3

        self.window.update_notice("Start gomoku game ^_^")
        time.sleep(1)

        while True:
            self.window.update_round(self.roundCounter)

            # AI回合
            if current_player == ai:
                self.window.update_notice("AI正在下棋...")
                start_time = time.time()
                x, y = self.ai_move(ai)
                end_time = time.time()
            # 玩家回合
            else:
                if self.roundCounter == 1:
                    self.window.update_notice("第一手請落子在正中心位置")
                else:
                    self.window.update_notice("玩家正在下棋...")
                
                start_time = time.time()
                point = self.window.get_click()
                end_time = time.time()
                
                # 處理按鈕行為
                if self.operation_button(point, player, ai):
                    continue

                x = round((point.getX() - const.MARGIN) / const.GRID)
                y = round((point.getY() - const.MARGIN) / const.GRID)
                print(f"PLayer Move: ({x}, {y})")
            # 檢查落子是否合法
            if self.check_valid_move(x, y, current_player):
                piece = self.window.create_piece(x, y, current_player == 1)
                number = self.window.create_number(x, y, self.roundCounter)

                self.board.add_move(x, y, current_player, piece, number)
                ai_lib.updateZobristKey(x, y, current_player)
                self.window.update_time(end_time - start_time)

                if self.check_win(current_player):
                    if current_player == ai:
                        self.window.update_notice(f"AI花了{self.roundCounter // 2}手才勝利!")
                    else:
                        self.window.update_notice("恭喜玩家!")
                    # 處理游戲結束后的操作
                    end_undo = False
                    point = self.window.get_click()
                    while True:
                        if self.operation_button(point, player, ai):
                            end_undo = True
                            break
                        else:
                            break
                    if(end_undo): 
                        self.roundCounter += 1
                        current_player = 3 - current_player
                        continue
                    else:
                        break # 關閉

                self.roundCounter += 1
                current_player = 3 - current_player
                time.sleep(0.5)
            else:
                chance -= 1
                if chance == 0:
                    self.window.update_notice(f"AI勝利!")
                    break
                self.window.update_notice(f"犯規，你還有{chance}次機會")
                time.sleep(1)
                continue

def main():
    game = GomokuGame()
    game.start()

if __name__ == "__main__":
    main()