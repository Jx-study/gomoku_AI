#include <stdlib.h>
#include <time.h>

#include "types.h"
#include "zobrist.h"
#include "pattern.h"
#include "boardstate.h"
#include "lines.h"
#include "eval.h"
#include "movegen.h"
#include "vcf.h"
#include "search.h"

// 回傳這顆 DLL 實際編譯時使用的棋盤大小
// Python 端據此建立 ctypes 陣列與版面尺寸，確保與二進位檔一致
int getBoardMax(void) {
    return BOARD_MAX;
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
