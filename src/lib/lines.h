#ifndef LINES_H
#define LINES_H
#include <stdbool.h>

#include "types.h"

// 檢查該位置落子后的連綫數
void checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int my_line[16]);

// 計算棋盤自己和對手的縂連綫數量
void checkNow(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int player, int my_now[16]);

// 落子後通過該點的最長連續棋子數；hasFive 回報是否有任一方向恰好五連
int maxRunAt(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int *hasFive);

/* 落子判定：checkUnValid 與 endGame 共用，避免規則邏輯分散而漂移。
   回傳： 2 = 勝著（五連；白棋長連也算勝）
          1 = 一般合法著法
          0 = 已有棋子
         -3/-4/-6 = 黑棋禁手（三三/四四/長連） */
int judgeMove(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player);

// 直接查 patternTable 四個方向，只認 5、15 兩個代碼；endGame、listFivePoints 共用
bool winsAt(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player);

/* 檢查指定位置是否有棋子/落子後是否形成禁手
返回值：返回1如果落子後形成有效連線，否則返回禁手代碼（0：已有棋子，-3：三三禁手，-4：四四禁手，-5：長連禁手）*/
int checkUnValid(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player);

#endif
