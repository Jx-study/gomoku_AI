/* 效能量測版：不複製 ai.c，改用生成的中間檔 + wrapper 記錄呼叫次數與耗時。
   ai.c 一改就跟著改，不會像舊版那樣悄悄漂成化石。

   編譯（在 src/_bench/ 執行）：
       python gen_profiled.py && gcc -shared -o ai_profiled.dll -fPIC ai_profiled.c

   注意不能用 `#define evaluate prof_real_evaluate` 這種改名法：那會把 ai.c 內部的
   呼叫一起改掉，內部呼叫直接跳過 wrapper，所有計數器恆為 0。生成器只改定義處。
   計數器與 getXxxSeconds() 皆為非 static，供 ctypes 讀取。 */

#include <stdint.h>

/* 生成檔：函數定義已改名為 prof_real_*，呼叫處維持原名，連結時綁到下方 wrapper。
   ai.c 內部彼此的呼叫也會經過 wrapper —— 這正是要的：checkLine 的耗時包含
   它被 evaluate/sortMoves/endGame 各處呼叫的部分。 */
#include "ai_profiled_core.generated.c"

/* 高解析度計時：clock() 在 Windows 上只有 ~15ms 粒度，量 checkLine 這種
   單次數十奈秒的函數會整片讀成 0。改用 QueryPerformanceCounter。 */
#if defined(_WIN32)
  #include <windows.h>
  static double profFreq = 0.0;
  static inline double profNow(void) {
      LARGE_INTEGER t;
      if (profFreq == 0.0) {
          LARGE_INTEGER f;
          QueryPerformanceFrequency(&f);
          profFreq = (double)f.QuadPart;
      }
      QueryPerformanceCounter(&t);
      return (double)t.QuadPart / profFreq;
  }
#else
  #include <time.h>
  static inline double profNow(void) {
      struct timespec ts;
      clock_gettime(CLOCK_MONOTONIC, &ts);
      return ts.tv_sec + ts.tv_nsec * 1e-9;
  }
#endif

long long g_evaluateCalls      = 0;
long long g_quickEvaluateCalls = 0;
long long g_miniMaxCalls       = 0;
long long g_sortMovesCalls     = 0;
long long g_endGameCalls       = 0;
long long g_checkWinCalls      = 0;
long long g_checkLineCalls     = 0;
long long g_judgeMoveCalls     = 0;

static double g_evaluateSec      = 0.0;
static double g_quickEvaluateSec = 0.0;
static double g_sortMovesSec     = 0.0;
static double g_endGameSec       = 0.0;
static double g_checkWinSec      = 0.0;
static double g_checkLineSec     = 0.0;
static double g_judgeMoveSec     = 0.0;

void resetProfileCounters(void) {
    g_evaluateCalls = g_quickEvaluateCalls = g_miniMaxCalls = 0;
    g_sortMovesCalls = g_endGameCalls = g_checkWinCalls = 0;
    g_checkLineCalls = g_judgeMoveCalls = 0;
    g_evaluateSec = g_quickEvaluateSec = g_sortMovesSec = 0.0;
    g_endGameSec = g_checkWinSec = g_checkLineSec = g_judgeMoveSec = 0.0;
}

double getEvaluateSeconds(void)      { return g_evaluateSec; }
double getQuickEvaluateSeconds(void) { return g_quickEvaluateSec; }
double getSortMovesSeconds(void)     { return g_sortMovesSec; }
double getEndGameSeconds(void)       { return g_endGameSec; }
double getCheckWinSeconds(void)      { return g_checkWinSec; }
double getCheckLineSeconds(void)     { return g_checkLineSec; }
double getJudgeMoveSeconds(void)     { return g_judgeMoveSec; }

/* 巢狀耗時的處理：checkLine 由 evaluate/sortMoves/endGame 等呼叫，
   各自的秒數會重疊，不能直接相加當「總計 100%」。每個數字都是
   「該函數的 inclusive 總耗時佔單手 aiRound 的比例」，分開讀。
   miniMax 是遞迴的，只計次不計時（inclusive 時間等於整次搜索，無資訊）。

   呼叫次數極高的函數（checkLine、judgeMove 一手可達數十萬次）的佔比含 profNow()
   自身的開銷，會偏高。排名可信，絕對數字不可信——不要拿它推估優化能省多少。 */

int evaluate(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int player) {
    g_evaluateCalls++;
    double t0 = profNow();
    int r = prof_real_evaluate(board, minX, maxX, minY, maxY, player);
    g_evaluateSec += profNow() - t0;
    return r;
}

int quickEvaluate(int board[BOARD_MAX][BOARD_MAX], int x, int y, int minX, int maxX, int minY, int maxY, int player) {
    g_quickEvaluateCalls++;
    double t0 = profNow();
    int r = prof_real_quickEvaluate(board, x, y, minX, maxX, minY, maxY, player);
    g_quickEvaluateSec += profNow() - t0;
    return r;
}

int miniMax(int board[BOARD_MAX][BOARD_MAX], int depth, bool isMaximizing, int currentPlayer, int ai, int alpha, int beta, int minX, int maxX, int minY, int maxY) {
    g_miniMaxCalls++;
    return prof_real_miniMax(board, depth, isMaximizing, currentPlayer, ai, alpha, beta, minX, maxX, minY, maxY);
}

void sortMoves(int board[BOARD_MAX][BOARD_MAX], Move* moves, int *count, int minX, int maxX, int minY, int maxY, int player) {
    g_sortMovesCalls++;
    double t0 = profNow();
    prof_real_sortMoves(board, moves, count, minX, maxX, minY, maxY, player);
    g_sortMovesSec += profNow() - t0;
}

int endGame(int board[BOARD_MAX][BOARD_MAX], int *bestX, int *bestY, int minX, int maxX, int minY, int maxY, int currentPlayer) {
    g_endGameCalls++;
    double t0 = profNow();
    int r = prof_real_endGame(board, bestX, bestY, minX, maxX, minY, maxY, currentPlayer);
    g_endGameSec += profNow() - t0;
    return r;
}

int checkWin(int board[BOARD_MAX][BOARD_MAX], int minX, int maxX, int minY, int maxY, int currentPlayer) {
    g_checkWinCalls++;
    double t0 = profNow();
    int r = prof_real_checkWin(board, minX, maxX, minY, maxY, currentPlayer);
    g_checkWinSec += profNow() - t0;
    return r;
}

void checkLine(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player, int my_line[14]) {
    g_checkLineCalls++;
    double t0 = profNow();
    prof_real_checkLine(board, x, y, player, my_line);
    g_checkLineSec += profNow() - t0;
}

int judgeMove(int board[BOARD_MAX][BOARD_MAX], int x, int y, int player) {
    g_judgeMoveCalls++;
    double t0 = profNow();
    int r = prof_real_judgeMove(board, x, y, player);
    g_judgeMoveSec += profNow() - t0;
    return r;
}
