/**#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

typedef struct {
    int x;
    int y;
    int player;
} Coordinate;

typedef struct {
    Coordinate* cord;
    int size;
} Chess;

void initChess(Chess* chess) {
    chess->cord = NULL;
    chess->size = 0;
}

int setXY(Chess* chess, int x, int y, int player) {
    if (x == 0 || y == 0) {
        return 0;
    }

    for (int i = 0; i < chess->size; i++) {
        if (chess->cord[i].x == x && chess->cord[i].y == y) {
            return 0;
        }
    }

    chess->cord = (Coordinate*)realloc(chess->cord, (chess->size + 1) * sizeof(Coordinate));
    chess->cord[chess->size].x = x;
    chess->cord[chess->size].y = y;
    chess->cord[chess->size].player = player;
    chess->size++;

    return 1;
}

void writeChessBoard(Chess* chess, int player, int* x, int* y) {
    while (1) {
        *x = rand() % 20 + 1;
        *y = rand() % 20 + 1;
        if (setXY(chess, *x, *y, player) == 1) {
            return;
        }
    }
}
**/

#include "chessData.h"

void printChess(Chess* chess) {
    for (int i = 0; i < chess->size; i++) {
        printf("(%d, %d, %d) ", chess->cord[i].x, chess->cord[i].y, chess->cord[i].player);
    }
    printf("size=%d\n", chess->size);
}

void writeBackServer(const char* fileName, int x, int y) {
    FILE* f = fopen(fileName, "w");
    fprintf(f, "R\n");
    fprintf(f, "%d %d", x, y);
    fclose(f);
}

int go(const char* fileName, Chess* chess, char playerRole) {
    FILE* f = fopen(fileName, "r");
    char buffer[256];

    int player = 1;
    int co_player = 0;
    if (playerRole == 'A') {
        player = 0;
        co_player = 1;
    }

    if (fgets(buffer, sizeof(buffer), f) != NULL && buffer[0] == 'W') {
        int x, y;
        fscanf(f, "%d %d", &x, &y);

        if (player == 1 && x == 0 && y == 0) {
            fclose(f);
            return 0;
        }

        printf("%c:2: %d %d\n", playerRole, x, y);
        setXY(chess, x, y, co_player);

        int new_x, new_y;
        writeChessBoard(chess, player, &new_x, &new_y);
        printf("1: %d %d\n", new_x, new_y);
        writeBackServer(fileName, new_x, new_y);

        fclose(f);
        return 1;
    }

    fclose(f);
    return 0;
}

int main() {
    srand(time(NULL));
    Chess chess;
    initChess(&chess);

    char fileName[256];
    printf("fileName: ");
    scanf("%s", fileName);

    char playerRole;
    printf("Player A/B: ");
    scanf(" %c", &playerRole);
    fflush(stdin); // 清理輸入緩衝區
    int count = 0;
    while (1) {
        if (go(fileName, &chess, playerRole) == 1) {
            count++;
            printf("%d\n", count);
            printChess(&chess);
            if (count > 50) {
                break;
            }
        }
        sleep(3); // 3 seconds
    }

    return 0;
}
