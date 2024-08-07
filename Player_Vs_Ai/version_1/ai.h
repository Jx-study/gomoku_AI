#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <limits.h>
#include <string.h>

#define BOARD_MAX 22


int checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY, int player, int num);

// 檢查指定位置落子後是否形成無效連線（禁手）
int checkUnValid(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player);

void checkNow(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int player, int my_now[9], int op_now[9]);

// 檢查周圍是否有自己的棋子
bool hasAdjacentSameColor(int board[BOARD_MAX][BOARD_MAX], int x, int y, int ai);

// 加權函數
int evaluatePosition(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY,int player);

// 加權函數
int evaluate(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY,int player, int m, int n);

// 檢查是否結束
int checkWin(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int currentPlayer);

// AlphaBeta--> MiniMax
int miniMax(int board[BOARD_MAX][BOARD_MAX], int depth, bool isMaximizing, int currentPlayer, int ai, int alpha, int beta, int minX, int maxX, int minY, int maxY, int m,int n);

// 找最佳落子
void findBestMove(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int ai, int minX, int maxX, int minY, int maxY);

void aiRound(int board[BOARD_MAX][BOARD_MAX], int ai, int roundCounter,int* bestx, int* besty, int minX, int maxX, int minY, int maxY);
