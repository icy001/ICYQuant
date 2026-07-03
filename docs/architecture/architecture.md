# ICYQuant Architecture

## Business Flow

```text
User

↓

Authentication

↓

Account Service

↓

Market Data Service

↓

Order Management System (OMS)

↓

Risk Engine

↓

Execution Engine

↓

Position Service

↓

Portfolio Service
```

---

## Core Services

### Authentication

- User Login
- JWT Authentication
- Permission Management

### Account Service

- Account Information
- Cash Balance
- Available Balance

### Market Data

- Quotes
- K-Line
- Tick Data

### OMS

- Place Order
- Cancel Order
- Order Status

### Risk Engine

- Position Limit
- Daily Loss Limit
- Buying Power Check

### Execution

- Order Matching (Simulation)

### Position

- Holdings
- Average Cost
- Unrealized PnL

### Portfolio

- Total Assets
- Daily Return
- Performance Analysis
