// 檢查該位置落子后的連綫數
int checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int num) {
    int total = 0;  // 有 num 連線的數量
    int dx[] = {1, 1, 0, -1}; // 水準、垂直、主對角線、副對角線的移動方向
    int dy[] = {0, 1, 1, 1};

    // 檢查四個方向
    for (int i = 0; i < 4; i++) {
        int count = 1;  // 包含假設落子的這一個
        int maxConnect = 0;   // 最大連綫數
        int openEnds = 0; // 記錄連線的兩端是否開放
        int op_num = 0; // 對手棋子數量
        int gaps = 0; // 連綫中是否有空格
        int max_count = 1;

        for (int direction = -1; direction <= 1; direction += 2) { // 正反兩個方向
            int consecutiveEmpty = 0;   // 連續空位數
            if(max_count== 0)max_count++;

            for (int j = 1; j < 6; j++) {
                int nx = x + j * dx[i] * direction;
                int ny = y + j * dy[i] * direction;

                if (nx >= 1 && nx < (BOARD_MAX-1) && ny >= 1 && ny < (BOARD_MAX-1)) {
                    if (board[ny][nx] == player) {
                        count++;
                        max_count++;
                        if(consecutiveEmpty != 0){
                            gaps++;     // 中間有空格
                            openEnds--;
                        }
                        if(max_count > maxConnect) maxConnect = max_count;
                        consecutiveEmpty = 0; // 重置連續空位數
                    } else if (board[ny][nx] == 0) {
                        consecutiveEmpty++;
                        if (consecutiveEmpty == 1) {
                            max_count = 0;
                            openEnds++;
                        }
                        else if (consecutiveEmpty >= 2){
                            max_count = maxConnect;
                            break; // 遇到兩次連續空位停止
                        } 
                    } else {
                        if(consecutiveEmpty == 0)op_num++;
                        max_count = maxConnect;
                        break; // 遇到對手棋子停止計算
                    }
                } else {
                    break; // 超出邊界停止計算
                }
            }
            
        }

        // Debug output
        //printf("Direction %d: Count = %d, Max_c = %d, Open Ends = %d, op num = %d\n", i, count, maxConnect,openEnds, op_num);

        // 判斷是否符合條件
        // 特殊情況優先處理，例如 "X01112"或是"011X10"
        if(gaps == 1){
            if(num == 9 && count == 3 && maxConnect == 2 )total++;
            if(num == 10 && count == 4 && maxConnect == 3)total++;
        }
        else if(gaps == 0){
            // 長連
            if(maxConnect > 5 && num == 11) total++;
            // 五連
            else if (maxConnect == 5 && num == 5) total++;
            // 眠二/眠三/沖四
            else if (openEnds == 1 && op_num == 1 && ((num == 6 && maxConnect == 2) || (num == 7 && maxConnect == 3) || (num == 8 && maxConnect == 4))) total++;
            // 活二、活三、活四、活五
            else if (openEnds == 2 && maxConnect == count && maxConnect == num && op_num == 0) total++;
        }
    }
    return total;
}