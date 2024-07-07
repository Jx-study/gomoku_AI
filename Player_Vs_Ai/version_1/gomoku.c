#include <stdio.h>
#include <stdlib.h> // 亂數相關函數
#include <time.h>   // 時間相關函數 
#include <unistd.h> // usleep()
#include <stdbool.h>
#include <limits.h>
#include "ai.h"


#define MAX 22
#define MIDPOINT_X 11
#define MIDPOINT_Y 11

// 全域變數（回合數）
int roundCounter = 1;

//----------------------------------------------------------
// Function
void initBoard(int board[MAX][MAX]) __attribute__((visibility("default")));
void print(int board[22][22]) __attribute__((visibility("default")));
int play(int board[MAX][MAX], int player, int ai) __attribute__((visibility("default")));


void initBoard(int board[MAX][MAX]){
    for(int i=0;i<MAX;i++){
        for(int j=0;j<MAX;j++){
            board[i][j]=0;
        }
    }
}

// 计算当前棋局的最小和最大边界
void getBounds(int board[MAX][MAX], int *minX, int *maxX, int *minY, int *maxY) {
    *minX = MAX;
    *maxX = 1;
    *minY = MAX;
    *maxY = 1;
    
    for (int x = 0; x < MAX; x++) {
        for (int y = 0; y < MAX; y++) {
            if (board[y][x] != 0) {
                if (x < *minX) *minX = x;
                if (x > *maxX) *maxX = x;
                if (y < *minY) *minY = y;
                if (y > *maxY) *maxY = y;
            }
        }
    }
    
    // 扩大边界
    *minX = (*minX - 2 >= 0) ? *minX - 2 : 1;
    *maxX = (*maxX + 2 < MAX) ? *maxX + 2 : MAX -1;
    *minY = (*minY - 2 >= 0) ? *minY - 2 : 1;
    *maxY = (*maxY + 2 < MAX) ? *maxY + 2 : MAX -1;
}

void print(int board[22][22]) {
    for (int i=0; i<22; i++) {
        for (int j=0; j<22; j++) {
            if(i == 0 && j<10)  printf("%d  ", j);
            else if(i == 0 && j>9)  printf("%d ", j);
            else if(j == 0 && i<10) printf("%d  ", i);
            else if(j == 0 && i>9) printf("%d ", i);
            else printf("%d  ",board[i][j]);
        }
        printf("\n");
    }
}

int play(int board[MAX][MAX], int player, int ai){
    int round = 1;  // 1=黑棋回合，2=白棋回合
    int winner = 0, chance = 3;

    while(1){
        char text[50];
        int x=0,y=0;    // 坐標
        int minX, maxX, minY, maxY;
        getBounds(board, &minX, &maxX, &minY, &maxY);

        printf("round = %d\n",round);
        if(roundCounter == 1 && round==player) print(board);
        // 提示詞
        if(roundCounter == 1 && round ==player){
            printf("Please place at (11,11)\n");
        }else if(roundCounter == 2 && round == player){
            printf("Please place in the 3*3 area at the center\n");
        }

        // 選擇落子位置
        if(round == player){    // 是玩家回合
            printf("Enter coordinate-->x y:");
            scanf("%d %d",&x,&y);
        }else{                  // 是AI回合
            aiRound(board,round, roundCounter,&x,&y, minX, maxX, minY, maxY);
            printf("AI place at (%d,%d)\n", x,y);
        }

        // 檢查落子是否合法
        if(checkUnValid(board, x, y, round) == 1){
            board[y][x] = round;
            print(board);
        }
        else{   //不合法
            chance--;
            printf("Unvalid coordinate! You have %d more chances\n", chance);
            if(chance == 0){
                winner = 3 - round;
                break;
            }
            continue;
        }

        // 檢查是否(勝利)
        winner = checkWin(board,minX, maxX, minY, maxY, round);
        if(winner == 0){
            // 轉換回合
            round = 3 - round;
            roundCounter++;
            // 預留時間
            sleep(2); // 2s
        }
        else break;
    }
    return winner;
}

int main(){
    int board[MAX][MAX];
    initBoard(board);
    
    char filename[10];
    printf("Start gomoku game ^_^\n");

    // 玩家選擇黑白方
    int player = 0, ai = 2;
    printf("Please enter whether want to play Black(1) or White(2):");
    scanf("%d", &player);
    if(player == 2) ai = 1;

    int result = play(board,player,ai);
    if(result == player){
        printf("Winner is Player!!!");
    }
    else{
        printf("Winner is AI, try better next time :)");
    }

    return 0;
}
