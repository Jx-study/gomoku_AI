#include <stdio.h>
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

void initChess(Chess* chess);

int setXY(Chess* chess, int x, int y, int player);

void writeChessBoard(Chess* chess, int player, int* x, int* y);