# ICYQuant Quant Research Workflow

> 本文档描述 ICYQuant 的量化研究工作流与标准。

---

## 1. 研究标准

```text
Idea
 ↓
Data
 ↓
Hypothesis
 ↓
Factor
 ↓
Backtest
 ↓
Validation
 ↓
Cost Model
 ↓
Risk Analysis
 ↓
Paper Trading
 ↓
Production
```

**禁止直接：**

```text
Idea → Live Trading
```

---

## 2. 各阶段说明

| 阶段 | 说明 |
|------|------|
| Idea | 研究假设与想法 |
| Data | 数据收集与清洗 |
| Hypothesis | 提出可检验假设 |
| Factor | 因子构造 |
| Backtest | 历史回测 |
| Validation | 样本外验证 |
| Cost Model | 交易成本建模 |
| Risk Analysis | 风险特征分析 |
| Paper Trading | 模拟交易 |
| Production | 生产上线（需评审） |

---

## 3. 研究原则

- 任何结论必须基于**统计证据**，而非主观感觉
- 必须经过样本外验证
- 必须纳入交易成本
- 必须分析风险特征（暴露 / 回撤 / 尾部）

---

## 4. 研究产出

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

## 5. 相关文档

- 因子研究工作流：[FACTOR_RESEARCH_WORKFLOW.md](./FACTOR_RESEARCH_WORKFLOW.md)
- 回测：[BACKTESTING.md](./BACKTESTING.md)
- 绩效归因：[PERFORMANCE_ATTRIBUTION.md](./PERFORMANCE_ATTRIBUTION.md)
- 策略验证：[STRATEGY_VALIDATION.md](./STRATEGY_VALIDATION.md)
