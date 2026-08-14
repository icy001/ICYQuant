# ICYQuant Strategy Engine

> 本文档描述策略引擎的职责、生命周期与信号生成机制。

---

## 1. 职责

Strategy Engine 负责策略的全生命周期管理：

```text
Load → Validate → Deploy → Run → Snapshot → Recovery
```

| 阶段 | 说明 |
|------|------|
| Load | 加载策略定义与配置 |
| Validate | 验证策略合法性（参数、依赖、风险元数据） |
| Deploy | 部署策略运行时 |
| Run | 消费行情，产生信号 |
| Snapshot | 定期快照策略状态 |
| Recovery | 从快照恢复策略状态 |

---

## 2. 信号生成

```text
Market Data → Strategy Runtime → Signal
```

信号携带：

- 策略 ID
- 方向（BUY / SELL）
- 数量
- 价格约束
- 时间戳
- 元数据（版本、标签）

---

## 3. 信号验证与订单意图

```text
Signal
    ↓
Signal Validation
    ↓
OrderIntent（订单意图）
    ↓
OrderIntentValidator
    ↓
Approved Signal
```

- `services/strategy/portfolio/order_intent_validator.py` — 订单意图验证
- 验证内容：Symbol 合法性、数量有效性、方向、约束

---

## 4. 组合决策

- `services/strategy/portfolio` — 组合层决策
- 资金分配、组合约束、订单意图组合

---

## 5. 与风险决策的衔接

```text
Approved Signal
    ↓
RiskDecisionContext
    ↓
RiskDecisionService.evaluate
    ↓
APPROVED / REJECTED
```

策略引擎不直接产生订单；信号经验证后进入风险决策，由决策结果决定是否生成订单。

---

## 6. 核心模块

| 模块 | 职责 |
|------|------|
| `services/strategy/strategy_engine.py` | 策略引擎主流程 |
| `services/strategy/portfolio` | 组合决策与订单意图 |
| `services/strategy/signal` | 信号模型与验证 |
| `services/strategy/adapter` | 策略接入适配 |

---

## 7. 相关文档

- 领域模型：[DOMAIN_MODEL.md](./DOMAIN_MODEL.md)
- 风控引擎：[RISK_ENGINE.md](./RISK_ENGINE.md)
- 订单引擎：[ORDER_ENGINE.md](./ORDER_ENGINE.md)
