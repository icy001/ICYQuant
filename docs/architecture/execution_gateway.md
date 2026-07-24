# Execution Gateway Service

## Responsibility

Execution Gateway manages:

- Broker connection
- Exchange routing
- Order execution
- Execution tracking
- Trade confirmation

## Execution Flow


Order

|

v

Execution Gateway

|

v

Broker Adapter

|

v

Execution Result

|

v

Position Update


## Adapter Design


Execution Gateway

  |

  +---- IBKR Adapter

  |

  +---- FIX Adapter

  |

  +---- Exchange Adapter