# ICYQuant Strategy Validation

> 本文档描述 ICYQuant 的策略验证体系。

---

## 1. 验证目标

确认策略**经过严格验证**后，才允许进入交易链路。

```text
Strategy → Validation → Risk Decision → Order → ...
```

---

## 2. 验证层次

| 层次 | 说明 |
|------|------|
| 数据验证 | 数据质量、无前视偏差 |
| 回测验证 | 历史表现、成本模型 |
| 样本外验证 | 防过拟合 |
| 稳健性验证 | 参数敏感性、市场情景 |
| 风险验证 | 回撤、暴露、尾部风险 |
| 模拟验证 | Paper Trading |

---

## 3. 验证流程

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
Validation（样本外）
 ↓
Cost Model
 ↓
Risk Analysis
 ↓
Paper Trading
 ↓
Production（评审后）
```

---

## 4. 红线规则

- **禁止** `Idea → Live Trading`
- 无统计证据不进入生产
- 未纳入交易成本的结论无效
- 未通过风险分析的策略不上线

---

## 5. 生产准入

```text
回测通过
    +
样本外通过
    +
成本模型纳入
    +
风险分析通过
    +
Paper Trading 稳定
    +
独立评审
→ Production
```

---

## 6. 相关文档

- 量化研究工作流：[QUANT_RESEARCH_WORKFLOW.md](./QUANT_RESEARCH_WORKFLOW.md)
- 回测：[BACKTESTING.md](./BACKTESTING.md)
- 风控规范：[../01-product/RISK_CONTROL_SPEC.md](../01-product/RISK_CONTROL_SPEC.md)
