# ICYQuant API Reference

> Complete API reference for ICYQuant v0.4.0-alpha1 GA

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

All API endpoints (except `/health` and `/auth/login`) require a valid JWT token in the `Authorization` header:

```
Authorization: Bearer <your-jwt-token>
```

### Obtaining a Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password"
}
```

### Response

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJub25jZSI6...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## API Endpoints

### Core API v1 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | System health check |
| `/api/v1/metrics` | GET | Prometheus metrics |
| `/api/v1/auth/login` | POST | Authenticate and obtain JWT |
| `/api/v1/auth/refresh` | POST | Refresh JWT token |
| `/api/v1/research/alpha` | POST | Run alpha factor research |
| `/api/v1/research/signals` | GET | List research signals |
| `/api/v1/ai/sessions` | POST | Create AI session |
| `/api/v1/ai/chat` | POST | AI chat completion |
| `/api/v1/backtest/run` | POST | Execute backtest job |
| `/api/v1/backtest/results/{id}` | GET | Get backtest results |
| `/api/v1/oms/orders` | POST | Submit new order |
| `/api/v1/oms/orders/{id}` | GET | Get order status |
| `/api/v1/oms/orders/{id}/cancel` | POST | Cancel order |
| `/api/v1/oms/orders/{id}/fill` | POST | Submit fill |
| `/api/v1/ems/execute` | POST | Execute order |
| `/api/v1/risk/check` | POST | Perform pre-trade risk check |
| `/api/v1/risk/limits` | GET | Get current risk limits |
| `/api/v1/risk/portfolio` | GET | Get portfolio risk metrics |
| `/api/v1/portfolio/positions` | GET | List all positions |
| `/api/v1/portfolio/pnl` | GET | Get portfolio PnL |
| `/api/v1/portfolio/nav` | GET | Get NAV history |
| `/api/v1/lakehouse/query` | POST | Execute data lake query |
| `/api/v1/observability/traces` | GET | Query distributed traces |
| `/api/v1/observability/logs` | GET | Query structured logs |
| `/api/v1/security/audit` | GET | Query security audit events |
| `/api/v1/jobs` | GET | List scheduled jobs |
| `/api/v1/jobs/{id}` | POST | Trigger job execution |

---

## Order Management Endpoints

### Submit Order

```http
POST /api/v1/oms/orders
Content-Type: application/json
Authorization: Bearer <token>

{
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "order_type": "MARKET",
  "account_id": "account-001"
}
```

### Response

```json
{
  "order_id": "ord-20260730-0001",
  "status": "SUBMITTED",
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "filled_quantity": 0,
  "created_at": "2026-07-30T10:00:00+08:00"
}
```

### Get Order Status

```http
GET /api/v1/oms/orders/{id}
Authorization: Bearer <token>
```

---

## Risk Management Endpoints

### Pre-Trade Risk Check

```http
POST /api/v1/risk/check
Content-Type: application/json
Authorization: Bearer <token>

{
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 1000,
  "price": 150.50,
  "account_id": "account-001"
}
```

### Response

```json
{
  "passed": true,
  "checks": {
    "position_limit": "PASS",
    "cash_available": "PASS",
    "order_size": "PASS",
    "portfolio_delta": "PASS"
  },
  "violations": []
}
```

### Get Risk Limits

```http
GET /api/v1/risk/limits
Authorization: Bearer <token>
```

---

## Portfolio Endpoints

### List Positions

```http
GET /api/v1/portfolio/positions
Authorization: Bearer <token>
```

### Response

```json
{
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 500,
      "avg_cost": 145.30,
      "market_value": 75250.00,
      "unrealized_pnl": 2600.00,
      "currency": "USD"
    }
  ]
}
```

### Get Portfolio PnL

```http
GET /api/v1/portfolio/pnl
Authorization: Bearer <token>
```

---

## Market Data Endpoints

### Get Market Data

```http
GET /api/v1/marketdata/{symbol}/tick
Authorization: Bearer <token>
```

### Get Historical Bars

```http
GET /api/v1/marketdata/{symbol}/bars?interval=1d&from=2026-01-01&to=2026-07-30
Authorization: Bearer <token>
```

---

## Error Codes

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication required or failed |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict |
| 422 | Unprocessable | Business logic validation failed |
| 429 | Rate Limited | Too many requests |
| 500 | Internal Server Error | Server-side error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Error Response Format

```json
{
  "error": {
    "code": "ORDER_NOT_FOUND",
    "message": "Order ord-0001 not found",
    "details": null,
    "request_id": "req-abc123"
  }
}
```

---

## Versioning

- API Version: v1
- Current Version: v0.4.0-alpha1
- OpenAPI Spec: [openapi_v0.4.0-alpha1.yaml](openapi_v0.4.0-alpha1.yaml)