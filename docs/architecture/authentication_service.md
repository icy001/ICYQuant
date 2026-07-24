# Authentication Service


## Login Flow




Client

|

v

API Gateway

|

v

Authentication Service

|

+--> Identity Validation

|

+--> Token Generation

|

+--> Session Creation

|

v

Auth Context




## Supported Roles




Admin

Trader

Viewer




## Security Responsibilities




- Identity verification
- Token lifecycle
- Session management
- Permission validation
- Access control