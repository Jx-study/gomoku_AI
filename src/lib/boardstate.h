#ifndef BOARDSTATE_H
#define BOARDSTATE_H
#include <stdbool.h>

#include "types.h"

// 增量索引：[視角][y][x][方向] -> 該格為中心、該方向的 encodeWindow 結果
// 視角 p 對應玩家 p+1；牆在 rebuild 時就編進初值，增量更新不碰牆
extern int windowIdx[2][BOARD_MAX][BOARD_MAX][4];

// windowIdx 與 neighborCount 是否可信；只在 findBestMove/vcfProbe 的搜索期間為真
// checkUnValid 這條路徑不經過搜索入口，兩張表可能是舊局面甚至全零，靠這個旗標退回原地掃描
extern bool idxValid;

// stoneList[p]：玩家 p+1 的所有棋子座標，以 y * BOARD_MAX + x 存；stoneCount[p] 是長度
extern short stoneList[2][BOARD_MAX * BOARD_MAX];
extern int stoneCount[2];

#define ADJ_RANGE 2                                        // hasAdjacentPiece 的掃描半徑，與表共用避免漂移
// neighborCount[y][x]：以 (x,y) 為中心的 5×5 內、不含中心的棋子數（不分黑白），上限 24 不會溢位
extern unsigned char neighborCount[BOARD_MAX][BOARD_MAX];

// 全盤重算三張增量表，掛在搜索入口，不依賴逐手同步
void rebuildWindowIndex(int board[BOARD_MAX][BOARD_MAX]);
void rebuildStoneList(int board[BOARD_MAX][BOARD_MAX]);
void rebuildNeighborCount(int board[BOARD_MAX][BOARD_MAX]);

// 落子/撤銷單一入口，同步修正三張增量表
void placeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player);
void removeStone(int board[BOARD_MAX][BOARD_MAX], int x, int y);

#endif
