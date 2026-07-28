# API Gateway Load Balancer

## Responsibility

Provides:

- Request routing
- Load distribution
- Health based routing
- Service scalability

## Flow


Client

|
v
Gateway

|
v
Load Balancer

|
v
Service Instance


## Future Upgrade

Production Features:

- Kubernetes Ingress
- Nginx Integration
- Envoy Proxy
- Weighted Routing
- Circuit Breaker
- Traffic Shadowing
- Canary Deployment