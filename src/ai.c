#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <limits.h>
#include <string.h>
#include <time.h>
#include <stdint.h> // unsigned long long int.....

#define MIDPOINT_X 11
#define MIDPOINT_Y 11
#define BOARD_MAX 22
#define MAX_DEPTH 7 // 定義搜索深度
#define TABLE_SIZE (1 << 20)   // 1,048,576 個 entry，約 16MB
#define TABLE_MASK (TABLE_SIZE - 1)

typedef struct {
    unsigned long long key;  // Zobrist 哈希鍵(結點局面的 64 位校驗值)
    int depth;               // 搜索深度
    int score;               // 評估分數
    char flag;                // 標誌（精確值、上界、下界）
    signed char bestX, bestY; // 此局面的最佳走法（座標範圍 1-21，-1 表無記錄）
} HashEntry;

typedef struct {
    int x, y, score;
} Move;

HashEntry transpositionTable[TABLE_SIZE];
unsigned long long zobristTable[BOARD_MAX][BOARD_MAX][2];  // 2 for player 1, player 2
unsigned long long currentZobristKey = 0;

// 初始化 Zobrist 哈希表
void initZobristTable() {
    srand(time(NULL));
    for (int i = 0; i < BOARD_MAX; i++) {
        for (int j = 0; j < BOARD_MAX; j++) {
            for (int k = 0; k < 2; k++) {
                unsigned long long rand1 = (unsigned long long)rand();
                unsigned long long rand2 = (unsigned long long)rand();
                zobristTable[i][j][k] = (rand1 << 32) | rand2;
            }
        }
    }
}

// 初始化 置換表
void initTranspositionTable() {
    memset(transpositionTable, 0, TABLE_SIZE * sizeof(HashEntry));
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
void updateZobristKey(int x, int y, int player) {
    currentZobristKey ^= zobristTable[x][y][player-1];  // 异或操作来更新哈希值
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

// 通用的檢查連綫邏輯
void checkConsecutive(int board[BOARD_MAX][BOARD_MAX], int x, int y, int dx, int dy, int player, int *count, int *maxConnect, int *openEnds, int *gaps, int *op_num) {
    int consecutiveEmpty = 0;
    int max_count = 1;

    for (int direction = -1; direction <= 1; direction += 2) {
        if(max_count== 0)max_count++;
        consecutiveEmpty = 0;
        for (int j = 1; j < 6; j++) {
            int nx = x + j * dx * direction;
            int ny = y + j * dy * direction;

            if (nx >= 1 && nx < (BOARD_MAX) && ny >= 1 && ny < (BOARD_MAX)) {
                if (board[ny][nx] == player) {
                    (*count)++;
                    max_count++;
                    if (consecutiveEmpty != 0) {
                        (*gaps)++;      // 中間有空格
                        (*openEnds)--;
                    }
                    if (max_count > *maxConnect) *maxConnect = max_count;
                    consecutiveEmpty = 0;
                } else if (board[ny][nx] == 0) {
                    consecutiveEmpty++;
                    if (consecutiveEmpty == 1) {
                        max_count = 0;
                        (*openEnds)++;
                    } else if (consecutiveEmpty >= 2) {
                        max_count = *maxConnect;
                        break;// 遇到liang次連續空位停止（可能有11001的情況）
                    }
                } else {
                    if (consecutiveEmpty == 0) (*op_num)++;
                    max_count = *maxConnect;
                    break; // 遇到對手棋子停止計算
                }
            } else {
                break; // 超出邊界停止計算
            }
        }
    }
}

// 檢查該位置落子后的連綫數
void checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int my_line[14]) {
    int dx[] = {1, 1, 0, -1}; // 水準、垂直、主對角線、副對角線的移動方向
    int dy[] = {0, 1, 1, 1};

    // 檢查四個方向
    for (int i = 0; i < 4; i++) {
        int count = 1;  // 包含假設落子的這一個
        int maxConnect = 0;   // 最大連綫數
        int openEnds = 0; // 記錄連線的兩端是否開放
        int op_num = 0; // 對手棋子數量
        int gaps = 0; // 連綫中是否有空格
        int max_count = 1;

        checkConsecutive(board, x, y, dx[i], dy[i], player, &count, &maxConnect, &openEnds, &gaps, &op_num);

        // Debug output
        //printf("Direction %d: Count = %d, Max_c = %d, Open Ends = %d, op num = %d, gap = %d\n", i, count, maxConnect,openEnds, op_num, gaps);
        // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四，9:跳活三, 10:跳活四, 11:跳三, 12:跳四, 13:長連]
        // 判斷是否符合條件
        // 特殊情況優先處理，例如 "X01112"或是"011X10"
        if(gaps == 1){
            if (op_num == 0){
                if(count == 3 && maxConnect == 2 )my_line[9]++;     // 10110
                if(count == 4 && maxConnect == 3)my_line[10]++;     // 10111...
            }
            else if (op_num == 1){
                if(count == 3 && maxConnect >=1)my_line[11]++;      // 21011  | 210101
                if(count == 4 && maxConnect >= 2)my_line[12]++;     // 210111 | 211011
            }
        }else if(gaps == 2){         
            if (op_num == 0){
                if(count == 3 && maxConnect >= 1 )my_line[9]++;     // 10011 | 10101
            }
        }else if(gaps == 0) {
            if (maxConnect > 5) my_line[13]++;     // 長連
            else if (count == 5 && gaps == 0) my_line[5]++;     // 五连
            else if (openEnds == 1 && op_num == 1 && maxConnect == 2)my_line[6]++;  // 眠二
            else if (openEnds == 1 && op_num == 1 && maxConnect == 3)my_line[7]++;  // 眠三
            else if (openEnds == 1 && op_num == 1&& maxConnect == 4)my_line[8]++;  // 冲四
            else if (openEnds > 1 && maxConnect >= 2)my_line[maxConnect]++;  // 活二、活三、活四

        }
    }
}

// 計算棋盤自己和對手的縂連綫數量
void checkNow(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int player, int my_now[14]) {
    for (int x = minX; x <= maxX; x++) {
        for (int y = minY; y <= maxY; y++) {
            if (board[y][x] == player) {
                checkLine(board,x,y,player,my_now);
            }
        }
    }
}

/* 統一的「落子判定」：對「player 在 (x,y) 落子」這個動作做完整分類。
   checkUnValid 與 endGame 共用此函數，避免規則邏輯分散在多處而漂移。
   回傳： 2 = 勝著（五連；白棋長連也算勝）
          1 = 一般合法著法
          0 = 已有棋子
         -3/-4/-6 = 黑棋禁手（三三/四四/長連） */
int judgeMove(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {
    if (board[y][x] != 0) return 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四，9:跳活三, 10:跳活四, 11:跳三, 12:跳四, 13:長連]
    int line[14] = {0};
    checkLine(board, x, y, player, line);
    if (line[5] > 0) return 2;                    // 五連即勝，優先於一切禁手
    if (player == 2 && line[13] > 0) return 2;    // 長連只對白棋算勝
    if (player == 1) {
        if ((line[3] + line[9]) >= 2) return -3;
        if ((line[4] + line[8] + line[10] + line[12]) >= 2) return -4;
        if (line[13] >= 1) return -6;
    }
    return 1;
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
    // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四，9:跳活三, 10:跳活四, 11:跳三, 12:跳四, 13:長連]
    int my_line[14] = {0,0,0,0,0,0,0,0,0,0,0,0,0,0}, op_line[14] = {0,0,0,0,0,0,0,0,0,0,0,0,0}; // 该位置落子后，自己和对手的连线数

    // 更新
    checkLine(board, x, y, player, my_line);
    checkLine(board, x, y, 3-player, op_line);

    // 進攻策略 - 提升關鍵連線得分，特別是活四、沖四、跳四
    attack   += 1000000 * my_line[5] +  // 五連
                100000  * my_line[4] +  // 活四
                20000   * my_line[10]+  // 跳活四
                10000   * my_line[8] +  // 沖四
                7000    * my_line[12]+  // 跳四
                8000    * my_line[3] +  // 活三
                4000    * my_line[9] +  // 跳活三
                500     * my_line[7] +  // 眠三
                700     * my_line[11]+  // 跳三
                50      * my_line[2] +  // 活二
                10      * my_line[6];   // 眠二

    // 四三解禁策略，若當前形成威脅可以加大進攻分數
    if (player == 1 && (my_line[3] > 0 || my_line[7]>0 || my_line[9]>0|| my_line[11]>0) && (my_line[4] > 0 ||my_line[8] > 0 ||my_line[10]>0||my_line[12]>0)) { 
        attack += 500000;  
    }

    // 防守策略 - 防守時同樣拉大連線得分差距，尤其是活四、沖四等關鍵連線
    defence  += 1000000 * op_line[5] +  // 五連
                100000  * op_line[4] +  // 活四
                20000   * op_line[10]+  // 跳活四
                10000   * op_line[8] +  // 沖四
                7000    * op_line[12]+  // 跳四
                8000    * op_line[3] +  // 活三
                4000    * op_line[9] +  // 跳活三
                500     * op_line[7] +  // 眠三
                700     * op_line[11] + // 跳三
                50      * op_line[2] +  // 活二
                10      * op_line[6];   // 眠二

    // 計算（整數運算：避免浮點轉換的精度損耗）
    // 注意：此處是 attack + defence（排序用：攻或防有價值的點都該排前面），
    // 與 evaluate 的 attack - defence 聚合方式不同，是刻意設計，不要「順手統一」。
    total_score += attack + defence * 4 / 5;
    // 增加防守
    if(attack <= defence) total_score += defence / 10;
    return total_score;
}

// 評估函數
int evaluate(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY,int player) {
    // 初始化總分(避免劣勢時全部都是負分無法計算)、自己與對手的分數
    int total_score = 12000, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四，9:跳活三, 10:跳活四, 11:跳三, 12:跳四, 13:長連]
    int my_now[14] = {0,0,0,0,0,0,0,0,0,0,0,0,0,0}, op_now[14] = {0,0,0,0,0,0,0,0,0,0,0,0,0,0}; // 目前自己和对手的连线数 

    // 更新
    checkNow(board, minX, maxX, minY,  maxY, player, my_now);
    checkNow(board, minX, maxX, minY,  maxY, 3 - player, op_now);
    // 優先級：五連>活四>跳活四>冲四=活三>跳四>
    // 進攻策略
    attack   += 9999999 * (my_now[5]/5) +   // 五連
                20000   * (my_now[4]/4) +   // 活四
                15000   * (my_now[10]/4)+   // 跳活四
                10000   * (my_now[8]/4) +   // 冲四
                10000   * (my_now[12]/4)+   // 跳四
                7000    * (my_now[3]/3) +   // 活三
                4000    * (my_now[9]/3) +  // 跳活三
                2000    * (my_now[11]/3) +  // 跳三
                500     * (my_now[7]/3) +   // 眠三
                20      * (my_now[2]/2) +   // 活二
                5       * (my_now[6]/2);    // 眠二

    // 防守策略
    defence  += 9999999 * (op_now[5]/5) +   // 五連
                20000   * (op_now[4]/4) +   // 活四
                15000   * (op_now[10]/4)+   // 跳活四
                10000   * (op_now[8]/4) +   // 冲四
                10000   * (op_now[12]/4)+   // 跳四
                7000    * (op_now[3]/3) +   // 活三
                4000    * (op_now[9]/3) +  // 跳活三
                2000    * (op_now[11]/3) +  // 跳三
                500     * (op_now[7]/3) +   // 眠三
                20      * (op_now[2]/2) +   // 活二
                5       * (op_now[6]/2);    // 眠二
    
    // 若對手已經有活四(有可能是未來)，可是我沒有活四/冲四(非常危險-->幾乎沒救了)
    if (op_now[4] > 0 && (my_now[4] == 0 || my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 4000; 
    }
    // 若對手已經有冲四(有可能是未來)，可是我沒有活四/冲四(危險)
    else if ((op_now[8] > 0) && (my_now[4] == 0 || my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 900;
    }// 若對手已經有活三(有可能是未來)，可是我沒有活三或以上的(危險)
    else if ((op_now[3] > 0) && (my_now[3] == 0)) {
        if (my_now[4] == 0|| my_now[8] == 0){
            if(my_now[5] == 0)
                defence += 1000;
        }    
    }// 若對手已經有眠三(有可能是未來)，可是我沒有眠三以上的
    else if ((op_now[7] > 0) && (my_now[7] == 0||my_now[3] == 0)) {
        if (my_now[4] == 0|| my_now[8] == 0){
            if(my_now[5] == 0)
                defence += 100;
        }    
    }
    if((op_now[3]>0 || op_now[9]>0) && (op_now[4]>0 ||op_now[8]>0 || op_now[10]>0)){
        defence += 4000; 
    }

    // 計算（整數運算：避免浮點轉換的精度損耗）
    // 0.6 / 0.8 係數是「執黑 vs 執白時激進程度不同」的調參選擇（ai 在一局內固定，
    // 單次搜索內為常數），非正確性問題；是否統一留待 Texel tuning 決定。
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
    int my_now[14] = {0,0,0,0,0,0,0,0,0,0,0,0,0}, op_now[14] = {0,0,0,0,0,0,0,0,0,0,0,0,0}; // 目前自己和对手的连线数 
    checkNow(board, minX, maxX, minY,  maxY, currentPlayer, my_now);
    checkNow(board, minX, maxX, minY,  maxY, 3 - currentPlayer, op_now);
    
    // 若有一方玩家赢了
    if((currentPlayer == 2 && my_now[13]>0) ||my_now[5]>0) return currentPlayer;
    else if((3 - currentPlayer == 2 && op_now[13]>0) || op_now[5]>0) return 3-currentPlayer;
    else return 0; // 没有玩家赢
}

// 檢查5*5周圍是否有棋子
bool hasAdjacentPiece(int board[BOARD_MAX][BOARD_MAX], int x, int y) {
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
int endGame(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int minX, int maxX, int minY, int maxY, int currentPlayer){
    int counter =0;
    for (int player = currentPlayer; counter <2; player = 3 - player){
        for (int x = minX; x <= maxX; x++) {
            for (int y = minY; y <= maxY; y++) {
                if (board[y][x] == 0 && hasAdjacentPiece(board, x, y)) {
                    // 實際落子的是 currentPlayer：黑棋禁手點不能下（成五回傳 2，勝著不受影響）
                    if (currentPlayer == 1 && judgeMove(board, x, y, 1) < 1) continue;
                    // ai勝利（直接落子）/ 對手勝利（防守）：單點判定，免落子、免全盤掃描
                    if (judgeMove(board, x, y, player) == 2) {
                        *bestX = x;
                        *bestY = y;
                        return 1;  // 立即返回獲勝移動
                    }
                }
            }
        }
        counter++;
    }
    return 0;
}

// 啓發式函數Heuristic Function：快速評估落點后排序
void sortMoves(int board[BOARD_MAX][BOARD_MAX], Move* moves, int *count, int minX, int maxX, int minY, int maxY, int player) {
    *count = 0;

    // 最高優先級：檢查是否有立即獲勝的棋路
    int bestX = -1, bestY = -1;
    if (endGame(board, &bestX, &bestY, minX, maxX, minY, maxY, player)) {
        moves[(*count)++] = (Move){bestX, bestY, 9999999};
        return;
    }

    // 統計當前AI和玩家的棋形數
    int my_now[14] = {0}, op_now[14] = {0};
    checkNow(board, minX, maxX, minY, maxY, player, my_now);
    checkNow(board, minX, maxX, minY, maxY, 3 - player, op_now);
    
    // 策略：條件+分數+檢查對象
    // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四，9:跳活三, 10:跳活四, 11:跳三, 12:跳四]
    // 優先級：五連>活四>跳活四>冲四=活三>跳四>....
    struct {
        bool condition;
        int score;
        int check_player;
    } strategy_moves[] = {
        // 次優先級：對手已有兩個三連綫/23連綫，且自己沒有活三以上的連綫（防守)
        {
            op_now[2] > 0 && (op_now[3]+op_now[7]+op_now[9]+op_now[11])/3 >= 1,
            99999,
            3 - player  // 檢查對手
        },
        
        // 第三優先級：若自己已經有活三/跳活三必勝了,且對手沒有活三以上的連綫（進攻）
        {
            (my_now[3] > 0 || my_now[9] > 0) && 
            op_now[4] == 0 && op_now[8] == 0 && op_now[10] == 0,
            100000,
            player  // 檢查自己
        },
        
        // 第四優先級：對手已有活三/活跳三，且自己沒有活三以上的連綫（防守）
        {
            (op_now[3] > 0 || op_now[9] > 0) && 
            my_now[3] == 0 && my_now[4] == 0 && my_now[8] == 0 && my_now[10] == 0,
            88888,
            3 - player  // 檢查對手
        },
        // 第五優先級：無腦冲四
        {
            my_now[7]>0 || my_now[11]>0,
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
                // 跳过无效位置
                if (player == 1 && checkUnValid(board, x, y, player) != 1) continue;
                if (board[y][x] != 0 || !hasAdjacentPiece(board, x, y)) continue;

                // 检查位置的棋型
                int line[14] = {0};
                checkLine(board, x, y, strategy_moves[strategy].check_player, line);
                
                bool valid_move = false;
                switch (strategy) {
                    // 防御多重威胁线
                    case 0:
                        valid_move = (line[3] + line[7] + line[9] + line[11]) >= 1 && 
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
                    // 主动创建冲四
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
    if (*count > 4) return;
    // 若無適用策略：通用走法评估
    for (int x = minX; x <= maxX; x++) {
        for (int y = minY; y <= maxY; y++) {
            // 跳过无效位置
            if (player == 1 && checkUnValid(board, x, y, player) != 1) continue;
            if (board[y][x] != 0 || !hasAdjacentPiece(board, x, y)) continue;

            // 快速评估位置价值
            int score = quickEvaluate(board, x, y, minX, maxX, minY, maxY, player);
            if (score != 0) {  // 修改為 != 0
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

    // TT flag 判定必須對照進入節點時的原始邊界，不能用迴圈中被更新過的 alpha/beta
    int alphaOrig = alpha, betaOrig = beta;

    // 在置換表中查找當前棋盤狀態
    HashEntry* entry = lookupHashEntry(currentZobristKey);

    // 先複製 TT 的 bestMove 到區域變數：遞迴子搜索的 always-replace 寫入
    // 可能覆蓋同一個 bucket，迴圈中不能再讀 entry 指標本身
    int ttMoveX = -1, ttMoveY = -1;
    if (entry != NULL && entry->bestX > 0) {
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

    int bestScore = isMaximizing ? INT_MIN : INT_MAX;
    int moveCount = 0;
    Move moves[BOARD_MAX * BOARD_MAX];
    sortMoves(board, moves, &moveCount, minX, maxX, minY, maxY, currentPlayer);
    if (moveCount == 0) return isMaximizing ? INT_MIN : INT_MAX;

    // PV-Move ordering：TT 的 bestMove 不受 depth 限制，在完整候選列表（截斷前）
    // 找到後 memmove 到首位，同時把它從硬截斷中救回來
    if (ttMoveX > 0) {
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

    int count = moveCount > 10 ? 10 : moveCount;
    int bestMx = moves[0].x, bestMy = moves[0].y;
    for (int i = 0; i <count; i++) {
        int x = moves[i].x, y = moves[i].y;
        board[y][x] = currentPlayer;
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
        board[y][x] = 0;
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
void findBestMove(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int ai, int minX, int maxX, int minY, int maxY, int roundCounter) {
    static bool ttInitialized = false;
    if (!ttInitialized) {
        initTranspositionTable();
        ttInitialized = true;
    }
    // 每次搜索前以實際盤面重算，key 為絕對值——不依賴外部呼叫方逐手同步
    currentZobristKey = computeZobristKey(board);
    int moveCount = 0;

    int maxDepth = MAX_DEPTH + (ai == 1 ? 1 : 0);
    if (roundCounter <=8 && maxDepth>6) maxDepth -=2;
    Move moves[BOARD_MAX * BOARD_MAX];
    sortMoves(board, moves, &moveCount, minX, maxX, minY, maxY, ai);
    int count = moveCount > 12 ? 12 : moveCount;
    if (count == 0) return;
    *bestX = moves[0].x;
    *bestY = moves[0].y;

    for (int d = 1; d <= maxDepth; d++) {
        int bestScore = INT_MIN;
        int bestIdx = 0;
        int alpha = INT_MIN;
        for (int i = 0; i < count; i++) {
            int x = moves[i].x, y = moves[i].y;
            board[y][x] = ai;
            updateZobristKey(x,y,ai);
            int score = miniMax(board, d-1, false, 3 - ai, ai, alpha, INT_MAX, minX, maxX, minY, maxY);
            updateZobristKey(x,y,ai);
            board[y][x] = 0;

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

// 計算當前棋局的最小和最大邊界
void getBounds(int board[BOARD_MAX][BOARD_MAX], int *minX, int *maxX, int *minY, int *maxY) {
    *minX = BOARD_MAX;
    *maxX = 1;
    *minY = BOARD_MAX;
    *maxY = 1;
    
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
    
    // 扩大边界
    *minX = (*minX - 2 >= 0) ? *minX - 2 : 1;
    *maxX = (*maxX + 2 < BOARD_MAX) ? *maxX + 2 : BOARD_MAX -1;
    *minY = (*minY - 2 >= 0) ? *minY - 2 : 1;
    *maxY = (*maxY + 2 < BOARD_MAX) ? *maxY + 2 : BOARD_MAX -1;
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
        
        // 第二步
        else if(roundCounter == 3){ 
            x = 10;
            y = 10;
            if(board[y][x] != 0|| board[10][10] != 0) { 
                x = 12; 
                y = 10;
            }else if (board[10][11] != 0 !=0){
                x = 10; 
                y = 12;
            }
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
            x = 10 + rand() % 3;  // 生成介於 10 和 12 之間的隨機整數
            y = 10 + rand() % 3;  // 生成介於 10 和 12 之間的隨機整數
            while(x==y&&x ==11){
                x = 10;
                y = 10;
            }
        }
        else{
            findBestMove(board,&x, &y, ai, minX, maxX, minY, maxY, roundCounter); // 找到最佳位置
        }
    }

    *bestx = x;
    *besty = y;
}
