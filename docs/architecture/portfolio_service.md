# Portfolio Service

## Responsibility

Portfolio Service manages:

- Investment portfolio
- Strategy portfolio
- Asset allocation
- Portfolio snapshot
- Performance state

## Domain Flow


Account

|

v

Portfolio Service

|

+--> Allocation

|

+--> Snapshot

|

v

Position Service


## Portfolio Types


Investment

Strategy

Model

Simulation