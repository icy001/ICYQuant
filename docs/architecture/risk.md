# Risk Management Architecture

## Overview

The Risk service performs risk checks on orders before execution to ensure compliance with risk limits.

## Components

### RiskEngine

- Subscribes to ORDER_CREATED events
- Performs risk validation (e.g., quantity limits)
- Publishes RISK_CHECKED and ORDER_APPROVED/ORDER_REJECTED events

## Risk Rules

- **Quantity Limit**: Orders exceeding 1000 units are rejected

## Flow

1. ORDER_CREATED event received
2. RiskEngine evaluates order against rules
3. Publishes RISK_CHECKED with approval status
4. Publishes ORDER_APPROVED or ORDER_REJECTED
