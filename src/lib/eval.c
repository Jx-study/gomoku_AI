#include "eval.h"
#include "lines.h"

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
    // 初始化總分(避免劣勢時全部都是負分無法計算)、自己與對手的分數
    int total_score = 12000, attack = 0, defence = 0;
    // [0:0, 1:0, 2:活二，3:活三，4:活四，5:五連，6:眠二，7:純衝四眠三，8:衝四，
    //  9:跳活三，10:跳活四，11:偏活跳三，12:跳四，13:偏活三，14:純衝四跳三，15:長連]
    int my_now[16] = {0}, op_now[16] = {0}; // 目前自己和对手的连线数

    // 更新
    checkNow(board, minX, maxX, minY,  maxY, player, my_now);
    checkNow(board, minX, maxX, minY,  maxY, 3 - player, op_now);
    // 優先級：五連>活四>跳活四>衝四=活三>跳四>
    // 進攻策略：偏活三/偏活跳三（13/11）與跳活三同級，純衝四眠三/跳三（7/14）
    // 延伸方向已鎖死，權重明顯低於 11/13（見 quickEvaluate 上方註解）
    attack   += 9999999 * (my_now[5]/5) +   // 五連
                20000   * (my_now[4]/4) +   // 活四
                15000   * (my_now[10]/4)+   // 跳活四
                10000   * (my_now[8]/4) +   // 衝四
                10000   * (my_now[12]/4)+   // 跳四
                7000    * (my_now[3]/3) +   // 活三
                4000    * (my_now[9]/3) +   // 跳活三
                4000    * (my_now[13]/3)+   // 偏活三
                4000    * (my_now[11]/3)+   // 偏活跳三
                500     * (my_now[7]/3) +   // 純衝四眠三
                700     * (my_now[14]/3)+   // 純衝四跳三
                20      * (my_now[2]/2) +   // 活二
                5       * (my_now[6]/2);    // 眠二

    // 防守策略
    defence  += 9999999 * (op_now[5]/5) +   // 五連
                20000   * (op_now[4]/4) +   // 活四
                15000   * (op_now[10]/4)+   // 跳活四
                10000   * (op_now[8]/4) +   // 衝四
                10000   * (op_now[12]/4)+   // 跳四
                7000    * (op_now[3]/3) +   // 活三
                4000    * (op_now[9]/3) +   // 跳活三
                4000    * (op_now[13]/3)+   // 偏活三
                4000    * (op_now[11]/3)+   // 偏活跳三
                500     * (op_now[7]/3) +   // 純衝四眠三
                700     * (op_now[14]/3)+   // 純衝四跳三
                20      * (op_now[2]/2) +   // 活二
                5       * (op_now[6]/2);    // 眠二

    // 若對手已經有活四(有可能是未來)，可是我沒有活四/衝四(非常危險-->幾乎沒救了)
    if (op_now[4] > 0 && (my_now[4] == 0 && my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 4000;
    }
    // 若對手已經有衝四(有可能是未來)，可是我沒有活四/衝四(危險)
    else if ((op_now[8] > 0) && (my_now[4] == 0 && my_now[8] == 0)) {
        if (my_now[5] == 0)
            defence += 900;
    }// 若對手已經有活三/偏活三/偏活跳三(能成活四)，可是我沒有活三或以上的(危險)
    else if ((op_now[3] > 0 || op_now[9] > 0 || op_now[13] > 0 || op_now[11] > 0) &&
             (my_now[3] == 0 && my_now[9] == 0 && my_now[13] == 0 && my_now[11] == 0)) {
        if (my_now[4] == 0 && my_now[8] == 0){
            if(my_now[5] == 0)
                defence += 1000;
        }
    }// 若對手已經有純衝四眠三/跳三(只鎖死方向，延伸方向已定型)，可是我沒有同級以上的
    else if ((op_now[7] > 0 || op_now[14] > 0) &&
             (my_now[7] == 0 && my_now[14] == 0 &&
              my_now[3] == 0 && my_now[9] == 0 && my_now[13] == 0 && my_now[11] == 0)) {
        if (my_now[4] == 0 && my_now[8] == 0){
            if(my_now[5] == 0)
                defence += 100;
        }
    }
    if((op_now[3]>0 || op_now[9]>0 || op_now[13]>0 || op_now[11]>0) &&
       (op_now[4]>0 || op_now[8]>0 || op_now[10]>0)){
        defence += 4000;
    }

    // 計算（整數運算：避免浮點轉換的精度損耗）
    // 3/5 與 4/5：執黑與執白的激進程度不同，非正確性問題
    // ai 在一局內固定，單次搜索中為常數
    if(player == 1)total_score +=  attack - defence * 3 / 5;
    else total_score +=  attack - defence * 4 / 5;
    // 強化防守策略，根據當前的局勢
    // 當對手有優勢時，提高防守的影響力
    if (defence > attack) {
        total_score -= defence / 10;
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
