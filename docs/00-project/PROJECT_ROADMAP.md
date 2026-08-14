# ICYQuant Project Roadmap

> 本文档定义 ICYQuant 从"工程收口"走向"可运行产品"的路线图。

---

## 1. 阶段转换：从 Engineering Project → Trading Product

此前的开发模式是无限 Commit：

```text
Commit 1
Commit 2
...
Commit 40
Commit 41
```

**现在正式停止这种无限扩张。**

下一阶段是：

```text
ICYQuant
   │
   ├── Documentation（完成）
   ├── Deployment
   ├── Integration
   ├── Testing
   ├── Paper Trading
   └── Production Validation
```

> 除非以后真正进入新的产品版本（如 v0.5.0），否则不再以 Commit 序列方式扩张。

---

## 2. 路线图

### Phase 1：Deployment（部署）

| 任务 | 说明 |
|------|------|
| Docker 本地部署 | 使用 `docker-compose.yml` 一键拉起 api / worker / postgres / redis / kafka |
| 配置校验 | 环境变量、`configs/` 配置核对 |
| 数据库迁移 | `alembic upgrade head` |
| 健康检查 | `/health`、`/metrics` 验证 |

### Phase 2：Integration（集成）

| 任务 | 说明 |
|------|------|
| 服务联调 | Strategy → Risk → Order → Execution → Position → Ledger 全链路 |
| 事件总线验证 | Event Bus / Replay / Idempotency |
| 控制平面验证 | Kill Switch / Control Gateway / Incident |
| 治理流程验证 | 四眼审批 / 职责分离 / 决策台账 |

### Phase 3：Testing（验证）

| 任务 | 说明 |
|------|------|
| 端到端测试 | 正常交易、拒单、风控拒绝、重复事件、事件丢失、状态重建 |
| Recovery 测试 | 恢复测试的重要性不低于 Happy Path |
| 一致性测试 | 账实不一致检测与修复 |
| 压测 | API 延迟、事件处理速率、队列积压 |

### Phase 4：Paper Trading（模拟交易）

| 任务 | 说明 |
|------|------|
| 测试数据接入 | 历史行情 / 合成数据 |
| 模拟行情 | Market Data → Strategy 全链路 |
| 模拟执行 | Execution Simulator |
| 记账验证 | Ledger / Position / PnL 一致性 |

### Phase 5：Production Validation（生产验证）

| 任务 | 说明 |
|------|------|
| 真实行情 | 接入真实行情源 |
| 策略接入 | 真实策略上线 |
| 小资金验证 | 最小化资金实测 |
| 生产评审 | 独立评审 + 合规 + 安全清单 |

---

## 3. 明确不做的事

- 不继续按 Commit 序列无限扩张功能
- 不承诺实盘盈利
- 不跳过验证阶段直接上线

---

## 4. 里程碑定义

| 里程碑 | 完成标准 |
|--------|----------|
| M1 部署 | Docker 本地可运行，健康检查通过 |
| M2 集成 | 全链路事件打通，幂等验证通过 |
| M3 验证 | E2E + Recovery 测试通过 |
| M4 Paper | 模拟交易周期运行，账实一致 |
| M5 生产 | 小资金实盘验证 + 独立评审通过 |

---

## 5. 相关文档

- 项目状态：[PROJECT_STATUS.md](./PROJECT_STATUS.md)
- 项目范围：[PROJECT_SCOPE.md](./PROJECT_SCOPE.md)
- 部署文档：[../03-operations/DEPLOYMENT.md](../03-operations/DEPLOYMENT.md)
- 最终发布检查清单：[../07-release/FINAL_RELEASE_CHECKLIST.md](../07-release/FINAL_RELEASE_CHECKLIST.md)
