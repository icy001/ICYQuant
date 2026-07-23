# Centralized Logging System


## Architecture




Service A

|

Service B

|

Service C

|

v

Logger SDK

|

v

Log Pipeline

|

v

Log Storage

|

v

Monitoring




## Log Event Structure




{
service,
level,
timestamp,
correlation_id,
message,
context
}