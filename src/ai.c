#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <limits.h>
#include <string.h>
#include <time.h>
#include <stdint.h> // unsigned long long int.....

// 棋盤大小的唯一定義處。Python 端透過 getBoardMax() 讀取此值
#define BOARD_MAX 15
#define MIDPOINT_X (BOARD_MAX / 2)
#define MIDPOINT_Y (BOARD_MAX / 2)
#define MAX_DEPTH 7 // 定義搜索深度
// 強制著法門檻：分數不低於此值的候選不受 top-N 截斷
// 代理指標而非精確判定：攻防相加，普通點也可能湊到門檻以上
// 改權重時要一併重算此值
#define FORCING_SCORE 8000
#define TABLE_SIZE (1 << 20)   // 1,048,576 個 entry，約 24MB
#define TABLE_MASK (TABLE_SIZE - 1)

typedef struct {
    unsigned long long key;  // Zobrist 哈希鍵(結點局面的 64 位校驗值)
    int depth;               // 搜索深度
    int score;               // 評估分數
    char flag;                // 標誌（精確值、上界、下界）
    signed char bestX, bestY; // 此局面的最佳走法（座標範圍 0 ~ BOARD_MAX-1，-1 表無記錄）
} HashEntry;

typedef struct {
    int x, y, score;
} Move;

HashEntry transpositionTable[TABLE_SIZE];
unsigned long long zobristTable[BOARD_MAX][BOARD_MAX][2];  // 2 for player 1, player 2
unsigned long long currentZobristKey = 0;

// 回傳這顆 DLL 實際編譯時使用的棋盤大小
// Python 端據此建立 ctypes 陣列與版面尺寸，確保與二進位檔一致
int getBoardMax(void) {
    return BOARD_MAX;
}

// 64 位元亂數產生器（splitmix64）
// 不能用 rand()：Windows/mingw 的 RAND_MAX 僅 15 位元，key 熵不足會造成 TT 假命中
static unsigned long long splitmix64(unsigned long long *state) {
    unsigned long long z = (*state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

// 初始化 Zobrist 哈希表
// 種子固定：key 分布不需隨機，固定反而讓 A/B 對照可重現
void initZobristTable() {
    unsigned long long state = 0x243F6A8885A308D3ULL;
    for (int i = 0; i < BOARD_MAX; i++) {
        for (int j = 0; j < BOARD_MAX; j++) {
            for (int k = 0; k < 2; k++) {
                zobristTable[i][j][k] = splitmix64(&state);
            }
        }
    }
}

// 初始化 置換表
void initTranspositionTable() {
    memset(transpositionTable, 0, TABLE_SIZE * sizeof(HashEntry));
    // 0 是合法座標，未寫入的 entry 必須用 -1 標記無記錄
    for (int i = 0; i < TABLE_SIZE; i++) {
        transpositionTable[i].bestX = -1;
        transpositionTable[i].bestY = -1;
    }
}

// 計算初始哈希值
unsigned long long computeZobristKey(int board[BOARD_MAX][BOARD_MAX]) {
    unsigned long long key = 0;
    for (int i = 0; i < BOARD_MAX; i++) {
        for (int j = 0; j < BOARD_MAX; j++) {
            if (board[i][j] != 0) {
                key ^= zobristTable[i][j][board[i][j] - 1];
            }
        }
    }
    return key;
}

// 尋找現在哈希值是否有在置換表中
HashEntry* lookupHashEntry(unsigned long long zobristKey) {
    int index = zobristKey & TABLE_MASK;
    if (transpositionTable[index].key == zobristKey) {
        return &transpositionTable[index];
    }
    return NULL;
}

// 更新哈希值
// 索引順序必須與 computeZobristKey 的 board[y][x] 一致
// 否則整盤重算與逐手 XOR 對不起來，同一局面在不同手會算出不同的 key
void updateZobristKey(int x, int y, int player) {
    currentZobristKey ^= zobristTable[y][x][player-1];  // 异或操作来更新哈希值
}

// 存取哈希值進哈希表
void storeHashEntry(unsigned long long zobristKey, int depth, int score, char flag, int bestX, int bestY) {
    int index = zobristKey & TABLE_MASK;
    // Always-replace: 直接覆蓋，不管舊 entry 是什麼
    transpositionTable[index].key   = zobristKey;
    transpositionTable[index].depth = depth;
    transpositionTable[index].score = score;
    transpositionTable[index].flag  = flag;
    transpositionTable[index].bestX = (signed char)bestX;
    transpositionTable[index].bestY = (signed char)bestY;
}

// 棋型查表：一條方向線的 11 格窗口（中心 + 左右各 5）換成棋型 index
// 中心恆為 SELF 不入索引，周邊 10 格三態，出界的牆併入 OPP
#define CELL_EMPTY 0
#define CELL_SELF  1
#define CELL_OPP   2   // 含出界的牆
#define PATTERN_TABLE_SIZE 59049   // 3^10

static unsigned char patternTable[PATTERN_TABLE_SIZE];

// 把窗口編成 patternTable 索引：off 從 -5 到 +5 跳過中心，依序 idx = idx * 3 + cell
// 編解碼順序必須一致，對應的解碼在 initPatternTable
int encodeWindow(int board[BOARD_MAX][BOARD_MAX], int x, int y, int dx, int dy, int player) {
    int idx = 0;
    for (int off = -5; off <= 5; off++) {
        if (off == 0) continue;   // 中心不入索引
        int nx = x + off * dx;
        int ny = y + off * dy;
        int cell;
        if (nx < 0 || nx >= BOARD_MAX || ny < 0 || ny >= BOARD_MAX) {
            cell = CELL_OPP;
        } else if (board[ny][nx] == player) {
            cell = CELL_SELF;
        } else if (board[ny][nx] == 0) {
            cell = CELL_EMPTY;
        } else {
            cell = CELL_OPP;   // 對方棋子（含第三方）
        }
        idx = idx * 3 + cell;
    }
    return idx;
}

// 增量索引：[視角][y][x][方向] -> 該格為中心、該方向的 encodeWindow 結果
// 視角 p 對應玩家 p+1；牆在 rebuild 時就編進初值，增量更新不碰牆
static int windowIdx[2][BOARD_MAX][BOARD_MAX][4];

// windowIdx 與 neighborCount 是否可信；只在 findBestMove/vcfProbe 的搜索期間為真
// checkUnValid 這條路徑不經過搜索入口，兩張表可能是舊局面甚至全零，靠這個旗標退回原地掃描
static bool idxValid = false;

// 3 的次方表，POW3[e] = 3^e，e 對應 weightExp 算出的位權指數
static const int POW3[10] = {1, 3, 9, 27, 81, 243, 729, 2187, 6561, 19683};

// off 對應 encodeWindow 索引裡的位權指數：off<0 -> 4-off，off>0 -> 5-off
static int weightExp(int off) {
    return (off < 0) ? (4 - off) : (5 - off);
}

// 全盤重算 windowIdx，掛在搜索入口，不依賴逐手同步
static void rebuildWindowIndex(int board[BOARD_MAX][BOARD_MAX]) {
    int dx[] = {1, 1, 0, -1};
    int dy[] = {0, 1, 1, 1};
    for (int p = 0; p < 2; p++) {
        for (int y = 0; y < BOARD_MAX; y++) {
            for (int x = 0; x < BOARD_MAX; x++) {
                for (int d = 0; d < 4; d++) {
                    windowIdx[p][y][x][d] = encodeWindow(board, x, y, dx[d], dy[d], p + 1);
                }
            }
        }
    }
}

// 落子/撤銷在鄰格窗口造成的增量修正，delta 為 +1/-1（落子/撤銷）
// 一次修正雙視角：該子對自己是 SELF、對對手是 OPP，權重分別是 delta 與 2*delta
static void adjustWindowIndex(int x, int y, int player, int delta) {
    int dx[] = {1, 1, 0, -1};
    int dy[] = {0, 1, 1, 1};
    int selfPlane = player - 1;
    int oppPlane = 2 - player;
    for (int d = 0; d < 4; d++) {
        for (int off = -5; off <= 5; off++) {
            if (off == 0) continue;
            int nx = x + off * dx[d];
            int ny = y + off * dy[d];
            if (nx < 0 || nx >= BOARD_MAX || ny < 0 || ny >= BOARD_MAX) continue;   // 牆不參與增量
            int w = POW3[weightExp(-off)];
            windowIdx[selfPlane][ny][nx][d] += delta * w;        // 己方視角：EMPTY -> SELF
            windowIdx[oppPlane][ny][nx][d]  += 2 * delta * w;    // 敵方視角：EMPTY -> OPP
        }
    }
}

// stoneList[p]：玩家 p+1 的所有棋子座標，以 y * BOARD_MAX + x 存；stoneCount[p] 是長度
// 用 short 而非 unsigned char：BOARD_MAX 改大到 16 以上時 y*BOARD_MAX+x 會超過 255
static short stoneList[2][BOARD_MAX * BOARD_MAX];
static int stoneCount[2];

// 全盤重算 stoneList，掛在搜索入口，不依賴逐手同步
static void rebuildStoneList(int board[BOARD_MAX][BOARD_MAX]) {
    stoneCount[0] = 0;
    stoneCount[1] = 0;
    for (int y = 0; y < BOARD_MAX; y++) {
        for (int x = 0; x < BOARD_MAX; x++) {
            int p = board[y][x] - 1;
            if (p == 0 || p == 1) stoneList[p][stoneCount[p]++] = (short)(y * BOARD_MAX + x);
        }
    }
}

// 落子在 stoneList 造成的增量修正：附加一筆
static void addStone(int x, int y, int player) {
    int p = player - 1;
    stoneList[p][stoneCount[p]++] = (short)(y * BOARD_MAX + x);
}

// 撤銷在 stoneList 造成的增量修正：線性搜尋該筆、與最後一筆對調再縮短
// 不假設 pop-back 成立——搜索確實是 LIFO，但那是隱性不變量；線性搜尋每次只掃一色的十來筆，成本可忽略
static void dropStone(int x, int y, int player) {
    int p = player - 1;
    short target = (short)(y * BOARD_MAX + x);
    for (int i = 0; i < stoneCount[p]; i++) {
        if (stoneList[p][i] == target) {
            stoneList[p][i] = stoneList[p][--stoneCount[p]];
            return;
        }
    }
}

#ifdef WINDOW_IDX_CHECK
#include <assert.h>
// debug build 專用：增量結果必須等於當場重算，掛在 placeStone/removeStone 之後
static void checkWindowIndex(int board[BOARD_MAX][BOARD_MAX]) {
    int dx[] = {1, 1, 0, -1};
    int dy[] = {0, 1, 1, 1};
    for (int p = 0; p < 2; p++) {
        for (int y = 0; y < BOARD_MAX; y++) {
            for (int x = 0; x < BOARD_MAX; x++) {
                for (int d = 0; d < 4; d++) {
                    assert(windowIdx[p][y][x][d] == encodeWindow(board, x, y, dx[d], dy[d], p + 1));
                }
            }
        }
    }
}
#endif

#define ADJ_RANGE 2                                        // hasAdjacentPiece 的掃描半徑，與表共用避免漂移
// neighborCount[y][x]：以 (x,y) 為中心的 5×5 內、不含中心的棋子數（不分黑白），上限 24 不會溢位
static unsigned char neighborCount[BOARD_MAX][BOARD_MAX];

// 全盤重算 neighborCount，掛在搜索入口，不依賴逐手同步
static void rebuildNeighborCount(int board[BOARD_MAX][BOARD_MAX]) {
    for (int y = 0; y < BOARD_MAX; y++) {
        for (int x = 0; x < BOARD_MAX; x++) {
            int count = 0;
            for (int dy = -ADJ_RANGE; dy <= ADJ_RANGE; dy++) {
                for (int dx = -ADJ_RANGE; dx <= ADJ_RANGE; dx++) {
                    if (dx == 0 && dy == 0) continue;
                    int nx = x + dx, ny = y + dy;
                    if (nx >= 0 && nx < BOARD_MAX && ny >= 0 && ny < BOARD_MAX && board[ny][nx] != 0) count++;
                }
            }
            neighborCount[y][x] = (unsigned char)count;
        }
    }
}

// 落子/撤銷在 5×5 鄰域造成的增量修正，delta 為 +1/-1（落子/撤銷）
static void adjustNeighborCount(int x, int y, int delta) {
    for (int dy = -ADJ_RANGE; dy <= ADJ_RANGE; dy++) {
        for (int dx = -ADJ_RANGE; dx <= ADJ_RANGE; dx++) {
            if (dx == 0 && dy == 0) continue;
            int nx = x + dx, ny = y + dy;
            if (nx < 0 || nx >= BOARD_MAX || ny < 0 || ny >= BOARD_MAX) continue;
            neighborCount[ny][nx] += delta;
        }
    }
}

#ifdef WINDOW_IDX_CHECK
// debug build 專用：增量結果必須等於當場重算，掛在 placeStone/removeStone 之後
static void checkNeighborCount(int board[BOARD_MAX][BOARD_MAX]) {
    for (int y = 0; y < BOARD_MAX; y++) {
        for (int x = 0; x < BOARD_MAX; x++) {
            int count = 0;
            for (int dy = -ADJ_RANGE; dy <= ADJ_RANGE; dy++) {
                for (int dx = -ADJ_RANGE; dx <= ADJ_RANGE; dx++) {
                    if (dx == 0 && dy == 0) continue;
                    int nx = x + dx, ny = y + dy;
                    if (nx >= 0 && nx < BOARD_MAX && ny >= 0 && ny < BOARD_MAX && board[ny][nx] != 0) count++;
                }
            }
            assert(neighborCount[y][x] == (unsigned char)count);
        }
    }
}

// debug build 專用：stoneList 當場重掃棋盤，比對兩邊的集合（不計順序）
static void checkStoneList(int board[BOARD_MAX][BOARD_MAX]) {
    for (int p = 0; p < 2; p++) {
        int count = 0;
        for (int y = 0; y < BOARD_MAX; y++) {
            for (int x = 0; x < BOARD_MAX; x++) {
                if (board[y][x] != p + 1) continue;
                count++;
                short cell = (short)(y * BOARD_MAX + x);
                bool found = false;
                for (int i = 0; i < stoneCount[p]; i++) {
                    if (stoneList[p][i] == cell) { found = true; break; }
                }
                assert(found);
            }
        }
        assert(count == stoneCount[p]);
    }
}
#endif

// 含中心的不間斷 SELF 長度
static int solidRun(int cells[11]) {
    int leftRun = 0, rightRun = 0;
    for (int j = 1; j < 6 && cells[5 - j] == CELL_SELF; j++) leftRun++;
    for (int j = 1; j < 6 && cells[5 + j] == CELL_SELF; j++) rightRun++;
    return leftRun + 1 + rightRun;
}

// 是否存在一個含中心的 5 格區間全為 SELF
static bool makesFive(int cells[11]) {
    for (int start = 1; start <= 5; start++) {
        bool all = true;
        for (int k = 0; k < 5; k++) {
            if (cells[start + k] != CELL_SELF) { all = false; break; }
        }
        if (all) return true;
    }
    return false;
}

// 四：能再加一子成五。回傳成五點的個數，兩個以上即活四
static int fivePoints(int cells[11]) {
    int n = 0;
    for (int i = 0; i < 11; i++) {
        if (cells[i] != CELL_EMPTY) continue;
        cells[i] = CELL_SELF;
        if (makesFive(cells)) n++;
        cells[i] = CELL_EMPTY;
    }
    return n;
}

// 三：能再加一子成活四且不同時成五。回傳成活四的填法數，兩種以上即活三
static int threePoints(int cells[11]) {
    int n = 0;
    for (int i = 0; i < 11; i++) {
        if (cells[i] != CELL_EMPTY) continue;
        cells[i] = CELL_SELF;
        if (!makesFive(cells) && fivePoints(cells) >= 2) n++;
        cells[i] = CELL_EMPTY;
    }
    return n;
}

// 眠三/跳三專用：能再加一子成衝四（不同時成五、也不同時成活四）的格數
// 與 threePoints 互斥（同一格只會落在成五點=2 或=1 其中一類），量的是
// 「這個三連唯一能推進的方向只剩衝四」——延伸方向已被鎖死的訊號
static int rushPoints(int cells[11]) {
    int n = 0;
    for (int i = 0; i < 11; i++) {
        if (cells[i] != CELL_EMPTY) continue;
        cells[i] = CELL_SELF;
        if (!makesFive(cells) && fivePoints(cells) == 1) n++;
        cells[i] = CELL_EMPTY;
    }
    return n;
}

// 二：RIF 未定義的殘留棋型，靠兩端是否被封區分活二與眠二
// 只認實心二連，且兩端外側不得再有隔空的己方子（那屬於更強的棋型，已被前面分支處理）
static int classifyMinor(int cells[11]) {
    if (solidRun(cells) != 2) return 0;

    int leftRun = 0;
    for (int j = 1; j < 6 && cells[5 - j] == CELL_SELF; j++) leftRun++;
    int left = 5 - leftRun - 1;              // 實連左端外一格
    int right = left + 3;                    // 實連右端外一格

    bool leftOpen = left >= 0 && cells[left] == CELL_EMPTY;
    bool rightOpen = right < 11 && cells[right] == CELL_EMPTY;

    // 端點外再一格若是己方子，掃描時算 gap，舊版不歸類為二
    if (leftOpen && left - 1 >= 0 && cells[left - 1] == CELL_SELF) return 0;
    if (rightOpen && right + 1 < 11 && cells[right + 1] == CELL_SELF) return 0;

    if (leftOpen && rightOpen) return 2;     // 活二
    if (leftOpen || rightOpen) return 6;     // 眠二
    return 0;
}

// [0:0, 1:0, 2:活二，3:活三，4:活四，5:五連，6:眠二，7:純衝四眠三，8:衝四，9:跳活三，10:跳活四，11:偏活跳三，12:跳四，13:偏活三，14:純衝四跳三，15:長連]
/* 回傳中心（cells[5] 為 SELF）在此 11 格窗口形成的最強棋型 index，無棋型回傳 0 */
int classifyWindow(int cells[11]) {
    if (cells[5] != CELL_SELF) return 0;   // 建表恆為 SELF，這道防護給外部直接呼叫用

    int run = solidRun(cells);
    if (run >= 6) return 15;               // 長連
    if (makesFive(cells)) return 5;        // 五連

    // 四級與三級依 RIF 定義推導，牆與敵子都不是 EMPTY，成五點自然數不到
    int fp = fivePoints(cells);
    if (fp > 0) {
        if (run == 4) return fp >= 2 ? 4 : 8;      // 活四、衝四
        return fp >= 2 ? 10 : 12;                  // 跳活四、跳四
    }

    // tp>=1 代表還有方向能成活四，緊急程度與活四同級，不受延伸方向鎖死與否影響
    int tp = threePoints(cells);
    if (tp > 0) {
        if (run == 3) return tp >= 2 ? 3 : 13;     // 活三、偏活三
        return tp >= 2 ? 9 : 11;                   // 跳活三、偏活跳三
    }

    // tp==0：不能成活四，但仍能成衝四代表延伸方向已被鎖死一端，
    // 只是個預先可防守的單點威脅，見 Note/technical/renju-rules.md
    if (rushPoints(cells) > 0) return run == 3 ? 7 : 14;   // 眠三、跳三

    return classifyMinor(cells);
}

// 全枚舉所有窗口編碼，逐一分類填進 patternTable
void initPatternTable() {
    for (int idx = 0; idx < PATTERN_TABLE_SIZE; idx++) {
        int cells[11];
        cells[5] = CELL_SELF;
        int rem = idx;
        // 解碼：off +5 是最低位，與 encodeWindow 反向
        for (int off = 5; off >= -5; off--) {
            if (off == 0) continue;
            cells[5 + off] = rem % 3;
            rem /= 3;
        }
        patternTable[idx] = (unsigned char)classifyWindow(cells);
    }
}

// 首次呼叫時建表：checkUnValid 這條路徑不經過 aiRound，不能靠它初始化
// 與 findBestMove 初始化置換表同一個模式；checkLine、winsAt 共用
static void ensurePatternTable(void) {
    static bool patternTableReady = false;
    if (!patternTableReady) {
        initPatternTable();
        patternTableReady = true;
    }
}

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
        // 三三只認活三/跳活三（tp>=2，兩個方向都能成活四）；偏活三/偏活跳三
        // （13/11，tp==1，只有一個方向能成活四）不算，只用於評分權重
        if ((line[3] + line[9]) >= 2) return -3;
        if ((line[4] + line[8] + line[10] + line[12]) >= 2) return -4;
    }
    return 1;
}

// 直接查 patternTable 四個方向，索引與 checkLine 一致，但跳過 line[16] 的清零與累加，只認 5、15 兩個代碼
// 語意須與 judgeMove 逐項對得上：成五與白棋長連 true，黑棋長連與其餘一律 false
static bool winsAt(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {
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

// 快速評估函數
int quickEvaluate(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY,int player) {
    // 根据进攻和防守策略评估位置的函数
    int total_score = 0, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四，5:五連，6:眠二，7:純衝四眠三，8:衝四，9:跳活三，10:跳活四，11:偏活跳三，12:跳四，13:偏活三，14:純衝四跳三，15:長連]
    int my_line[16] = {0}, op_line[16] = {0}; // 该位置落子后，自己和对手的连线数

    // 成五直接給最高分，與 judgeMove 共用同一套判定
    // 勝著不必再經棋型分類，也避免這類點被 score != 0 濾掉
    if (judgeMove(board, x, y, player) == 2) return 2000000;

    // 更新
    checkLine(board, x, y, player, my_line);
    checkLine(board, x, y, 3-player, op_line);

    // 進攻策略 - 提升關鍵連線得分，特別是活四、衝四、跳四
    // 偏活三/偏活跳三（13/11）緊急程度與跳活三同級：缺口一旦填上就是
    // 兩端全開的活四，不是弱棋型；純衝四眠三/跳三（7/14）延伸方向已鎖死，
    // 只是預先可防守的單點威脅，權重明顯低於 11/13
    attack   += 1000000 * my_line[5] +  // 五連
                100000  * my_line[4] +  // 活四
                20000   * my_line[10]+  // 跳活四
                10000   * my_line[8] +  // 衝四
                7000    * my_line[12]+  // 跳四
                8000    * my_line[3] +  // 活三
                4000    * my_line[9] +  // 跳活三
                4000    * my_line[13]+  // 偏活三
                4000    * my_line[11]+  // 偏活跳三
                700     * my_line[14]+  // 純衝四跳三
                500     * my_line[7] +  // 純衝四眠三
                50      * my_line[2] +  // 活二
                10      * my_line[6];   // 眠二

    // 四三解禁策略，若當前形成威脅可以加大進攻分數
    if (player == 1 && (my_line[3] > 0 || my_line[7]>0 || my_line[9]>0 || my_line[11]>0 || my_line[13]>0 || my_line[14]>0) && (my_line[4] > 0 ||my_line[8] > 0 ||my_line[10]>0||my_line[12]>0)) {
        attack += 500000;
    }

    // 防守策略 - 防守時同樣拉大連線得分差距，尤其是活四、衝四等關鍵連線
    defence  += 1000000 * op_line[5] +  // 五連
                100000  * op_line[4] +  // 活四
                20000   * op_line[10]+  // 跳活四
                10000   * op_line[8] +  // 衝四
                7000    * op_line[12]+  // 跳四
                8000    * op_line[3] +  // 活三
                4000    * op_line[9] +  // 跳活三
                4000    * op_line[13]+  // 偏活三
                4000    * op_line[11]+  // 偏活跳三
                700     * op_line[14]+  // 純衝四跳三
                500     * op_line[7] +  // 純衝四眠三
                50      * op_line[2] +  // 活二
                10      * op_line[6];   // 眠二

    // 計算（整數運算：避免浮點轉換的精度損耗）
    // 排序用 attack + defence：攻或防有價值的點都該排前面
    // 與 evaluate 的 attack - defence 不同，是刻意的
    total_score += attack + defence * 4 / 5;
    // 增加防守
    if(attack <= defence) total_score += defence / 10;
    return total_score;
}

// 評估函數
int evaluate(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY,int player) {
    // 初始化總分(避免劣勢時全部都是負分無法計算)、自己與對手的分數
    int total_score = 12000, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四，5:五連，6:眠二，7:純衝四眠三，8:衝四，
    //  9:跳活三，10:跳活四，11:偏活跳三，12:跳四，13:偏活三，14:純衝四跳三，15:長連]
    int my_now[16] = {0}, op_now[16] = {0}; // 目前自己和对手的连线数

    // 更新
    checkNow(board, minX, maxX, minY,  maxY, player, my_now);
    checkNow(board, minX, maxX, minY,  maxY, 3 - player, op_now);
    // 優先級：五連>活四>跳活四>衝四=活三>跳四>
    // 進攻策略：偏活三/偏活跳三（13/11）與跳活三同級，純衝四眠三/跳三（7/14）
    // 延伸方向已鎖死，權重明顯低於 11/13（見 quickEvaluate 上方註解）
    attack   += 9999999 * (my_now[5]/5) +   // 五連
                20000   * (my_now[4]/4) +   // 活四
                15000   * (my_now[10]/4)+   // 跳活四
                10000   * (my_now[8]/4) +   // 衝四
                10000   * (my_now[12]/4)+   // 跳四
                7000    * (my_now[3]/3) +   // 活三
                4000    * (my_now[9]/3) +   // 跳活三
                4000    * (my_now[13]/3)+   // 偏活三
                4000    * (my_now[11]/3)+   // 偏活跳三
                500     * (my_now[7]/3) +   // 純衝四眠三
                700     * (my_now[14]/3)+   // 純衝四跳三
                20      * (my_now[2]/2) +   // 活二
                5       * (my_now[6]/2);    // 眠二

    // 防守策略
    defence  += 9999999 * (op_now[5]/5) +   // 五連
                20000   * (op_now[4]/4) +   // 活四
                15000   * (op_now[10]/4)+   // 跳活四
                10000   * (op_now[8]/4) +   // 衝四
                10000   * (op_now[12]/4)+   // 跳四
                7000    * (op_now[3]/3) +   // 活三
                4000    * (op_now[9]/3) +   // 跳活三
                4000    * (op_now[13]/3)+   // 偏活三
                4000    * (op_now[11]/3)+   // 偏活跳三
                500     * (op_now[7]/3) +   // 純衝四眠三
                700     * (op_now[14]/3)+   // 純衝四跳三
                20      * (op_now[2]/2) +   // 活二
                5       * (op_now[6]/2);    // 眠二
    
    // 若對手已經有活四(有可能是未來)，可是我沒有活四/衝四(非常危險-->幾乎沒救了)
    if (op_now[4] > 0 && (my_now[4] == 0 && my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 4000;
    }
    // 若對手已經有衝四(有可能是未來)，可是我沒有活四/衝四(危險)
    else if ((op_now[8] > 0) && (my_now[4] == 0 && my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 900;
    }// 若對手已經有活三/偏活三/偏活跳三(能成活四)，可是我沒有活三或以上的(危險)
    else if ((op_now[3] > 0 || op_now[9] > 0 || op_now[13] > 0 || op_now[11] > 0) &&
             (my_now[3] == 0 && my_now[9] == 0 && my_now[13] == 0 && my_now[11] == 0)) {
        if (my_now[4] == 0 && my_now[8] == 0){
            if(my_now[5] == 0)
                defence += 1000;
        }
    }// 若對手已經有純衝四眠三/跳三(只鎖死方向，延伸方向已定型)，可是我沒有同級以上的
    else if ((op_now[7] > 0 || op_now[14] > 0) &&
             (my_now[7] == 0 && my_now[14] == 0 &&
              my_now[3] == 0 && my_now[9] == 0 && my_now[13] == 0 && my_now[11] == 0)) {
        if (my_now[4] == 0 && my_now[8] == 0){
            if(my_now[5] == 0)
                defence += 100;
        }
    }
    if((op_now[3]>0 || op_now[9]>0 || op_now[13]>0 || op_now[11]>0) &&
       (op_now[4]>0 || op_now[8]>0 || op_now[10]>0)){
        defence += 4000;
    }

    // 計算（整數運算：避免浮點轉換的精度損耗）
    // 3/5 與 4/5：執黑與執白的激進程度不同，非正確性問題
    // ai 在一局內固定，單次搜索中為常數
    if(player == 1)total_score +=  attack - defence * 3 / 5;
    else total_score +=  attack - defence * 4 / 5;
    // 強化防守策略，根據當前的局勢
    // 當對手有優勢時，提高防守的影響力
    if (defence > attack) {
        total_score -= defence / 10;
    }
    return total_score;
}

// 檢查是否有人勝利
int checkWin(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int currentPlayer) {
    int my_now[16] = {0}, op_now[16] = {0}; // 目前自己和对手的连线数
    checkNow(board, minX, maxX, minY,  maxY, currentPlayer, my_now);
    checkNow(board, minX, maxX, minY,  maxY, 3 - currentPlayer, op_now);

    // 若有一方玩家赢了
    if((currentPlayer == 2 && my_now[15]>0) ||my_now[5]>0) return currentPlayer;
    else if((3 - currentPlayer == 2 && op_now[15]>0) || op_now[5]>0) return 3-currentPlayer;
    else return 0; // 没有玩家赢
}

// 檢查5*5周圍是否有棋子；索引可信時查表，否則退回掃描
bool hasAdjacentPiece(int board[BOARD_MAX][BOARD_MAX], int x, int y) {
    if (idxValid) return neighborCount[y][x] > 0;
    int range = 2;
    for (int dx = -range; dx <= range; dx++) {
        for (int dy = -range; dy <= range; dy++) {
            if (dx == 0 && dy == 0) continue;
            int nx = x + dx, ny = y + dy;
            if (nx >= 0 && nx < BOARD_MAX && ny >= 0 && ny < BOARD_MAX && board[ny][nx] != 0) {
                return true;
            }
        }
    }
    return false;
}

// 大到小排序
int Big_Small(const void* a, const void* b) {
    Move *moveA = (Move *)a;
    Move *moveB = (Move *)b;
    return moveB->score - moveA->score; // 大到小排序
}

// 快速處理勝局/敗局
// selfCanFive / oppCanFive 由呼叫端從棋型計數導出，見 sortMoves
int endGame(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int minX, int maxX, int minY, int maxY, int currentPlayer, bool selfCanFive, bool oppCanFive){
    int counter =0;
    // counter 併進 for 的遞增段：迴圈體現在有 continue，留在體末會漏遞增
    for (int player = currentPlayer; counter <2; player = 3 - player, counter++){
        // 該方沒有成五點，這一趟全框掃描整個跳過
        if (!(counter == 0 ? selfCanFive : oppCanFive)) continue;
        for (int x = minX; x <= maxX; x++) {
            for (int y = minY; y <= maxY; y++) {
                if (board[y][x] == 0 && hasAdjacentPiece(board, x, y)) {
                    // 實際落子的是 currentPlayer，黑棋禁手點不能下
                    if (currentPlayer == 1 && judgeMove(board, x, y, 1) < 1) continue;
                    // ai勝利（直接落子）/ 對手勝利（防守）：單點判定，免落子、免全盤掃描
                    // winsAt 直接查 patternTable，不經 judgeMove／checkLine 的完整分類
                    if (winsAt(board, x, y, player)) {
                        *bestX = x;
                        *bestY = y;
                        return 1;  // 立即返回獲勝移動
                    }
                }
            }
        }
    }
    return 0;
}

// VCF：連續衝四的強制勝搜索
// 守方應手唯一（擋成五點），樹極窄，故能搜得比主搜索 7 層深很多。
// 只算衝四／活四，不含應手不唯一的活三（那是 VCT）；守方擋出反四則放棄該線；
// 守方已有成五點則衝四救不了——寧可漏殺，不可誤判必勝

// 直接數成五點而非用 checkLine 分類：恰 1 個是衝四，2 個以上是活四
// 與 judgeMove 共用同一套判定，避免規則漂移

#define VCF_MAX_PLY 16        // 攻方著手數上限（= 最多算 8 連沖）
#define VCF_MAX_NODES 200000  // 節點預算：算殺樹窄是常態不是保證，仍需防爆炸
#define VCF_MAX_FIVE_PTS 8

static long long vcfNodes = 0;

// 列出 player 落子即成五的空點，回傳總數（可能多於寫入 pts 的數量）
static int listFivePoints(int board[BOARD_MAX][BOARD_MAX], int player,
                          int minX, int maxX, int minY, int maxY,
                          int pts[][2], int maxPts) {
    int n = 0;
    for (int y = minY; y <= maxY; y++) {
        for (int x = minX; x <= maxX; x++) {
            if (board[y][x] != 0 || !hasAdjacentPiece(board, x, y)) continue;
            if (!winsAt(board, x, y, player)) continue;
            if (n < maxPts) { pts[n][0] = x; pts[n][1] = y; }
            n++;
        }
    }
    return n;
}

// 列舉 player 的成四著法（含直接成五），依威脅程度降冪排序
static int listFourMoves(int board[BOARD_MAX][BOARD_MAX], int player, Move *moves,
                         int minX, int maxX, int minY, int maxY) {
    int n = 0;
    for (int y = minY; y <= maxY; y++) {
        for (int x = minX; x <= maxX; x++) {
            if (board[y][x] != 0 || !hasAdjacentPiece(board, x, y)) continue;
            int verdict = judgeMove(board, x, y, player);
            if (verdict < 1) continue;   // 已有子，或黑棋禁手點不能當攻擊手段
            if (verdict == 2) {          // 直接成五
                moves[n++] = (Move){x, y, 1000000};
                continue;
            }
            int line[16] = {0};
            checkLine(board, x, y, player, line);
            if (line[4] || line[10])      moves[n++] = (Move){x, y, 100000};  // 活四
            else if (line[8] || line[12]) moves[n++] = (Move){x, y, 10000};   // 衝四
        }
    }
    qsort(moves, n, sizeof(Move), Big_Small);
    return n;
}

// 落子單一入口，賦值後同步增量修正 windowIdx 與 neighborCount，不動 Zobrist key
static void placeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {
    board[y][x] = player;
    adjustWindowIndex(x, y, player, 1);
    adjustNeighborCount(x, y, 1);
    addStone(x, y, player);
#ifdef WINDOW_IDX_CHECK
    checkWindowIndex(board);
    checkNeighborCount(board);
    checkStoneList(board);
#endif
}

// 撤銷單一入口，對稱於 placeStone；落子色從盤面現值讀出，呼叫端不必多帶參數
static void removeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y) {
    int player = board[y][x];
    adjustWindowIndex(x, y, player, -1);
    adjustNeighborCount(x, y, -1);
    dropStone(x, y, player);
    board[y][x] = 0;
#ifdef WINDOW_IDX_CHECK
    checkWindowIndex(board);
    checkNeighborCount(board);
    checkStoneList(board);
#endif
}

// attacker 是否有連續衝四強制勝；是則回傳 1 並寫入首手 *wx,*wy
static int vcfSearch(int board[BOARD_MAX][BOARD_MAX], int attacker, int ply,
                     int minX, int maxX, int minY, int maxY, int *wx, int *wy) {
    if (ply > VCF_MAX_PLY) return 0;
    if (++vcfNodes > VCF_MAX_NODES) return 0;

    int defender = 3 - attacker;
    Move moves[BOARD_MAX * BOARD_MAX];
    int n = listFourMoves(board, attacker, moves, minX, maxX, minY, maxY);

    for (int i = 0; i < n; i++) {
        int x = moves[i].x, y = moves[i].y;
        if (judgeMove(board, x, y, attacker) == 2) {   // 直接成五，不必再算
            *wx = x; *wy = y;
            return 1;
        }

        placeStone(board, x, y, attacker);
        int pts[VCF_MAX_FIVE_PTS][2];
        int atkN = listFivePoints(board, attacker, minX, maxX, minY, maxY, pts, VCF_MAX_FIVE_PTS);
        if (atkN == 0) { removeStone(board, x, y); continue; }  // 沒造成成五威脅 -> 不具強制性

        // 守方當下已能成五：他搶先落子就贏了，攻方的衝四救不回來
        int defPts[VCF_MAX_FIVE_PTS][2];
        if (listFivePoints(board, defender, minX, maxX, minY, maxY, defPts, VCF_MAX_FIVE_PTS) > 0) {
            removeStone(board, x, y);
            continue;
        }

        if (atkN >= 2) {   // 活四：守方擋一點，攻方下另一點即成五
            removeStone(board, x, y);
            *wx = x; *wy = y;
            return 1;
        }

        int bx = pts[0][0], by = pts[0][1];   // 衝四：守方唯一擋點
        if (judgeMove(board, bx, by, defender) < 0) {   // 守方是黑棋且該點是禁手 -> 擋不了
            removeStone(board, x, y);
            *wx = x; *wy = y;
            return 1;
        }

        placeStone(board, bx, by, defender);
        // 反四：守方的擋子同時做出自己的四，攻方必須回應，保守放棄此線
        int counterFour = listFivePoints(board, defender, minX, maxX, minY, maxY, defPts, VCF_MAX_FIVE_PTS);
        int win = 0;
        if (counterFour == 0) {
            int nx, ny;
            win = vcfSearch(board, attacker, ply + 2, minX, maxX, minY, maxY, &nx, &ny);
        }
        removeStone(board, bx, by);
        removeStone(board, x, y);

        if (win) { *wx = x; *wy = y; return 1; }
    }
    return 0;
}

// 根節點入口：重置節點預算後開跑
int vcfFindWin(int board[BOARD_MAX][BOARD_MAX], int attacker,
               int minX, int maxX, int minY, int maxY, int *wx, int *wy) {
    vcfNodes = 0;
    return vcfSearch(board, attacker, 1, minX, maxX, minY, maxY, wx, wy);
}

long long getVcfNodes(void) { return vcfNodes; }

// 啓發式函數Heuristic Function：快速評估落點后排序
void sortMoves(int board[BOARD_MAX][BOARD_MAX], Move* moves, int *count, int minX, int maxX, int minY, int maxY, int player) {
    *count = 0;

    // 統計當前AI和玩家的棋形數
    int my_now[16] = {0}, op_now[16] = {0};
    checkNow(board, minX, maxX, minY, maxY, player, my_now);
    checkNow(board, minX, maxX, minY, maxY, 3 - player, op_now);

    // 成五點存在的充要條件：該方有四。任何成五點的窗口裡都有四顆同色，
    // 那四顆各自為中心必被分類成活四/沖四/跳活四/跳四之一
    // 併入五連與長連：根節點不經 checkWin，盤上已成五時 endGame 仍須掃
    bool selfCanFive = (my_now[4] + my_now[5] + my_now[8] + my_now[10] + my_now[12] + my_now[15]) > 0;
    bool oppCanFive  = (op_now[4] + op_now[5] + op_now[8] + op_now[10] + op_now[12] + op_now[15]) > 0;

    // 最高優先級：檢查是否有立即獲勝的棋路
    int bestX = -1, bestY = -1;
    if (endGame(board, &bestX, &bestY, minX, maxX, minY, maxY, player, selfCanFive, oppCanFive)) {
        moves[(*count)++] = (Move){bestX, bestY, 9999999};
        return;
    }

    // 策略：條件+分數+檢查對象
    // [0:0, 1:0, 2:活二，3:活三，4:活四，5:五連，6:眠二，7:純衝四眠三，8:衝四，
    //  9:跳活三，10:跳活四，11:偏活跳三，12:跳四，13:偏活三，14:純衝四跳三，15:長連]
    // 優先級：五連>活四>跳活四>衝四=活三>跳四>....
    // 3/9/11/13 都能成活四（RIF 的 Three），威脅同級，防守/進攻觸發條件必須一併涵蓋
    // 曾經漏掉 11：只認 3/9 讓兩端仍開放的跳三（見 loss-analysis-jump-three-gap.md）
    // 從未進入候選列表，AI 因此漏防、輸掉一局
    struct {
        bool condition;
        int score;
        int check_player;
    } strategy_moves[] = {
        // 次優先級：對手已有兩個三連綫/23連綫，且自己沒有活三以上的連綫（防守)
        {
            op_now[2] > 0 && (op_now[3]+op_now[7]+op_now[9]+op_now[11]+op_now[13]+op_now[14])/3 >= 1,
            99999,
            3 - player  // 檢查對手
        },

        // 第三優先級：若自己已經有活三/跳活三/偏活三/偏活跳三必勝了,且對手沒有活三以上的連綫（進攻）
        {
            (my_now[3] > 0 || my_now[9] > 0 || my_now[13] > 0 || my_now[11] > 0) &&
            op_now[4] == 0 && op_now[8] == 0 && op_now[10] == 0,
            100000,
            player  // 檢查自己
        },

        // 第四優先級：對手已有活三/跳活三/偏活三/偏活跳三，且自己沒有活三以上的連綫（防守）
        {
            (op_now[3] > 0 || op_now[9] > 0 || op_now[13] > 0 || op_now[11] > 0) &&
            my_now[3] == 0 && my_now[4] == 0 && my_now[8] == 0 && my_now[10] == 0,
            88888,
            3 - player  // 檢查對手
        },
        // 第五優先級：無腦衝四（純衝四眠三/跳三只能推進到衝四，主動推進不虧）
        {
            my_now[7]>0 || my_now[14]>0,
            66666,
            player      // 檢查自己
        }
    };

    // 遍历每种策略
    for (int strategy = 0; strategy < 4; strategy++) {
        // 跳过不符合条件的策略
        if (!strategy_moves[strategy].condition) continue;
        
        // 遍历棋盘寻找符合策略的走法
        for (int x = minX; x <= maxX; x++) {
            for (int y = minY; y <= maxY; y++) {
                // 跳过无效位置；便宜的條件先過濾，禁手判定要掃線
                if (board[y][x] != 0 || !hasAdjacentPiece(board, x, y)) continue;
                if (player == 1 && checkUnValid(board, x, y, player) != 1) continue;

                // 检查位置的棋型
                int line[16] = {0};
                checkLine(board, x, y, strategy_moves[strategy].check_player, line);

                bool valid_move = false;
                switch (strategy) {
                    // 防御多重威胁线
                    case 0:
                        valid_move = (line[3] + line[7] + line[9] + line[11] + line[13] + line[14]) >= 1 &&
                                   (line[4] + line[8] + line[10] + line[12]) >= 1;
                        break;
                    // 主动创建活四
                    case 1: 
                        valid_move = line[4] >= 1;
                        break;
                    // 防御对手活四
                    case 2: 
                        valid_move = line[4] >= 1 || line[10] >= 1;
                        break;
                    // 主动创建衝四
                    case 3:
                        valid_move = line[8] >= 1 || line[10] >= 1 || line[12] >= 1;
                        break;
                }
                
                // 找到有效走法，添加到列表
                if (valid_move) {
                    moves[(*count)++] = (Move){x, y, strategy_moves[strategy].score};
                }
                memset(line, 0, sizeof(line));  // 重置line数组
            }
        }
    }
    // 已知限制：策略走法超過 4 個時跳過通用評估，一般著法根本沒生成
    // 截斷延伸只救得回已生成的強制手
    if (*count > 4) {
        // 這條出口也必須排序：呼叫端的截斷延伸靠降冪才能在第一個低於門檻處停下
        // 策略哨兵分數本身不遞減
        qsort(moves, *count, sizeof(Move), Big_Small);
        return;
    }
    // 若無適用策略：通用走法评估
    for (int x = minX; x <= maxX; x++) {
        for (int y = minY; y <= maxY; y++) {
            // 跳过无效位置；便宜的條件先過濾，禁手判定要掃線
            if (board[y][x] != 0 || !hasAdjacentPiece(board, x, y)) continue;
            if (player == 1 && checkUnValid(board, x, y, player) != 1) continue;

            // 快速评估位置价值
            int score = quickEvaluate(board, x, y, minX, maxX, minY, maxY, player);
            if (score != 0) {  // 0 分點無攻防價值，不佔候選名額
                moves[(*count)++] = (Move){x, y, score};
            }
        }
    }

    // 錯誤檢查和排序
    if (*count == 0) {
        printf("Error: No valid moves found! Board position might be invalid.\n");
        return;
    }

    qsort(moves, *count, sizeof(Move), Big_Small);
}

// Alpha Beta --> minimax函數
int miniMax(int board[BOARD_MAX][BOARD_MAX], int depth, bool isMaximizing, int currentPlayer, int ai, int alpha, int beta, int minX, int maxX, int minY, int maxY) {
    // 檢查是否達到搜索深度或遊戲結束
    int result = checkWin(board, minX, maxX, minY, maxY, currentPlayer);

    // 如果遊戲結束，添加深度獎勵（越早勝利分數越高）
    if (result != 0) {
        if (result == ai) {
            // AI 勝利：基礎分 + 深度獎勵（depth 越大表示越早勝利）
            return 10000000 + depth * 10000;
        } else {
            // AI 失敗：基礎懲罰 - 深度懲罰（depth 越大表示越晚失敗，懲罰較小）
            return -10000000 - depth * 10000;
        }
    }

    // 到達搜索深度限制，返回靜態評估分數
    if (depth == 0) {
        return evaluate(board, minX, maxX, minY, maxY, ai);
    }

    // 在置換表中查找當前棋盤狀態
    HashEntry* entry = lookupHashEntry(currentZobristKey);

    // 先複製 bestMove 到區域變數：遞迴的 always-replace 寫入
    // 可能覆蓋同一個 bucket，迴圈中不能再讀 entry 指標本身
    // (0,0) 是合法座標，判定用 >= 0 而非 > 0
    int ttMoveX = -1, ttMoveY = -1;
    if (entry != NULL && entry->bestX >= 0) {
        ttMoveX = entry->bestX;
        ttMoveY = entry->bestY;
    }

    // 如果在置換表中找到了當前狀態，並且存儲的深度大於等於當前深度
    if (entry != NULL && entry->depth >= depth) {
        if (entry->flag == 'E') {
            return entry->score;
        } else if (entry->flag == 'L' && entry->score > alpha) {
            // 如果是下界，更新 alpha 值
            alpha = entry->score;
        } else if (entry->flag == 'U' && entry->score < beta) {
            // 如果是上界，更新 beta 值
            beta = entry->score;
        }

        // Alpha-Beta 剪枝
        if (alpha >= beta) {
            return entry->score;
        }
    }

    // flag 必須對照實際搜索用的視窗：TT 命中會收窄 alpha/beta
    // 用收窄前的邊界會把上界誤存成 'E'，覆蓋更深的正確 entry
    int alphaOrig = alpha, betaOrig = beta;

    int bestScore = isMaximizing ? INT_MIN : INT_MAX;
    int moveCount = 0;
    Move moves[BOARD_MAX * BOARD_MAX];
    sortMoves(board, moves, &moveCount, minX, maxX, minY, maxY, currentPlayer);
    if (moveCount == 0) return isMaximizing ? INT_MIN : INT_MAX;

    // PV-Move ordering：bestMove 不受 depth 限制，在截斷前的列表
    // 找到後 memmove 到首位，同時把它從硬截斷中救回來
    if (ttMoveX >= 0) {
        for (int i = 0; i < moveCount; i++) {
            if (moves[i].x == ttMoveX && moves[i].y == ttMoveY) {
                if (i > 0) {
                    Move ttMove = moves[i];
                    memmove(&moves[1], &moves[0], i * sizeof(Move));
                    moves[0] = ttMove;
                }
                break;
            }
        }
    }

    // 截斷保險：候選是降冪排序的，所以「保留所有 >= 門檻的著法」等於把截斷點
    // 延到第一個低於門檻的位置；必須在 PV-Move 搬移之後
    // moves[0] 換成 TT move 後不再有序，但 moves[1..] 仍降冪
    int count = moveCount > 10 ? 10 : moveCount;
    while (count < moveCount && moves[count].score >= FORCING_SCORE) count++;
    int bestMx = moves[0].x, bestMy = moves[0].y;
    for (int i = 0; i <count; i++) {
        int x = moves[i].x, y = moves[i].y;
        placeStone(board, x, y, currentPlayer);
        updateZobristKey(x, y, currentPlayer);// 更新雜湊值
        // 遞迴呼叫 miniMax，切換到對手回合
        if (isMaximizing) {
            int score = miniMax(board, depth - 1, false, 3 - currentPlayer, ai, alpha, beta, minX, maxX, minY, maxY);
            if (score > bestScore) { bestScore = score; bestMx = x; bestMy = y; }
            // 更新 Alpha 值
            alpha = (bestScore > alpha) ? bestScore : alpha;
        }else {
            int score = miniMax(board, depth - 1, true, 3 - currentPlayer, ai, alpha, beta, minX, maxX, minY, maxY);
            if (score < bestScore) { bestScore = score; bestMx = x; bestMy = y; }
            // 更新 Beta 值
            beta = (bestScore < beta) ? bestScore : beta;
        }
        // 撤銷移動
        removeStone(board, x, y);
        updateZobristKey(x, y, currentPlayer); // 還原雜湊值

        // Alpha-Beta 剪枝
        if (alpha >= beta) break;
    }

    // 在返回分數之前，將結果存儲到置換表中
    char flag;
    if (bestScore <= alphaOrig) {
        flag = 'U';  // 上界 (fail-low)
    } else if (bestScore >= betaOrig) {
        flag = 'L';  // 下界 (fail-high)
    } else {
        flag = 'E';  // 精確值
    }
    storeHashEntry(currentZobristKey, depth, bestScore, flag, bestMx, bestMy);

    return bestScore;
}

// 找最佳落子（迭代加深：從深度 1 逐層加深，每層用上一層的最佳走法改善排序）
static void findBestMoveImpl(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int ai, int minX, int maxX, int minY, int maxY, int roundCounter) {
    static bool ttInitialized = false;
    if (!ttInitialized) {
        initTranspositionTable();
        ttInitialized = true;
    }
    // 每次搜索前以實際盤面重算，key 為絕對值——不依賴外部呼叫方逐手同步
    currentZobristKey = computeZobristKey(board);
    rebuildWindowIndex(board);
    rebuildNeighborCount(board);
    rebuildStoneList(board);
    int moveCount = 0;

    int maxDepth = MAX_DEPTH + (ai == 1 ? 1 : 0);
    if (roundCounter <=8 && maxDepth>6) maxDepth -=2;
    Move moves[BOARD_MAX * BOARD_MAX];
    sortMoves(board, moves, &moveCount, minX, maxX, minY, maxY, ai);
    // 截斷保險：同 miniMax，強制著法（成四/擋四等級）不受 top-N 截斷
    int count = moveCount > 12 ? 12 : moveCount;
    while (count < moveCount && moves[count].score >= FORCING_SCORE) count++;
    if (count == 0) return;
    *bestX = moves[0].x;
    *bestY = moves[0].y;

    // 算殺：找到強制勝就直接走，不必進主搜索
    // 擺在 sortMoves 之後，成五/擋五已由 endGame 快速路徑處理
    int vx, vy;
    if (vcfFindWin(board, ai, minX, maxX, minY, maxY, &vx, &vy)) {
        *bestX = vx;
        *bestY = vy;
        return;
    }

    for (int d = 1; d <= maxDepth; d++) {
        int bestScore = INT_MIN;
        int bestIdx = 0;
        int alpha = INT_MIN;
        for (int i = 0; i < count; i++) {
            int x = moves[i].x, y = moves[i].y;
            placeStone(board, x, y, ai);
            updateZobristKey(x,y,ai);
            int score = miniMax(board, d-1, false, 3 - ai, ai, alpha, INT_MAX, minX, maxX, minY, maxY);
            updateZobristKey(x,y,ai);
            removeStone(board, x, y);

            //printf("d=%d %d(x:%d,y:%d)--->%d\n",d,score,x,y,moves[i].score);
            if (score > bestScore) {
                bestScore = score;
                bestIdx = i;
            }
            if (bestScore > alpha) alpha = bestScore;
        }
        // 把本層最佳走法移到候選首位（其餘保持相對順序），供下一層優先搜索
        Move best = moves[bestIdx];
        memmove(&moves[1], &moves[0], bestIdx * sizeof(Move));
        moves[0] = best;
        *bestX = best.x;
        *bestY = best.y;
        // 已找到必勝走法，不需要再加深
        if (bestScore >= 10000000) break;
    }
}

// 對外入口：只在這裡開關 idxValid，保證有效期不跨越回 Python 的邊界
// 用包裝函式而非在 Impl 每個 return 前設偽，改動內部提前返回時不會漏設
void findBestMove(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int ai, int minX, int maxX, int minY, int maxY, int roundCounter) {
    idxValid = true;
    findBestMoveImpl(board, bestX, bestY, ai, minX, maxX, minY, maxY, roundCounter);
    idxValid = false;
}

// 計算當前棋局的最小和最大邊界
void getBounds(int board[BOARD_MAX][BOARD_MAX], int *minX, int *maxX, int *minY, int *maxY) {
    *minX = BOARD_MAX;
    *maxX = 0;
    *minY = BOARD_MAX;
    *maxY = 0;
    
    for (int x = 0; x < BOARD_MAX; x++) {
        for (int y = 0; y < BOARD_MAX; y++) {
            if (board[y][x] != 0) {
                if (x < *minX) *minX = x;
                if (x > *maxX) *maxX = x;
                if (y < *minY) *minY = y;
                if (y > *maxY) *maxY = y;
            }
        }
    }
    
    // 擴大邊界（棋盤為 0-indexed，下限夾在 0）
    *minX = (*minX - 2 >= 0) ? *minX - 2 : 0;
    *maxX = (*maxX + 2 < BOARD_MAX) ? *maxX + 2 : BOARD_MAX - 1;
    *minY = (*minY - 2 >= 0) ? *minY - 2 : 0;
    *maxY = (*maxY + 2 < BOARD_MAX) ? *maxY + 2 : BOARD_MAX - 1;
}

// 測試用入口：自行算邊界後跑算殺，不必隔著 aiRound 驗證 VCF
static int vcfProbeImpl(int board[BOARD_MAX][BOARD_MAX], int attacker, int *wx, int *wy) {
    int minX, maxX, minY, maxY;
    getBounds(board, &minX, &maxX, &minY, &maxY);
    rebuildWindowIndex(board);
    rebuildNeighborCount(board);
    rebuildStoneList(board);
    return vcfFindWin(board, attacker, minX, maxX, minY, maxY, wx, wy);
}

// 對外入口：同 findBestMove，包裝函式集中管理 idxValid 的開關與清除
int vcfProbe(int board[BOARD_MAX][BOARD_MAX], int attacker, int *wx, int *wy) {
    idxValid = true;
    int found = vcfProbeImpl(board, attacker, wx, wy);
    idxValid = false;
    return found;
}

// AI回合
void aiRound(int board[BOARD_MAX][BOARD_MAX], int ai, int roundCounter,int* bestx, int* besty) {
    int x, y;
    int minX, maxX, minY, maxY;
    getBounds(board, &minX, &maxX, &minY, &maxY);
    if(ai == 1){ // 黑棋
        // 開局
        if (roundCounter == 1) { 
            x = MIDPOINT_X;
            y = MIDPOINT_Y;
        } 
        
        // 第二步：優先取中心左上斜角，被佔則依序換其他斜角
        // 依序掃描四個斜角，取第一個空點。舊版用 if/else-if 串接，但
        // else-if 的守衛檢查的是中心正上方、與該分支要下的斜角無關，
        // 且改用右上角後從未再檢查該點是否已被佔據。
        else if(roundCounter == 3){
            const int diag[4][2] = {
                {MIDPOINT_X - 1, MIDPOINT_Y - 1},
                {MIDPOINT_X + 1, MIDPOINT_Y - 1},
                {MIDPOINT_X - 1, MIDPOINT_Y + 1},
                {MIDPOINT_X + 1, MIDPOINT_Y + 1}
            };
            x = -1;
            y = -1;
            for(int i = 0; i < 4; i++){
                if(board[diag[i][1]][diag[i][0]] == 0){
                    x = diag[i][0];
                    y = diag[i][1];
                    break;
                }
            }
            // 四個斜角都被佔（正常對局不會發生，僅在悔棋等異常狀態下可能）
            // 時退回一般搜索，確保不會回傳已有棋子的座標。
            if(x < 0) findBestMove(board, &x, &y, ai, minX, maxX, minY, maxY, roundCounter);
        }
        // 第三手開始
        else{
            findBestMove(board,&x, &y, ai, minX, maxX, minY, maxY, roundCounter); // 找到最佳位置
        }
    }
    // 白棋
    else{
        if (roundCounter == 2){
            srand(time(NULL));  // 初始化隨機數生成器
            x = MIDPOINT_X - 1 + rand() % 3;  // 中心點 ±1 範圍內的隨機整數
            y = MIDPOINT_Y - 1 + rand() % 3;
            // 隨機點已被佔據（正常對局只有黑棋第一手在中心，但悔棋等異常
            // 狀態下可能有其他棋子），依序找 3x3 內第一個空點。
            if(board[y][x] != 0){
                int found = 0;
                for(int j = MIDPOINT_Y - 1; j <= MIDPOINT_Y + 1 && !found; j++){
                    for(int i = MIDPOINT_X - 1; i <= MIDPOINT_X + 1 && !found; i++){
                        if(board[j][i] == 0){
                            x = i;
                            y = j;
                            found = 1;
                        }
                    }
                }
                if(!found) findBestMove(board, &x, &y, ai, minX, maxX, minY, maxY, roundCounter);
            }
        }
        else{
            findBestMove(board,&x, &y, ai, minX, maxX, minY, maxY, roundCounter); // 找到最佳位置
        }
    }

    *bestx = x;
    *besty = y;
}
