# Service Communication Framework


## Architecture




Service A

|

Request Context

|

RPC Client

|

Service Discovery

|

Service B




## Reliability Layer




Request

↓

Timeout

↓

Retry

↓

Circuit Breaker

↓

Response