# Research Universe v1.1 & Research Dataset 规范

> 状态:定稿(RESEARCH_UNIVERSE_V1_1)/ 数据源阶段
> 适用范围:Research Layer 全部策略发现与验证工作

## 1. Research Universe v1.1 — 九大核心研究资产

不再继续扩张。以下 9 个资产构成第一版 Research Universe,覆盖三类研究维度:

| 维度 | 资产 | 地区 | 交易所 | 时区 | 交易时段 | 连续合约 |
|---|---|---|---|---|---|---|
| Equity | NVDA | US | NASDAQ | America/New_York | 09:30-16:00 | — |
| Equity | SPY | US | NYSE | America/New_York | 09:30-16:00 | — |
| Equity | QQQ | US | NASDAQ | America/New_York | 09:30-16:00 | — |
| Equity | 000688.SH(科创50) | CN | SSE | Asia/Shanghai | 09:30-15:00(11:30-13:00 休) | — |
| Equity | HSTECH(恒生科技) | HK | HKEX | Asia/Hong_Kong | 09:30-16:00(12:00-13:00 休) | — |
| FX | EURUSD | GLOBAL | OTC | Etc/UTC | 24h(Mon-Fri) | — |
| Precious | XAUUSD(伦敦金) | GLOBAL | OTC | Etc/UTC | 近 24h(Mon-Fri) | — |
| Precious | AU(沪金) | CN | SHFE | Asia/Shanghai | 09:00-15:00 + 21:00-02:30(夜盘) | ✔ 连续主力 |
| Precious | AG(沪银) | CN | SHFE | Asia/Shanghai | 09:00-15:00 + 21:00-02:30(夜盘) | ✔ 连续主力 |

**价值**:贵金属三元组(伦敦金 / 沪金 / 沪银)用于检验策略是"只适用于某报价体系"还是"对全球黄金与中国期货贵金属具有共同有效性"。

代码位置:`research/universe/research_universe.py`(Asset 模型在 `research/universe/asset.py`)。

## 2. Research Dataset v1.1 — 数据标准

```
9 Assets × 15m / 1h / 1D × ≥ 3–5 Years
```

- 当前合成数据覆盖 **3 个日历年**(2023–2025),15m / 1h / 1d 共 27 个数据集
- 时间戳为资产本地 **naive local 时间**(时区记录在 Dataset Manifest,不隐式转换)
- 合成数据源(`source: "synthetic"`)用于打通管线与开发策略;真实数据源接入后保持同一规范

## 3. 数据管线

```
Raw ──► Processed ──► Dataset Manifest ──► Quality Gate ──► Backtest
```

| 阶段 | 路径/形式 | 说明 |
|---|---|---|
| Raw | `data/raw/{symbol}_{tf}.csv` | 原始数据(真实数据源落地处,当前未填充) |
| Processed | `data/processed/{symbol}_{tf}.csv` | 通过质量门禁的清洗序列(provider 读取处) |
| Manifest | `data/manifests/{symbol}_{tf}.json` | 数据集注册表:资产、时区、时段、起止、bar 数、门禁结果 |
| Quality Gate | `research/data/quality_gate.py` | 8 项检查,全过才可进入回测 |

**生成与验证命令**:

```bash
# 全量生成 9 资产 × 3 TF(默认 3 年),生成后自动跑 Quality Gate + 写 Manifest
python infra/scripts/generate_research_dataset.py --years 3

# 子集
python infra/scripts/generate_research_dataset.py \
  --assets NVDA,SPY,QQQ --timeframes 15m,1h,1d --years 3
```

## 4. Quality Gate 检查项(第一版)

| # | 检查 | 语义 |
|---|---|---|
| 1 | `bars_non_empty` | 至少 1 根 bar |
| 2 | `coverage_years` | 覆盖 ≥ min_years 个日历年(默认 3) |
| 3 | `no_missing_fields` | OHLCV/时间戳无缺失 |
| 4 | `no_duplicate_timestamps` | 无重复时间戳 |
| 5 | `monotonic_timestamps` | 时间严格递增 |
| 6 | `ohlc_consistency` | high≥low, open/close ∈ [low, high] |
| 7 | `cadence` | 相邻 bar 间隔为 bar 长度的整数倍且 ≥ 1 bar(兼容午休/隔夜/周末/夜盘) |
| 8 | `metadata` | 时区存在、连续合约有报价货币 |

> 这是研究门槛,不是盈利保证。真实数据接入后需补充:交易日历(节假日)、复权/除权、真实展期处理。

## 5. 特殊资产规范(不能照搬美股 CSV 规则)

1. **HSTECH(恒生科技)**:Asia/Hong_Kong;09:30-12:00 + 13:00-16:00;港股交易日历。
2. **XAUUSD(伦敦金)**:Etc/UTC;近 24h 连续交易(Mon-Fri);报价体系为美元/盎司现货。
3. **AU / AG(沪金/沪银)**:Asia/Shanghai;**连续主力合约**`continuous_contract: true`,合成数据为单一连续价格序列;白盘 09:00-11:30 + 13:30-15:00,夜盘 21:00-02:30(跨日,rollover);真实数据需处理主力换月与展期价差。
4. **000688.SH(科创50)**:Asia/Shanghai;09:30-11:30 + 13:00-15:00;A 股交易日历。
5. **EURUSD**:Etc/UTC;24h(Mon-Fri);高精度报价(4 位小数)。

## 6. 已知限制与后续

- **合成数据**:当前 27 个数据集均为确定性 GBM 合成(seed 固定可复现),用于管线验证与策略开发;任何收益/胜率数字不具统计意义。
- **节假日**:合成数据仅按工作日生成,未建模各市场节假日;真实数据接入后由交易日历补齐。
- **连续合约**:AU/AG 为简化连续序列,未建模换月展期;真实期货数据需引入展期规则。
- **下一步**:接入真实数据源(如 yfinance / akshare / 专业行情 API)到 Raw 层,走同一 Manifest + Quality Gate 流程。
