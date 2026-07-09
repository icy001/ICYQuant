# Execution Service Architecture

## Overview

The Execution service handles order routing and trade execution.

## Components

### ExecutionEngine

- Subscribes to ORDER_APPROVED events
- Publishes ORDER_SENT event
- Simulates trade execution and publishes TRADE_EXECUTED event

### Broker

Placeholder for future broker integrations (IBKR, Alpaca, etc.)

## Flow

1. ORDER_APPROVED event received
2. ExecutionEngine sends order to broker
3. Publishes ORDER_SENT event
4. Simulates trade execution
5. Publishes TRADE_EXECUTED event with trade details
