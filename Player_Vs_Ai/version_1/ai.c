#include "ai.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <limits.h>
#include <string.h>

#define MIDPOINT_X 11
#define MIDPOINT_Y 11
#define BOARD_MAX 22
#define MAX_DEPTH 3 // 定義搜索深度


// 定義位置权重
int positionWeight[BOARD_MAX][BOARD_MAX] = {
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0 },
    { 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 6, 7, 7, 7, 7, 7, 7, 7, 6, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 6, 7, 8, 8, 8, 8, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 6, 7, 8, 8, 8, 8, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 6, 7, 7, 7, 7, 7, 7, 7, 6, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 1, 0, 0 },
    { 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0 },
    { 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};


int checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY, int player, int num) {
    int total = 0;  // 有 num 连线的数量
    int dx[] = {1, 1, 0, -1}; // 水平、垂直、主对角线、副对角线的移动方向
    int dy[] = {0, 1, 1, 1};

    // 检查四个方向
    for (int i = 0; i < 4; i++) {
        int count = 1; // 包含假设落子的这一个
        int openEnds = 0; // 记录连线的两端是否开放

        for (int round = 0; round < 2; round++) {
            for (int j = 1; j < 6; j++) {
                int nx = x + j * dx[i]; // 计算相邻位置的 x 坐标
                int ny = y + j * dy[i]; // 计算相邻位置的 y 坐标
                if (round == 1) { // 反方向
                    nx = x - j * dx[i];
                    ny = y - j * dy[i];
                }
                if (nx >= minX && nx < maxX && ny >= minY && ny < maxY) {
                    if (board[ny][nx] == player) {
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

        // 勝利條件
        if(count == 5 && num == 5)total++;
        // 眠二/眠三/冲四
        else if(openEnds == 1){
            if ((num == 6 && count == 2) ||(num == 7 && count == 3) || (num == 8 && count == 4)) total++;
        }
        // 活二三四五
        else if(openEnds > 1){
            if(count == num) total++;
        }
        
    }
    return total;
}

/* 檢查指定位置落子後是否形成無效連線（禁手）
參數：
- board: 棋盤的狀態，二維整數陣列表示
- x: 要檢查的位置的 x 座標
- y: 要檢查的位置的 y 座標
- player: 當前玩家的標識（1 或 2）
返回值：
- 返回1如果落子後形成有效連線，否則返回禁手代碼（-3：三三禁手，-4：四四禁手，-5：長連禁手）*/
int checkUnValid(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {
    int dx[] = {1, 1, 0, -1}; // 水平、垂直、主對角線、副對角線的移動方向
    int dy[] = {0, 1, 1, 1};
    int threeCount = 0, fourCount = 0; // 禁手規則計數器

    if (board[y][x] != 0) return 0; // 如果指定位置已經有棋子，則無效
    else if(x < 1 || x >= BOARD_MAX || y < 1 || y >= BOARD_MAX) return 0;
    else if(player == 2) return 1; // 白棋
    // 檢查指定位置周圍的相鄰位置
    for (int i = 0; i < 4; i++) {
        int count = 1; // 包含假設落子的這一個

        for (int round = 0; round < 2; round++) {
            for (int j = 1; j < BOARD_MAX; j++) {
                int nx = x + j * dx[i]; // 計算相鄰位置的 x 座標
                int ny = y + j * dy[i]; // 計算相鄰位置的 y 座標
                if (round == 1) { // 反方向
                    nx = x - j * dx[i];
                    ny = y - j * dy[i];
                }
                if (nx < 0 || ny < 0 || nx >= BOARD_MAX || ny >= BOARD_MAX || board[ny][nx] == 3 - player) {
                    break; // 遇到邊界或對手棋子停止計算
                }

                if (board[ny][nx] == player) {
                    count++;
                }
            }
        }

        // 檢查三三禁點
        if (count == 3) {
            threeCount++;
        }
        // 檢查四四禁點
        if (count == 4) {
            fourCount++;
        }
        // 檢查長連禁點
        if (count > 5) {
            return -5; // 長連禁點
        }
    }

    if (threeCount >= 2 || fourCount >= 2) {
        return -3; // 三三禁點 / 四四禁點
    }
    return 1; // 有效
}

void checkNow(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int player, int my_now[9], int op_now[9]) {
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

                    for (round = 0; round < 2; round++) {
                        for (j = 1; j < 6; j++) {
                            int nx = x + j * dx[i]; // 计算相邻位置的 x 坐标
                            int ny = y + j * dy[i]; // 计算相邻位置的 y 坐标
                            if (round == 1) { // 反方向
                                nx = x - j * dx[i];
                                ny = y - j * dy[i];
                            }
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

                    // 更新 my_now 数组 // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四]
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
            } else if (board[y][x] == 3 - player) {
                for (i = 0; i < 4; i++) { // 检查四个方向
                    int count = 1; // 包含当前点
                    int openEnds = 0; // 记录连线的两端是否开放
                    int linePositions[10][2]; // 记录连线的点
                    linePositions[0][0] = x;
                    linePositions[0][1] = y;

                    for (round = 0; round < 2; round++) {
                        for (j = 1; j < 6; j++) {
                            int nx = x + j * dx[i]; // 计算相邻位置的 x 坐标
                            int ny = y + j * dy[i]; // 计算相邻位置的 y 坐标
                            if (round == 1) { // 反方向
                                nx = x - j * dx[i];
                                ny = y - j * dy[i];
                            }
                            if (nx >= minX && nx < maxX && ny >= minY && ny < maxY) {
                                if (board[ny][nx] == 3 - player) {
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

                    // 更新 op_now 数组 // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四]
                    if(count == 5){// 五連
                        op_now[5]++;
                    }else if (openEnds == 1 && count == 2) { // 眠二
                        op_now[6]++;
                    }else if (openEnds == 1 && count == 3) { // 眠三
                        op_now[7]++;
                    }else if (openEnds == 1 && count == 4) { // 冲四
                        op_now[8]++;
                    }else if (openEnds > 1 && count >= 2) {
                        op_now[count]++;
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


// 加權函數（備用版-使用情況為ai完全沒有連綫或是連綫數遠低於玩家）
int evaluatePosition(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY,int player) {
    // 根据进攻和防守策略评估位置的函数
    int total_score = 0, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四]
    int my_line[9] = {0,0,0,0,0,0,0,0}, op_line[9] = {0,0,0,0,0,0,0,0}; // 该位置落子后，自己和对手的连线数
    int my_now[9] = {0,0,0,0,0,0,0,0}, op_now[9] = {0,0,0,0,0,0,0,0}; 
    
    // 更新
    for (int i = 2; i < 9; i++) {
        my_line[i] = checkLine(board, x, y, minX, maxX, minY, maxY, player, i); 
        op_line[i] = checkLine(board, x, y, minX, maxX, minY, maxY, 3 - player, i);
    }
    
    // 目前自己和对手的连线数
    checkNow(board, minX, maxX, minY, maxY, player, my_now, op_now);

    // 進攻策略
    attack   += 500000 * my_line[5] +// 五連
                10000 * my_line[4] + // 活四
                8000 * my_line[8] +  // 冲四
                7000 * my_line[3] +  // 活三
                500 * my_line[7] +   // 眠三
                50 * my_line[2] +    // 活二
                10 * my_line[6];     // 眠二

    // 防守策略
    defence  += 500000 * op_line[5] +// 五連
                10000 * op_line[4] + // 活四
                8000 * op_line[8] +  // 冲四
                7000 * op_line[3] +  // 活三
                500 * op_line[7] +   // 眠三
                50 * op_line[2] +    // 活二
                10 * op_line[6];     // 眠二
    
    // 若對手已經要有活四(現在已經是活三)，可是我沒有活四/冲四（危險）
    if (op_line[4] > 0 && (my_now[4] == 0 || my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 100000; 
    }
    // 若對手已經要有冲四(現在已經是眠三)，可是我沒有活四/冲四(非常危險)
    else if ((op_line[8] > 0) && (my_now[4] == 0 || my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 20000;
    }
    // 計算
    if(player == 1){
        total_score +=  2 * attack +  defence + 10 * positionWeight[y][x] ;
    }
    else total_score +=  attack + 2 *defence + 10 * positionWeight[y][x] ;
    return total_score;
}

// 加權函數
int evaluate(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY,int player, int m, int n) {
    // 根据进攻和防守策略评估位置的函数
    int total_score = 0, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四， 5:五連，6:眠二，7:眠三，8:冲四]
    int my_now[9] = {0,0,0,0,0,0,0,0}, op_now[9] = {0,0,0,0,0,0,0,0}; // 目前自己和对手的连线数 
    int my_line[9] = {0,0,0,0,0,0,0,0}, op_line[9] = {0,0,0,0,0,0,0,0}; // 该位置落子后，自己和对手的连线数

    // 更新
    checkNow(board, minX, maxX, minY,  maxY, player, my_now, op_now);
    for (int i = 2; i < 9; i++) {
        my_line[i] = checkLine(board, m, n, minX, maxX, minY, maxY, player, i); 
        op_line[i] = checkLine(board, m, n, minX, maxX, minY, maxY, 3 - player, i);
    }
    
    // 進攻策略
    attack   += 9999999 * (my_now[5]/5) +// 五連
                10000 * (my_now[4]/4) +  // 活四
                8000 * (my_now[8]/4) +   // 冲四
                7000 * (my_now[3]/3) +   // 活三
                500 * (my_now[7]/3) +    // 眠三
                20 * (my_now[2]/2) +     // 活二
                5 * (my_now[6]/2);      // 眠二
    // 四三解禁(進攻時機)
    if (player == 1 && (my_line[2] > 0 && my_line[7]) && (my_line[4] > 0 ||my_line[8] > 0)) { 
        attack += 10000;
    }
    // 防守策略
    defence  += 9999999 * (op_now[5]/5) +// 五連
                10000 * (op_now[4]/4) +  // 活四
                8000 * (op_now[8]/4) +   // 冲四
                7000 * (op_now[3]/3) +   // 活三
                500 * (op_now[7]/3) +    // 眠三
                20 * (op_now[2]/2) +     // 活二
                5 * (op_now[6]/2);      // 眠二

    // 若對手已經有活四(有可能是未來)，可是我沒有活四/冲四(非常危險-->幾乎沒救了)
    if (op_now[4] > 0 && (my_now[4] == 0 || my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 10000; 
    }
    // 若對手已經有冲四(有可能是未來)，可是我沒有活四/冲四(危險)
    else if ((op_now[8] > 0) && (my_now[4] == 0 || my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 6000;
    }// 若對手已經有活三(有可能是未來)，可是我沒有活三或以上的(危險)
    else if ((op_now[3] > 0) && (my_now[3] == 0)) {
        if (my_now[4] == 0|| my_now[8] == 0){
            if(my_now[5] == 0)
                defence += 4000;
        }    
    }// 若對手已經有眠三(有可能是未來)，可是我沒有眠三以上的(危險)
    else if ((op_now[7] > 0) && (my_now[7] == 0||my_now[3] == 0)) {
        if (my_now[4] == 0|| my_now[8] == 0){
            if(my_now[5] == 0)
                defence += 2000;
        }    
    }
    
    
    // 計算
    total_score +=  attack - 0.2 * 0.6* defence; 
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
    checkNow(board, minX, maxX, minY,  maxY, currentPlayer, my_now, op_now);
    
    // 若有一方玩家赢了
    if(my_now[5]>0) return currentPlayer;
    else if(op_now[5]>0) return 3-currentPlayer; 
    else return 0; // 没有玩家赢
}

// AlphaBeta--> MiniMax
int miniMax(int board[BOARD_MAX][BOARD_MAX], int depth, bool isMaximizing, int currentPlayer,int ai, int alpha, int beta, int minX, int maxX, int minY, int maxY, int m,int n) {
    int result = checkWin(board, minX, maxX, minY, maxY,currentPlayer);
    // 到現在的節點/終端節點（有人要贏了）
    if (depth == 0 || result != 0) { // 注意：当 depth 为 0 时，应该计算当前玩家自己的分數/不是對手的-->Max_depth=1/3/5....
        return evaluate(board,minX,maxX,minY,maxY,ai,m,n);
    }

    if (isMaximizing) {
        int bestScore = 0;
        for (int x = minX; x <= maxX; x++) {
            for (int y = minY; y <= maxY; y++) {
                if (board[y][x] == 0) {
                    if(currentPlayer == 1 && checkUnValid(board, x, y, currentPlayer) != 1) continue;
                    else{
                        board[y][x] = currentPlayer; // 假设当前玩家在此位置落子
                        int score = miniMax(board, depth - 1, false, currentPlayer, ai, alpha, beta, minX, maxX, minY, maxY,m,n);
                        board[y][x] = 0; // 撤销此步
                        if (score > bestScore) bestScore = score;
                        if (bestScore > alpha) alpha = bestScore;
                        if (alpha >= beta) break; // Beta 剪枝
                    }
                }
            }
        }
        return bestScore;
    } else {
        int bestScore = INT_MAX;
        for (int x = minX; x <= maxX; x++) {
            for (int y = minY; y <= maxY; y++) {
                if (board[y][x] == 0) {
                    if(currentPlayer == 2 && checkUnValid(board, x, y, 3 - currentPlayer) != 1) continue;
                    else{
                        board[y][x] = 3 - currentPlayer; // 假设对手在此位置落子
                        int score = miniMax(board, depth - 1, true, currentPlayer, ai, alpha, beta, minX, maxX, minY, maxY,m,n);
                        board[y][x] = 0; // 撤销此步

                        if (score < bestScore) bestScore = score;
                        if (bestScore < beta) beta = bestScore;
                        if (beta <= alpha) break; // Alpha 剪枝
                    }
                }
            }
        }
        return bestScore;
    }
}

// 檢查周圍是否有自己的棋子
bool hasAdjacentSameColor(int board[BOARD_MAX][BOARD_MAX], int x, int y, int ai) {
    return (board[y+1][x-1] == ai ||board[y+1][x+1] == ai ||
            board[y-1][x-1] == ai ||board[y-1][x+1] == ai ||
            board[y-1][x] == ai || board[y+1][x] == ai ||
            board[y][x-1] == ai || board[y][x+1] == ai);
}

// 找最佳落子
void findBestMove(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int ai, int minX, int maxX, int minY, int maxY) {
    int maxScore = INT_MIN; // 初始化最大分數
    int x, y;
    bool found = false; // 判斷是否找到合適位置
    int win = 0;    // 找到勝利之路就停止搜尋
    // 遍歷棋盤上的每個位置
    for (x = minX; x <= maxX; x++) {
        for (y = minY; y <= maxY; y++) {
            if(board[y][x] == 0){
                if (ai == 1 && checkUnValid(board, x, y, ai) != 1) continue;
                else{
                    int depth = MAX_DEPTH;
                    if(ai == 2) depth++;

                    board[y][x] = ai;
                    int score = miniMax(board, depth-1, false, ai, ai, INT_MIN, INT_MAX, minX, maxX, minY, maxY,x,y);
                    board[y][x] = 0;
                    
                    //if(score >= 0&& hasAdjacentSameColor(board, x, y, ai)) score += 500;
                    printf("%d(x:%d,y:%d)\n",score,x,y);
                    // 若當前位置的權重值大於當前最大值，更新最大值及對應座標
                    if (score > maxScore) {
                        maxScore = score;
                        *bestX = x;
                        *bestY = y;
                        found = true;
                    }
                    if(score >9999000){
                        win = 1;
                        break;
                    }
                }
            }
        }
        if(win) break;
    }
    if(!found || maxScore <= 0||*bestX>maxX || *bestX<minX|| *bestY>maxY|| *bestY<minY){
        printf("----------------------------->damn\n");
        for (x = minX; x <= maxX; x++) {
            for (y = minY; y <= maxY; y++) {
                if(board[y][x] == 0){
                    if (ai == 1 && checkUnValid(board, x, y, ai) != 1) continue; // 使用禁手規則檢查
                    else{ 
                        int score = evaluatePosition(board, x, y, minX, maxX, minY, maxY,ai); // 計算放入指定位置后的分數
                        // 若當前位置的權重值大於當前最大值，更新最大值及對應座標
                        if (score > maxScore) {
                            maxScore = score;
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

void aiRound(int board[BOARD_MAX][BOARD_MAX], int ai, int roundCounter,int* bestx, int* besty, int minX, int maxX, int minY, int maxY) {
    int x, y;

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
            x = MIDPOINT_X + ((float)rand() / RAND_MAX) * 2.0f - 1.0f;
            y = MIDPOINT_Y + ((float)rand() / RAND_MAX) * 2.0f - 1.0f;
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
