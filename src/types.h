#ifndef TYPES_H
#define TYPES_H
#include <stdint.h>

// 棋盤大小的唯一定義處。Python 端透過 getBoardMax() 讀取此值
#define BOARD_MAX 15
#define MIDPOINT_X (BOARD_MAX / 2)
#define MIDPOINT_Y (BOARD_MAX / 2)
#define MAX_DEPTH 7 // 定義搜索深度
// 強制著法門檻：分數不低於此值的候選不受 top-N 截斷
// 代理指標而非精確判定：攻防相加，普通點也可能湊到門檻以上
// 改權重時要一併重算此值
#define FORCING_SCORE 8000
#define TABLE_SIZE (1 << 20)   // 1,048,576 個 entry，約 24MB
#define TABLE_MASK (TABLE_SIZE - 1)

typedef struct {
    unsigned long long key;  // Zobrist 哈希鍵(結點局面的 64 位校驗值)
    int depth;               // 搜索深度
    int score;               // 評估分數
    char flag;                // 標誌（精確值、上界、下界）
    signed char bestX, bestY; // 此局面的最佳走法（座標範圍 0 ~ BOARD_MAX-1，-1 表無記錄）
} HashEntry;

typedef struct {
    int x, y, score;
} Move;

#endif
