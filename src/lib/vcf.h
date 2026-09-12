#ifndef VCF_H
#define VCF_H
#include "types.h"

// 根節點入口：重置節點預算後開跑。attacker 是否有連續衝四強制勝，是則寫入首手 *wx,*wy
int vcfFindWin(int board[BOARD_MAX][BOARD_MAX], int attacker,
               int minX, int maxX, int minY, int maxY, int *wx, int *wy);

long long getVcfNodes(void);

#endif
