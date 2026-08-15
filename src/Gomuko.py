from graphics import*
import time     # 延遲執行+記錄運行時間
import ctypes   # 調用C語言函式庫
import os, sys
import tkinter as tk
from tkinter import Scrollbar

from game_state import GameState   # 盤面/輪次/開局規則/悔棋（有測試涵蓋）

# 加載共享庫
# 必須在 const 之前載入：棋盤大小由 ai.c 決定，const 需要先取得該值。
ai_lib = ctypes.CDLL('./ai.dll')
ai_lib.getBoardMax.restype = ctypes.c_int

# 定義常量+全域變數
class const:
    MARGIN = 100              # 棋盤邊距
    GRID = 30                 # 每個網格的大小
    PIECE_RADIUS = 10         # 棋子的半徑
    # 棋盤邊長（格點數），座標範圍 0 ~ BOARD_MAX-1。
    # 唯一定義處是 ai.c；此處讀取 DLL 實際編譯值，故兩端不可能失去同步。
    BOARD_MAX = ai_lib.getBoardMax()
    NUM = BOARD_MAX           # 繪製線條數，與格點數相同
    LEN = (NUM - 1) * GRID    # 棋盤的總長度
    MIDPOINT_X = BOARD_MAX // 2
    MIDPOINT_Y = BOARD_MAX // 2

    # --- 以下版面尺寸由棋盤大小推導，改 BOARD_MAX 時自動貼合 ---
    BOARD_END = MARGIN + LEN          # 棋盤右／下緣座標
    BUTTON_W = 100                    # 按鈕寬
    BUTTON_H = 40                     # 按鈕高
    BUTTON_GAP = 40                   # 按鈕間距
    BUTTON_TOP = BOARD_END + 15       # 按鈕頂緣（棋盤下方）
    BUTTON_BOTTOM = BUTTON_TOP + BUTTON_H
    # 視窗需容納棋盤與其下方的按鈕列（右側留與左側相同的邊距）
    WIN_W = max(BOARD_END + MARGIN, 3 * BUTTON_W + 2 * BUTTON_GAP + 2 * MARGIN)
    WIN_H = BUTTON_BOTTOM + 15
    CENTER_X = WIN_W // 2             # 視窗水平中心（提示文字、對話框用）

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
# 注意：Zobrist key 由 C 端 findBestMove 每次搜索前以實際盤面重算（絕對值），
# Python 端不需要、也不應該再逐手同步（原本的同步呼叫已移除）。

# 定义 ctypes 二维数组的类型
CBoardType = (ctypes.c_int * const.BOARD_MAX) * const.BOARD_MAX

#---------------------------（游戲畫面+提示）-------------------------
class GameHistory:
    """棋盤狀態 + 對應的圖形物件。

    盤面／輪次／悔棋這些純邏輯一律委派給 `GameState`（`game_state.py`），
    本類別只額外管理 graphics 物件的生命週期。邏輯不要在這裡重寫一份——
    `src/tests/` 測的是 `GameState`，兩邊各寫一份就會漂移。
    """

    def __init__(self):
        self.state = GameState(const.BOARD_MAX)
        self.piece_objects = []     # 棋子圖形
        self.number_objects = []    # 棋子回合數提示

    @property
    def board(self):
        return self.state.board

    @property
    def moves_history(self):
        return self.state.moves

    def add_move(self, x, y, player, piece, number):
        """落子並記錄對應的圖形物件。回傳是否成功。

        只有 state.play() 成功時才收下圖形物件，否則 piece/number 兩份
        清單會比 moves 多出一筆，悔棋時就會 undraw 到錯誤的棋子。
        """
        if not self.state.play(x, y, player):
            return False
        self.piece_objects.append(piece)
        self.number_objects.append(number)
        return True

    def undo_last_move(self):
        """悔棋，回傳實際撤銷的手數（0 表示沒有可悔的棋）。

        撤銷手數與 roundCounter 的回捲量由 `GameState.undo()` 保證一致；
        這裡只負責把對應的圖形物件移除。
        """
        undone = self.state.undo(2)

        for _ in range(undone):
            self.piece_objects[-1].undraw()
            self.piece_objects.pop()
            self.number_objects[-1].undraw()
            self.number_objects.pop()

        return undone

    def clear_board(self):
        self.state.reset()
        for piece in self.piece_objects:
            piece.undraw()
        for number in self.number_objects:
            number.undraw()
        self.piece_objects.clear()
        self.number_objects.clear()
    
    def get_board_state(self):
        return self.board

class RulesWindow:
    def __init__(self):
        # 創建一個新的窗口
        self.win = tk.Tk()
        self.win.title("Game Rules")
        self.win.geometry("600x400")  # 設置窗口大小

        # 創建滾動條
        scrollbar = Scrollbar(self.win)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 創建一個Text控件顯示遊戲規則
        self.text_widget = tk.Text(self.win, wrap=tk.WORD, yscrollcommand=scrollbar.set)
        self.text_widget.insert(tk.END, "Gomoku Game Rules:\n\n"
                                        "1. 勝利條件：五子連綫\n"
                                        "2. 黑方在棋盤中心落下第1手棋。\n"
                                        "3.白方在棋盤中心的3x3方格內落下第2手棋。\n"
                                        "4.黑方在棋盤中心的5x5方格內落下第3手棋，確立26種連珠開局之一。\n"
                                        "5.白方選擇自己與對方的棋子顏色（稱為「三手交換」）。\n"
                                        "6.白方在棋盤的空點處落下第4手。\n"
                                        "7.黑方有三三、四四及長連禁手（包含四三三、三三四...），在連成五子前，無論主動或被動下出禁著點，立即判定為負。換言之，黑方唯一獲勝的可能為下出四三。\n"
                                        "8.白方無任何禁點，長連亦為勝。\n"
                                        "9.五連與禁手同時形成則不算禁手，黑方可算獲勝。\n"
                                        "\n"
                                        "禁點規則說明：\n"
                                        "1. 雙活三禁點\n"
                                        "2. 雙活四禁點\n"
                                        "3. 長連禁點\n"
                                        "*注意*：若其中一個三無法形成連四，僅能成為死四，則禁點不成立。此即為「以禁解禁」原則\n"
                                        "詳細資訊請到 https://587.renju.org.tw/teach/teach018.htm\n")
        self.text_widget.config(state=tk.DISABLED)  # 禁止編輯
        self.text_widget.pack(padx=10, pady=10, expand=True, fill=tk.BOTH)

        # 將滾動條綁定到Text控件
        scrollbar.config(command=self.text_widget.yview)

        # 創建關閉按鈕
        self.close_button = tk.Button(self.win, text="Close", command=self.win.destroy)
        self.close_button.pack(pady=10)

    def show(self):
        self.win.grab_set()  # 禁止父窗口交互，直到關閉規則窗口
        self.win.wait_window()  # 等待規則窗口關閉

class GameWindow:
    def __init__(self):
        self.win = GraphWin(title="Gomoku", width=const.WIN_W, height=const.WIN_H)
        self.txt_notice = None
        self.txt_round = None
        self.txt_time = None
        self.restart_button = None
        self.undo_button = None
        self.rules_button = None

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
        self.txt_notice = self.create_text(Point(const.CENTER_X, const.MARGIN // 2), 30, (0, 0, 0), 'courier', 'bold')
        self.txt_round = self.create_text(Point(const.MARGIN // 2, const.MARGIN + 20), 18, (0, 0, 0), 'helvetica', 'normal')
        self.txt_time = self.create_text(Point(const.MARGIN // 2, const.BOARD_END - 30), 12, (255, 0, 0), 'courier', 'normal')
        
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
        center_x = const.MARGIN + const.MIDPOINT_X * const.GRID
        center_y = const.MARGIN + const.MIDPOINT_Y * const.GRID
        n_piece = Circle(Point(center_x, center_y), 7)
        n_piece.setFill('black')
        n_piece.draw(self.win)
        
        # 創建按鈕：三顆等寬按鈕以視窗中心對齊，置於棋盤下方
        row_w = 3 * const.BUTTON_W + 2 * const.BUTTON_GAP
        left = const.CENTER_X - row_w // 2
        top, bottom = const.BUTTON_TOP, const.BUTTON_BOTTOM
        step = const.BUTTON_W + const.BUTTON_GAP
        self.restart_button, _ = self.create_button(
            left, top, left + const.BUTTON_W, bottom, "Restart", "red", "white")
        self.undo_button, _ = self.create_button(
            left + step, top, left + step + const.BUTTON_W, bottom, "Undo", "Orange", "white")
        self.rules_button, _ = self.create_button(
            left + 2 * step, top, left + 2 * step + const.BUTTON_W, bottom, "Rules", "green", "white")

    def get_click(self):
        return self.win.getMouse()

    def check_button_click(self, point):
        if (self.restart_button.getP1().getX() < point.getX() < self.restart_button.getP2().getX() and
            self.restart_button.getP1().getY() < point.getY() < self.restart_button.getP2().getY()):
            return "restart"
        
        if (self.undo_button.getP1().getX() < point.getX() < self.undo_button.getP2().getX() and
            self.undo_button.getP1().getY() < point.getY() < self.undo_button.getP2().getY()):
            return "undo"
        if (self.rules_button.getP1().getX() < point.getX() < self.rules_button.getP2().getX() and
            self.rules_button.getP1().getY() < point.getY() < self.rules_button.getP2().getY()):
            return "rules"
        return None

    def create_piece(self, x, y, is_black):
        piece = Circle(Point(const.MARGIN + x * const.GRID, const.MARGIN + y * const.GRID), const.GRID // 2)
        piece.setFill('black' if is_black else 'white')
        piece.draw(self.win)
        return piece

    def create_number(self, x, y, number):
        txt_num = Text(Point(const.MARGIN + x * const.GRID, const.MARGIN + y * const.GRID), str(number))
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
        # 接上禁手判斷：GameState 先過濾範圍/空位/開局規則，再問 C 端禁手。
        self.board.state.set_forbidden_checker(self._is_not_forbidden)

        # 初始化 AI
        ai_lib.initZobristTable()
        ai_lib.initTranspositionTable()

    # 手數只有一份真實來源（GameState），避免與盤面脫鉤。
    @property
    def roundCounter(self):
        return self.board.state.round_counter

    def start(self):
        self.window.init_window()
        player, ai = self.choose_player()
        self.game(player, ai)
        self.window.close()

    # 重置遊戲狀態，保留現有物件，不重新初始化。
    def reset_game_state(self):
        self.board.clear_board()      # 一併把 round_counter 歸 1
        ai_lib.initZobristTable()
        ai_lib.initTranspositionTable()
        self.window.update_notice("重新開始遊戲")

    # 在現有的視窗上顯示讓玩家選擇先手或後手的畫面
    def choose_player(self):
        # 對話框以視窗中心對齊
        cx, cy = const.CENTER_X, const.WIN_H // 2
        background = Rectangle(Point(cx - 150, cy - 100), Point(cx + 150, cy + 100))
        background.setFill(color_rgb(255, 255, 255))
        background.draw(self.window.win)

        # 在視窗中央顯示提示文字
        message = Text(Point(cx, cy - 50), "Choose your role:")
        message.setTextColor(color_rgb(0, 0, 0))
        message.draw(self.window.win)

        # 建立選擇按鈕
        black_button = Rectangle(Point(cx - 100, cy), Point(cx, cy + 50))
        black_button.setFill(color_rgb(0, 0, 0))
        black_button.setOutline(color_rgb(255, 255, 255))
        black_text = Text(Point(cx - 50, cy + 25), "Black")
        black_text.setTextColor(color_rgb(255, 255, 255))
        black_button.draw(self.window.win)
        black_text.draw(self.window.win)

        white_button = Rectangle(Point(cx, cy), Point(cx + 100, cy + 50))
        white_button.setFill(color_rgb(255, 255, 255))
        white_button.setOutline(color_rgb(0, 0, 0))
        white_text = Text(Point(cx + 50, cy + 25), "White")
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

    # 禁手判斷（交給 C 端）。範圍/空位/開局規則由 GameState 先行過濾，
    # 所以進到這裡的座標保證在盤內，不會讓 C 端越界讀取。
    def _is_not_forbidden(self, board, x, y, player):
        c_board = self.convert_to_c_board()
        return ai_lib.checkUnValid(ctypes.byref(c_board), x, y, player) == 1

    # 檢查指定位置落子後是否形成無效連線（禁手）OR 開局規則下法
    def check_valid_move(self, x, y, player):
        # 規則本體在 GameState（有測試涵蓋），這裡只負責接上禁手檢查。
        # 檢查順序：範圍 → 空位 → 開局規則 → 禁手；範圍必須最先，否則
        # 越界座標會先被送進 C 端存取 board[y][x]（UB）。
        return self.board.state.is_valid_move(x, y, player)

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
        if clicked_button == "rules":
            # 打開規則視窗
            rules_win = RulesWindow()
            rules_win.show()  # 顯示規則視窗
            return False
        elif clicked_button == "restart":
            self.reset_game_state()  # 重置遊戲狀態
            player, ai = self.choose_player()  # 重新選擇玩家角色
            return self.game(player, ai)  # 重新開始遊戲
        elif clicked_button == "undo":
            # roundCounter 由 GameState.undo() 依實際撤銷手數回捲，這裡不需
            # （也不能）自行調整，否則會與盤面脫鉤、使開局規則失效。
            if self.board.undo_last_move():
                return True  # 成功悔棋，返回遊戲
            else:
                self.window.update_notice("沒有可以悔棋的步數")
        elif clicked_button == "exit":
            self.window.update_notice("遊戲結束，再見!")
            return False  # 結束遊戲
        else:
            return False  # 點擊其他地方，退出

    def game(self, player, ai):
        chance = 3          # 玩家的開局規則/禁手犯規機會
        ai_retry = 3        # AI 回傳非法走法的容忍次數（與玩家的 chance 分開計算）

        self.window.update_notice("Start gomoku game ^_^")
        time.sleep(1)

        while True:
            # 輪到誰下由 roundCounter 推導，不另外用變數追蹤：黑棋固定在奇數手、
            # 白棋在偶數手。悔棋是在 operation_button() 內部改動 roundCounter 的，
            # 那裡碰不到這個迴圈的區域變數；若另存一份 current_player，撤銷奇數
            # 手後兩者奇偶就會對不上，變成白棋先手。
            current_player = 1 if self.roundCounter % 2 == 1 else 2
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
                
                # 按鈕（尤其是悔棋）會改變 roundCounter，而輪到誰下是在外層
                # 迴圈開頭依 roundCounter 推導的。因此按下按鈕後必須跳回外層
                # 重新推導，不能只重啟這個內層點擊迴圈——否則悔棋換手後
                # current_player 仍是舊值，玩家會連下兩顆同色棋子。
                restart_turn = False
                while True:
                    start_time = time.time()
                    point = self.window.get_click()
                    end_time = time.time()
                    # 檢查是否點擊了按鈕
                    if self.operation_button(point, player, ai):
                        restart_turn = True
                        break

                    x = round((point.getX() - const.MARGIN) / const.GRID)
                    y = round((point.getY() - const.MARGIN) / const.GRID)
                    print(f"Player Move: ({x}, {y})")
                    # 如果x, y超出棋盤範圍，提示並重新點擊
                    if 0 <= x < const.BOARD_MAX and 0 <= y < const.BOARD_MAX:
                        break
                    else:
                        self.window.update_notice("請點擊棋盤內有效位置")

                if restart_turn:
                    continue

            # 檢查落子是否合法
            if self.check_valid_move(x, y, current_player):
                piece = self.window.create_piece(x, y, current_player == 1)
                number = self.window.create_number(x, y, self.roundCounter)

                self.board.add_move(x, y, current_player, piece, number)
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
                        # operation_button() 內的悔棋已經把 roundCounter 回捲到
                        # 正確的值，這裡不可再自行調整，否則又會與盤面脫鉤。
                        continue
                    else:
                        break # 關閉

                # roundCounter 已由 GameHistory.add_move() -> GameState.play() 推進
                time.sleep(0.5)
            elif current_player == ai:
                # AI 回傳了非法座標。這不是玩家犯規，不能扣玩家的機會，
                # 否則會出現「AI 自己犯規卻宣告 AI 勝利」。修好 aiRound 的
                # 開局分支後這條路徑理論上不該再發生，保留作為診斷用的防線。
                ai_retry -= 1
                print(f"[BUG] AI returned invalid move ({x}, {y}) at round {self.roundCounter}")
                if ai_retry == 0:
                    self.window.update_notice("AI 無法產生合法走法，遊戲中止")
                    break
                continue
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