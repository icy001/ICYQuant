# ICYQuant Factor Research

> 本文档描述 ICYQuant 的因子研究（Quant Research）能力。

---

## 1. 定位

ICYQuant 不仅负责交易执行，同时包含 Quant Research 能力。

Research Pipeline：

```text
Market Data
     ↓
Data Cleaning
     ↓
Factor Construction
     ↓
Factor Validation
     ↓
Factor Return
     ↓
IC / Rank IC
     ↓
Decay
     ↓
Turnover
     ↓
Performance Attribution
```

---

## 2. 研究方向

| 方向 | 说明 |
|------|------|
| Factor Analysis | 因子分析 |
| IC Analysis | IC 分析 |
| Rank IC | 秩相关 IC |
| Factor Return | 因子收益 |
| Factor Decay | 因子衰减 |
| Turnover | 换手率 |
| Exposure | 因子暴露 |
| Attribution | 绩效归因 |

---

## 3. 从"感觉"到"证据"

目标是把：

```text
"我觉得这个因子有效"
```

变成：

```text
统计证据
    +
历史表现
    +
风险特征
    +
交易成本
    +
稳定性
```

---

## 4. 核心模块

| 模块 | 说明 |
|------|------|
| `services/risk_intelligence` | 风险智能 |
| `services/attribution` | 绩效归因 |
| `apps/` 研究相关 | 研究流程支撑 |
| Alpha / Factor 相关 | 因子构造与评估 |

---

## 5. 研究结论的可交付形态

```text
因子定义
    +
历史表现（IC / Rank IC / 衰减 / 换手）
    +
风险特征（暴露 / 回撤 / 尾部）
    +
交易成本（费用 / 滑点）
    +
稳定性（样本外 / 稳健性）
```

---

## 6. 相关文档

- 研究工作流：[../06-research/QUANT_RESEARCH_WORKFLOW.md](../06-research/QUANT_RESEARCH_WORKFLOW.md)
- 回测：[../06-research/BACKTESTING.md](../06-research/BACKTESTING.md)
- 绩效归因：[../06-research/PERFORMANCE_ATTRIBUTION.md](../06-research/PERFORMANCE_ATTRIBUTION.md)
