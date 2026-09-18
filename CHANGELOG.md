# Changelog

## 1.0.0 (2026-09-18)


### Features

* add automated Windows release build on version tags ([d80723c](https://github.com/Jx-study/gomoku_AI/commit/d80723ccb41fb2572afc01a43067361d9b2f3f3b))
* **ai:** split three-level patterns by straight-four reachability ([5e1c852](https://github.com/Jx-study/gomoku_AI/commit/5e1c852f2a8c3c1848fcaccb5d92cca715c670c3))
* **bench:** add bench.py as the single entry point ([c167fc9](https://github.com/Jx-study/gomoku_AI/commit/c167fc9c15cb0fa68f681bb9ab00a4f177b76ce7))
* **bench:** add deterministic cell-access counter ([e702e10](https://github.com/Jx-study/gomoku_AI/commit/e702e100553131639a028df6e4ee4ed539e76900))
* **bench:** count stoneList walks in checkNow ([e3e58fd](https://github.com/Jx-study/gomoku_AI/commit/e3e58fd8eddce6ab6061af50e4e73fda3731d45f))
* **bench:** expand selfplay opening pool to 104 RIF openings ([36bc929](https://github.com/Jx-study/gomoku_AI/commit/36bc929a49ae19e2cf6e5ebea45ed45c7ae6d087))
* **bench:** measure the incremental index cost model ([fa2dd9f](https://github.com/Jx-study/gomoku_AI/commit/fa2dd9fb307ed5f295de4e590fc1d117065b44f5))
* **bench:** track box scans and candidate hits ([1330838](https://github.com/Jx-study/gomoku_AI/commit/13308381d7686886a02ef5454eaf42c2dfc81e72))
* **lines:** recognize double-three only when two threes can advance ([2cb9e67](https://github.com/Jx-study/gomoku_AI/commit/2cb9e67f026006746358cbc5748bb051897e1c91))
* **search:** add VCF forcing-win search ([2eb2624](https://github.com/Jx-study/gomoku_AI/commit/2eb26244a322d56e0b5c88c45b4cf40a3ad32a48))


### Performance Improvements

* **ai:** add neighbor-count table and skip checkLine for five-in-a-row checks ([4540c36](https://github.com/Jx-study/gomoku_AI/commit/4540c369e8baad056188ac4349d76c082e6d313e))
* **ai:** cache encodeWindow results in an incremental window index ([991c5ed](https://github.com/Jx-study/gomoku_AI/commit/991c5ed0f77c26eabd961b3ac97471ad4675954d))
* **ai:** change the order of conditions to optimize performance ([aff1ff2](https://github.com/Jx-study/gomoku_AI/commit/aff1ff2d2f47488989b2ebfc3fbf40057fd52547))
* **ai:** read five/overline codes from patternTable in judgeMove and winsAt ([bb50a8b](https://github.com/Jx-study/gomoku_AI/commit/bb50a8b34fc13f4fbf566916dcab731a9bfa4211))
* **ai:** replace endGame full-board scan with single-point judgeMove ([5661f36](https://github.com/Jx-study/gomoku_AI/commit/5661f36b4ab04d27c73f0b18e90ef662ae7406f5))
* **ai:** walk stoneList instead of the box scan in checkNow ([b0d5702](https://github.com/Jx-study/gomoku_AI/commit/b0d570238ac76528005404b4438eb1e01d299875))
* eliminate per-node malloc in sortMoves by using caller-provided stack buffer ([1601efd](https://github.com/Jx-study/gomoku_AI/commit/1601efd480f2b634cb512a9a731bfe23cce663a4))
* replace linear-probe transposition table with always-replace and bitmask indexing ([9b295c8](https://github.com/Jx-study/gomoku_AI/commit/9b295c88547b261dd05463c496953727880c896c))


### Bug Fixes

* **ai:** count fours per direction and pin the remaining double-three gaps ([c708f13](https://github.com/Jx-study/gomoku_AI/commit/c708f134ce090f6633a357cd4d884af1597e67c2))
* **ai:** detect five and overline by direct run length ([561326a](https://github.com/Jx-study/gomoku_AI/commit/561326a340616cd6c6536ce6e6a23e9ff9cfdd72))
* **ai:** return a legal move from aiRound opening branches ([0b8f806](https://github.com/Jx-study/gomoku_AI/commit/0b8f8061007f0907ac706a3529faf2016cb4ef64))
* **ai:** score spaced-five points in quickEvaluate ([8b67df6](https://github.com/Jx-study/gomoku_AI/commit/8b67df634bf29d6fbcb60fc09dc66e8c95870ef3))
* **bench:** write the generated worker as UTF-8 ([8a93af8](https://github.com/Jx-study/gomoku_AI/commit/8a93af88dbb3bf72847eee1623ebdd3beb1049fb))
* **board:** correct 0-indexed bounds and align board size across C and Python ([71cf94f](https://github.com/Jx-study/gomoku_AI/commit/71cf94f4c1e29158a769508520ecc0c20e796b65))
* correct 0-indexed board bounds and unify board size across C and Python ([199d7f9](https://github.com/Jx-study/gomoku_AI/commit/199d7f9b84c22bd226ed489b6ffb073ea099287e))
* correct Zobrist index off-by-one, remove debug printf, and add depth-based win/loss scoring in miniMax ([9c1623d](https://github.com/Jx-study/gomoku_AI/commit/9c1623d472433138d5dfb202ec01b4be9b5c4a72))
* **eval:** classify line shapes by RIF definitions ([4fe8943](https://github.com/Jx-study/gomoku_AI/commit/4fe89438e2b4ff151ca3913aa6cd2ee773d1815e))
* **Gomuko:** resolve the shared library path relative to the script ([267e2f9](https://github.com/Jx-study/gomoku_AI/commit/267e2f906e0f8d3da6bc3b3475ac3e5f948123d5))
* **pattern:** guard makesFive against overline false positives ([be0b7a9](https://github.com/Jx-study/gomoku_AI/commit/be0b7a973f9ec19e5451eb558dfcbc85429a5cc2))
* **release:** drop tag prefix and build all three platforms ([12a1d38](https://github.com/Jx-study/gomoku_AI/commit/12a1d38fdfec528f71d38f922cae3c3047f5d0a2))
* **release:** drop tag prefix and build all three platforms ([b2ccc8b](https://github.com/Jx-study/gomoku_AI/commit/b2ccc8bce1e1d33596d80d9d68ef8b6bfc05dfe8))
* **search:** exempt forcing moves from candidate truncation ([54ae9b2](https://github.com/Jx-study/gomoku_AI/commit/54ae9b256713932b27244acbfe00fe5d3af029c4))
* **state:** extract GameState and keep turn order tied to the board ([ebce0c8](https://github.com/Jx-study/gomoku_AI/commit/ebce0c8e277e1dbae36003b13d9e2f431f6ed177))
* **window_index:** keep the debug DLL and driver per-process ([644b49f](https://github.com/Jx-study/gomoku_AI/commit/644b49fa2584582f41a28982795b846d633182ef))
* **workflow:** Grant issue write access for release-please ([e935113](https://github.com/Jx-study/gomoku_AI/commit/e935113073c1e8023cdc8fe259ce8d8a127e6f45))
* **zobrist:** recompute key from board at search entry ([fde2069](https://github.com/Jx-study/gomoku_AI/commit/fde206975c82c95e06ef0c0602350103f86c0659))
* **zobrist:** restore full 64-bit key entropy and consistent index order ([42332f1](https://github.com/Jx-study/gomoku_AI/commit/42332f1dcdb222c3edd7c61ff9dacd08a4490d3f))

## 1.0.0 (2026-09-18)


### Features

* add automated Windows release build on version tags ([d80723c](https://github.com/Jx-study/gomoku_AI/commit/d80723ccb41fb2572afc01a43067361d9b2f3f3b))
* **ai:** split three-level patterns by straight-four reachability ([5e1c852](https://github.com/Jx-study/gomoku_AI/commit/5e1c852f2a8c3c1848fcaccb5d92cca715c670c3))
* **bench:** add bench.py as the single entry point ([c167fc9](https://github.com/Jx-study/gomoku_AI/commit/c167fc9c15cb0fa68f681bb9ab00a4f177b76ce7))
* **bench:** add deterministic cell-access counter ([e702e10](https://github.com/Jx-study/gomoku_AI/commit/e702e100553131639a028df6e4ee4ed539e76900))
* **bench:** count stoneList walks in checkNow ([e3e58fd](https://github.com/Jx-study/gomoku_AI/commit/e3e58fd8eddce6ab6061af50e4e73fda3731d45f))
* **bench:** expand selfplay opening pool to 104 RIF openings ([36bc929](https://github.com/Jx-study/gomoku_AI/commit/36bc929a49ae19e2cf6e5ebea45ed45c7ae6d087))
* **bench:** measure the incremental index cost model ([fa2dd9f](https://github.com/Jx-study/gomoku_AI/commit/fa2dd9fb307ed5f295de4e590fc1d117065b44f5))
* **bench:** track box scans and candidate hits ([1330838](https://github.com/Jx-study/gomoku_AI/commit/13308381d7686886a02ef5454eaf42c2dfc81e72))
* **lines:** recognize double-three only when two threes can advance ([2cb9e67](https://github.com/Jx-study/gomoku_AI/commit/2cb9e67f026006746358cbc5748bb051897e1c91))
* **search:** add VCF forcing-win search ([2eb2624](https://github.com/Jx-study/gomoku_AI/commit/2eb26244a322d56e0b5c88c45b4cf40a3ad32a48))


### Performance Improvements

* **ai:** add neighbor-count table and skip checkLine for five-in-a-row checks ([4540c36](https://github.com/Jx-study/gomoku_AI/commit/4540c369e8baad056188ac4349d76c082e6d313e))
* **ai:** cache encodeWindow results in an incremental window index ([991c5ed](https://github.com/Jx-study/gomoku_AI/commit/991c5ed0f77c26eabd961b3ac97471ad4675954d))
* **ai:** change the order of conditions to optimize performance ([aff1ff2](https://github.com/Jx-study/gomoku_AI/commit/aff1ff2d2f47488989b2ebfc3fbf40057fd52547))
* **ai:** read five/overline codes from patternTable in judgeMove and winsAt ([bb50a8b](https://github.com/Jx-study/gomoku_AI/commit/bb50a8b34fc13f4fbf566916dcab731a9bfa4211))
* **ai:** replace endGame full-board scan with single-point judgeMove ([5661f36](https://github.com/Jx-study/gomoku_AI/commit/5661f36b4ab04d27c73f0b18e90ef662ae7406f5))
* **ai:** walk stoneList instead of the box scan in checkNow ([b0d5702](https://github.com/Jx-study/gomoku_AI/commit/b0d570238ac76528005404b4438eb1e01d299875))
* eliminate per-node malloc in sortMoves by using caller-provided stack buffer ([1601efd](https://github.com/Jx-study/gomoku_AI/commit/1601efd480f2b634cb512a9a731bfe23cce663a4))
* replace linear-probe transposition table with always-replace and bitmask indexing ([9b295c8](https://github.com/Jx-study/gomoku_AI/commit/9b295c88547b261dd05463c496953727880c896c))


### Bug Fixes

* **ai:** count fours per direction and pin the remaining double-three gaps ([c708f13](https://github.com/Jx-study/gomoku_AI/commit/c708f134ce090f6633a357cd4d884af1597e67c2))
* **ai:** detect five and overline by direct run length ([561326a](https://github.com/Jx-study/gomoku_AI/commit/561326a340616cd6c6536ce6e6a23e9ff9cfdd72))
* **ai:** return a legal move from aiRound opening branches ([0b8f806](https://github.com/Jx-study/gomoku_AI/commit/0b8f8061007f0907ac706a3529faf2016cb4ef64))
* **ai:** score spaced-five points in quickEvaluate ([8b67df6](https://github.com/Jx-study/gomoku_AI/commit/8b67df634bf29d6fbcb60fc09dc66e8c95870ef3))
* **bench:** write the generated worker as UTF-8 ([8a93af8](https://github.com/Jx-study/gomoku_AI/commit/8a93af88dbb3bf72847eee1623ebdd3beb1049fb))
* **board:** correct 0-indexed bounds and align board size across C and Python ([71cf94f](https://github.com/Jx-study/gomoku_AI/commit/71cf94f4c1e29158a769508520ecc0c20e796b65))
* correct 0-indexed board bounds and unify board size across C and Python ([199d7f9](https://github.com/Jx-study/gomoku_AI/commit/199d7f9b84c22bd226ed489b6ffb073ea099287e))
* correct Zobrist index off-by-one, remove debug printf, and add depth-based win/loss scoring in miniMax ([9c1623d](https://github.com/Jx-study/gomoku_AI/commit/9c1623d472433138d5dfb202ec01b4be9b5c4a72))
* **eval:** classify line shapes by RIF definitions ([4fe8943](https://github.com/Jx-study/gomoku_AI/commit/4fe89438e2b4ff151ca3913aa6cd2ee773d1815e))
* **Gomuko:** resolve the shared library path relative to the script ([267e2f9](https://github.com/Jx-study/gomoku_AI/commit/267e2f906e0f8d3da6bc3b3475ac3e5f948123d5))
* **pattern:** guard makesFive against overline false positives ([be0b7a9](https://github.com/Jx-study/gomoku_AI/commit/be0b7a973f9ec19e5451eb558dfcbc85429a5cc2))
* **search:** exempt forcing moves from candidate truncation ([54ae9b2](https://github.com/Jx-study/gomoku_AI/commit/54ae9b256713932b27244acbfe00fe5d3af029c4))
* **state:** extract GameState and keep turn order tied to the board ([ebce0c8](https://github.com/Jx-study/gomoku_AI/commit/ebce0c8e277e1dbae36003b13d9e2f431f6ed177))
* **window_index:** keep the debug DLL and driver per-process ([644b49f](https://github.com/Jx-study/gomoku_AI/commit/644b49fa2584582f41a28982795b846d633182ef))
* **workflow:** Grant issue write access for release-please ([e935113](https://github.com/Jx-study/gomoku_AI/commit/e935113073c1e8023cdc8fe259ce8d8a127e6f45))
* **zobrist:** recompute key from board at search entry ([fde2069](https://github.com/Jx-study/gomoku_AI/commit/fde206975c82c95e06ef0c0602350103f86c0659))
* **zobrist:** restore full 64-bit key entropy and consistent index order ([42332f1](https://github.com/Jx-study/gomoku_AI/commit/42332f1dcdb222c3edd7c61ff9dacd08a4490d3f))
