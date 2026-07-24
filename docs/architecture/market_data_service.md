# Market Data Service

## Responsibility

Market Data Service manages:

- Real-time quotes
- Tick streams
- Historical bars
- Market data providers
- Data caching

## Data Flow


Exchange

|

v

Market Data Provider

|

v

Market Data Service

|

+---- Strategy

|

+---- Risk Engine

|

+---- Execution Engine


## Provider Adapter


Market Data Service

  |

  +---- IBKR Adapter

  |

  +---- Bloomberg Adapter

  |

  +---- Exchange Feed