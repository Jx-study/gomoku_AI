#include "chessData.h"

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
