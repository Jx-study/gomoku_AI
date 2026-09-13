#include "lines.h"
#include "pattern.h"
#include "boardstate.h"

#ifdef WINDOW_IDX_CHECK
#include <assert.h>
#endif

// 檢查該位置落子后的連綫數
// 四個方向各查一次棋型表，命中的棋型 index 累加進 my_line
void checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int my_line[16]) {
    ensurePatternTable();

    int dx[] = {1, 1, 0, -1};   // 水平、垂直、主對角線、副對角線
    int dy[] = {0, 1, 1, 1};

    for (int i = 0; i < 4; i++) {
        int idx = idxValid ? windowIdx[player - 1][y][x][i]
                            : encodeWindow(board, x, y, dx[i], dy[i], player);
        int code = patternTable[idx];
        if (code) my_line[code]++;
    }
}

// 計算棋盤自己和對手的縂連綫數量
// 搜索期間每顆棋子必落在 box 內，box 篩不掉任何一顆，idxValid 時改走 stoneList，
// 掃描路徑留給 checkUnValid 從 Python 進來的冷路徑（idxValid 為 false）
void checkNow(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int player, int my_now[16]) {
    if (idxValid) {
        int p = player - 1;
        for (int i = 0; i < stoneCount[p]; i++) {
#ifdef WINDOW_IDX_CHECK
            int x = stoneList[p][i] % BOARD_MAX, y = stoneList[p][i] / BOARD_MAX;
            assert(minX <= x && x <= maxX && minY <= y && y <= maxY);
#endif
            checkLine(board, stoneList[p][i] % BOARD_MAX, stoneList[p][i] / BOARD_MAX, player, my_now);
        }
        return;
    }

    for (int x = minX; x <= maxX; x++) {
        for (int y = minY; y <= maxY; y++) {
            if (board[y][x] == player) {
                checkLine(board,x,y,player,my_now);
            }
        }
    }
}

// 落子後通過該點的最長連續棋子數；hasFive 回報是否有任一方向恰好五連
// 勝負與長連只看連續長度，不經過棋型分類
// 兩者分開回報：五連與長連可能同時出現在不同方向，只看最長值會誤判黑棋禁手
// 已不在生產路徑：判定改查 patternTable（見 judgeMove、winsAt），這裡留作
// test_pattern_table.py 的參考實作與對拍用途，勿刪
int maxRunAt(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int *hasFive) {
    int dx[] = {1, 1, 0, -1};
    int dy[] = {0, 1, 1, 1};
    int best = 0;
    *hasFive = 0;

    for (int i = 0; i < 4; i++) {
        int run = 1;   // 包含假設落子的這一顆
        for (int direction = -1; direction <= 1; direction += 2) {
            for (int j = 1; ; j++) {
                int nx = x + j * dx[i] * direction;
                int ny = y + j * dy[i] * direction;
                if (nx < 0 || nx >= BOARD_MAX || ny < 0 || ny >= BOARD_MAX) break;
                if (board[ny][nx] != player) break;
                run++;
            }
        }
        if (run == 5) *hasFive = 1;
        if (run > best) best = run;
    }
    return best;
}

// 把一個方向的 11 格窗口讀進 cells，中心固定為 CELL_SELF，牆與敵子同視為 CELL_OPP
// 編碼規則與 encodeWindow 一致，兩邊同時改才不會漂移
static void loadWindow(int board[BOARD_MAX][BOARD_MAX], int x, int y, int dx, int dy,
                       int player, int cells[11]) {
    for (int off = -5; off <= 5; off++) {
        if (off == 0) { cells[5] = CELL_SELF; continue; }
        int nx = x + off * dx, ny = y + off * dy;
        if (nx < 0 || nx >= BOARD_MAX || ny < 0 || ny >= BOARD_MAX) cells[5 + off] = CELL_OPP;
        else if (board[ny][nx] == player) cells[5 + off] = CELL_SELF;
        else if (board[ny][nx] == 0) cells[5 + off] = CELL_EMPTY;
        else cells[5 + off] = CELL_OPP;
    }
}

// 含 pos 且含中心的「恰好五」區間起點，找不到回傳 -1
// 恰好五：區間兩側外一格不得再是己方子，否則是長連，依 RIF 不算成五
static int exactFiveStart(int cells[11], int pos) {
    int lo = pos - 4 >= 0 ? pos - 4 : 0;
    int hi = pos < 6 ? pos : 6;
    for (int s = lo; s <= hi; s++) {
        if (s < 1 || s > 5) continue;                    // 區間必須含中心
        bool all = true;
        for (int k = 0; k < 5; k++) if (cells[s + k] != CELL_SELF) { all = false; break; }
        if (!all) continue;
        if (s - 1 >= 0 && cells[s - 1] == CELL_SELF) continue;
        if (s + 5 < 11 && cells[s + 5] == CELL_SELF) continue;
        return s;
    }
    return -1;
}

// 同一個四的多個成五點共用同一組四顆子（活四即如此），用四子集合去重，
// 兩組不同的四子集合才算兩個四，同一直線上因此也可能四四禁手
/* 回傳一個方向內「四」的個數，上限 2（數到 2 即可判定四四，不必再數） */
static int countFours(int cells[11]) {
    unsigned int groups[2];
    int n = 0;
    for (int pos = 0; pos < 11 && n < 2; pos++) {
        if (cells[pos] != CELL_EMPTY) continue;
        cells[pos] = CELL_SELF;
        int s = exactFiveStart(cells, pos);
        if (s >= 0) {
            unsigned int mask = 0;
            for (int k = 0; k < 5; k++) if (s + k != pos) mask |= 1u << (s + k);
            bool seen = false;
            for (int i = 0; i < n; i++) if (groups[i] == mask) { seen = true; break; }
            if (!seen) groups[n++] = mask;
        }
        cells[pos] = CELL_EMPTY;
    }
    return n;
}

// 找出一個方向窗口內、能讓該方向構成三（tp>=1）的活四點盤面座標
// 回傳找到的活四點數（0~2），座標寫進 outX/outY；不判斷同時成五，那件事
// 交給呼叫端對這個座標跑一次 judgeMove（成五回傳 2，天然合法）
static int threeSpotsInDirection(int board[BOARD_MAX][BOARD_MAX], int x, int y,
                                  int dx, int dy, int player, int outX[2], int outY[2]) {
    int cells[11];
    loadWindow(board, x, y, dx, dy, player, cells);
    int n = 0;
    for (int i = 0; i < 11 && n < 2; i++) {
        if (cells[i] != CELL_EMPTY) continue;
        cells[i] = CELL_SELF;
        int fp = fivePoints(cells);
        cells[i] = CELL_EMPTY;
        if (fp < 2) continue;                 // 未達活四門檻，不是這個三的活四點
        int off = i - 5;
        outX[n] = x + off * dx;
        outY[n] = y + off * dy;
        n++;
    }
    return n;
}

/* 落子判定：checkUnValid 與 endGame 共用，避免規則邏輯分散而漂移。
   回傳： 2 = 勝著（五連；白棋長連也算勝）
          1 = 一般合法著法
          0 = 已有棋子
         -3/-4/-6 = 黑棋禁手（三三/四四/長連） */
int judgeMove(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {
    if (board[y][x] != 0) return 0;
    int line[16] = {0};
    checkLine(board, x, y, player, line);
    if (line[5] > 0) return 2;                       // 五連即勝，優先於一切禁手
    if (line[15] > 0) return player == 2 ? 2 : -6;   // 長連只對白棋算勝
    if (player == 1) {
        // 三是「能再加一子成活四」，一種填法就夠，碼 11/13（tp==1）依字面也算三
        // fivePoints 已加恰好五守衛，tp>=1 才等於真能成活四
        if ((line[3] + line[9] + line[11] + line[13]) >= 2) {
            // 9.3：雙三只在兩個以上的三都能推進到合法活四時才禁手；
            // 逐方向找出貢獻三的活四點，先真的落下 (x,y) 這顆子，
            // 讓活四點的窗口能看見它，再模擬落子遞迴判定該點合不合法
            // 搜索期間 idxValid==true 時 checkLine 只讀 windowIdx 不看 board，
            // 必須走 placeStone/removeStone 同步索引；冷路徑 windowIdx 未經
            // rebuildWindowIndex 初始化，不能對它做增量調整，直接寫 board 即可
            // （encodeWindow 即時重掃 board，不依賴 windowIdx）
            int dxT[] = {1, 1, 0, -1};
            int dyT[] = {0, 1, 1, 1};
            int advanceable = 0;
            if (idxValid) placeStone(board, x, y, player);
            else board[y][x] = player;
            for (int i = 0; i < 4 && advanceable < 2; i++) {
                int cellsT[11];
                loadWindow(board, x, y, dxT[i], dyT[i], player, cellsT);
                int code = classifyWindow(cellsT);
                if (code != 3 && code != 9 && code != 11 && code != 13) continue;
                int spotX[2], spotY[2];
                int n = threeSpotsInDirection(board, x, y, dxT[i], dyT[i], player, spotX, spotY);
                for (int k = 0; k < n; k++) {
                    // 活四點此時仍是空格，judgeMove 自己會假設落子在此判定
                    int r = judgeMove(board, spotX[k], spotY[k], player);
                    if (r >= 1) { advanceable++; break; }   // 這個三能推進到合法活四
                }
            }
            if (idxValid) removeStone(board, x, y);
            else board[y][x] = 0;
            if (advanceable >= 2) return -3;
        }
        // 四四逐方向數四，碼加總會把同一條線上的兩個四算成一個，見 renju-rules.md
        // 碼只當快篩：碼為 0 時該方向必無四，反向不成立
        if (line[4] + line[8] + line[10] + line[12] > 0) {
            int dxF[] = {1, 1, 0, -1};
            int dyF[] = {0, 1, 1, 1};
            int fours = 0;
            for (int i = 0; i < 4 && fours < 2; i++) {
                int cells[11];
                loadWindow(board, x, y, dxF[i], dyF[i], player, cells);
                fours += countFours(cells);
            }
            if (fours >= 2) return -4;
        }
    }
    return 1;
}

// 直接查 patternTable 四個方向，索引與 checkLine 一致，但跳過 line[16] 的清零與累加，只認 5、15 兩個代碼
// 語意須與 judgeMove 逐項對得上：成五與白棋長連 true，黑棋長連與其餘一律 false
bool winsAt(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {
    ensurePatternTable();

    int dx[] = {1, 1, 0, -1};   // 水平、垂直、主對角線、副對角線
    int dy[] = {0, 1, 1, 1};

    for (int i = 0; i < 4; i++) {
        int idx = idxValid ? windowIdx[player - 1][y][x][i]
                            : encodeWindow(board, x, y, dx[i], dy[i], player);
        int code = patternTable[idx];
        if (code == 5) return true;
        if (code == 15 && player == 2) return true;
    }
    return false;
}

/* 檢查指定位置是否有棋子/落子後是否形成禁手
返回值：返回1如果落子後形成有效連線，否則返回禁手代碼（0：已有棋子，-3：三三禁手，-4：四四禁手，-5：長連禁手）*/
int checkUnValid(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {
    int r = judgeMove(board, x, y, player);
    return (r == 2) ? 1 : r;   // 對外語義不變：勝著也是「有效落子」（回傳 1）
}
