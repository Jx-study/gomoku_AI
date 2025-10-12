# gomoku_AI

## 專案結構

```
gomoku_AI/
├── src/                    # 當前穩定版本（推薦使用）
│   ├── Gomuko.py          # 主程式（圖形界面人機對戰）
│   ├── ai.c               # C 語言 AI 引擎
│   ├── ai.dll             # 編譯好的動態庫
│   └── competition_chess.py  # 競賽版本
├── project/               # 競賽實作開發歷史
│   └── version 3/         # 最終競賽版本
├── Player_Vs_Ai/          # 人機對戰開發歷史
│   └── version_4/         # 最終人機版本
├── archive/               # 歷史開發版本存檔
│   ├── player_vs_ai/      # 人機對戰舊版本 (v1-v3)
│   └── project/           # 競賽舊版本 (v1-v2)
└── README.md
```

## 快速開始

### 方式一：執行打包好的程式（推薦）
1. 下載 `Player_Vs_Ai/version_4/Gomuko.exe`
2. 雙擊運行即可開始遊戲

### 方式二：從源碼運行
```bash
cd src/

# 編譯 C 語言 AI 引擎
gcc -shared -o ai.dll -fPIC ai.c

# 運行遊戲
python Gomuko.py
```

## 專案介紹

### 競賽版本 (project/)
- **目標**：國立臺北科技大學·計算機程式設計（二）·五子棋專題競賽
- **核心技術**：
  - MiniMax 演算法 + Alpha-Beta 剪枝
  - 符合 RIF 五子棋禁手規則（黑方三三、四四、長連禁手）
  - 適配競賽格式（21×21 棋盤）

### 人機對戰版本 (Player_Vs_Ai/ & src/)
- **功能特色**：
  - 圖形化遊戲界面（使用 graphics.py）
  - 鼠標點擊落子
  - 悔棋、重新開始、查看規則
  - AI 運算時間顯示
  - 回合數提示
- **核心技術**：
  - C 語言 AI 引擎（ctypes 調用）
  - Zobrist 哈希表 + 置換表優化
  - MiniMax 演算法深度搜索（最大深度 7）
  - 禁手規則檢測

## 版本演進歷史

| 版本 | 時間 | 主要更新 |
|------|------|----------|
| **v1.0** | 2024/06 | 基礎評分法 + 禁手規則 |
| **v2.0** | 2024/06 | 新增防守/進攻策略 |
| **v3.0** | 2024/06 | MiniMax + Alpha-Beta 剪枝 |
| **v4.0** | 2025/01 | 圖形界面 + Zobrist 哈希優化 + 打包執行檔 |

## 五子棋規則

### 基本規則
- 21×21 棋盤
- 黑棋先手，雙方輪流落子
- 橫、豎、斜任意方向連成五子獲勝
- 超過五子不算贏

### 開局規則
1. 黑方必須在棋盤中心落第 1 手
2. 白方在中心 3×3 範圍內落第 2 手
3. 黑方在中心 5×5 範圍內落第 3 手

### 禁手規則（僅限黑方）
- 禁止：雙活三
- 禁止：雙活四（包含四三三、三三四等）
- 禁止：長連（超過五子）
- 特例：五連與禁手同時形成，黑方獲勝

詳細規則：https://587.renju.org.tw/teach/teach018.htm

## 技術細節

### AI 演算法
- **搜索策略**：MiniMax 演算法 + Alpha-Beta 剪枝
- **優化技術**：
  - Zobrist 哈希快速狀態編碼
  - 置換表避免重複計算
  - 移動排序提升剪枝效率
- **搜索深度**：7 層（約 5 秒內完成）

### 編譯與打包
```bash
# 編譯 C 動態庫
gcc -shared -o ai.dll -fPIC ai.c

# 打包成可執行檔
pyinstaller --onefile --add-data "200w.gif;." --add-binary "ai.dll:." --hidden-import graphics Gomuko.py
```