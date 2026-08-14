# ICYQuant Factor Research Workflow

> 本文档描述因子研究的标准流程。

---

## 1. Research Pipeline

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

## 2. 研究维度

| 维度 | 说明 |
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

## 3. 数据要求

- 数据清洗（缺失 / 异常 / 幸存者偏差）
- 明确样本区间（样本内 / 样本外）
- 一致性（复权、时区、频率）

---

## 4. 因子评估

```text
IC / Rank IC（预测能力）
    ↓
Decay（衰减速度）
    ↓
Turnover（换手成本）
    ↓
Exposure（风险暴露）
    ↓
稳定性（跨期一致性）
```

---

## 5. 结论标准

> 从"我觉得这个因子有效"变成"统计证据 + 历史表现 + 风险特征 + 交易成本 + 稳定性"。

---

## 6. 相关文档

- 量化研究工作流：[QUANT_RESEARCH_WORKFLOW.md](./QUANT_RESEARCH_WORKFLOW.md)
- 因子研究技术设计：[../02-technical/FACTOR_RESEARCH.md](../02-technical/FACTOR_RESEARCH.md)
- 回测：[BACKTESTING.md](./BACKTESTING.md)
