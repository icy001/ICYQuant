# ICYQuant API 参考

> 完整 REST API 端点文档

## 目录

- [认证 API](#认证-api)
- [行情数据 API](#行情数据-api)
- [订单管理 API](#订单管理-api)
- [执行 API](#执行-api)
- [风控 API](#风控-api)
- [组合 API](#组合-api)
- [账户 API](#账户-api)
- [平台 API](#平台-api)

---

## 认证 API

### 登录

```
POST /api/v1/auth/login
```

**请求体：**

```json
{
  "username": "trader@example.com",
  "password": "your-password"
}
```

**成功响应 (200 OK)：**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "id": "usr_001",
    "username": "trader@example.com",
    "role": "trader",
    "permissions": ["view_positions", "create_orders"]
  }
}
```

**失败响应 (401 Unauthorized)：**

```json
{
  "detail": "Invalid credentials"
}
```

### API Key 认证

```
POST /api/v1/auth/api-key
```

**请求体：**

```json
{
  "api_key": "your-api-key",
  "api_secret": "your-api-secret"
}
```

**成功响应 (200 OK)：**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 28800
}
```

### 刷新 Token

```
POST /api/v1/auth/refresh
```

**请求体：**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**成功响应 (200 OK)：**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 28800
}
```

### 登出

```
POST /api/v1/auth/logout
```

**请求头：**

```
Authorization: Bearer <token>
```

**成功响应 (204 No Content)：** 无响应体

### 获取当前用户

```
GET /api/v1/auth/me
```

**请求头：**

```
Authorization: Bearer <token>
```

**成功响应 (200 OK)：**

```json
{
  "id": "usr_001",
  "username": "trader@example.com",
  "email": "trader@example.com",
  "role": "trader",
  "permissions": ["view_positions", "create_orders"],
  "last_login": "2026-07-30T10:30:00Z",
  "created_at": "2025-01-01T00:00:00Z"
}
```

### 列出 API Keys

```
GET /api/v1/auth/api-keys
```

**成功响应 (200 OK)：**

```json
{
  "keys": [
    {
      "id": "key_001",
      "name": "Production Key",
      "key_prefix": "sk-abc123...",
      "role": "trader",
      "created_at": "2026-07-01T00:00:00Z",
      "last_used": "2026-07-30T09:00:00Z",
      "expires_at": null
    }
  ]
}
```

### 创建 API Key

```
POST /api/v1/auth/api-keys
```

**请求体：**

```json
{
  "name": "My API Key",
  "role": "trader",
  "permissions": ["view_positions", "create_orders"],
  "expires_in_days": 90
}
```

**成功响应 (201 Created)：**

```json
{
  "id": "key_002",
  "name": "My API Key",
  "api_key": "sk-abc123def456...",
  "api_secret": "secret_xyz789...",
  "role": "trader",
  "permissions": ["view_positions", "create_orders"],
  "created_at": "2026-07-30T10:00:00Z",
  "expires_at": "2026-10-28T10:00:00Z"
}
```

### 删除 API Key

```
DELETE /api/v1/auth/api-keys/{key_id}
```

**成功响应 (204 No Content)：** 无响应体

---

## 行情数据 API

### 获取实时行情

```
GET /api/v1/market/quote/{symbol}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 交易对符号，如 `BTCUSDT` |

**成功响应 (200 OK)：**

```json
{
  "symbol": "BTCUSDT",
  "price": 67234.50,
  "change_24h": 1234.50,
  "change_pct_24h": 1.87,
  "high_24h": 68500.00,
  "low_24h": 65000.00,
  "volume_24h": 12345.67,
  "quote_volume_24h": 830000000.00,
  "last_updated": "2026-07-30T10:30:00Z"
}
```

### 获取 K 线数据

```
GET /api/v1/market/candles/{symbol}
```

**查询参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `interval` | string | 是 | 时间间隔：`1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w` |
| `limit` | integer | 否 | 返回数量，默认 500，最大 1000 |
| `start` | string | 否 | 开始时间 (ISO 8601) |
| `end` | string | 否 | 结束时间 (ISO 8601) |

**请求示例：**

```
GET /api/v1/market/candles/BTCUSDT?interval=1h&limit=100
```

**成功响应 (200 OK)：**

```json
{
  "symbol": "BTCUSDT",
  "interval": "1h",
  "candles": [
    {
      "open_time": "2026-07-30T09:00:00Z",
      "open": 67100.00,
      "high": 67500.00,
      "low": 67000.00,
      "close": 67234.50,
      "volume": 1234.56,
      "quote_volume": 83000000.00,
      "trades": 5678,
      "taker_buy_volume": 700.00,
      "taker_buy_quote_volume": 47000000.00
    }
  ]
}
```

### 获取市场深度

```
GET /api/v1/market/depth/{symbol}
```

**查询参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `limit` | integer | 否 | 深度档位，默认 100，最大 500 |

**成功响应 (200 OK)：**

```json
{
  "symbol": "BTCUSDT",
  "last_updated": "2026-07-30T10:30:00Z",
  "bids": [
    {
      "price": 67234.50,
      "quantity": 0.123,
      "total": 8270.84
    }
  ],
  "asks": [
    {
      "price": 67235.00,
      "quantity": 0.456,
      "total": 30659.16
    }
  ]
}
```

### 获取资金费率

```
GET /api/v1/market/funding/{symbol}
```

**成功响应 (200 OK)：**

```json
{
  "symbol": "BTCUSDT",
  "funding_rate": 0.000100,
  "funding_time": "2026-07-30T08:00:00Z",
  "next_funding_time": "2026-07-30T16:00:00Z"
}
```

### 实时行情订阅

```
WS /api/v1/market/stream
```

**WebSocket 订阅消息：**

```json
{
  "type": "subscribe",
  "channel": "ticker",
  "symbols": ["BTCUSDT", "ETHUSDT"]
}
```

**WebSocket 推送消息：**

```json
{
  "type": "ticker",
  "symbol": "BTCUSDT",
  "data": {
    "price": 67234.50,
    "change_24h": 1234.50,
    "volume_24h": 12345.67
  },
  "timestamp": "2026-07-30T10:30:00Z"
}
```

---

## 订单管理 API

### 创建订单

```
POST /api/v1/orders
```

**请求体：**

```json
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "type": "LIMIT",
  "quantity": 0.5,
  "price": 67000.00,
  "time_in_force": "GTC",
  "stop_loss": 65000.00,
  "take_profit": 70000.00,
  "client_order_id": "my-order-001",
  "strategy_id": "strat_001",
  "metadata": {
    "reason": "dual_ma_cross"
  }
}
```

**字段说明：**

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `symbol` | string | 是 | 交易对 |
| `side` | string | 是 | `BUY` 或 `SELL` |
| `type` | string | 是 | `MARKET`, `LIMIT`, `STOP`, `STOP_MARKET` |
| `quantity` | number | 是 | 订单数量 |
| `price` | number | 否 | 限价单价格 |
| `time_in_force` | string | 否 | `GTC`, `IOC`, `FOK` |
| `stop_loss` | number | 否 | 止损价 |
| `take_profit` | number | 否 | 止盈价 |
| `client_order_id` | string | 否 | 客户端订单 ID |
| `strategy_id` | string | 否 | 关联策略 ID |
| `metadata` | object | 否 | 自定义元数据 |

**成功响应 (201 Created)：**

```json
{
  "order_id": "ord_20260730_001",
  "client_order_id": "my-order-001",
  "symbol": "BTCUSDT",
  "side": "BUY",
  "type": "LIMIT",
  "status": "PENDING",
  "quantity": 0.5,
  "filled_quantity": 0.0,
  "price": 67000.00,
  "avg_fill_price": null,
  "strategy_id": "strat_001",
  "created_at": "2026-07-30T10:00:00Z",
  "updated_at": "2026-07-30T10:00:00Z"
}
```

### 获取订单

```
GET /api/v1/orders/{order_id}
```

**成功响应 (200 OK)：**

```json
{
  "order_id": "ord_20260730_001",
  "symbol": "BTCUSDT",
  "side": "BUY",
  "type": "LIMIT",
  "status": "FILLED",
  "quantity": 0.5,
  "filled_quantity": 0.5,
  "price": 67000.00,
  "avg_fill_price": 66998.50,
  "commission": 0.0335,
  "commission_asset": "USDT",
  "strategy_id": "strat_001",
  "fills": [
    {
      "price": 66998.50,
      "quantity": 0.5,
      "commission": 0.0335,
      "timestamp": "2026-07-30T10:00:01Z"
    }
  ],
  "created_at": "2026-07-30T10:00:00Z",
  "updated_at": "2026-07-30T10:00:01Z"
}
```

### 列出订单

```
GET /api/v1/orders
```

**查询参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 按状态筛选 |
| `symbol` | string | 否 | 按交易对筛选 |
| `strategy_id` | string | 否 | 按策略筛选 |
| `from` | string | 否 | 开始时间 |
| `to` | string | 否 | 结束时间 |
| `page` | integer | 否 | 页码，默认 1 |
| `page_size` | integer | 否 | 每页数量，默认 20，最大 100 |

**成功响应 (200 OK)：**

```json
{
  "orders": [
    {
      "order_id": "ord_20260730_001",
      "symbol": "BTCUSDT",
      "side": "BUY",
      "status": "FILLED",
      "quantity": 0.5,
      "filled_quantity": 0.5,
      "price": 67000.00,
      "avg_fill_price": 66998.50,
      "created_at": "2026-07-30T10:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "pages": 8
}
```

### 取消订单

```
DELETE /api/v1/orders/{order_id}
```

**请求体：**

```json
{
  "reason": "Strategy signal reversed"
}
```

**成功响应 (200 OK)：**

```json
{
  "order_id": "ord_20260730_001",
  "status": "CANCELED",
  "cancel_reason": "Strategy signal reversed",
  "canceled_at": "2026-07-30T10:05:00Z"
}
```

### 批量取消订单

```
POST /api/v1/orders/cancel-all
```

**请求体：**

```json
{
  "symbol": "BTCUSDT",
  "reason": "Emergency risk control"
}
```

**成功响应 (200 OK)：**

```json
{
  "canceled_count": 5,
  "failed_cancellations": [],
  "canceled_at": "2026-07-30T10:05:00Z"
}
```

### 修改订单

```
PATCH /api/v1/orders/{order_id}
```

**请求体：**

```json
{
  "quantity": 1.0,
  "price": 66500.00
}
```

**成功响应 (200 OK)：**

```json
{
  "order_id": "ord_20260730_001",
  "quantity": 1.0,
  "price": 66500.00,
  "updated_at": "2026-07-30T10:10:00Z"
}
```

---

## 执行 API

### 执行策略交易

```
POST /api/v1/execution/market-order
```

**请求体：**

```json
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "quantity": 0.5,
  "strategy_id": "strat_001",
  "execution_type": "IMMEDIATE",
  "slippage_tolerance": 0.001,
  "max_participation": 0.1
}
```

**成功响应 (200 OK)：**

```json
{
  "execution_id": "exe_20260730_001",
  "order_id": "ord_20260730_001",
  "symbol": "BTCUSDT",
  "quantity": 0.5,
  "filled_quantity": 0.5,
  "avg_fill_price": 66998.50,
  "slippage": 0.00022,
  "market_impact": 0.00015,
  "execution_time": 150,
  "status": "COMPLETED"
}
```

### 算法执行

```
POST /api/v1/execution/algorithm
```

**请求体：**

```json
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "total_quantity": 10.0,
  "algorithm": "TWAP",
  "duration_minutes": 60,
  "interval_seconds": 60,
  "max_participation": 0.1,
  "strategy_id": "strat_001"
}
```

**成功响应 (202 Created)：**

```json
{
  "execution_id": "exe_20260730_algo_001",
  "algorithm": "TWAP",
  "status": "RUNNING",
  "scheduled_slices": 60,
  "completed_slices": 0,
  "total_quantity": 10.0,
  "executed_quantity": 0.0,
  "start_time": "2026-07-30T10:00:00Z",
  "expected_end_time": "2026-07-30T11:00:00Z"
}
```

### 获取执行状态

```
GET /api/v1/execution/{execution_id}
```

**成功响应 (200 OK)：**

```json
{
  "execution_id": "exe_20260730_algo_001",
  "algorithm": "TWAP",
  "status": "RUNNING",
  "total_quantity": 10.0,
  "executed_quantity": 5.2,
  "remaining_quantity": 4.8,
  "avg_fill_price": 67100.00,
  "slippage": 0.00030,
  "slices": [
    {
      "time": "2026-07-30T10:01:00Z",
      "quantity": 0.2,
      "price": 67050.00,
      "status": "FILLED"
    }
  ],
  "progress": 52.0
}
```

### 取消执行

```
DELETE /api/v1/execution/{execution_id}
```

**成功响应 (200 OK)：**

```json
{
  "execution_id": "exe_20260730_algo_001",
  "status": "CANCELED",
  "executed_quantity": 5.2,
  "remaining_quantity": 4.8,
  "canceled_at": "2026-07-30T10:30:00Z"
}
```

---

## 风控 API

### 风险检查

```
POST /api/v1/risk/check
```

**请求体：**

```json
{
  "order": {
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 1.0,
    "price": 67000.00
  },
  "portfolio_id": "pf_001",
  "context": {
    "strategy_id": "strat_001",
    "account_id": "acc_001"
  }
}
```

**成功响应 (200 OK)：**

```json
{
  "approved": true,
  "decision": "APPROVE",
  "checks": [
    {
      "rule": "position_size_limit",
      "status": "PASSED",
      "current": 0.15,
      "limit": 0.30,
      "message": "Position within limit"
    },
    {
      "rule": "max_leverage",
      "status": "PASSED",
      "current": 2.5,
      "limit": 5.0,
      "message": "Leverage within limit"
    },
    {
      "rule": "daily_loss_limit",
      "status": "PASSED",
      "current": 0.02,
      "limit": 0.05,
      "message": "Daily loss within limit"
    }
  ],
  "risk_score": 0.25,
  "checked_at": "2026-07-30T10:00:00Z"
}
```

### 获取风险仪表盘

```
GET /api/v1/risk/dashboard
```

**成功响应 (200 OK)：**

```json
{
  "portfolio_id": "pf_001",
  "risk_metrics": {
    "total_exposure": 500000.00,
    "exposure_pct": 0.65,
    "leverage": 3.2,
    "var_95": 15000.00,
    "var_99": 25000.00,
    "expected_shortfall": 20000.00,
    "max_drawdown": 0.08,
    "current_drawdown": 0.03
  },
  "limits": [
    {
      "metric": "position_size",
      "current": 0.15,
      "limit": 0.30,
      "status": "NORMAL"
    },
    {
      "metric": "leverage",
      "current": 3.2,
      "limit": 5.0,
      "status": "NORMAL"
    },
    {
      "metric": "daily_loss",
      "current": 0.03,
      "limit": 0.05,
      "status": "WARNING"
    }
  ],
  "alerts": [],
  "updated_at": "2026-07-30T10:00:00Z"
}
```

### 设置风险限额

```
PUT /api/v1/risk/limits
```

**请求体：**

```json
{
  "limits": [
    {
      "metric": "position_size",
      "value": 0.30,
      "unit": "ratio",
      "scope": "portfolio"
    },
    {
      "metric": "max_leverage",
      "value": 5.0,
      "unit": "multiple",
      "scope": "account"
    },
    {
      "metric": "daily_loss_limit",
      "value": 0.05,
      "unit": "ratio",
      "scope": "portfolio"
    }
  ]
}
```

**成功响应 (200 OK)：**

```json
{
  "updated": true,
  "limits": [
    {
      "metric": "position_size",
      "value": 0.30,
      "updated_at": "2026-07-30T10:00:00Z"
    }
  ]
}
```

### 压力测试

```
POST /api/v1/risk/stress-test
```

**请求体：**

```json
{
  "portfolio_id": "pf_001",
  "scenarios": ["market_crash", "flash_crash", "liquidity_crisis"],
  "confidence_level": 0.95
}
```

**成功响应 (200 OK)：**

```json
{
  "results": [
    {
      "scenario": "market_crash",
      "description": "Broad market decline -20%",
      "portfolio_loss": -125000.00,
      "loss_pct": -0.25,
      "var_impact": 0.15,
      "status": "EXCEEDS_LIMIT"
    },
    {
      "scenario": "flash_crash",
      "description": "Rapid 10% decline in 1 hour",
      "portfolio_loss": -80000.00,
      "loss_pct": -0.16,
      "var_impact": 0.08,
      "status": "WITHIN_LIMIT"
    }
  ],
  "summary": {
    "worst_case_loss": -125000.00,
    "var_99": 85000.00,
    "capital_adequacy": 4.2
  }
}
```

---

## 组合 API

### 获取组合概览

```
GET /api/v1/portfolio
```

**查询参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `portfolio_id` | string | 否 | 组合 ID，默认主组合 |

**成功响应 (200 OK)：**

```json
{
  "portfolio_id": "pf_001",
  "name": "Primary Portfolio",
  "currency": "USDT",
  "total_value": 1000000.00,
  "cash_balance": 350000.00,
  "positions_value": 650000.00,
  "daily_pnl": 5000.00,
  "total_pnl": 50000.00,
  "return_pct": 0.05,
  "benchmark_return": 0.03,
  "excess_return": 0.02,
  "updated_at": "2026-07-30T10:00:00Z"
}
```

### 获取持仓列表

```
GET /api/v1/portfolio/positions
```

**查询参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `symbol` | string | 否 | 按交易对筛选 |
| `portfolio_id` | string | 否 | 组合 ID |

**成功响应 (200 OK)：**

```json
{
  "positions": [
    {
      "symbol": "BTCUSDT",
      "side": "LONG",
      "quantity": 2.5,
      "avg_price": 65000.00,
      "current_price": 67234.50,
      "market_value": 168086.25,
      "unrealized_pnl": 5586.25,
      "unrealized_pnl_pct": 0.0344,
      "weight": 0.25,
      "leverage": 3.0,
      "liquidation_price": 50000.00
    },
    {
      "symbol": "ETHUSDT",
      "side": "LONG",
      "quantity": 15.0,
      "avg_price": 3200.00,
      "current_price": 3350.00,
      "market_value": 50250.00,
      "unrealized_pnl": 2250.00,
      "unrealized_pnl_pct": 0.0469,
      "weight": 0.075
    }
  ],
  "total_positions": 3
}
```

### 获取 PnL 报表

```
GET /api/v1/portfolio/pnl
```

**查询参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `from` | string | 否 | 开始日期 |
| `to` | string | 否 | 结束日期 |
| `group_by` | string | 否 | 分组维度：`day`, `week`, `month`, `symbol`, `strategy` |
| `portfolio_id` | string | 否 | 组合 ID |

**成功响应 (200 OK)：**

```json
{
  "period": {
    "from": "2026-07-01T00:00:00Z",
    "to": "2026-07-30T23:59:59Z"
  },
  "summary": {
    "total_pnl": 15000.00,
    "realized_pnl": 10000.00,
    "unrealized_pnl": 5000.00,
    "trading_pnl": 12000.00,
    "funding_pnl": 500.00,
    "commission": 500.00,
    "return_pct": 0.015
  },
  "breakdown": [
    {
      "period": "2026-07-28",
      "pnl": 3500.00,
      "trades": 25,
      "win_rate": 0.60
    },
    {
      "period": "2026-07-29",
      "pnl": 2000.00,
      "trades": 18,
      "win_rate": 0.55
    }
  ]
}
```

### 获取净值曲线

```
GET /api/v1/portfolio/nav
```

**查询参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `from` | string | 否 | 开始日期 |
| `to` | string | 否 | 结束日期 |
| `interval` | string | 否 | 采样间隔：`1d`, `1h` |
| `portfolio_id` | string | 否 | 组合 ID |

**成功响应 (200 OK)：**

```json
{
  "nav": [
    {
      "timestamp": "2026-07-28T00:00:00Z",
      "value": 1002500.00,
      "return": 0.0025,
      "drawdown": 0.0
    },
    {
      "timestamp": "2026-07-29T00:00:00Z",
      "value": 1004500.00,
      "return": 0.0045,
      "drawdown": 0.0
    }
  ],
  "statistics": {
    "start_value": 1000000.00,
    "end_value": 1005000.00,
    "total_return": 0.005,
    "annual_return": 0.06,
    "max_drawdown": 0.02,
    "sharpe_ratio": 1.5,
    "volatility": 0.08
  }
}
```

---

## 账户 API

### 获取账户信息

```
GET /api/v1/account
```

**成功响应 (200 OK)：**

```json
{
  "account_id": "acc_001",
  "user_id": "usr_001",
  "type": "TRADING",
  "status": "ACTIVE",
  "currency": "USDT",
  "total_balance": 1000000.00,
  "available_balance": 350000.00,
  "frozen_balance": 50000.00,
  "margin_balance": 600000.00,
  "unrealized_pnl": 15000.00,
  "equity": 1015000.00,
  "leverage": 1.015,
  "margin_ratio": 0.591,
  "liquidation_price": null,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-07-30T10:00:00Z"
}
```

### 获取余额

```
GET /api/v1/account/balance
```

**查询参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `asset` | string | 否 | 资产筛选，如 `BTC`, `USDT` |

**成功响应 (200 OK)：**

```json
{
  "balances": [
    {
      "asset": "USDT",
      "free": 350000.00,
      "locked": 50000.00,
      "total": 400000.00
    },
    {
      "asset": "BTC",
      "free": 0.5,
      "locked": 0.0,
      "total": 0.5
    }
  ],
  "last_updated": "2026-07-30T10:00:00Z"
}
```

### 获取账户流水

```
GET /api/v1/account/transactions
```

**查询参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `type` | string | 否 | 类型：`DEPOSIT`, `WITHDRAW`, `TRADE`, `FUNDING`, `COMMISSION` |
| `asset` | string | 否 | 资产筛选 |
| `from` | string | 否 | 开始时间 |
| `to` | string | 否 | 结束时间 |
| `page` | integer | 否 | 页码 |
| `page_size` | integer | 否 | 每页数量 |

**成功响应 (200 OK)：**

```json
{
  "transactions": [
    {
      "id": "tx_001",
      "type": "TRADE",
      "asset": "USDT",
      "amount": -33500.00,
      "balance_after": 350000.00,
      "reference": "ord_20260730_001",
      "timestamp": "2026-07-30T10:00:01Z",
      "status": "COMPLETED"
    }
  ],
  "total": 250,
  "page": 1,
  "pages": 13
}
```

### 资金划转

```
POST /api/v1/account/transfer
```

**请求体：**

```json
{
  "from_account": "acc_001",
  "to_account": "acc_002",
  "asset": "USDT",
  "amount": 10000.00,
  "memo": "Strategy allocation"
}
```

**成功响应 (200 OK)：**

```json
{
  "transaction_id": "tx_002",
  "status": "COMPLETED",
  "from_account": "acc_001",
  "to_account": "acc_002",
  "amount": 10000.00,
  "timestamp": "2026-07-30T10:00:00Z"
}
```

---

## 平台 API

### 平台状态

```
GET /api/v1/platform/status
```

**成功响应 (200 OK)：**

```json
{
  "state": "operational",
  "version": "0.4.0",
  "build": "2026.07.30",
  "uptime": "12:34:56:78",
  "environment": "production",
  "modules": {
    "api": {"status": "running", "version": "0.4.0"},
    "ai": {"status": "running", "version": "0.4.0"},
    "risk": {"status": "running", "version": "0.4.0"},
    "oms": {"status": "running", "version": "0.4.0"},
    "ems": {"status": "running", "version": "0.4.0"},
    "portfolio": {"status": "running", "version": "0.4.0"},
    "market_gateway": {"status": "running", "version": "0.4.0"}
  },
  "dependencies": {
    "postgresql": {"status": "connected", "latency_ms": 2},
    "redis": {"status": "connected", "latency_ms": 1},
    "kafka": {"status": "connected", "latency_ms": 5}
  }
}
```

### 版本信息

```
GET /api/v1/platform/version
```

**成功响应 (200 OK)：**

```json
{
  "version": "0.4.0",
  "release_date": "2026-07-30",
  "release_type": "GA",
  "supported_versions": [
    {"version": "0.4.x", "status": "current", "supported_until": "2027-07-30"},
    {"version": "0.3.x", "status": "maintenance", "supported_until": "2026-12-31"},
    {"version": "0.2.x", "status": "eol", "supported_until": "2026-06-30"}
  ],
  "changelog_url": "https://docs.icyquant.io/changelog"
}
```

### API 兼容性

```
GET /api/v1/platform/compatibility
```

**成功响应 (200 OK)：**

```json
{
  "api_version": "v1",
  "deprecated_versions": [],
  "sunset_policy": "Versions are supported for 12 months after deprecation",
  "breaking_changes": [],
  "sdk_versions": {
    "python": "0.4.0",
    "cli": "0.4.0"
  }
}
```

### 生命周期管理

```
GET /api/v1/platform/lifecycle
```

**成功响应 (200 OK)：**

```json
{
  "release_phases": [
    {"phase": "alpha", "description": "Feature development and testing"},
    {"phase": "beta", "description": "Open testing with limited features"},
    {"phase": "rc", "description": "Release candidate, production validation"},
    {"phase": "ga", "description": "General availability, production ready"},
    {"phase": "lts", "description": "Long-term support, critical fixes only"}
  ],
  "current_phase": "ga",
  "support_matrix": {
    "ga": "Full support, all features",
    "lts": "Security and critical bug fixes only"
  }
}
```

### 健康检查

```
GET /api/v1/health
```

**成功响应 (200 OK)：**

```json
{
  "status": "healthy",
  "version": "0.4.0",
  "uptime": "12:34:56",
  "timestamp": "2026-07-30T10:00:00Z"
}
```

### 组件健康检查

```
GET /api/v1/health/components
```

**成功响应 (200 OK)：**

```json
{
  "status": "healthy",
  "components": {
    "api": "healthy",
    "ai": "healthy",
    "risk": "healthy",
    "oms": "healthy",
    "ems": "healthy",
    "portfolio": "healthy",
    "market_gateway": "healthy"
  }
}
```

### 依赖健康检查

```
GET /api/v1/health/dependencies
```

**成功响应 (200 OK)：**

```json
{
  "status": "healthy",
  "dependencies": {
    "postgresql": {
      "status": "connected",
      "latency_ms": 2,
      "connections": 45,
      "max_connections": 100
    },
    "redis": {
      "status": "connected",
      "latency_ms": 1,
      "memory_used_mb": 512,
      "memory_peak_mb": 1024
    },
    "kafka": {
      "status": "connected",
      "latency_ms": 5,
      "brokers": 3,
      "under_replicated_partitions": 0
    }
  }
}
```

### 获取指标

```
GET /api/v1/metrics
```

**成功响应 (200 OK)：**

```
# HELP icyquant_requests_total Total API requests
# TYPE icyquant_requests_total counter
icyquant_requests_total{method="GET",path="/api/v1/health",status="200"} 1024
icyquant_requests_total{method="POST",path="/api/v1/orders",status="201"} 150

# HELP icyquant_request_duration_seconds Request duration
# TYPE icyquant_request_duration_seconds histogram
icyquant_request_duration_seconds_bucket{le="0.1"} 900
icyquant_request_duration_seconds_bucket{le="0.5"} 1000
icyquant_request_duration_seconds_bucket{le="1.0"} 1023
icyquant_request_duration_seconds_sum 25.5
icyquant_request_duration_seconds_count 1023

# HELP icyquant_portfolio_total_value Total portfolio value
# TYPE icyquant_portfolio_total_value gauge
icyquant_portfolio_total_value{portfolio="pf_001"} 1005000.00

# HELP icyquant_risk_alerts_total Total risk alerts
# TYPE icyquant_risk_alerts_total counter
icyquant_risk_alerts_total{level="critical"} 2
icyquant_risk_alerts_total{level="warning"} 15
```

---

**文档版本**: 1.0
**创建日期**: 2026-07-30
**适用版本**: ICYQuant v0.4.0 GA