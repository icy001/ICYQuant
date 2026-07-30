# ICYQuant v0.4.0-alpha1 API 冻结声明

## 概述

本声明正式宣布 ICYQuant v0.4.0-alpha1 Release Candidate 1 (RC1) 的 API 冻结。自此日期起，所有对外暴露的 API 接口进入冻结状态，确保 API 兼容性承诺得以履行。

## 冻结信息

| 项目 | 内容 |
|------|------|
| **版本号** | v0.4.0-alpha1-rc1 |
| **发布阶段** | Release Candidate 1 (RC1) |
| **冻结日期** | 2026年07月30日 00:00:00 (UTC+8) |
| **API 版本** | v1 |
| **兼容性承诺** | RC 至 GA 期间保持向后兼容 |

## 冻结的 REST API 清单

### 核心 API 端点

#### 1. 订单管理 API (`/api/v1/orders`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/orders` | POST | 🧊 已冻结 | 创建订单 |
| `/api/v1/orders/{orderId}` | GET | 🧊 已冻结 | 查询订单 |
| `/api/v1/orders/{orderId}` | PUT | 🧊 已冻结 | 修改订单 |
| `/api/v1/orders/{orderId}` | DELETE | 🧊 已冻结 | 取消订单 |
| `/api/v1/orders` | GET | 🧊 已冻结 | 查询订单列表 |
| `/api/v1/orders/{orderId}/status` | GET | 🧊 已冻结 | 查询订单状态 |

#### 2. 组合管理 API (`/api/v1/portfolio`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/portfolio` | GET | 🧊 已冻结 | 查询组合信息 |
| `/api/v1/portfolio/positions` | GET | 🧊 已冻结 | 查询持仓 |
| `/api/v1/portfolio/balance` | GET | 🧊 已冻结 | 查询资金余额 |
| `/api/v1/portfolio/pnl` | GET | 🧊 已冻结 | 查询盈亏 |
| `/api/v1/portfolio/nav` | GET | 🧊 已冻结 | 查询净值 |

#### 3. 风险管理 API (`/api/v1/risk`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/risk/check` | POST | 🧊 已冻结 | 风险检查 |
| `/api/v1/risk/limits` | GET | 🧊 已冻结 | 查询限额 |
| `/api/v1/risk/limits` | PUT | 🧊 已冻结 | 设置限额 |
| `/api/v1/risk/exposure` | GET | 🧊 已冻结 | 查询敞口 |
| `/api/v1/risk/metrics` | GET | 🧊 已冻结 | 查询风险指标 |

#### 4. 回测 API (`/api/v1/backtest`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/backtest/jobs` | POST | 🧊 已冻结 | 创建回测任务 |
| `/api/v1/backtest/jobs/{jobId}` | GET | 🧊 已冻结 | 查询回测任务 |
| `/api/v1/backtest/jobs/{jobId}/results` | GET | 🧊 已冻结 | 查询回测结果 |
| `/api/v1/backtest/jobs/{jobId}/cancel` | POST | 🧊 已冻结 | 取消回测任务 |

#### 5. 数据服务 API (`/api/v1/data`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/data/bars` | GET | 🧊 已冻结 | 查询 K 线数据 |
| `/api/v1/data/ticks` | GET | 🧊 已冻结 | 查询 Tick 数据 |
| `/api/v1/data/symbols` | GET | 🧊 已冻结 | 查询证券列表 |
| `/api/v1/data/factors` | GET | 🧊 已冻结 | 查询因子数据 |

#### 6. AI 服务 API (`/api/v1/ai`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/ai/sessions` | POST | 🧊 已冻结 | 创建 AI 会话 |
| `/api/v1/ai/sessions/{sessionId}` | GET | 🧊 已冻结 | 查询会话状态 |
| `/api/v1/ai/sessions/{sessionId}/chat` | POST | 🧊 已冻结 | 发送消息 |
| `/api/v1/ai/sessions/{sessionId}/terminate` | POST | 🧊 已冻结 | 终止会话 |

#### 7. 策略管理 API (`/api/v1/strategies`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/strategies` | GET | 🧊 已冻结 | 查询策略列表 |
| `/api/v1/strategies` | POST | 🧊 已冻结 | 创建策略 |
| `/api/v1/strategies/{strategyId}` | GET | 🧊 已冻结 | 查询策略详情 |
| `/api/v1/strategies/{strategyId}` | PUT | 🧊 已冻结 | 更新策略 |
| `/api/v1/strategies/{strategyId}` | DELETE | 🧊 已冻结 | 删除策略 |

#### 8. 用户管理 API (`/api/v1/users`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/users` | POST | 🧊 已冻结 | 创建用户 |
| `/api/v1/users/{userId}` | GET | 🧊 已冻结 | 查询用户信息 |
| `/api/v1/users/{userId}` | PUT | 🧊 已冻结 | 更新用户信息 |
| `/api/v1/users/{userId}` | DELETE | 🧊 已冻结 | 删除用户 |

#### 9. 认证授权 API (`/api/v1/auth`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/auth/login` | POST | 🧊 已冻结 | 用户登录 |
| `/api/v1/auth/logout` | POST | 🧊 已冻结 | 用户登出 |
| `/api/v1/auth/refresh` | POST | 🧊 已冻结 | 刷新令牌 |
| `/api/v1/auth/verify` | GET | 🧊 已冻结 | 验证令牌 |

#### 10. 系统监控 API (`/api/v1/monitoring`)
| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| `/api/v1/monitoring/health` | GET | 🧊 已冻结 | 健康检查 |
| `/api/v1/monitoring/metrics` | GET | 🧊 已冻结 | 查询指标 |
| `/api/v1/monitoring/status` | GET | 🧊 已冻结 | 系统状态 |

## 冻结的 SDK 清单

### 1. Python SDK (`icyquant-sdk`)

| 组件 | 版本 | 状态 | 说明 |
|------|------|------|------|
| `icyquant.client` | 0.4.0a1 | 🧊 已冻结 | 客户端核心库 |
| `icyquant.models` | 0.4.0a1 | 🧊 已冻结 | 数据模型定义 |
| `icyquant.auth` | 0.4.0a1 | 🧊 已冻结 | 认证授权模块 |
| `icyquant.orders` | 0.4.0a1 | 🧊 已冻结 | 订单管理模块 |
| `icyquant.portfolio` | 0.4.0a1 | 🧊 已冻结 | 组合管理模块 |
| `icyquant.risk` | 0.4.0a1 | 🧊 已冻结 | 风险管理模块 |
| `icyquant.backtest` | 0.4.0a1 | 🧊 已冻结 | 回测模块 |
| `icyquant.data` | 0.4.0a1 | 🧊 已冻结 | 数据服务模块 |
| `icyquant.ai` | 0.4.0a1 | 🧊 已冻结 | AI 服务模块 |

**冻结的公共接口**:
```python
# 客户端初始化
class Client:
    def __init__(self, api_key: str, endpoint: str): ...
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    
# 订单管理
class OrderClient:
    def create_order(self, order: OrderRequest) -> OrderResponse: ...
    def get_order(self, order_id: str) -> OrderResponse: ...
    def cancel_order(self, order_id: str) -> CancelResponse: ...
    
# 组合管理
class PortfolioClient:
    def get_positions(self) -> List[Position]: ...
    def get_balance(self) -> Balance: ...
    def get_pnl(self) -> PnL: ...
```

### 2. REST SDK (OpenAPI Specification)

| 项目 | 版本 | 状态 | 说明 |
|------|------|------|------|
| OpenAPI Specification | v1.0.0 | 🧊 已冻结 | REST API 规范 |
| Swagger UI | v1.0.0 | 🧊 已冻结 | API 文档界面 |
| API Examples | v1.0.0 | 🧊 已冻结 | 示例代码 |

**规范文档位置**: `docs/api/api.md`

### 3. Plugin SDK (`platform/sdk/`)

| 组件 | 版本 | 状态 | 说明 |
|------|------|------|------|
| `plugin_sdk.base` | 0.4.0a1 | 🧊 已冻结 | 插件基类 |
| `plugin_sdk.hooks` | 0.4.0a1 | 🧊 已冻结 | 钩子接口 |
| `plugin_sdk.events` | 0.4.0a1 | 🧊 已冻结 | 事件接口 |
| `plugin_sdk.config` | 0.4.0a1 | 🧊 已冻结 | 配置接口 |

**冻结的插件接口**:
```python
# 插件基类
class PluginBase(ABC):
    @abstractmethod
    def initialize(self, context: PluginContext) -> None: ...
    
    @abstractmethod
    def shutdown(self) -> None: ...
    
    def get_info(self) -> PluginInfo: ...
    
# 钩子接口
class OrderHook(ABC):
    @abstractmethod
    def before_order(self, order: Order) -> Optional[Order]: ...
    
    @abstractmethod
    def after_order(self, order: Order, result: OrderResult) -> None: ...
```

## API 兼容性承诺

### RC 到 GA 兼容性保证

ICYQuant 承诺从 RC1 到 GA 版本发布期间，保持以下兼容性：

1. **向后兼容性**: 所有 RC1 版本中的 API 将在 GA 版本中保持向后兼容
2. **响应格式**: API 响应的数据结构不会发生破坏性变更
3. **错误码**: 错误码和错误消息格式保持稳定
4. **认证方式**: 认证机制和授权模型保持不变
5. **SDK 接口**: Python SDK 和 Plugin SDK 的公共接口保持稳定

### 兼容性测试

| 测试类型 | 状态 | 说明 |
|----------|------|------|
| API 契约测试 | ✅ 已通过 | OpenAPI 规范验证 |
| SDK 兼容性测试 | ✅ 已通过 | Python SDK 接口验证 |
| 回归测试 | 🔄 进行中 | 功能回归验证 |

## 破坏性变更政策

### 严格禁止的变更

在 API 冻结期间，以下类型的变更将被严格禁止：

#### ❌ 端点变更
- 删除现有 API 端点
- 重命名 API 端点路径
- 修改 HTTP 方法

#### ❌ 请求变更
- 修改必需参数
- 删除现有参数
- 修改参数类型或格式
- 修改参数校验规则

#### ❌ 响应变更
- 修改响应数据结构
- 删除响应字段
- 修改字段类型
- 修改状态码

#### ❌ SDK 变更
- 删除公共类或函数
- 修改函数签名
- 修改类继承关系
- 修改模块结构

### 允许的非破坏性变更

以下类型的变更将被允许：

#### ✅ 新增端点
- 添加新的 API 端点
- **要求**: 新端点使用新路径，不修改现有端点

#### ✅ 新增字段
- 添加新的可选参数
- 添加新的响应字段
- **要求**: 现有客户端不受影响

#### ✅ 文档更新
- 更新 API 文档
- 添加使用示例
- **要求**: 不改变实际行为

#### ✅ Bug 修复
- 修复 API 实现缺陷
- **要求**: 使行为符合文档描述

### 例外流程

如果必须进行破坏性变更，需要：

1. **评估影响**: 分析受影响的客户端和用户
2. **发布通知**: 提前通知所有利益相关方
3. **提供迁移路径**: 提供详细的迁移指南
4. **版本控制**: 考虑引入新的 API 版本
5. **获得批准**: 需要架构委员会和产品委员会双重批准

## API 版本控制策略

### 版本命名

- **主版本**: `v1` (当前)
- **发布版本**: `v0.4.0-alpha1-rc1`
- **SDK 版本**: `0.4.0a1`

### 版本演进原则

1. **URL 版本**: 在 URL 中包含版本号 (`/api/v1/...`)
2. **语义化版本**: 遵循语义化版本规范
3. **向后兼容**: 同一主版本内保持向后兼容
4. **弃用策略**: 提前通知弃用计划，提供过渡期

### 弃用流程

| 阶段 | 时间 | 操作 |
|------|------|------|
| 通知期 | T+0 | 发布弃用通知 |
| 过渡期 | T+3 个月 | 同时支持新旧 API |
| 弃用期 | T+6 个月 | 标记为已弃用，返回警告 |
| 移除期 | T+12 个月 | 移除旧 API |

## API 质量保证

### 自动化测试

- ✅ 契约测试 (Contract Testing)
- ✅ 端到端测试 (E2E Testing)
- ✅ 性能测试 (Performance Testing)
- ✅ 安全测试 (Security Testing)

### 文档要求

- ✅ OpenAPI 规范文档
- ✅ 请求/响应示例
- ✅ 错误码说明
- ✅ 认证说明
- ✅ 速率限制说明

## 监控与告警

### API 监控指标

| 指标 | 目标 | 告警阈值 |
|------|------|----------|
| 可用性 | 99.9% | < 99.5% |
| P95 响应时间 | < 200ms | > 500ms |
| 错误率 | < 0.1% | > 1% |
| QPS | > 1000 | < 500 |

### 告警联系

| 级别 | 响应时间 | 联系方式 |
|------|----------|----------|
| P0 (严重) | 15 分钟 | oncall@icyquant.io |
| P1 (高) | 1 小时 | api-team@icyquant.io |
| P2 (中) | 4 小时 | api-team@icyquant.io |

---

## 审批签名

本 API 冻结声明经以下负责人签署确认：

### 架构负责人

```
姓名: __________________
签名: __________________
日期: __________________
```

### API 团队负责人

```
姓名: __________________
签名: __________________
日期: __________________
```

### SDK 团队负责人

```
姓名: __________________
签名: __________________
日期: __________________
```

### 发布经理

```
姓名: __________________
签名: __________________
日期: __________________
```

---

**文档版本**: 1.0  
**创建日期**: 2026-07-30  
**最后更新**: 2026-07-30  
**文档状态**: 已生效