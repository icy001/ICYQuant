# Backtest Engine Service

## Responsibility

Backtest Engine provides:

- Historical replay
- Strategy simulation
- Order simulation
- Performance evaluation

## Flow

Historical Data

  |
  v
Replay Engine

  |
  v
Strategy Runtime

  |
  v
Order Simulator

  |
  v
Backtest Result

## Future Upgrade

Production Features:

- Event Driven Backtest
- Tick Level Replay
- Transaction Cost Model
- Slippage Model
- Market Impact Model
- Walk Forward Validation
- Parameter Optimization