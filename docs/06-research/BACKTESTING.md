# ICYQuant Backtesting

> 本文档描述 ICYQuant 的回测体系。

---

## 1. 回测目的

- 验证策略在历史数据上的表现
- 估计策略的收益、风险与成本
- 为 Paper Trading 与 Production 提供依据

---

## 2. 回测流程

```text
策略定义
    ↓
历史数据
    ↓
信号生成
    ↓
订单模拟
    ↓
成本模型（费用 + 滑点）
    ↓
绩效计算
    ↓
风险分析
    ↓
样本外验证
```

---

## 3. 回测约束

- 使用样本外数据验证（防过拟合）
- 纳入交易成本（佣金、滑点、冲击）
- 避免前视偏差 / 幸存者偏差

---

## 4. 关键指标

| 指标 | 说明 |
|------|------|
| 收益 | 总收益 / 年化收益 |
| 回撤 | 最大回撤 |
| 夏普 | 风险调整后收益 |
| 换手 | 换手率与成本影响 |
| IC / Rank IC | 预测能力 |

---

## 5. 回测到生产

```text
Backtest → Validation → Paper Trading → Production
```

禁止直接：`Idea → Live Trading`

---

## 6. 相关文档

- 量化研究工作流：[QUANT_RESEARCH_WORKFLOW.md](./QUANT_RESEARCH_WORKFLOW.md)
- 策略验证：[STRATEGY_VALIDATION.md](./STRATEGY_VALIDATION.md)
- 绩效归因：[PERFORMANCE_ATTRIBUTION.md](./PERFORMANCE_ATTRIBUTION.md)
