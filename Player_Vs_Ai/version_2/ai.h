#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <limits.h>
#include <string.h>

#define BOARD_MAX 22
#define TABLE_SIZE 10000003

typedef struct {
    unsigned long long key;  // Zobrist 哈希鍵(結點局面的 64 位校驗值)
    int depth;               // 搜索深度
    int score;               // 評估分數
    char flag;                // 標誌（精確值、上界、下界）  
} HashEntry;

extern HashEntry transpositionTable[TABLE_SIZE];

void initZobristTable();

void initTranspositionTable();

void updateZobristKey(int x, int y, int player);

unsigned long long computeZobristKey(int board[BOARD_MAX][BOARD_MAX]);

HashEntry* lookupHashEntry(unsigned long long zobristKey);

void storeHashEntry(unsigned long long zobristKey, int depth, int score, char flag);

int checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY, int player, int num);

// 檢查指定位置落子後是否形成無效連線（禁手）
int checkUnValid(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player);

void checkNow(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int player, int my_now[9], int op_now[9]);

// 加權函數
int evaluatePosition(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY,int player);

// 加權函數
int evaluate(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY,int player, int m, int n);

// 檢查是否結束
int checkWin(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int currentPlayer);

// AlphaBeta--> MiniMax
int miniMax(int board[BOARD_MAX][BOARD_MAX], int depth, bool isMaximizing, int currentPlayer, int ai, int alpha, int beta, int minX, int maxX, int minY, int maxY, int m,int n);

// 檢查周圍是否有棋子
bool hasAdjacentPiece(int board[BOARD_MAX][BOARD_MAX], int x, int y);
// 找最佳落子
void findBestMove(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int ai, int minX, int maxX, int minY, int maxY);

void aiRound(int board[BOARD_MAX][BOARD_MAX], int ai, int roundCounter,int* bestx, int* besty, int minX, int maxX, int minY, int maxY);
