# G6-2 历史证据报告：Stage 02 产物先于 Phase 0 v2 设计文档的流程顺序

## 0. 元信息

| 项 | 值 |
|---|---|
| 调查对象 | Stage 02 产物（及 B+C 流水线产物）先于 Phase 0 v2 设计文档（`f4125ee1`，2026-10-14 16:58）的流程顺序问题 |
| 调查方式 | **仅只读**：`git log` / `git show` / `grep` / `ls` / `stat` / `head` / `cat` |
| 调查日期 | 2026-10-15 |
| 本记录版本 | v1 |
| 裁定状态 | 候选 C（推迟）已由仓主于 2026-10-15 采纳（见 §6） |

**本记录的性质：** 本文件是**证据报告**，不是裁定书。§4 列出的是候选裁定建议，§6 登记仓主的裁定结果。本记录不修改任何设计文档、代码、验收契约或数据产物。

---

## 1. 关键事实（机器证据）

### 1.1 流程顺序时间线

```
10-13 10:43  9a208ce3  "add" (26y EURUSD M1 数据导入)
10-13 13:31  3083be9e  feat(histdata): v9 Stage 01 acceptance pipeline — 14/14 PASS on 26y EURUSD M1
10-13 14:00  9634aaf4  feat(histdata): Stage 02 D1 resample with spike quarantine on 26y EURUSD
10-13 14:04  15eec64b  feat(histdata): gitignore generated M1/D1 parquets under artifacts/histdata_v9
10-14 10:29  B+C_acceptance_summary.log mtime
10-14 10:35  8a1872df  feat(histdata): B+C step 1 — contract generation, gating, pipeline validation
10-14 10:36  16595900  feat(histdata): B+C step 2 — independent parsed-reference audit in 03_verify
10-14 10:36  02_post_commit_test.log / 03_commit_audit.log mtime
10-14 10:47  04_delivery_record.log mtime  ← B+C 流水线实际完成时间
────────── v2 设计阶段开始 ──────────
10-14 16:58  f4125ee1  v2 doc
10-14 16:58  9e42bfd6  v3 doc
10-14 16:58  4bd38063  v4 doc
10-14 16:58  470182df  v5 doc
10-14 17:17  1fa4a34d  "add" (B+C step 2 产物 + 1 个 2024 MT 数据)
10-15 09:51  e4d5fdec  v6 doc
10-15 10:27  bac5da10  v7 doc
10-15 13:27  85817d33  v8 doc
```

### 1.2 B+C 实际运行时间（关键证据）

`artifacts/histdata_v9_bc/step2/04_delivery_record.log` 头部：
```
== Stage 01/02 + B/C 交付记录 (2026-10-14T10:47:12Z) ==
branch: develop
local HEAD:  1659590029d1f5d757ec77ebeadd8dc09205185a
origin HEAD: 1659590029d1f5d757ec77ebeadd8dc09205185a
ahead/behind: 0/0
```

- B+C 流水线实际完成时间：**2026-10-14 10:47:12Z**
- 交付时 local HEAD = origin HEAD = `16595900`，ahead/behind = 0/0
- **10:47 < 16:58（v2 doc）**——B+C 实际运行早于 v2 doc
- `1fa4a34d` commit B+C 产物时间 17:17——**运行在 10:47，commit 在 17:17，间隔约 6.5 小时，且 commit 晚于 v2 doc**

### 1.3 B+C 交付清单（`04_delivery_record.log` [B] 段）

| Commit | 描述 | files | 时间 |
|---|---|---|---|
| `16595900` | B+C step 2 — independent parsed-reference audit | 4 | 10-14 10:36:17 |
| `8a1872df` | B+C step 1 — contract generation, gating | 11 | 10-14 10:35:55 |
| `15eec64b` | gitignore generated M1/D1 parquets | 1 | 10-13 14:04:11 |
| `9634aaf4` | Stage 02 D1 resample with spike quarantine | 4 | 10-13 14:00:27 |
| `3083be9e` | v9 Stage 01 acceptance 14/14 PASS | 20 | 10-13 13:31:10 |

**全部 5 个 commit 早于 v2 doc**——B+C 交付物封存时（10:47）HEAD 已是 `16595900`。

### 1.4 v2 doc 与 v8 doc 中关于 Stage 02 的明文

**v2 doc 第 32 行 = v8 doc 第 34 行**（两版本**完全一致**）：
> "Stage 02 在 Phase 0 中仅作为设计参考对象，不作为实施对象。本阶段对 Stage 02 的分析仅用于确认当前实现行为、识别契约缺口和制定 Stage D 的独立验证要求，**不授权修改 Stage 02 代码、运行其流水线、重建其产物或改变既有验收记录**。Stage 02 的实现变更须在后续实施阶段获得独立授权。"

**v2 doc 第 87 行 = v8 doc 第 85–91 行**（同文）：
> "已报告的 Stage 02 派生产物位于 `artifacts/histdata_v9/derived/`...**此前关于'Stage 02 从未运行'的说法已被更正**。"

**v8 doc §11 第 9 条**：
> "**技术债与授权边界明确：** ...**设计评审通过不等于代码实施、Stage 02 运行、产物生成或下游数据集准入已获授权。任何后续实施须独立启动并获得相应授权。**"

### 1.5 B+C 在设计文档中的引用

| 关键词 | v2 doc | v8 doc |
|---|---|---|
| `B and C` / `B+C` / `B/C` | **0 命中** | **0 命中** |
| `step 1` / `step 2` | 0 命中 | 0 命中 |
| `baseline` / `B-stage` / `C-stage` | 0 命中 | 0 命中 |

**B+C 流水线在 v2–v8 doc 中无任何引用。**

### 1.6 仓库内流程/治理文档

| 路径 | 状态与内容 |
|---|---|
| `docs/05-development/CONTRIBUTING.md` | 存在（1137 B）：贡献流程（阅读指南→明确范围→实现+测试→回归→PR Review）；项目状态 "Documentation Freeze / Development Phase Concluded" |
| `docs/05-development/GIT_WORKFLOW.md` | 存在（1367 B）：分支模型（main/develop/feature/fix）；提交规范；**冻结约定**（自 v0.4.0-alpha2 / Commit 41 起停止无限 Commit 扩张）；Review 流程（开发→自测→提交分支→Review→合并到 develop→回归→发布） |
| `docs/05-development/DEVELOPMENT_GUIDE.md` | 存在（1935 B）：开发流程（Issue→Design→Implementation→Unit Test→Integration Test→Regression→Commit→Review→Release）；核心原则（Domain First / Explicit State / Idempotency / Immutable Audit / Deterministic Replay） |
| `docs/05-development/CODE_STYLE.md` / `TESTING.md` | 存在（1312 B / 1516 B） |
| 根 `CONTRIBUTING.md` | 存在但为 **0 字节空文件** |
| `docs/design/governance_execution_flow.md` | 存在（289 B）：仅含 Agent Runtime → … → Governance Dashboard 的示意框图，**不含**评审流程定义 |
| v8 doc §11 第 9 条"设计评审通过 ≠ 实施授权" | 存在 |

**结论：** 仓库内**有**通用开发流程成文规范（CONTRIBUTING / GIT_WORKFLOW / DEVELOPMENT_GUIDE / CODE_STYLE / TESTING）。缺的是 **Stage D 特有治理规范**——通用 Review 流程为"提交分支→Review→合并到 develop"，**未定义**："设计评审 ≠ 实施授权"的分离、"角色持有人登记"（P0-11）、"证据分级"（有证据/证据不足/无法独立确认）、"历史事实裁定"流程。

**勘误说明：** 本节初稿（G6-2 对话层版本）曾记载 "`CONTRIBUTING*` / `GOVERNANCE*` / `PROCESS*` / `WORKFLOW*` **0 命中**"。该结论源于一次 `find` 命令因 shell 报错（`zsh: unknown file attribute`）未能执行成功而被误判为"无结果"。经 2026-10-15 独立路径列举复核后更正。

---

## 2. 证据分级

| 证据项 | 分级 |
|---|---|
| 全部 commit 时间戳与顺序 | 有证据（直接） |
| 6 个 pre-design commit 全部早于 v2 doc | 有证据（直接） |
| B+C 流水线实际完成时间 10:47（早于 v2 doc） | 有证据（直接） |
| `1fa4a34d` commit 17:17（晚于 v2 doc） | 有证据（直接） |
| v2 doc 第 32 行："不授权运行 Stage 02" | 有证据（直接） |
| v2 doc 第 87 行："Stage 02 已运行过"——v2 起草时已知 | 有证据（直接） |
| v2 doc 第 32/87 行与 v8 doc 第 34/85–91 行完全一致 | 有证据（直接） |
| v8 doc §11 第 9 条："设计评审通过 ≠ 实施授权" | 有证据（直接） |
| B+C 在 v2–v8 doc 中 0 命中 | 有证据（直接） |
| `3083be9e` "14/14 PASS" 的同期审批依据 | 证据不足（仅 commit message，无审查记录） |
| B+C step 1/2 实施前是否经设计评审 | 证据不足（v2 doc 0 命中 B+C） |
| `1fa4a34d` commit B+C 产物是否经"独立授权" | 证据不足（commit message 仅"add"） |
| B+C 与 Stage 02 的关系（并列 / 扩展 / 同义） | 证据不足（`04_delivery_record.log` 顶部作"Stage 01/02 + B/C"，与 Stage 01/02 并列，具体定位不明） |
| `9a208ce3` 26y EURUSD M1 数据导入授权 | 无法独立确认（仓库内无同期来源/license 文档；G6-1 建议 2 已补来源登记，但不构成同期授权证据） |
| `3083be9e` "14/14 PASS" 当时是否经设计批准 | 无法独立确认（14/14 在 10-13 完成，v2 doc 在 10-14；治理时序不清） |

---

## 3. 发现的核心事实

1. **"先有实施，后有设计"是事实**：6 个 pre-design commit（`9a208ce3` / `3083be9e` / `9634aaf4` / `15eec64b` / `8a1872df` / `16595900`）全部早于 v2 doc。
2. **v2 起草时已知该事实**：v2 doc 第 87 行明文"此前关于'Stage 02 从未运行'的说法已被更正"。
3. **v2 治理立场为"向未来不授权"**：第 32 行 + v8 §11 第 9 条——已发生的不追溯否认；未来仍须独立授权。
4. **B+C 实际运行早于 v2 doc**：`04_delivery_record.log` 显示 10:47 完成，远早于 v2 doc 16:58。
5. **B+C 在设计文档 0 命中**：属"未在设计文档中体现的独立流水线"。
6. **`1fa4a34d` 的 B+C 产物 commit 晚于 v2 doc**：实际运行 10:47，commit 17:17。
7. **通用开发流程有成文规范，Stage D 特有治理无成文规范**：`CONTRIBUTING` / `GIT_WORKFLOW` / `DEVELOPMENT_GUIDE` 定义通用开发与 Review 流程；但"设计评审 ≠ 实施授权"分离、角色持有人登记、证据分级与历史事实裁定无成文规范。

---

## 4. 候选裁定（**未在记录中作为结论**）

> 本节列出基于 §1–§3 的候选裁定。裁定结果见 §6。

### 候选 A（综合）：历史流程问题 + 证据引用问题混合

- 6 个 pre-design commit 早于 v2 doc → 历史流程问题
- B+C 在 v2–v8 doc 0 命中 → 证据引用问题
- v2 起草时已承认 Stage 02 已运行 + 治理立场"向未来不授权" → 不属于纯"治理违规"
- 处置含义：`3083be9e` / `9634aaf4` / `9a208ce3` / `8a1872df` / `16595900` 归类为"v2 doc 起草前已发生的实施事实"，不追溯否认；`1fa4a34d` 归类为"既有运行产物的事后归档入库"；在设计文档中建立"设计文档—实施产物"交叉索引（含 B+C）

### 候选 B（流程问题主导）

- 全部 pre-design 实施早于 v2 doc；v2 起草时已知 + 主动承认 + 向未来不授权
- 处置含义：不构成治理违规或证据引用错误；仅属"先有实施后有设计"的历史流程问题；建议补充成文规范，但不对历史 commit 重新定性

### 候选 C（推迟）

- G6-2 定性高度依赖 G6-1 建议 1/2/3 归类稳定
- 处置含义：G6-2 报告暂不落盘（除非前置满足）；评审记录中登记为"流程顺序缺口"，不含裁定结论

### 候选 D（治理违规）

- 认为 `1fa4a34d` 在 v2 doc 之后 commit B+C 产物，违反"设计评审通过 ≠ 实施授权"
- **反证**：`04_delivery_record.log` 显示封存时 ahead/behind = 0/0，封存 commit 全部为既有 5 个；`1fa4a34d` 为归档动作；v2 doc 第 87 行已承认既有运行；B+C step 1/2 commit 早于 v2 doc
- **评价**：候选 D 缺乏直接证据支持

---

## 5. 只读声明

本轮**仅执行只读命令**（`git log/show/grep`、`ls`、`stat`、`head`、`cat`）。未触动任何文件、未暂存、未提交、未推送。

---

## 6. 裁定记录（仓主 2026-10-15）

| 项 | 内容 |
|---|---|
| 采纳候选 | **候选 C（推迟）** |
| 采纳日期 | 2026-10-15 |
| 推迟理由 | G6-2 定性高度依赖 G6-1 建议 1/2/3 的归类稳定 |
| 推迟期间处置 | 候选 A 含义中"B+C 交叉索引"作为事实登记，写入评审记录 §4.3（**不**作裁定） |
| 后续动作 | G6-1 完整闭环（评审记录 v1 创建，commit `34b1bc4e`）后，本报告方可落盘 |
| 落盘状态 | 本报告（`docs/reviews/g6-2_evidence_report.md`）——G6-1 闭环后落盘 |

**裁定的证据边界：** `1fa4a34d` 与 `9a208ce3` 的授权来源在仓库证据下**无法独立确认**；Stage 02 产物先于 v2 设计文档的流程顺序在本报告中**登记为事实，不做重新定性**。两项历史事实不得写成已通过的结论。

---

## 7. 参考文件清单

| 类型 | 路径 / 标识 | 说明 |
|---|---|---|
| 被调查实施提交 | `9a208ce3`、`3083be9e`、`9634aaf4`、`15eec64b`、`8a1872df`、`16595900`、`1fa4a34d` | 前 6 个早于 v2 doc；`1fa4a34d` 晚于 v2 doc |
| v2 设计文档 | `f4125ee1:docs/design/histdata_stage_d_phase0_design.md` | 第 32 行（不授权运行 Stage 02）、第 87 行（已更正"从未运行"） |
| v8 设计文档 | `docs/design/histdata_stage_d_phase0_design.md`（`85817d33`） | 第 34 行同 v2 第 32 行；§11 第 9 条授权边界 |
| B+C 交付记录 | `artifacts/histdata_v9_bc/step2/04_delivery_record.log` | 文件头 `2026-10-14T10:47:12Z`；交付时 HEAD = `16595900` |
| G6-1 证据报告 | `docs/reviews/g6-1_evidence_report.md` | 前置依赖 |
| 评审记录 v1 | `docs/reviews/histdata_stage_d_phase0_design_review.md`（`34b1bc4e`） | §4 登记本事项 |
| 通用开发流程文档 | `docs/05-development/CONTRIBUTING.md`（1137 B）、`GIT_WORKFLOW.md`（1367 B）、`DEVELOPMENT_GUIDE.md`（1935 B）、`CODE_STYLE.md`、`TESTING.md` | 存在；定义通用开发流程；不含 Stage D 特有治理（缺口 G-4） |
| 根 `CONTRIBUTING.md` | 0 字节空文件 | 存在但为空 |
| 治理示意文档 | `docs/design/governance_execution_flow.md`（289 B） | 仅示意框图，不含评审流程定义 |
