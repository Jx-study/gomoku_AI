#include <string.h>

#include "zobrist.h"

HashEntry transpositionTable[TABLE_SIZE];
unsigned long long zobristTable[BOARD_MAX][BOARD_MAX][2];  // 2 for player 1, player 2
unsigned long long currentZobristKey = 0;

// 64 位元亂數產生器（splitmix64）
// 不能用 rand()：Windows/mingw 的 RAND_MAX 僅 15 位元，key 熵不足會造成 TT 假命中
static unsigned long long splitmix64(unsigned long long *state) {
    unsigned long long z = (*state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

// 初始化 Zobrist 哈希表
// 種子固定：key 分布不需隨機，固定反而讓 A/B 對照可重現
void initZobristTable() {
    unsigned long long state = 0x243F6A8885A308D3ULL;
    for (int i = 0; i < BOARD_MAX; i++) {
        for (int j = 0; j < BOARD_MAX; j++) {
            for (int k = 0; k < 2; k++) {
                zobristTable[i][j][k] = splitmix64(&state);
            }
        }
    }
}

// 初始化 置換表
void initTranspositionTable() {
    memset(transpositionTable, 0, TABLE_SIZE * sizeof(HashEntry));
    // 0 是合法座標，未寫入的 entry 必須用 -1 標記無記錄
    for (int i = 0; i < TABLE_SIZE; i++) {
        transpositionTable[i].bestX = -1;
        transpositionTable[i].bestY = -1;
    }
}

// 計算初始哈希值
unsigned long long computeZobristKey(int board[BOARD_MAX][BOARD_MAX]) {
    unsigned long long key = 0;
    for (int i = 0; i < BOARD_MAX; i++) {
        for (int j = 0; j < BOARD_MAX; j++) {
            if (board[i][j] != 0) {
                key ^= zobristTable[i][j][board[i][j] - 1];
            }
        }
    }
    return key;
}

// 尋找現在哈希值是否有在置換表中
HashEntry* lookupHashEntry(unsigned long long zobristKey) {
    int index = zobristKey & TABLE_MASK;
    if (transpositionTable[index].key == zobristKey) {
        return &transpositionTable[index];
    }
    return NULL;
}

// 更新哈希值
// 索引順序必須與 computeZobristKey 的 board[y][x] 一致
// 否則整盤重算與逐手 XOR 對不起來，同一局面在不同手會算出不同的 key
void updateZobristKey(int x, int y, int player) {
    currentZobristKey ^= zobristTable[y][x][player-1];  // 异或操作来更新哈希值
}

// 存取哈希值進哈希表
void storeHashEntry(unsigned long long zobristKey, int depth, int score, char flag, int bestX, int bestY) {
    int index = zobristKey & TABLE_MASK;
    // Always-replace: 直接覆蓋，不管舊 entry 是什麼
    transpositionTable[index].key   = zobristKey;
    transpositionTable[index].depth = depth;
    transpositionTable[index].score = score;
    transpositionTable[index].flag  = flag;
    transpositionTable[index].bestX = (signed char)bestX;
    transpositionTable[index].bestY = (signed char)bestY;
}
