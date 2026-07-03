# OMS Data Model

## Order

- order_id
- user_id
- symbol
- side (BUY / SELL)
- quantity
- price
- status
- created_at

---

## Trade

- trade_id
- order_id
- symbol
- price
- quantity
- timestamp

---

## Position

- user_id
- symbol
- quantity
- avg_price
- unrealized_pnl

---

## Account

- user_id
- cash
- available_cash
- margin
