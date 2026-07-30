# ICYQuant 部署指南

> Docker、Kubernetes、Helm、配置管理与多集群部署

## 目录

- [Docker 部署](#docker-部署)
- [Kubernetes 部署](#kubernetes-部署)
- [Helm Charts](#helm-charts)
- [配置管理](#配置管理)
- [环境设置](#环境设置)
- [资源要求](#资源要求)
- [多集群部署](#多集群部署)
- [灾难恢复](#灾难恢复)

---

## Docker 部署

### 单容器部署

适用于开发测试。

#### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir .

COPY . .

CMD [\
    "uvicorn",\
    "apps.api.main:app",\
    "--host",\
    "0.0.0.0",\
    "--port",\
    "8000"\
]
```

#### 构建与运行

```bash
# 构建镜像
docker build -t icyquant:0.4.0 .

# 运行容器
docker run -d \
  --name icyquant \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://icyquant:password@postgres:5432/icyquant \
  -e REDIS_URL=redis://redis:6379 \
  icyquant:0.4.0

# 查看日志
docker logs -f icyquant

# 停止容器
docker stop icyquant
```

### Docker Compose 部署

适用于单机生产环境。

#### docker-compose.yml

```yaml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: icyquant-api
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      kafka:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://icyquant:${DB_PASSWORD}@postgres:5432/icyquant
      REDIS_URL: redis://redis:6379
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      JWT_SECRET: ${JWT_SECRET}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    command: >
      bash -c "
      alembic upgrade head &&
      uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --workers 4
      "
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 4G
        reservations:
          cpus: "500m"
          memory: 1G
    logging:
      driver: json-file
      options:
        max-size: "100m"
        max-file: "5"
    networks:
      - icyquant-net

  worker:
    build:
      context: .
    container_name: icyquant-worker
    command: python -m services.worker
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://icyquant:${DB_PASSWORD}@postgres:5432/icyquant
      REDIS_URL: redis://redis:6379
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: "2"
          memory: 4G
    networks:
      - icyquant-net

  postgres:
    image: postgres:16
    container_name: icyquant-postgres
    environment:
      POSTGRES_USER: icyquant
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: icyquant
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_v1_schema.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U icyquant"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - icyquant-net

  redis:
    image: redis:7-alpine
    container_name: icyquant-redis
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - icyquant-net

  kafka:
    image: bitnami/kafka:latest
    container_name: icyquant-kafka
    environment:
      KAFKA_ENABLE_KRAFT: "yes"
      KAFKA_CFG_NODE_ID: "1"
      KAFKA_CFG_PROCESS_ROLES: broker,controller
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CFG_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: CONTROLLER
      ALLOW_PLAINTEXT_LISTENER: "yes"
    ports:
      - "9092:9092"
    restart: unless-stopped
    volumes:
      - kafka_data:/bitnami/kafka
    networks:
      - icyquant-net

  prometheus:
    image: prom/prometheus:latest
    container_name: icyquant-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./configs/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: unless-stopped
    networks:
      - icyquant-net

  grafana:
    image: grafana/grafana:latest
    container_name: icyquant-grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped
    networks:
      - icyquant-net

volumes:
  postgres_data:
  redis_data:
  kafka_data:
  prometheus_data:
  grafana_data:

networks:
  icyquant-net:
    driver: bridge
```

#### 启动

```bash
# 启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f api

# 停止所有服务
docker compose down

# 清理所有数据（慎用）
docker compose down -v
```

---

## Kubernetes 部署

### 命名空间与 RBAC

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: icyquant
  labels:
    app.kubernetes.io/part-of: icyquant
    pod-security.kubernetes.io/enforce: restricted
---
# rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: icyquant-sa
  namespace: icyquant
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: icyquant-role
  namespace: icyquant
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list"]
  - apiGroups: ["metrics.k8s.io"]
    resources: ["pods", "nodes"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: icyquant-role-binding
  namespace: icyquant
subjects:
  - kind: ServiceAccount
    name: icyquant-sa
    namespace: icyquant
roleRef:
  kind: Role
  name: icyquant-role
  apiGroup: rbac.authorization.k8s.io
```

### 部署 API 网关

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: icyquant-api
  namespace: icyquant
  labels:
    app: icyquant-api
    version: v0.4.0
spec:
  replicas: 5
  selector:
    matchLabels:
      app: icyquant-api
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: icyquant-api
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
    spec:
      serviceAccountName: icyquant-sa
      containers:
        - name: api
          image: ghcr.io/icyquant/api:0.4.0
          ports:
            - containerPort: 8080
              name: http
            - containerPort: 9090
              name: metrics
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: icyquant-db-secret
                  key: url
            - name: REDIS_URL
              value: redis://icyquant-redis:6379
            - name: JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: icyquant-auth-secret
                  key: jwt_secret
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 2
              memory: 4Gi
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: config
              mountPath: /app/config
      volumes:
        - name: tmp
          emptyDir: {}
        - name: config
          configMap:
            name: icyquant-config
      nodeSelector:
        kubernetes.io/os: linux
      tolerations: []
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    app: icyquant-api
                topologyKey: kubernetes.io/hostname
---
# api-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: icyquant-api
  namespace: icyquant
spec:
  selector:
    app: icyquant-api
  ports:
    - port: 8080
      targetPort: 8080
      name: http
    - port: 9090
      targetPort: 9090
      name: metrics
  type: ClusterIP
```

### Ingress 配置

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: icyquant-ingress
  namespace: icyquant
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.cors: "true"
    nginx.ingress.cors-allow-origin: "https://*.icyquant.io"
    nginx.ingress.cors-allow-credentials: "true"
    nginx.ingress.cors-allow-headers: "Authorization,Content-Type"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.icyquant.io
      secretName: icyquant-tls
  rules:
    - host: api.icyquant.io
      http:
        paths:
          - path: /api/v1
            pathType: Prefix
            backend:
              service:
                name: icyquant-api
                port:
                  number: 8080
          - path: /ws
            pathType: Prefix
            backend:
              service:
                name: icyquant-api
                port:
                  number: 8080
    - host: ai.icyquant.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: icyquant-ai
                port:
                  number: 8081
    - host: metrics.icyquant.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: prometheus
                port:
                  number: 9090
```

### HPA 自动伸缩

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: icyquant-api-hpa
  namespace: icyquant
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: icyquant-api
  minReplicas: 5
  maxReplicas: 50
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 75
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
```

---

## Helm Charts

### 添加 Helm 仓库

```bash
helm repo add icyquant https://charts.icyquant.io
helm repo update
helm search repo icyquant
```

### 安装

```bash
# 默认安装
helm install icyquant icyquant/icyquant \
  --namespace icyquant \
  --create-namespace

# 自定义 values 安装
helm install icyquant icyquant/icyquant \
  --namespace icyquant \
  -f custom-values.yaml
```

### 升级

```bash
helm upgrade icyquant icyquant/icyquant \
  --namespace icyquant \
  -f custom-values.yaml
```

### 回滚

```bash
# 查看历史版本
helm history icyquant --namespace icyquant

# 回滚到指定版本
helm rollback icyquant <version> --namespace icyquant
```

### 卸载

```bash
helm uninstall icyquant --namespace icyquant
```

### Values 配置参考

```yaml
# values-prod.yaml
global:
  environment: production
  imageRegistry: ghcr.io/icyquant
  imagePullPolicy: IfNotPresent
  serviceMesh:
    enabled: true
    provider: istio
  observability:
    enabled: true
    tracing: true
    metrics: true
    logging: true

api:
  replicaCount: 5
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 50
    targetCPUUtilization: 70
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2
      memory: 4Gi

ai:
  replicaCount: 3
  gpu:
    enabled: true
    model: nvidia-t4
    count: 1
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetGPUUtilization: 80
  resources:
    requests:
      cpu: 1
      memory: 4Gi
      nvidia.com/gpu: 1
    limits:
      cpu: 4
      memory: 16Gi
      nvidia.com/gpu: 1

risk:
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilization: 60

redis:
  enabled: true
  architecture: replication
  auth:
    enabled: true
  master:
    persistence:
      enabled: true
      size: 50Gi
  replica:
    replicaCount: 2
    persistence:
      enabled: true
      size: 50Gi

postgresql:
  enabled: true
  primary:
    persistence:
      enabled: true
      size: 500Gi
  replication:
    enabled: true
    replicaCount: 2
    persistence:
      enabled: true
      size: 500Gi

kafka:
  enabled: true
  replicas: 3
  kraft:
    enabled: true

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
  hosts:
    - host: api.icyquant.io
      paths:
        - path: /api/v1
          pathType: Prefix
          service: api

prometheus:
  enabled: true
  server:
    persistentVolume:
      size: 100Gi
    retention: 30d

grafana:
  enabled: true
  persistence:
    enabled: true
    size: 10Gi

jaeger:
  enabled: true

istio:
  enabled: true
```

---

## 配置管理

### 配置文件结构

```
configs/
├── environments/
│   ├── production.yaml
│   ├── staging.yaml
│   └── development.yaml
├── database/
│   └── postgres.yaml
├── redis/
│   └── redis.yaml
├── kafka/
│   └── kafka.yaml
├── monitoring/
│   ├── prometheus.yml
│   └── grafana-dashboards.yaml
├── security/
│   ├── rbac.yaml
│   └── secrets.yaml
└── trading/
    ├── exchanges.yaml
    └── risk-limits.yaml
```

### 环境配置示例

```yaml
# configs/environments/production.yaml
environment:
  name: production
  level: critical

database:
  host: postgres-primary
  port: 5432
  name: icyquant
  pool_size: 50
  max_overflow: 20
  ssl_mode: require

redis:
  hosts:
    - redis://redis-1:6379
    - redis://redis-2:6379
    - redis://redis-3:6379
  password: ${REDIS_PASSWORD}
  db: 0
  max_connections: 1000

kafka:
  bootstrap_servers:
    - kafka-1:9092
    - kafka-2:9092
    - kafka-3:9092
  consumer_group: icyquant-consumer
  topics:
    orders:
      name: orders
      partitions: 32
      replication_factor: 3
    market_data:
      name: market-data
      partitions: 64
      replication_factor: 3

trading:
  exchanges:
    binance:
      enabled: true
      api_key: ${BINANCE_API_KEY}
      api_secret: ${BINANCE_API_SECRET}
      testnet: false
    alpaca:
      enabled: true
      api_key: ${ALPACA_API_KEY}
      api_secret: ${ALPACA_API_SECRET}
      paper: false

risk:
  max_drawdown: 0.15
  max_leverage: 5.0
  position_limit: 0.30
  daily_loss_limit: 0.05
  circuit_breaker_threshold: 0.10

security:
  jwt_secret: ${JWT_SECRET}
  jwt_expiry: 28800
  encryption_key: ${ENCRYPTION_KEY}
  tls_enabled: true

observability:
  log_level: INFO
  metrics_enabled: true
  tracing_enabled: true
  tracing_sample_rate: 0.1
```

### Kubernetes ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: icyquant-config
  namespace: icyquant
data:
  environment.yaml: |
    environment:
      name: production
    database:
      host: postgres-primary
      port: 5432
      name: icyquant
      pool_size: 50
    redis:
      hosts:
        - redis://redis-1:6379
      password: ${REDIS_PASSWORD}
    kafka:
      bootstrap_servers:
        - kafka-1:9092
    trading:
      risk:
        max_drawdown: 0.15
        max_leverage: 5.0
    security:
      jwt_expiry: 28800
      tls_enabled: true
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    scrape_configs:
      - job_name: 'icyquant'
        static_configs:
          - targets:
              - 'icyquant-api:9090'
              - 'icyquant-ai:9090'
              - 'icyquant-risk:9090'
        scheme: https
        tls_config:
          cert_file: /certs/client.crt
          key_file: /certs/client.key
```

### Kubernetes Secret

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: icyquant-db-secret
  namespace: icyquant
type: Opaque
stringData:
  url: "postgresql://icyquant:password@postgres:5432/icyquant"
  password: "your-secure-password"
---
apiVersion: v1
kind: Secret
metadata:
  name: icyquant-auth-secret
  namespace: icyquant
type: Opaque
stringData:
  jwt_secret: "your-256-bit-jwt-secret"
  encryption_key: "your-aes-256-encryption-key"
  oauth2_client_secret: "your-oauth2-client-secret"
```

### 密钥轮换

```bash
# 使用 sealed secrets
kubeseal --format=yaml --cert=pub-cert.pem < secret.yaml > sealed-secret.yaml

# 更新密钥
kubectl create secret generic icyquant-auth-secret \
  --from-literal=jwt_secret=new-secret \
  --dry-run=client -o yaml | kubectl apply -f -

# 滚动重启
kubectl rollout restart deployment icyquant-api -n icyquant
```

---

## 环境设置

### 环境变量

#### 必需变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `DATABASE_URL` | PostgreSQL 连接 URL | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | Redis 连接 URL | `redis://host:6379` |
| `JWT_SECRET` | JWT 签名密钥 | 256 位随机字符串 |
| `ENCRYPTION_KEY` | 数据加密密钥 | AES-256 密钥 |

#### 可选变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka 地址 | - |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `ENVIRONMENT` | 环境标识 | `production` |
| `BINANCE_API_KEY` | Binance API Key | - |
| `BINANCE_API_SECRET` | Binance API Secret | - |
| `ALPACA_API_KEY` | Alpaca API Key | - |
| `ALPACA_API_SECRET` | Alpaca API Secret | - |

### 初始化脚本

```bash
# 数据库迁移
alembic upgrade head

# 创建管理员账户
icyquant init-admin --username admin --password <password>

# 创建默认风控规则
icyquant init-risk-rules

# 验证环境
icyquant env-check
```

---

## 资源要求

### 最低要求（单节点测试）

| 资源 | 规格 |
|------|------|
| CPU | 4 核 |
| 内存 | 8 GB |
| 存储 | 50 GB SSD |
| 网络 | 100 Mbps |

### 生产推荐配置

#### API 网关

| 资源 | 开发 | 生产 |
|------|------|------|
| CPU/副本 | 500m | 500m - 2 |
| 内存/副本 | 1Gi | 1Gi - 4Gi |
| 副本数 | 1 | 5-50 |

#### AI 服务

| 资源 | 开发 | 生产 |
|------|------|------|
| CPU/副本 | 1 | 1 - 4 |
| 内存/副本 | 4Gi | 4Gi - 16Gi |
| GPU/副本 | 可选 | 1x T4/A10 |
| 副本数 | 1 | 3-20 |

#### 数据库

| 资源 | 开发 | 生产 |
|------|------|------|
| CPU | 2 | 4 - 16 |
| 内存 | 4Gi | 16Gi - 64Gi |
| 存储 | 50GB | 500GB NVMe |
| 连接池 | 50 | 200 |

#### Redis

| 资源 | 开发 | 生产 |
|------|------|------|
| 架构 | 单节点 | 3 主 3 从 |
| 内存 | 256MB | 32GB |
| 存储 | - | 100GB |

#### Kafka

| 资源 | 开发 | 生产 |
|------|------|------|
| 架构 | 单节点 | 3 节点 KRaft |
| 存储 | 10GB | 1TB |

### 容量规划

```
日交易量 × 平均订单大小 = 每日数据量
每日数据量 × 30 天 = 月度数据量
月度数据量 × 12 月 = 年度数据量
年度数据量 × 3 = 数据保留总量

示例：
10,000 笔/日 × 1KB/订单 = 10MB/日
10MB × 30 = 300MB/月
300MB × 12 = 3.6GB/年
3.6GB × 3 = 10.8GB 存储
```

---

## 多集群部署

### 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        全局负载均衡                                  │
│                    (DNS / GeoIP / Anycast)                           │
└──────────┬──────────────────┬──────────────────────────────────────┘
           │                  │
           ▼                  ▼
┌───────────────────┐  ┌───────────────────┐
│   主集群 (Region)  │  │  备用集群 (Region) │
│   us-east-1       │  │  eu-west-1       │
│                   │  │                   │
│  ┌─────────────┐  │  │  ┌─────────────┐  │
│  │  API x5     │  │  │  │  API x5     │  │
│  │  AI  x3     │  │  │  │  AI  x3     │  │
│  │  Risk x3    │  │  │  │  Risk x3    │  │
│  └─────────────┘  │  │  └─────────────┘  │
│                   │  │                   │
│  ┌─────────────┐  │  │  ┌─────────────┐  │
│  │  PostgreSQL  │  │  │  │  PostgreSQL  │  │
│  │  (主从)      │  │  │  │  (主从)      │  │
│  └─────────────┘  │  │  └─────────────┘  │
│                   │  │                   │
│  ┌─────────────┐  │  │  ┌─────────────┐  │
│  │  Redis Cluster│ │  │  │  Redis Cluster│ │
│  └─────────────┘  │  │  └─────────────┘  │
└───────────────────┘  └───────────────────┘
           │                  │
           ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        跨集群同步                                    │
│  PostgreSQL 流式复制 · Redis 集群同步 · Kafka MirrorMaker             │
└─────────────────────────────────────────────────────────────────────┘
```

### 主从集群配置

#### PostgreSQL 流式复制

```yaml
# postgres-primary.yaml
apiVersion: v1
kind: Pod
metadata:
  name: postgres-primary
  annotations:
    postgres.primary: "true"
spec:
  containers:
    - name: postgres
      image: postgres:16
      env:
        - name: POSTGRES_REPLICATION_ROLE
          value: primary
        - name: WAL_LEVEL
          value: replica
        - name: MAX_WAL_SENDERS
          value: "10"
```

#### Redis 跨区域同步

```yaml
# redis-sync.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-sync-config
data:
  redis.conf: |
    # 主从复制
    replicaof master-host 6379
    masterauth ${REDIS_PASSWORD}
    
    # 跨集群同步
    # 使用 Redis CRDT 或自定义同步
```

#### Kafka MirrorMaker

```yaml
# kafka-mirror.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka-mirror-maker
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: mirror-maker
          image: bitnami/kafka:latest
          command:
            - /opt/bitnami/kafka/bin/connect-distributed.sh
          env:
            - name: KAFKA_CFG_BOOTSTRAP_SERVERS
              value: "kafka-primary:9092,kafka-secondary:9092"
            - name: KAFKA_CFG_REPLICATION_FACTOR
              value: "3"
```

### 流量切换

```bash
# DNS 权重切换
# Route53 配置主备权重
aws route53 change-resource-record-sets \
  --hosted-zone-id ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.icyquant.io",
        "Type": "A",
        "SetIdentifier": "primary",
        "Weight": 80,
        "ResourceRecords": [{"Value": "PRIMARY_IP"}],
        "TTL": 60
      }
    }]
  }'

# 备用集群切换权重到 0
aws route53 change-resource-record-sets \
  --hosted-zone-id ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.icyquant.io",
        "Type": "A",
        "SetIdentifier": "secondary",
        "Weight": 0,
        "ResourceRecords": [{"Value": "SECONDARY_IP"}],
        "TTL": 60
      }
    }]
  }'
```

---

## 灾难恢复

### DR 策略

| 场景 | RPO | RTO | 策略 |
|------|-----|-----|------|
| 单服务故障 | 0 | < 1 分钟 | 自动重启/HPA |
| 单节点故障 | 0 | < 5 分钟 | Pod 迁移 |
| 数据中心故障 | < 5 分钟 | < 30 分钟 | 跨集群故障转移 |
| 区域故障 | < 15 分钟 | < 1 小时 | 备用区域激活 |

### 灾难恢复计划

#### 1. 服务恢复

```bash
# 重启单个服务
kubectl rollout restart deployment icyquant-api -n icyquant

# 重建 Pod
kubectl delete pod -l app=icyquant-api -n icyquant

# 扩展服务
kubectl scale deployment icyquant-api -n icyquant --replicas=10
```

#### 2. 数据库恢复

```bash
# PostgreSQL 主从切换
# 步骤 1: 提升从库为主库
pg_ctl promote -D /var/lib/postgresql/data

# 步骤 2: 重新建立主从关系
# 在新主库上
SELECT pg_create_physical_replication_slot('replica_slot');
# 在旧主库上
pg_basebackup -h new-primary -U replicator -D /var/lib/postgresql/data

# 步骤 3: 重建应用连接
kubectl set env deployment icyquant-api \
  DATABASE_URL="postgresql://user:pass@new-primary:5432/db" \
  -n icyquant
kubectl rollout restart deployment icyquant-api -n icyquant
```

#### 3. 数据恢复

```bash
# 从备份恢复
pg_restore -h postgres -U icyquant -d icyquant backup-20260730.dump

# 增量恢复 (WAL replay)
pg_waldump /backups/wal/ -start 2026-07-30T10:00:00 -end 2026-07-30T12:00:00

# Redis 数据恢复
cp /backups/redis/dump.rdb /var/lib/redis/dump.rdb
redis-cli shutdown
redis-server /etc/redis/redis.conf

# 数据验证
# 对比主从数据一致性
SELECT count(*) FROM orders;
SELECT count(*) FROM positions;
SELECT count(*) FROM trades;
```

#### 4. 区域故障转移

```bash
# 1. 激活备用区域
kubectl config use-context secondary-cluster

# 2. 部署服务
helm install icyquant icyquant/icyquant \
  --namespace icyquant \
  -f values-secondary.yaml

# 3. 切换 DNS
# 将流量指向备用区域

# 4. 验证服务
curl https://secondary.icyquant.io/health

# 5. 主区域恢复后同步数据
# 使用 pg_basebackup 同步
rsync -av /var/lib/postgresql/data/ primary-cluster:/data/

# 6. 切回主区域
```

### 备份恢复清单

| 项目 | 频率 | 存储位置 | 保留周期 |
|------|------|----------|----------|
| PostgreSQL 全量 | 每日 | S3 备份桶 | 30 天 |
| PostgreSQL WAL | 实时 | S3 备份桶 | 7 天 |
| Redis RDB | 每小时 | 本地 + S3 | 7 天 |
| Kafka 消息 | 按主题保留 | Kafka 自身 | 7 天 |
| 配置文件 | 变更时 | Git | 永久 |
| 审计日志 | 实时 | S3 + 本地 | 90 天 |
| 应用日志 | 每日 | 本地 + S3 | 30 天 |

### DR 测试

```bash
# 每季度进行 DR 测试
# 1. 模拟单节点故障
kubectl delete node <node-name>

# 2. 模拟数据库故障
# 停止 PostgreSQL 主库
kubectl scale deployment postgres-primary --replicas=0

# 3. 执行恢复流程
# 验证 RTO 和 RPO 是否满足要求

# 4. 记录测试结果
# 更新 DR 计划
```

---

**文档版本**: 1.0
**创建日期**: 2026-07-30
**适用版本**: ICYQuant v0.4.0 GA