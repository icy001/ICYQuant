# G6-1 历史授权取证报告（Preliminary）

> **状态**：Preliminary。本报告为 G6-1 取证的证据收集与分级，**不**是 G6-1 的正式裁定，亦**不**构成对历史事实的重新定性。
>
> **落盘日期**：2026-10-15
>
> **取证窗口**：1fa4a34d（2026-10-14 17:17:45 +0800）与 9a208ce3（2026-10-13 10:43:08 +0800）
>
> **取证方式**：仅只读命令（`git show/log/reflog`、`find`、`stat`、`ls`、`cat`、`grep`）。**未触动任何仓库内既有文件、未暂存、未提交、未推送、未改历史**。
>
> **本报告范围之外**：① G6-2 流程顺序裁定（依赖 G6-1 结论）；② 正式评审记录（待 G6-1、G6-2 完成后另行创建）；③ 第 2–5 组的逐项核验结果（此前未落盘）；④ PC-5 具体数值阈值（与本报告无关，由 §7.x 另行管理）。

---

## 1. 关键事实（机器证据）

### 1.1 1fa4a34d 提交元数据

| 字段 | 值 |
|---|---|
| Hash | `1fa4a34d47c29830524271aa32b1e1ec572655e7` |
| Author | `icy001 <pkxueyingqi@163.com>` |
| AuthorDate / CommitDate | `2026-10-14 17:17:45 +0800`（同日同分） |
| Subject | `add`（**无 commit body**） |
| 父提交 | `470182df`（v5） |
| 子提交 | `e4d5fdec`（v6）→ `bac5da10`（v7）→ `85817d33`（v8） |
| 所在分支 | `develop`（= `origin/develop`） |
| 改动 | 119 files, 379,872 insertions(+), 0 deletions(-) |

### 1.2 1fa4a34d 实际内容（按目录/类型分级）

| 类别 | 数量 | 顶层路径 | 备注 |
|---|---|---|---|
| 流水线产物 | 118 | `artifacts/histdata_v9_bc/**` | before_a / after_a / before_b / after_b / step2 等多轮 |
| 原始 M1 数据 | 1 | `data/real/histdata/EURUSD_M1/DAT_MT_EURUSD_M1_2024.csv` | 372,379 行；与 9a208ce3 的 `DAT_ASCII_*` 同一标的、不同格式 |
| 可执行脚本 | 2 | `artifacts/histdata_v9_bc/probe_03_tests.py`、`step2/compare_runs.py` | probe + 对比工具，B+C step 2 自身生成 |
| 静态评审报告 | 2 | `artifacts/histdata_v9_bc/{before_b,step2/before_b2}/STATIC_REVIEW.md` | B+C 评审产物 |
| **未触动** | — | `docs/`、`scripts/`（除 b3_validation 外）、`tests/`、`release/` | 与 6-4 报告一致 |

文件类型分布：81 JSON + 24 YAML + 9 JSONL + 2 `.py` + 2 `.md` + 1 CSV（共 119）。

### 1.3 同窗口提交历史（2026-10-13 ~ 10-15）

```
9a208ce3  2026-10-13 10:43  add                                   ← 同模式 "add"
9634aaf4  2026-10-13 14:00  feat(histdata): Stage 02 D1 resample…
3083be9e  2026-10-13 13:31  feat(histdata): v9 Stage 01 acceptance…
15eec64b  2026-10-13 14:04  feat(histdata): gitignore generated M1/D1…
8a1872df  2026-10-14 10:35  feat(histdata): B+C step 1 — contract…
16595900  2026-10-14 10:36  feat(histdata): B+C step 2 — independent…
f4125ee1  2026-10-14 16:58  docs(histdata): add Stage D Phase 0 design draft v2
9e42bfd6  2026-10-14 16:58  docs(histdata): … v3
4bd38063  2026-10-14 16:58  docs(histdata): … v4
470182df  2026-10-14 16:58  docs(histdata): … v5
1fa4a34d  2026-10-14 17:17  add                                    ← 本次
e4d5fdec  2026-10-15 09:51  docs(histdata): … v6
bac5da10  2026-10-15        docs(histdata): … v7
85817d33  2026-10-15        docs(histdata): … v8
```

**关键观察**：
- **第二个非描述性 "add" 提交（9a208ce3，10-13 10:43）** 此前未在 6-4 中识别。9a208ce3 引入 26 年 EURUSD M1 原始数据（2000–2026，含 CSV+TXT 两个格式）+ `research/data/histdata/` + `scripts/b3_validation/`（5 文件）+ 2 份 research 报告 + 1 个 playwright 抓取。**两个 "add" 形成模式**。
- v2–v5 在 16:58:28–29 一分钟内连发，1fa4a34d 在 17:17:45（**+19 分钟**）插入；v6 次日 09:51 出现。
- 流水线产物最后 mtime 2026-10-14 10:47，1fa4a34d 提交 17:17——**产物生成与提交间隔 6.5 小时**。

### 1.4 设计链对 1fa4a34d 的引用情况

| 邻接 commit | 主题 | 主体是否引用 1fa4a34d |
|---|---|---|
| `470182df`（v5，前一条） | "per-gate unfrozen-item labels, unify list indentation" | **否** |
| `e4d5fdec`（v6，后一条） | "per-gate PASS-W conditions, named approval roles, §10.2 tri-labels" | **否** |
| `bac5da10`（v7） | "rule-gate mapping, enumerable PASS conditions, state transitions, P0 task table" | **否** |
| `85817d33`（v8） | "review findings N1–N4, N6–N7" | **否** |

### 1.5 仓库内授权/数据来源文档扫描

| 检索目标 | 结果 |
|---|---|
| `LICENSE*` / `DATA_LICENSE*` / `DATA_SOURCE*` / `provenance*` / `attribution*` | 仅命中 `release/{artifacts,ga}/provenance.json`（**SLSA in-toto 模板**，针对 v0.4.0-alpha1 应用发布；**非 histdata 数据来源**） |
| `docs/` 下含 Dukascopy / DAT_MT / EURUSD data 关键词 | **0 命中**（`docs/02-technical/DATA_ARCHITECTURE.md` 在该路径下不存在） |
| 1fa4a34d 的 `probe_03_tests.py` / `compare_runs.py` 是否引用 `data/real/histdata` | **否**（probe 只引用 `scripts/histdata/tests/test_verify_crossref.py`） |
| `scripts/histdata/tests/test_verify_crossref.py` 是否存在 | 是（被 probe 引用，B+C step 2 的被验证实现） |

---

## 2. 证据分级

| 证据项 | 分级 | 备注 |
|---|---|---|
| 1fa4a34d 是 `icy001` 本人创建 | **有证据（直接）** | git 自身元数据 |
| 1fa4a34d 在 v5 与 v6 之间线性插入 | **有证据（直接）** | `--ancestry-path` + `--parents` |
| 1fa4a34d 包含 119 文件（118 流水线产物 + 1 原始数据） | **有证据（直接）** | `--name-only` 完整列表 |
| 1fa4a34d 未触动 `docs/scripts/tests/release` 目录 | **有证据（直接）** | 按目录聚合 |
| 同模式非描述性 "add" 至少还有 9a208ce3 | **有证据（直接）** | 主题统计命中 2 |
| 邻接 v2–v8 设计 commit 均未引用 1fa4a34d | **有证据（直接）** | 逐条 `git log -1 --format=%B` 文本检索 |
| 仓库内**无** EURUSD M1 数据来源/License 文档 | **有证据（直接，但 docs 扫描未全量）** | `find` + `grep -rli` 命中 0 |
| 数据来源是否经正式授权（如：Dukascopy 许可、内部采购单） | **无法独立确认** | 仓库内无对应文件；如需独立确认需仓库外证据 |
| 1fa4a34d 是否经他人审批（项目维护者 / 治理角色） | **无法独立确认** | 单作者仓库，reflog 中无第三方 commit；评审授权链不存在于 git 自身证据 |
| "add" 是否掩盖了未公开的授权流程（如口头决定、IM 沟通） | **无法独立确认** | 此类证据原则上不入库 |
| 9a208ce3 与 1fa4a34d 之间的 26 年原始数据是否完整、是否再加工 | **证据不足** | 9a208ce3 的实际内容未全量核查 |
| 流水线产物中的 `probe_03_tests.py` 是否被纳入正式测试套件 | **证据不足** | 该文件位于 `artifacts/` 而非 `tests/`，未被 `tests/histdata/` 收录 |

---

## 3. 发现的缺口

1. **数据来源授权链完全缺失**：26 年 EURUSD M1 + 2024 MT 格式数据**未在任何仓库文档**中说明来源、下载日期、license、再分发权利。`docs/02-technical/DATA_ARCHITECTURE.md` 不存在。
2. **设计文档与 1fa4a34d 的内容无任何交叉引用**：v6、v7、v8 均未在 commit message 或文档正文中提及 B+C 产物、`artifacts/histdata_v9_bc/` 或 1fa4a34d hash。即 1fa4a34d 在设计链上**未被作为设计输入**采纳。
3. **两次 "add" 形成模式但无复盘记录**：9a208ce3、1fa4a34d 均无 commit body、均含大量数据/产物；后续 commit 无任何反思/规范声明。
4. **9a208ce3 实际改动**未全量核查（仅核查顶层目录与文件类型分布，未逐文件读取 `research/data/histdata/**` 与 `scripts/b3_validation/**` 的内容性质）。
5. **流水线探针脚本（probe_03_tests.py、compare_runs.py）**的运行结果与正式测试套件的关系未核查。

---

## 4. 候选裁定建议（**未授权；非结论**）

> **重要声明**：本节列出的是基于第 1–3 节证据推导出的**候选建议**。每条均明确标注"未授权"——在获得仓主明确授权前，**不**构成对历史事实的重新定性，亦**不**作为后续评审/设计/实施的依据。

### 建议 1（未授权）：把 1fa4a34d 明确归类为「范围外可追溯的运行产物」，而非「设计前置证据」

**依据**：
- 1fa4a34d 未触动 `docs/design/`，与设计文档无引用关系
- v6–v8 邻接设计 commit 均未引用 1fa4a34d
- 1fa4a34d 的全部内容是 B+C step 2 的运行产物 + 单年 M1 数据副本
- 这些产物**已被 .gitignore 部分覆盖**（15eec64b 已对 `artifacts/histdata_v9` 设忽略，但 `artifacts/histdata_v9_bc` 仍跟踪）

**若被采纳的含义**：
- 在 v9 文档的 §11 退出条件或 §6.6 映射中**不应引用** 1fa4a34d 的 hash 或路径作为设计证据
- 1fa4a34d 可保留在 develop 上作为**历史运行产物**（不重写历史），但**不参与** Phase 0 通过判定
- 评审记录中应明确：1fa4a34d **不在 P0-01~P0-15 任何一项的"已获证据"列**

### 建议 2（未授权）：把 9a208ce3 同样归类为「范围外的数据导入」，并要求补数据来源文档

**依据**：
- 9a208ce3 与 1fa4a34d 同模式（非描述性 "add" + 大批量数据/产物）
- 9a208ce3 引入了 D-G07（数据集准入）的实际标的——26 年 EURUSD M1 数据
- 仓库内**无任何文档**说明该数据的来源、下载方式、license

**若被采纳的含义**：
- v9 文档的 §8（数据集级声明）或 §7.7（用途级声明）的"事实"行（如 `2000-05-30` 案例）所引用的数据基础需追溯到 9a208ce3
- 在 Phase 0 通过前应补：
  - 数据来源（`docs/02-technical/HISTDATA_DATA_SOURCE.md` 或类似）
  - license 文本（如适用）
  - 下载日期与下载命令（如可复现）
  - 任何内部授权记录的引用（编号、日期、签发人）

### 建议 3（未授权）：在评审记录中**显式标注**两个 "add" 的可追溯性缺口

**依据**：
- 6-4 已识别 1fa4a34d 的授权来源问题
- 本次新发现：9a208ce3 同样存在该问题，且 9a208ce3 才是更早、更基础的数据导入
- 任一缺口都足以让"评审授权链"中断

**若被采纳的含义**：
- 评审记录需在"证据"部分单列"G6-1 缺口"段，而非混入其他结论
- 不写"G6-1 通过"或"已确认"——按当前证据只能写"无法独立确认"或"已识别缺口，处置方案待裁定"

---

## 5. 边界声明

本报告**不**构成：

- Phase 0 通过判定
- 任何 P0-01~P0-15 的 PASS 判定
- 对 1fa4a34d / 9a208ce3 的"已授权"重新定性
- 对 26 年 EURUSD M1 数据准入 D-G07 的判定
- 对设计文档 v8（`85817d33`）的任何修订或补充

本报告**仅**为：

- G6-1 取证结果的事实陈述
- 证据等级（直接证据 / 证据不足 / 无法独立确认）的分类
- 候选建议的列举（**非**结论）

---

## 6. 取证时的工作区状态（落盘时的快照）

| 项 | 值 |
|---|---|
| 本地 HEAD | `85817d33`（v8, Draft for Review） |
| `origin/develop` | `85817d33`（与本地一致） |
| 工作区 | 干净 |
| stash | 空 |
| reflog 改写 | 无（仅标准 commit + push 条目） |

---

## 7. 落盘授权与操作

**授权指令**："G6-1 报告 也提交github"（仓主，2026-10-15）。

**落盘操作**：
- 新建文件：`docs/reviews/g6-1_evidence_report.md`（仅此一文件）
- 独立提交：与 v8 解耦
- 主题：`docs(review): G6-1 historical evidence report for 1fa4a34d/9a208ce3 (preliminary)`
- 状态：`(preliminary)` 后缀，避免与未来"正式评审记录"混淆

**未做之事**：
- 未修改任何既有文件（包括 v8 设计文档 `docs/design/histdata_stage_d_phase0_design.md`）
- 未运行 Stage 02 或任何流水线
- 未冻结任何 PC-5 数值
- 未改历史提交
- 未推送时若遇网络异常，commit 保留在本地，待网络恢复后重试
