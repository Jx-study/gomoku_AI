#include "eval.h"
#include "lines.h"
#include <string.h>

// 評估參數：依 ai 顏色分兩組，每組 EVAL_PARAMS_PER_COLOR 個 int
// [0,15) 攻擊權重、[15,30) 防守權重（依棋型 index 2..14，index 0/1/15 不使用但保留位置對齊）
// [30,35) 五個條件防守加成，[35] 防守係數（/100），[36] 劣勢加罰係數（/100）
// 預設值來自 Texel tuning（tied 結構，attack/defence 共用、黑白共用，僅防守係數分色）
#define EVAL_PARAMS_PER_COLOR 37
#define EVAL_W_ATK 0
#define EVAL_W_DEF 15
#define EVAL_BONUS 30
#define EVAL_DEF_NUM 35
// 劣勢加罰係數：效果已被放大後的 EVAL_DEF_NUM 吸收，故保留欄位但值為 0
#define EVAL_EXTRA_NUM 36
static int evalParams[2][EVAL_PARAMS_PER_COLOR] = {
    {0, 0, 808, 5624, 29212, 9999999, 0, 1603, 10637, 4000, 15000, 4564, 13281, 4639, 1761,
     0, 0, 808, 5624, 29212, 9999999, 0, 1603, 10637, 4000, 15000, 4564, 13281, 4639, 1761,
     102517, 1193, 1482, 1014, 13273, 60, 0},
    {0, 0, 808, 5624, 29212, 9999999, 0, 1603, 10637, 4000, 15000, 4564, 13281, 4639, 1761,
     0, 0, 808, 5624, 29212, 9999999, 0, 1603, 10637, 4000, 15000, 4564, 13281, 4639, 1761,
     102517, 1193, 1482, 1014, 13273, 152, 0},
};

// 棋型計數的除數：同一條棋型被其中每顆子各算一次，除以子數還原成條數
static const int PATTERN_LEN[16] = {1, 1, 2, 3, 4, 5, 2, 3, 4, 3, 4, 3, 4, 3, 3, 1};

// 調參實驗用：一次寫入/讀出兩組共 2 * EVAL_PARAMS_PER_COLOR 個參數
// n 需與陣列總長度相符，否則不動作並回傳 0，避免呼叫端緩衝區算錯而溢位讀寫
int setEvalParams(const int *p, int n) {
    if (n != 2 * EVAL_PARAMS_PER_COLOR) return 0;
    memcpy(evalParams, p, sizeof(evalParams));
    return 1;
}

int getEvalParams(int *p, int n) {
    if (n != 2 * EVAL_PARAMS_PER_COLOR) return 0;
    memcpy(p, evalParams, sizeof(evalParams));
    return 1;
}

int getEvalParamsPerColor(void) { return EVAL_PARAMS_PER_COLOR; }

// 快速評估函數
int quickEvaluate(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY,int player) {
    // 根据进攻和防守策略评估位置的函数
    int total_score = 0, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四，5:五連，6:眠二，7:純衝四眠三，8:衝四，9:跳活三，10:跳活四，11:偏活跳三，12:跳四，13:偏活三，14:純衝四跳三，15:長連]
    int my_line[16] = {0}, op_line[16] = {0}; // 该位置落子后，自己和对手的连线数

    // 成五直接給最高分，與 judgeMove 共用同一套判定
    // 勝著不必再經棋型分類，也避免這類點被 score != 0 濾掉
    if (judgeMove(board, x, y, player) == 2) return 2000000;

    // 更新
    checkLine(board, x, y, player, my_line);
    checkLine(board, x, y, 3-player, op_line);

    // 進攻策略 - 提升關鍵連線得分，特別是活四、衝四、跳四
    // 偏活三/偏活跳三（13/11）緊急程度與跳活三同級：缺口一旦填上就是
    // 兩端全開的活四，不是弱棋型；純衝四眠三/跳三（7/14）延伸方向已鎖死，
    // 只是預先可防守的單點威脅，權重明顯低於 11/13
    attack   += 1000000 * my_line[5] +  // 五連
                100000  * my_line[4] +  // 活四
                20000   * my_line[10]+  // 跳活四
                10000   * my_line[8] +  // 衝四
                7000    * my_line[12]+  // 跳四
                8000    * my_line[3] +  // 活三
                4000    * my_line[9] +  // 跳活三
                4000    * my_line[13]+  // 偏活三
                4000    * my_line[11]+  // 偏活跳三
                700     * my_line[14]+  // 純衝四跳三
                500     * my_line[7] +  // 純衝四眠三
                50      * my_line[2] +  // 活二
                10      * my_line[6];   // 眠二

    // 四三解禁策略，若當前形成威脅可以加大進攻分數
    if (player == 1 && (my_line[3] > 0 || my_line[7]>0 || my_line[9]>0 || my_line[11]>0 || my_line[13]>0 || my_line[14]>0) && (my_line[4] > 0 ||my_line[8] > 0 ||my_line[10]>0||my_line[12]>0)) {
        attack += 500000;
    }

    // 防守策略 - 防守時同樣拉大連線得分差距，尤其是活四、衝四等關鍵連線
    defence  += 1000000 * op_line[5] +  // 五連
                100000  * op_line[4] +  // 活四
                20000   * op_line[10]+  // 跳活四
                10000   * op_line[8] +  // 衝四
                7000    * op_line[12]+  // 跳四
                8000    * op_line[3] +  // 活三
                4000    * op_line[9] +  // 跳活三
                4000    * op_line[13]+  // 偏活三
                4000    * op_line[11]+  // 偏活跳三
                700     * op_line[14]+  // 純衝四跳三
                500     * op_line[7] +  // 純衝四眠三
                50      * op_line[2] +  // 活二
                10      * op_line[6];   // 眠二

    // 計算（整數運算：避免浮點轉換的精度損耗）
    // 排序用 attack + defence：攻或防有價值的點都該排前面
    // 與 evaluate 的 attack - defence 不同，是刻意的
    total_score += attack + defence * 4 / 5;
    // 增加防守
    if(attack <= defence) total_score += defence / 10;
    return total_score;
}

// 評估函數
int evaluate(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY,int player) {
    const int *ep = evalParams[player - 1];
    // 初始化總分(避免劣勢時全部都是負分無法計算)、自己與對手的分數
    int total_score = 12000, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四，5:五連，6:眠二，7:純衝四眠三，8:衝四，
    //  9:跳活三，10:跳活四，11:偏活跳三，12:跳四，13:偏活三，14:純衝四跳三，15:長連]
    int my_now[16] = {0}, op_now[16] = {0}; // 目前自己和对手的连线数

    // 更新
    checkNow(board, minX, maxX, minY,  maxY, player, my_now);
    checkNow(board, minX, maxX, minY,  maxY, 3 - player, op_now);

    // 長連（15）不計分，迴圈只到 14
    for (int k = 2; k <= 14; k++) {
        attack  += ep[EVAL_W_ATK + k] * (my_now[k] / PATTERN_LEN[k]);
        defence += ep[EVAL_W_DEF + k] * (op_now[k] / PATTERN_LEN[k]);
    }

    // 若對手已經有活四(有可能是未來)，可是我沒有活四/衝四(非常危險-->幾乎沒救了)
    if (op_now[4] > 0 && (my_now[4] == 0 && my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += ep[EVAL_BONUS + 0];
    }
    // 若對手已經有衝四(有可能是未來)，可是我沒有活四/衝四(危險)
    else if ((op_now[8] > 0) && (my_now[4] == 0 && my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += ep[EVAL_BONUS + 1];
    }// 若對手已經有活三/偏活三/偏活跳三(能成活四)，可是我沒有活三或以上的(危險)
    else if ((op_now[3] > 0 || op_now[9] > 0 || op_now[13] > 0 || op_now[11] > 0) &&
             (my_now[3] == 0 && my_now[9] == 0 && my_now[13] == 0 && my_now[11] == 0)) {
        if (my_now[4] == 0 && my_now[8] == 0){
            if(my_now[5] == 0)
                defence += ep[EVAL_BONUS + 2];
        }
    }// 若對手已經有純衝四眠三/跳三(只鎖死方向，延伸方向已定型)，可是我沒有同級以上的
    else if ((op_now[7] > 0 || op_now[14] > 0) &&
             (my_now[7] == 0 && my_now[14] == 0 &&
              my_now[3] == 0 && my_now[9] == 0 && my_now[13] == 0 && my_now[11] == 0)) {
        if (my_now[4] == 0 && my_now[8] == 0){
            if(my_now[5] == 0)
                defence += ep[EVAL_BONUS + 3];
        }
    }
    if((op_now[3]>0 || op_now[9]>0 || op_now[13]>0 || op_now[11]>0) &&
       (op_now[4]>0 || op_now[8]>0 || op_now[10]>0)){
        defence += ep[EVAL_BONUS + 4];
    }

    // 計算（整數運算：避免浮點轉換的精度損耗）
    // 防守係數依執黑執白不同，ai 在一局內固定，單次搜索中為常數
    // 乘法先轉 long long：調參後的權重放大時 defence * 係數可能超出 int
    total_score += attack - (int)((long long)defence * ep[EVAL_DEF_NUM] / 100);
    // 強化防守策略，根據當前的局勢
    // 當對手有優勢時，提高防守的影響力
    if (defence > attack) {
        total_score -= (int)((long long)defence * ep[EVAL_EXTRA_NUM] / 100);
    }
    return total_score;
}

// 檢查是否有人勝利
int checkWin(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int currentPlayer) {
    int my_now[16] = {0}, op_now[16] = {0}; // 目前自己和对手的连线数
    checkNow(board, minX, maxX, minY,  maxY, currentPlayer, my_now);
    checkNow(board, minX, maxX, minY,  maxY, 3 - currentPlayer, op_now);

    // 若有一方玩家赢了
    if((currentPlayer == 2 && my_now[15]>0) ||my_now[5]>0) return currentPlayer;
    else if((3 - currentPlayer == 2 && op_now[15]>0) || op_now[5]>0) return 3-currentPlayer;
    else return 0; // 没有玩家赢
}
