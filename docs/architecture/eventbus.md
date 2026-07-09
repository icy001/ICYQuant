# Event Bus Architecture

## Overview

The Event Bus provides a publish-subscribe mechanism for communication between services.

## Components

### EventPublisher

- Core event publishing component
- Manages subscribers for different event types
- Supports synchronous event delivery

### EventSubscriber

- Helper class for subscribing to events
- Wraps the publisher for simplified subscription

## Event Types

- ORDER_CREATED
- RISK_CHECKED
- ORDER_APPROVED
- ORDER_REJECTED
- ORDER_SENT
- TRADE_EXECUTED
- POSITION_CHANGED

## Usage

```python
from services.eventbus.publisher import EventPublisher
from services.contracts.events import Event, EventType

bus = EventPublisher()

def handler(event):
    print(f"Received event: {event.event_type}")

bus.subscribe(EventType.ORDER_CREATED, handler)
```
