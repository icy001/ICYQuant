# Day 17 — tp_to_open 证据审计

审计对象：`tp_to_open`（EURUSD 5m 反转，止盈回到日开盘价 O），窗口 Beijing 15:00–18:00。

范围约束：只读已有文件。不改代码、不重跑回测、不新增工程任务。
审计日期：2026-10-23。

---

## 0. 需要区分的两件事

| 层面 | 本仓库的实际情况 |
|---|---|
| **验证规范** | `docs/06-research/`（6 个文件，477 行）中，`OOS` / 预登记 / 冻结 / look-ahead / walk-forward **一个词都没有** |
| **walk_forward.md** | 位于 `docs/architecture/`，全文 17 行，是 ASCII 流程图（Historical → Splitter → Rolling Optimizer → OOS Evaluation），属架构示意图；且描述的是**滚动优化**流程，而 tp_to_open 实际用的是**单次 IS/OOS 切分**，并未走 walk-forward |

结论：**规范存在不等于规范被遵守**；且本仓库研究规范未对 OOS 独立性作出任何规定，
因此不存在"按规范即可认定 OOS 独立"的依据。

---

## 1. 问题一：15–18 是事先确定的，还是比较后选出的？

### 判定：**比较后选出；是否"在查看结果前"确定 —— 未证实**

| 证据 | 内容 | 指向 |
|---|---|---|
| 原始 V1 规则 | `reversal_v1_report.json` 的 spec 写死 `09:00-10:00`，**无 15–18** | 15–18 非原始规则的一部分 |
| 引入点 | `git log -S "win_15_18" --all` 仅返回 `1726657a`（2026-10-16 09:46:05） | 无中间版本 |
| 提交数 | `git log --follow -- research/discovery/eurusd_reversal_v1_m5.py` 仅 1 条 | 脚本一次性入库 |
| 窗口列表 | `windows = [("win_09_10",9,10), ("win_15_18",15,18)]`，注释 `8 scenarios, ALL reported` | 只比较 2 个候选，且全部报告 |
| 登记动机 | docstring：`(London session, a market-structure candidate)` | 存在先验的市场结构理由 |
| 后续引用 | `exp02_threshold_report.json` 的 spec 中 15–18 已进入 `frozen` 字段 | exp02 时已作为既定组合 |

### 已排除的线索

- `git log -S "London" --all` 最早命中 `81a761d8`（2026-08-11），但内容为 `"LSE": "Europe/London"` 交易所时区表，**与时段窗口无关**，属噪声。
- `git fsck` 报出 8 个悬空提交（`d594c577` `70992d3b` `979993de` `89202d70` `57b42edf` `f6c2b4e3` `edca9769` `d4d16912`），逐一检查 `win_15_18 / tp_to_open / oos_year` 命中数**全部为 0**，与本次研究无关。
- reflog 中无相关中间版本。

### 判定依据

脚本是**结果产出后才一次性入库**的：既没有记录能证明窗口是在查看结果之前确定的，
也没有记录能证明它是事后挑的。缺乏落笔时点证据，此项只能停在**未证实**，
不能向任一方向外推。

---

## 2. 问题二：2016 年后数据是否参与过时段 / 阈值 / 止损选择？

### 判定：**未证实**

| 证据 | 内容 |
|---|---|
| 切分存在 | `--oos-year` 默认 2016；IS `<2016`，OOS `>=2016`；报告用的正是 2016 |
| 切分可调 | `--oos-year` 是**命令行参数**，可反复改动 |
| 无运行日志 | 没有任何运行记录能证明只跑过一次 |
| git 侧 | `git log -S "oos_year" --all` 的 4 条命中分属 4 个不同脚本各自引入该参数，**不是同一文件被反复修改** |

**标签存在 ≠ 独立性成立。** 报告把 2016 年及之后标记为 OOS，该标签本身不能证明
研究人员在选定窗口、阈值、止损时没有查看或利用这段数据。

---

## 3. 审计中新发现的否证证据（exp02 干净对照）

`exp02_threshold_report.json` 的 spec 将窗口冻结为 `Beijing 15:00-18:00`、
止损 A（固定 20 pip）、目标 `revert to day open O`，**只让触发阈值变动**。
这是在冻结窗口内做的对照实验，结果如下（成本 1.5 pip，与 spec 冻结值一致）：

| 触发阈值 | n | expR | netPF |
|---|---|---|---|
| 0.3% | **5916** | **−0.0627** | 0.875 |
| 0.5% | 2308 | **−0.0940** | 0.836 |
| **1.0%（选定）** | **280** | **+0.1796** | **1.289** |

三点单调，方向为**样本越多、结果越差**。

### 为什么这一条分量最重

它不只是"又一次小样本陷阱"，而是与因果假设直接冲突：

如果 1.0% 的偏离确实是**均值回归机会**，那么把阈值放宽到 0.5%、0.3%——
也就是把**同一类机会**多抓约 20 倍——每笔收益理应变小，但**不应变负**。
实际结果是负的。

因此 1.0% 的正结果不是"一个更频繁发生的效应里最肥的那一小段"，
而是"只有在这一段才出现"。这与均值回归的假设冲突，
更接近小样本噪声或特定时段漂移。

此证据**不依赖问题 1、2 的任何判断**：它是在窗口冻结前提下单独跑出的对照。

---

## 4. 成本口径（引用绩效时必须标注）

同一场景 `tp_to_open_15_18_A_fixed20` 在不同口径下的值**不可混用**：

| 来源 | 成本口径 | netPF |
|---|---|---|
| `reversal_v1_tp_window_report.json` / `exp02` spec | **1.5 pip**（标注 ASSUMED，bid-only 无点差） | **1.289** |
| `day15_verification.md` / `cost_break_even.md` | **1.0 pip**（账户真实成本） | **1.338** |

---

## 5. 与既有发现的叠加

| 发现 | 来源 |
|---|---|
| exp02 冻结窗口内，放宽阈值后效应转负 | 本轮新发现 |
| 信号频率衰减 −76%（IS 15.0 → OOS 3.6 笔/年）；2014/2017/2018/2019/2021 五年零交易 | Day 16 审计 |
| IS 有 50.8% 交易集中在 2008–2009 两年（122/240） | Day 16 审计 |
| 阈值扫描呈"样本越小、结果越好"模式，小样本候选曾被选中 | `day15_verification.md` |

---

## 6. 决策栏

| 核查项 | 判定 |
|---|---|
| 15–18 时段事先确定 | **未证实** |
| OOS 真正独立 | **未证实** |
| **tp_to_open 下一步** | **建议淘汰**（待终审） |

给"淘汰"而非"继续待验证"的理由：

1. exp02 干净对照显示效应不稳健——放宽阈值后转负，与均值回归假设冲突；
2. 信号频率衰减 −76%，近五年近乎不触发；
3. IS 过半交易集中于 2008–2009 两年。

三项叠加的含义是：**即便问题 1、2 将来查清为"事先确定、OOS 独立"，
该策略也已在"效应真实性"这一层被否掉**，独立性只是第二道关卡。

> 决策栏保留终审权。若裁定维持"待验证"，则上述三条作为已知的否证证据一并保留，
> 不构成支持推进的依据。

---

## 7. 引用文件

```
artifacts/research/eurusd_reversal_v1/reversal_v1_report.json
artifacts/research/eurusd_reversal_v1/reversal_v1_tp_window_report.json
artifacts/research/eurusd_reversal_v1/exp02_threshold_report.json
artifacts/research/eurusd_reversal_v1/exp03_audit_1pct_report.json
artifacts/research/day15_verification.md
artifacts/research/cost_break_even.md
research/discovery/eurusd_reversal_v1_m5.py
research/discovery/eurusd_reversal_v1_exp02_thresholds.py
docs/architecture/walk_forward.md
docs/06-research/            （核查为无 OOS 相关规定）
```

Git 追踪命令（可复现）：

```
git log -S "win_15_18" --all --oneline
git log -S "oos_year" --all --oneline
git log --follow -- research/discovery/eurusd_reversal_v1_m5.py
git fsck --lost-found          # 8 个悬空提交，逐一核查后全部 0 命中
```
