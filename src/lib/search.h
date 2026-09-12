#ifndef SEARCH_H
#define SEARCH_H
#include "types.h"

// 對外入口：找最佳落子，只在這裡開關 idxValid，保證有效期不跨越回 Python 的邊界
void findBestMove(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int ai, int minX, int maxX, int minY, int maxY, int roundCounter);

#endif
