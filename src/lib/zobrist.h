#ifndef ZOBRIST_H
#define ZOBRIST_H
#include "types.h"

extern HashEntry transpositionTable[TABLE_SIZE];
extern unsigned long long zobristTable[BOARD_MAX][BOARD_MAX][2];
extern unsigned long long currentZobristKey;

// 對外入口：Python 端遊戲啟動與重新開始各呼叫一次，不是 C 內部呼叫
void initZobristTable(void);
void initTranspositionTable(void);

unsigned long long computeZobristKey(int board[BOARD_MAX][BOARD_MAX]);
HashEntry* lookupHashEntry(unsigned long long zobristKey);
void updateZobristKey(int x, int y, int player);
void storeHashEntry(unsigned long long zobristKey, int depth, int score, char flag, int bestX, int bestY);

#endif
