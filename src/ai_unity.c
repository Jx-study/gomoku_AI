/* Unity build：把各模組 .c 併成單一 translation unit，供 _bench/ 的文字插樁工具
   （gen_profiled.py、count_budget.py、count_cells.py）與 test_window_index.py 使用。
   正式編譯（gcc -shared ... *.c）不使用這份檔案，會與各模組個別編譯衝突。 */
#include "zobrist.c"
#include "pattern.c"
#include "boardstate.c"
#include "lines.c"
#include "eval.c"
#include "movegen.c"
#include "vcf.c"
#include "search.c"
#include "ai.c"
