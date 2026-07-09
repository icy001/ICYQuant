# Contracts Architecture

## Overview

The Contracts module defines shared data structures and interfaces used across all services.

## Components

### Events

- **Event**: Base event model with event_id, event_type, order_id, timestamp, payload
- **EventType**: Enum defining all supported event types

### Commands

- **CreateOrderCommand**: Order creation parameters
- **CancelOrderCommand**: Order cancellation parameters
- **ExecuteOrderCommand**: Order execution parameters
- **CheckRiskCommand**: Risk check parameters

### DTOs

- **OrderDTO**: Order data transfer object
- **TradeDTO**: Trade data transfer object
- **PositionDTO**: Position data transfer object
- **CashBalanceDTO**: Cash balance data transfer object

### Responses

- **ApiResponse**: Generic API response wrapper
- **PagedResponse**: Paged API response wrapper

## Design Principles

- **Single Source of Truth**: All services reference the same contract definitions
- **Type Safety**: Pydantic models ensure data validation
- **Decoupling**: Services depend on contracts, not on each other
