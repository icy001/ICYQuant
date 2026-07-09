# Position Service Architecture

## Overview

The Position service tracks and manages user positions based on executed trades.

## Components

### PositionService

- Maintains position state in memory
- Subscribes to TRADE_EXECUTED events
- Updates positions based on trade direction (BUY/SELL)

## Position Calculation

For each trade event:
1. Extract symbol, quantity, and side from payload
2. Calculate signed quantity (positive for BUY, negative for SELL)
3. Update position: current_position += signed_quantity

## Usage

```python
from services.eventbus.publisher import EventPublisher
from services.position.service.position_service import PositionService

bus = EventPublisher()
position_service = PositionService(bus)

# Positions are automatically updated when trade events occur
```
