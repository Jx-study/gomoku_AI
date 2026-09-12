#ifndef PATTERN_H
#define PATTERN_H
#include "types.h"

// 棋型查表：一條方向線的 11 格窗口（中心 + 左右各 5）換成棋型 index
// 中心恆為 SELF 不入索引，周邊 10 格三態，出界的牆併入 OPP
#define CELL_EMPTY 0
#define CELL_SELF  1
#define CELL_OPP   2   // 含出界的牆
#define PATTERN_TABLE_SIZE 59049   // 3^10

extern unsigned char patternTable[PATTERN_TABLE_SIZE];
extern const int POW3[10];

// 把窗口編成 patternTable 索引：off 從 -5 到 +5 跳過中心，依序 idx = idx * 3 + cell
// 編解碼順序必須一致，對應的解碼在 initPatternTable
int encodeWindow(int board[BOARD_MAX][BOARD_MAX], int x, int y, int dx, int dy, int player);

// [0:0, 1:0, 2:活二，3:活三，4:活四，5:五連，6:眠二，7:純衝四眠三，8:衝四，9:跳活三，10:跳活四，11:偏活跳三，12:跳四，13:偏活三，14:純衝四跳三，15:長連]
/* 回傳中心（cells[5] 為 SELF）在此 11 格窗口形成的最強棋型 index，無棋型回傳 0 */
int classifyWindow(int cells[11]);

// 全枚舉所有窗口編碼，逐一分類填進 patternTable
void initPatternTable(void);

// 首次呼叫時建表：checkUnValid 這條路徑不經過 aiRound，不能靠它初始化
void ensurePatternTable(void);

#endif
