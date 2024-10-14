#include "ai.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <limits.h>
#include <string.h>
#include <time.h>

#define MIDPOINT_X 11
#define MIDPOINT_Y 11
#define BOARD_MAX 22
#define MAX_DEPTH 5 // 定義搜索深度
#define TABLE_SIZE 10000003  // 选择一个合适的大小

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

// 计算初始哈希值
unsigned long long computeZobristKey(int board[BOARD_MAX][BOARD_MAX]) {
    unsigned long long key = 0;
    for (int i = 0; i < BOARD_MAX; i++) {
        for (int j = 0; j < BOARD_MAX; j++) {
            if (board[i][j] != 0) {
                key ^= zobristTable[i][j][board[i][j]];
            }
        }
    }
    return key;
}


HashEntry* lookupHashEntry(unsigned long long zobristKey) {
    int index = zobristKey % TABLE_SIZE;
    int originalIndex = index;
    while (transpositionTable[index].key != 0) {
        if (transpositionTable[index].key == zobristKey) {
            return &transpositionTable[index];
        }
        index = (index + 1) % TABLE_SIZE;
        if (index == originalIndex) {
            break;
        }
    }
    return NULL;
}

void updateZobristKey(int x, int y, int player) {
    currentZobristKey ^= zobristTable[x][y][player-1];  // 异或操作来更新哈希值
}

void storeHashEntry(unsigned long long zobristKey, int depth, int score, char flag) {
    int index = zobristKey % TABLE_SIZE;
    int originalIndex = index;
    while (transpositionTable[index].key != 0 && transpositionTable[index].key != zobristKey) {
        index = (index + 1) % TABLE_SIZE;
        if (index == originalIndex) {
            printf("Warning: Transposition table is full\n");
            return;
        }
    }
    transpositionTable[index].key = zobristKey;
    transpositionTable[index].depth = depth;
    transpositionTable[index].score = score;
    transpositionTable[index].flag = flag;
}

int checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int num) {
    int total = 0;  // 有 num 連線的數量
    int dx[] = {1, 1, 0, -1}; // 水準、垂直、主對角線、副對角線的移動方向
    int dy[] = {0, 1, 1, 1};

    // 檢查四個方向
    for (int i = 0; i < 4; i++) {
        int count = 1;  // 包含假設落子的這一個
        int maxConnect = 0;   // 最大連綫數
        int openEnds = 0; // 記錄連線的兩端是否開放
        int op_num = 0; // 對手棋子數量
        int middle_space = 0; // 連綫中是否有空格
        int max_count = 1;

        for (int direction = -1; direction <= 1; direction += 2) { // 正反兩個方向
            int consecutiveEmpty = 0;   // 連續空位數
            if(max_count== 0)max_count++;

            for (int j = 1; j < 6; j++) {
                int nx = x + j * dx[i] * direction;
                int ny = y + j * dy[i] * direction;

                if (nx >= 1 && nx < (BOARD_MAX-1) && ny >= 1 && ny < (BOARD_MAX-1)) {
                    if (board[ny][nx] == player) {
                        count++;
                        max_count++;
                        if(consecutiveEmpty != 0)middle_space++;     // 中間有空格
                        if(max_count > maxConnect) maxConnect = max_count;
                        consecutiveEmpty = 0; // 重置連續空位數
                    } else if (board[ny][nx] == 0) {
                        consecutiveEmpty++;
                        if (consecutiveEmpty == 1) max_count = 0;
                        else if (consecutiveEmpty >= 2){
                            max_count = maxConnect;
                            openEnds++;
                            break; // 遇到兩次連續空位停止
                        } 
                    } else {
                        if(consecutiveEmpty == 0)op_num++;
                        break; // 遇到對手棋子停止計算
                    }
                } else {
                    break; // 超出邊界停止計算
                }
            }
            
        }

        // Debug output
        //printf("Direction %d: Count = %d, Max_c = %d, Open Ends = %d, op num = %d\n", i, count, maxConnect,openEnds, op_num);

        // 判斷是否符合條件
        // 特殊情況優先處理，例如 "X01112"
        if(middle_space >= 1){
            if(num == 9 && count == 4 && maxConnect == 3 && op_num == 1)total++;
        }
        
        // 長連
        if(maxConnect > 5 && num == 10) total++;
        // 五連
        else if (maxConnect == 5 && num == 5) total++;
        // 眠二/眠三/沖四
        else if (openEnds == 1 && op_num == 1 && ((num == 6 && maxConnect == 2) || (num == 7 && maxConnect == 3) || (num == 8 && maxConnect == 4))) total++;
        // 活二、活三、活四、活五
        else if (openEnds == 2 && maxConnect == num && op_num == 0) total++;
        
    }
    return total;
}

/* 檢查指定位置是否有棋子/落子後是否形成禁手
返回值：
- 返回1如果落子後形成有效連線，否則返回禁手代碼（0：已有棋子，-3：三三禁手，-4：四四禁手，-5：長連禁手）*/
int checkUnValid(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {
    // 已有棋子
    if(board[y][x] != 0) return 0;
    if(player == 1){
        // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四，9:跳四]
        int my_line[11] = {0,0,0,0,0,0,0,0,0,0,0};  // 该位置落子后，自己的连线数

        // 更新
        for (int i = 2; i < 11; i++) {
            my_line[i] = checkLine(board, x, y,  player, i); 
        }
        if(my_line[3] >= 2 || (my_line[4]+my_line[8])>= 2) return -3;
        else if(my_line[10] >= 1) return -6;
    }
    return 1; // 有效
}

void checkNow(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int player, int my_now[9]) {
    int visited[BOARD_MAX][BOARD_MAX];
    memset(visited, 0, sizeof(visited)); // 初始化为0，表示未访问过

    int dx[] = {1, 1, 0, -1}; // 水平、垂直、主对角线、副对角线的移动方向
    int dy[] = {0, 1, 1, 1};

    int x, y, i, j, round, k;
    for (x = minX; x <= maxX; x++) {
        for (y = minY; y <= maxY; y++) {
            if (board[y][x] == player) {
                for (i = 0; i < 4; i++) { // 檢查四個方向
                    int count = 1; // 包含當前的點
                    int openEnds = 0; // 連綫兩端是否打開
                    int linePositions[10][2]; // 記錄連綫的點
                    linePositions[0][0] = x;
                    linePositions[0][1] = y;

                    for (int direction = -1; direction <= 1; direction += 2) { // 正反兩個方向
                        for (int j = 1; j < 6; j++) {
                            int nx = x + j * dx[i] * direction;
                            int ny = y + j * dy[i] * direction;
                            if (nx >= minX && nx < maxX && ny >= minY && ny < maxY) {
                                if (board[ny][nx] == player) {
                                    linePositions[count][0] = nx;
                                    linePositions[count][1] = ny;
                                    count++;
                                } else if (board[ny][nx] == 0) {
                                    openEnds++;
                                    break; // 遇到空位停止计算
                                } else {
                                    break; // 遇到对手棋子停止计算
                                }
                            } else {
                                break; // 超出边界停止计算
                            }
                        }
                    }

                    // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四，9:跳四, 10: 長連]
                    if(count == 5){// 五連
                        my_now[5]++;
                    }else if (openEnds == 1 && count == 2) { // 眠二
                        my_now[6]++;
                    }else if (openEnds == 1 && count == 3) { // 眠三
                        my_now[7]++;
                    }else if (openEnds == 1 && count == 4) { // 冲四
                        my_now[8]++;
                    }else if (openEnds > 1 && count >= 2) {
                        my_now[count]++;
                    }

                    // 更新 visited 数组
                    for (k = 0; k < count; k++) {
                        visited[linePositions[k][1]][linePositions[k][0]] = count;
                    }
                }
            }
        }
    }
}

// 快速評估函數
int quickEvaluate(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY,int player) {
    // 根据进攻和防守策略评估位置的函数
    int total_score = 0, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四，9:跳四, 10:長連]
    int my_line[11] = {0,0,0,0,0,0,0,0,0,0,0}, op_line[11] = {0,0,0,0,0,0,0,0,0,0,0}; // 该位置落子后，自己和对手的连线数

    // 更新
    for (int i = 2; i < 11; i++) {
        my_line[i] = checkLine(board, x, y,  player, i); 
        op_line[i] = checkLine(board, x, y,  3 - player, i);
    }

     // 進攻策略
    attack   += 5000000 * my_line[5] +// 五連
                100000 * my_line[4] + // 活四
                8000 * my_line[8] +  // 冲四
                4000 * my_line[9] +  // 跳四
                5000 * my_line[3] +  // 活三
                500 * my_line[7] +   // 眠三
                50 * my_line[2] +    // 活二
                10 * my_line[6];     // 眠二

    // 四三解禁(進攻時機)
    if (player == 1 && (my_line[3] > 0 && my_line[7]) && (my_line[4] > 0 ||my_line[8] > 0)) { 
        attack += 200000;
    }

    // 防守策略
    defence  += 5000000 * op_line[5] +// 五連
                100000 * op_line[4] + // 活四
                8000 * op_line[8] +  // 冲四
                4000 * op_line[9] +  // 跳四
                5000 * op_line[3] +  // 活三
                500 * op_line[7] +   // 眠三
                50 * op_line[2] +    // 活二
                10 * op_line[6];     // 眠二

    // 計算
    if(player == 1) total_score +=  1.5 * attack + defence;
    else total_score += attack + 1.5 * defence;

    // 增加防守
    if(attack <= defence) total_score += 0.2*defence;
    return total_score;
}

// 評估函數
int evaluate(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY,int player) {
    // 初始化總分(避免劣勢時全部都是負分無法計算)、自己與對手的分數
    int total_score = 10000, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四]
    int my_now[9] = {0,0,0,0,0,0,0,0,0}, op_now[9] = {0,0,0,0,0,0,0,0,0}; // 目前自己和对手的连线数 

    // 更新
    checkNow(board, minX, maxX, minY,  maxY, player, my_now);
    checkNow(board, minX, maxX, minY,  maxY, 3 - player, op_now);
    
    // 進攻策略
    attack   += 9999999 * (my_now[5]/5) +// 五連
                20000 * (my_now[4]/4) +  // 活四
                14000 * (my_now[8]/4) +   // 冲四
                7000 * (my_now[3]/3) +   // 活三
                500 * (my_now[7]/3) +    // 眠三
                20 * (my_now[2]/2) +     // 活二
                5 * (my_now[6]/2);      // 眠二

    // 防守策略
    defence  += 9999999 * (op_now[5]/5) +// 五連
                20000 * (op_now[4]/4) +  // 活四
                14000 * (op_now[8]/4) +   // 冲四
                7000 * (op_now[3]/3) +   // 活三
                500 * (op_now[7]/3) +    // 眠三
                20 * (op_now[2]/2) +     // 活二
                5 * (op_now[6]/2);      // 眠二
    if(player == 1){
        // 若對手已經有活四(有可能是未來)，可是我沒有活四/冲四(非常危險-->幾乎沒救了)
        if (op_now[4] > 0 && (my_now[4] == 0 || my_now[8] == 0)) {
            if (my_now[5] == 0)
                defence += 4000; 
        }
        // 若對手已經有冲四(有可能是未來)，可是我沒有活四/冲四(危險)
        else if ((op_now[8] > 0) && (my_now[4] == 0 || my_now[8] == 0)) {
            if (my_now[5] == 0)
                defence += 1500;
        }// 若對手已經有活三(有可能是未來)，可是我沒有活三或以上的(危險)
        else if ((op_now[3] > 0) && (my_now[3] == 0)) {
            if (my_now[4] == 0|| my_now[8] == 0){
                if(my_now[5] == 0)
                    defence += 1000;
            }    
        }// 若對手已經有眠三(有可能是未來)，可是我沒有眠三以上的(危險)
        else if ((op_now[7] > 0) && (my_now[7] == 0||my_now[3] == 0)) {
            if (my_now[4] == 0|| my_now[8] == 0){
                if(my_now[5] == 0)
                    defence += 500;
            }    
        }
    }
    // 計算
    if(player == 1)total_score +=  attack - 0.2 * 0.7* defence;
    else total_score +=  attack - 0.8 * defence;
    // 強化防守策略，根據當前的局勢
    // 當對手有優勢時，提高防守的影響力
    if (defence > attack) {
        total_score -= defence * 0.1;
    }

    return total_score;
}

// 檢查是否結束
int checkWin(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int currentPlayer) {
    int my_now[9] = {0,0,0,0,0,0,0,0}, op_now[9] = {0,0,0,0,0,0,0,0}; // 目前自己和对手的连线数 
    checkNow(board, minX, maxX, minY,  maxY, currentPlayer, my_now);
    checkNow(board, minX, maxX, minY,  maxY, 3 - currentPlayer, op_now);
    
    // 若有一方玩家赢了
    if(my_now[5]>0) return currentPlayer;
    else if(op_now[5]>0) return 3-currentPlayer; 
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



Move* sortMoves(int board[BOARD_MAX][BOARD_MAX], int *count, int minX, int maxX, int minY, int maxY,int player) {
    Move* moves = (Move*)malloc(BOARD_MAX * BOARD_MAX * sizeof(Move));  // 動態分配內存
    if (moves == NULL) {
        printf("Memory allocation failed\n");
        return NULL;
    }

    // 首先檢查是否有立即獲勝的機會
    for (int x = minX; x <= maxX; x++) {
        for (int y = minY; y <= maxY; y++) {
            if (player == 1 && checkUnValid(board, x, y, player) != 1) continue;
            else if (board[y][x] == 0 && hasAdjacentPiece(board, x, y)) {
                int score = quickEvaluate(board, x, y, minX, maxX, minY, maxY, player);
                if (score == 0) continue;

                // 保存有效的棋步及其得分
                moves[*count].x = x;
                moves[*count].y = y;
                moves[*count].score = score;
                (*count)++;
            }
        }
    }

    // 根據玩家選擇排序
    qsort(moves, *count, sizeof(Move), Big_Small);

    return moves;  // 返回指向動態分配的 moves 數組
}

// Alpha Beta --> minimax
int miniMax(int board[BOARD_MAX][BOARD_MAX], int depth, bool isMaximizing, int currentPlayer, int ai, int alpha, int beta, int minX, int maxX, int minY, int maxY) {
    // 檢查是否達到搜索深度或遊戲結束
    int result = checkWin(board, minX, maxX, minY, maxY, currentPlayer);
    if (depth == 0 || result != 0) {
        // 到達葉子節點，返回評估分數
        return evaluate(board, minX, maxX, minY, maxY, ai);
    }

    // 在置換表中查找當前棋盤狀態
    HashEntry* entry = lookupHashEntry(currentZobristKey);

    // 如果在置換表中找到了當前狀態，並且存儲的深度大於等於當前深度
    if (entry != NULL && entry->depth <= depth) {
        if (entry->flag == 'E') {
            printf("bingo\n");
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
    Move* moves = sortMoves(board, &moveCount, minX, maxX, minY, maxY, currentPlayer); 
    
    int count = moveCount > 20 ? 20 : moveCount;
    for (int i = 0; i <count; i++) {
        int x = moves[i].x, y = moves[i].y;
        board[y][x] = currentPlayer;
        updateZobristKey(x, y, currentPlayer);// 更新雜湊值
        // 遞迴呼叫 miniMax，切換到對手回合
        if (isMaximizing) {
            int score = miniMax(board, depth - 1, false, 3 - currentPlayer, ai, alpha, beta, minX, maxX, minY, maxY);
            bestScore = (score > bestScore) ? score : bestScore;
            // 更新 Alpha 值
            alpha = (bestScore > alpha) ? bestScore : alpha;
        }else {
            int score = miniMax(board, depth - 1, true, 3 - currentPlayer, ai, alpha, beta, minX, maxX, minY, maxY);
            bestScore = (score < bestScore) ? score : bestScore;
            // 更新 Beta 值
            beta = (bestScore < beta) ? bestScore : beta;
        }
        // 撤銷移動
        board[y][x] = 0;
        updateZobristKey(x, y, currentPlayer); // 還原雜湊值
        
        // Alpha-Beta 剪枝
        if (alpha >= beta) break;
    }

     // 釋放動態分配的內存
    free(moves);

    // 在返回分數之前，將結果存儲到置換表中
    char flag;
    if (bestScore <= alpha) {
        flag = 'U';  // 上界
    } else if (bestScore >= beta) {
        flag = 'L';  // 下界
    } else {
        flag = 'E';  // 精確值
    }
    storeHashEntry(currentZobristKey, depth, bestScore, flag);

    return bestScore;
}

// 快速處理勝局/敗局
int endGame(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int *count, int minX, int maxX, int minY, int maxY, int ai){
    int counter =0;
    for (int player = ai; counter <2; player = 3 - player){
        for (int x = minX; x <= maxX; x++) {
            for (int y = minY; y <= maxY; y++) {
                if (board[y][x] == 0 && hasAdjacentPiece(board, x, y)) {
                    // ai勝利（直接落子）/ 玩家勝利（防守）
                    board[y][x] = player;
                    if (checkWin(board, minX, maxX, minY, maxY, player) == player) {
                        *bestX = x;
                        *bestY = y;
                        board[y][x] = 0;
                        return 1;  // 立即返回獲勝移動
                    }
                    board[y][x] = 0;
                    counter++;
                }
            }
        }
    }
    return 0;    
}

// 找最佳落子
void findBestMove(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int ai, int minX, int maxX, int minY, int maxY) {
    initTranspositionTable();
    int bestScore = INT_MIN; // 初始化最大分數
    int x,y;
    bool found = false; // 判斷是否找到合適位置
    int moveCount = 0;
    
    int check = endGame(board, bestX, bestY, &moveCount, minX, maxX, minY, maxY, ai);
    if(check == 0){
        int depth = MAX_DEPTH;
        if(ai == 1) {
            depth++;
        }
        Move* moves = sortMoves(board, &moveCount, minX, maxX, minY, maxY, ai); 
        if (moves == NULL) return;  // 確保 moves 不為 NULL

        int count = moveCount > 15 ? 15 : moveCount;
        
        for (int i = 0; i <count; i++) {
            
            x = moves[i].x, y = moves[i].y;
            board[y][x] = ai;
            updateZobristKey(x,y,ai);
            int score = miniMax(board, depth-1, false, 3 - ai, ai, INT_MIN, INT_MAX, minX, maxX, minY, maxY);
            updateZobristKey(x,y,ai);
            board[y][x] = 0;
            
            printf("%d(x:%d,y:%d)--->%d\n",score,x,y,moves[i].score);
            if (score > bestScore) {
                bestScore = score;
                *bestX = x;
                *bestY = y;
                found = true;
            }
            //if (bestScore > 10000000) break;
        }

        // 釋放動態分配的內存
        free(moves);

        if(!found || bestScore <= 0){
            printf("----------------------------->damn\n");
            for (x = minX; x <= maxX; x++) {
                for (y = minY; y <= maxY; y++) {
                    if(board[y][x] == 0){
                        if (ai == 1 && checkUnValid(board, x, y, ai) != 1) continue; // 使用禁手規則檢查
                        else{ 
                            int score = quickEvaluate(board, x, y, minX, maxX, minY, maxY,ai); // 計算放入指定位置后的分數
                            // 若當前位置的權重值大於當前最大值，更新最大值及對應座標
                            if (score > bestScore) {
                                bestScore = score;
                                *bestX = x;
                                *bestY = y;
                                found = true;
                            }
                        }
                    }
                }
            }
        }
    }
}

// 计算当前棋局的最小和最大边界
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
            //浦月開局
            x = 12;
            y = 12;
            if(board[y][x] != 0|| board[10][10] != 0) { 
                x = 12; // 不懂什麽開局
                y = 10;
            }else if (board[10][11] != 0 !=0){
                x = 10; // 不懂什麽開局
                y = 12;
            }
        }
        // 第三手開始
        else{
            findBestMove(board,&x, &y, ai, minX, maxX, minY, maxY); // 找到最佳位置
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
            findBestMove(board,&x, &y, ai, minX, maxX, minY, maxY); // 找到最佳位置
        }
    }

    *bestx = x;
    *besty = y;
}
