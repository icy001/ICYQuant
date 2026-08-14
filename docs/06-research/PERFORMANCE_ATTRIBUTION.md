# ICYQuant Performance Attribution

> 本文档描述 ICYQuant 的绩效归因能力。

---

## 1. 归因目的

回答：**"收益从哪里来？"**

- 因子贡献
- 行业 / 风格暴露贡献
- 选股能力 vs 配置能力
- 交易成本影响

---

## 2. 归因维度

| 维度 | 说明 |
|------|------|
| Factor Attribution | 因子归因 |
| Exposure Attribution | 暴露归因 |
| Selection / Allocation | 选股 / 配置分解 |
| Cost Attribution | 成本归因 |

---

## 3. 归因流程

```text
组合收益
    ↓
分解为因子暴露收益
    ↓
分解为选股收益
    ↓
扣除交易成本
    ↓
归因报告
```

---

## 4. 相关模块

- `services/attribution` — 绩效归因
- `services/risk_intelligence` — 风险智能

---

## 5. 研究价值

- 判断策略收益的**来源与可持续性**
- 识别依赖单一因子的风险
- 支持组合层面优化

---

## 6. 相关文档

- 量化研究工作流：[QUANT_RESEARCH_WORKFLOW.md](./QUANT_RESEARCH_WORKFLOW.md)
- 因子研究：[FACTOR_RESEARCH_WORKFLOW.md](./FACTOR_RESEARCH_WORKFLOW.md)
- 回测：[BACKTESTING.md](./BACKTESTING.md)
