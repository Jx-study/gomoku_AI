#ifndef MOVEGEN_H
#define MOVEGEN_H
#include <stdbool.h>

#include "types.h"

// 檢查5*5周圍是否有棋子；索引可信時查表，否則退回掃描
bool hasAdjacentPiece(int board[BOARD_MAX][BOARD_MAX], int x, int y);

// 大到小排序
int Big_Small(const void* a, const void* b);

// 快速處理勝局/敗局；selfCanFive / oppCanFive 由呼叫端從棋型計數導出，見 sortMoves
int endGame(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int minX, int maxX, int minY, int maxY, int currentPlayer, bool selfCanFive, bool oppCanFive);

// 啓發式函數：快速評估落點后排序
void sortMoves(int board[BOARD_MAX][BOARD_MAX], Move* moves, int *count, int minX, int maxX, int minY, int maxY, int player);

#endif
