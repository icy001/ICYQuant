# Order Service

## Responsibility

Order Service manages:

- Order creation
- Order lifecycle
- Order validation
- Order state transition
- Trading instruction management

## Order Flow


Strategy

|

v

Order Service

|

v

Execution Engine

|

v

Trade

|

v

Position


## State Machine


CREATED

|

SUBMITTED

|

ACCEPTED

|

FILLED


SUBMITTED

|

REJECTED

PARTIAL_FILLED

|

CANCELLED