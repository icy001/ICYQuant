# ICYQuant 部署指南

## 1. 前置条件

### 1.1 基础设施要求

| 组件 | 最低版本 | 推荐版本 | 用途 |
|------|----------|----------|------|
| Kubernetes | 1.24 | 1.28+ | 容器编排 |
| Docker / containerd | 24+ | 25+ | 容器运行时 |
| Helm | 3.12+ | 3.14+ | 应用部署 |
| kubectl | 1.28+ | 1.30+ | 集群管理 |

### 1.2 资源需求

| 环境 | 节点数 | CPU 总量 | 内存总量 | 存储 |
|------|--------|----------|----------|------|
| Dev | 2 | 8 核 | 16 GB | 100 GB SSD |
| Staging | 4 | 32 核 | 64 GB | 500 GB SSD |
| Prod | 6-8 | 64-128 核 | 128-256 GB | 2 TB NVMe |

### 1.3 外部依赖

- **容器镜像仓库**：Harbor（自建）或云厂商 ACR/ECR/GCR
- **数据库**：PostgreSQL 15+、Redis 7+、TimescaleDB（时序数据）
- **消息队列**：Apache Kafka 3.6+、Redis Streams
- **可观测性**：Prometheus + Grafana + Loki
- **云负载均衡**：用于南北向流量入口

### 1.4 网络要求

```
┌─────────────────────────────────────────────────┐
│  外部网络                                        │
│  ┌───────────┐    ┌───────────┐                 │
│  │ WAF       │───▶│ 负载均衡器│                 │
│  └───────────┘    └─────┬─────┘                 │
│                         │                        │
└─────────────────────────┼────────────────────────┘
                          │
┌─────────────────────────┼────────────────────────┐
│  K8s 集群               │                        │
│  ┌───────────┐    ┌─────┴─────┐                 │
│  │  Ingress  │───▶│ Service   │                 │
│  └───────────┘    └─────┬─────┘                 │
│                         │                        │
│              ┌──────────┼──────────┐             │
│              ▼          ▼          ▼             │
│         交易引擎    风控引擎    AI 推理服务       │
│              │          │          │             │
│              └──────────┼──────────┘             │
│                         ▼                        │
│              ┌─────────────────────┐             │
│              │   ConfigMap / Secret │             │
│              └─────────────────────┘             │
└────────────────────────────────────────────────────┘
```

### 1.5 安全要求

- 所有容器镜像必须签名（Cosign/Notary）
- RBAC 必须最小权限原则
- 网络策略：命名空间隔离，东西向流量加密（mTLS）
- Pod 安全策略：运行时非 root 用户，只读文件系统

---

## 2. 部署架构概览

### 2.1 系统分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    接入层 (Ingress)                       │
│  Nginx Ingress Controller / Istio Gateway               │
├─────────────────────────────────────────────────────────┤
│                    API 网关层                             │
│  api-gateway (Spring Cloud Gateway)                      │
├─────────────────────────────────────────────────────────┤
│                    业务服务层                             │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │
│  │ 交易引擎     │ │ 风控引擎     │ │ AI 推理服务     │  │
│  └──────────────┘ └──────────────┘ └────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │
│  │ 行情服务     │ │ 账户服务     │ │ 订单服务        │  │
│  └──────────────┘ └──────────────┘ └────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                    数据层                                │
│  PostgreSQL | TimescaleDB | Redis | Kafka               │
├─────────────────────────────────────────────────────────┤
│                    可观测性层                             │
│  Prometheus | Grafana | Loki | Alertmanager              │
└─────────────────────────────────────────────────────────┘
```

### 2.2 部署拓扑

- **Region 1 (Active)**：华东1（杭州）—— 主交易节点
- **Region 2 (Standby)**：华北2（北京）—— 热备节点
- **区域间通信**：专线/VPN，双向同步
- **DNS 策略**：主备切换通过 DNS 权重或 GSLB

---

## 3. 环境设置

### 3.1 环境规划

| 环境 | 命名空间 | 域名 | 用途 | 数据隔离 |
|------|----------|------|------|----------|
| Dev | icyquant-dev | dev.icyquant.io | 开发调试 | 独立数据库 |
| Staging | icyquant-stg | stg.icyquant.io | 预发布验证 | 生产数据脱敏副本 |
| Prod | icyquant-prod | api.icyquant.io | 生产交易 | 物理隔离 |

### 3.2 集群初始化

```bash
# 克隆基础设施仓库
git clone git@gitlab.company.com:devops/icyquant-infra.git
cd icyquant-infra

# Dev 环境初始化
kustomize build overlays/dev | kubectl apply -f -

# Staging 环境初始化
kustomize build overlays/staging | kubectl apply -f -

# Prod 环境初始化（需双人复核）
kustomize build overlays/prod | kubectl apply --dry-run=server -f -
# 确认无误后执行
kustomize build overlays/prod | kubectl apply -f -
```

### 3.3 命名空间与 RBAC

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: icyquant-prod
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: icyquant-quota
  namespace: icyquant-prod
spec:
  hard:
    requests.cpu: "64"
    requests.memory: "256Gi"
    limits.cpu: "128"
    limits.memory: "512Gi"
    persistentvolumeclaims: "20"
    pods: "100"
```

### 3.4 网络策略

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: icyquant-default-deny
  namespace: icyquant-prod
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: monitoring
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - port: 53
          protocol: UDP
        - port: 53
          protocol: TCP
```

---

## 4. Helm Chart 部署步骤

### 4.1 Chart 结构

```
helm/
├── Chart.yaml
├── values.yaml
├── values-dev.yaml
├── values-staging.yaml
├── values-prod.yaml
└── templates/
    ├── _helpers.tpl
    ├── configmap.yaml
    ├── secret.yaml
    ├── deployment.yaml
    ├── hpa.yaml
    ├── service.yaml
    ├── ingress.yaml
    ├── serviceaccount.yaml
    ├── pdb.yaml
    └── networkpolicy.yaml
```

### 4.2 Values 配置示例（生产）

```yaml
# values-prod.yaml
global:
  imageRegistry: "harbor.company.com/icyquant"
  imagePullPolicy: IfNotPresent
  imagePullSecrets:
    - name: regcred
  namespace: icyquant-prod

app:
  replicas: 6
  strategy: RollingUpdate
  maxUnavailable: 1
  maxSurge: 1
  containerPort: 8080
  resources:
    requests:
      cpu: "4"
      memory: "8Gi"
    limits:
      cpu: "8"
      memory: "16Gi"
  livenessProbe:
    httpGet:
      path: /actuator/health/liveness
      port: 8080
    initialDelaySeconds: 60
    periodSeconds: 10
    timeoutSeconds: 5
    failureThreshold: 6
  readinessProbe:
    httpGet:
      path: /actuator/health/readiness
      port: 8080
    initialDelaySeconds: 30
    periodSeconds: 5
    failureThreshold: 3
  env:
    SPRING_PROFILES_ACTIVE: prod
    JAVA_OPTS: "-Xms6g -Xmx12g -XX:+UseG1GC -XX:MaxGCPauseMillis=200"

autoscaling:
  enabled: true
  minReplicas: 6
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

podDisruptionBudget:
  minAvailable: 4

service:
  type: ClusterIP
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
  hosts:
    - host: api.icyquant.io
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: icyquant-tls
      hosts:
        - api.icyquant.io
```

### 4.3 部署流程

```bash
# 1. 升级 Helm 仓库
helm repo add icyquant-repo https://helm.company.com/chartrepo/icyquant
helm repo update

# 2. 查看可用版本
helm search repo icyquant-repo/icyquant --versions

# 3. 预检查
helm install icyquant icyquant-repo/icyquant \
  --namespace icyquant-prod \
  --create-namespace \
  -f values-prod.yaml \
  --version 0.4.0 \
  --dry-run --debug

# 4. 执行部署（Staging 环境先测试）
helm install icyquant icyquant-repo/icyquant \
  --namespace icyquant-stg \
  -f values-staging.yaml \
  --version 0.4.0 \
  --timeout 30m

# 5. 确认 Staging 部署成功后，部署到生产
helm install icyquant icyquant-repo/icyquant \
  --namespace icyquant-prod \
  -f values-prod.yaml \
  --version 0.4.0 \
  --timeout 30m

# 6. 后续升级使用 upgrade
helm upgrade icyquant icyquant-repo/icyquant \
  --namespace icyquant-prod \
  -f values-prod.yaml \
  --version 0.4.1 \
  --timeout 30m
```

---

## 5. 配置管理

### 5.1 ConfigMap 管理

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: icyquant-config
  namespace: icyquant-prod
  labels:
    app: icyquant
data:
  application.yml: |
    spring:
      datasource:
        url: jdbc:postgresql://postgresql.default.svc:5432/icyquant
        driver-class-name: org.postgresql.Driver
      redis:
        host: redis.default.svc
        port: 6379
        sentinel:
          master: mymaster
          nodes: redis-sentinel-0:26379,redis-sentinel-1:26379,redis-sentinel-2:26379
    
    kafka:
      bootstrap-servers: kafka-0.kafka-headless:9092,kafka-1.kafka-headless:9092,kafka-2.kafka-headless:9092
      consumer:
        group-id: icyquant-group
        auto-offset-reset: latest
      producer:
        acks: all
        retries: 3
        properties:
          enable.idempotence: "true"
    
    trading:
      broker:
        type: ctp
        gateway-id: "92"
        broker-id: "9999"
      risk:
        max-daily-loss: 0.05
        max-position-value: 10000000
        max-leverage: 5
    
    ai:
      model-path: /models/latest
      inference-timeout: 500
      batch-size: 32
```

### 5.2 Secret 管理

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: icyquant-secrets
  namespace: icyquant-prod
  annotations:
    # 标识此 Secret 已由 External Secrets Operator 管理
    externalsecrets.kubernetes-client.io/provider: vault
type: Opaque
stringData:
  # 数据库凭据（示例，实际应从 Vault/External Secrets 注入）
  db-username: "ICYQUANT_PROD_DB_USER"
  db-password: "ICYQUANT_PROD_DB_PASSWORD"
  redis-password: "ICYQUANT_PROD_REDIS_PASSWORD"
  kafka-jaas-config: "ICYQUANT_PROD_KAFKA_JAAS"
  # Broker 接入凭据
  ctp-investor-id: "ICYQUANT_PROD_CTP_INVESTOR"
  ctp-password: "ICYQUANT_PROD_CTP_PASSWORD"
  ctp-auth-code: "ICYQUANT_PROD_CTP_AUTH_CODE"
  # 加密密钥
  encryption-key: "ICYQUANT_PROD_ENCRYPTION_KEY"
  jwt-secret: "ICYQUANT_PROD_JWT_SECRET"
```

#### 最佳实践

- 禁止将 Secret 明文存入 Git
- 使用 External Secrets Operator 对接 HashiCorp Vault
- Secret 轮转周期：90 天
- 最小权限：每个服务使用独立凭据

---

## 6. 数据库迁移

### 6.1 Flyway 迁移

```bash
# 迁移脚本存放路径
# db/migrations/V1__init.sql
# db/migrations/V2__create_accounts.sql
# db/migrations/V3__create_orders.sql
# db/migrations/V4__create_positions.sql

# 构建镜像时打包装迁脚本
docker build -t harbor.company.com/icyquant/migrator:0.4.0 \
  -f Dockerfile.migrator .

# 执行迁移（Job 方式）
cat <<'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: icyquant-db-migration-040
  namespace: icyquant-prod
  labels:
    app: icyquant-migration
    version: "0.4.0"
spec:
  ttlSecondsAfterFinished: 3600
  backoffLimit: 3
  template:
    spec:
      containers:
        - name: migrator
          image: harbor.company.com/icyquant/migrator:0.4.0
          command: ["flyway", "migrate"]
          env:
            - name: FLYWAY_URL
              value: "jdbc:postgresql://postgresql.default.svc:5432/icyquant"
            - name: FLYWAY_USER
              valueFrom:
                secretKeyRef:
                  name: icyquant-secrets
                  key: db-username
            - name: FLYWAY_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: icyquant-secrets
                  key: db-password
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2"
              memory: "2Gi"
      restartPolicy: Never
      serviceAccountName: icyquant-migrator
EOF

# 查看迁移状态
kubectl get job icyquant-db-migration-040 -n icyquant-prod
kubectl logs -f job/icyquant-db-migration-040 -n icyquant-prod

# 验证迁移结果
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -d icyquant -c "SELECT version, description, success FROM flyway_schema_history;"
```

### 6.2 迁移注意事项

- **停写要求**：涉及表结构变更（如 DDL）的迁移需在交易非窗口期执行
- **回滚预案**：每个迁移脚本必须提供对应的回滚 SQL
- **大表处理**：超过 100 万行的表，使用 `CREATE TABLE ... PARTITION BY` 或分批次 ALTER
- **双写切换**：对于破坏性变更，采用双写-切读-旧表下线的三步流程

---

## 7. 部署后验证

### 7.1 健康检查清单

| 检查项 | 方法 | 预期结果 |
|--------|------|----------|
| Pod 状态 | `kubectl get pods` | 所有 Pod Running，Ready 1/1 |
| 就绪探针 | `kubectl describe pod` | Readiness 成功（HTTP 200） |
| 数据库连接 | `curl /actuator/health` | DB 组件 UP |
| Redis 连接 | `curl /actuator/health` | Redis 组件 UP |
| Kafka 连接 | `curl /actuator/health` | Kafka 组件 UP |
| Broker 连接 | `curl /actuator/health` | Broker 组件 UP |
| API 可达 | `curl https://api.icyquant.io/health` | 返回 200 |
| 日志输出 | `kubectl logs deployment/icyquant` | 无 ERROR 级日志 |

### 7.2 功能验证

```bash
# 冒烟测试脚本
#!/bin/bash
set -e

BASE_URL="https://api.icyquant.io"
TOKEN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"ops","password":"***"}' | jq -r '.data.token')

echo "=== 1. 健康检查 ==="
curl -sf "$BASE_URL/actuator/health" | jq .

echo "=== 2. 行情订阅 ==="
curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/marketdata/subscribe?symbol=IC2412" | jq .

echo "=== 3. 下单测试 ==="
curl -sf -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "$BASE_URL/api/v1/orders" \
  -d '{"symbol":"IC2412","direction":"LONG","offset":"OPEN","price":5500,"volume":1}' | jq .

echo "=== 4. 查询持仓 ==="
curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/positions" | jq .

echo "=== 5. 风控检查 ==="
curl -sf -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/api/v1/risk/check" | jq .

echo "=== 全部验证通过 ==="
```

### 7.3 性能基线验证

```bash
# 使用 wrk 进行压测
wrk -t12 -c400 -d30s \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.icyquant.io/api/v1/marketdata/IC2412/tick"

# 预期指标
# - P99 延迟 < 50ms
# - QPS > 5000
# - 错误率 < 0.1%
```

---

## 8. 部署回滚流程

### 8.1 手动回滚

```bash
# 查看发布历史
helm history icyquant --namespace icyquant-prod

# 回滚到上一版本
helm rollback icyquant --namespace icyquant-prod

# 回滚到指定版本
helm rollback icyquant --namespace icyquant-prod 3

# 回滚后验证
kubectl rollout status deployment/icyquant -n icyquant-prod
kubectl get pods -n icyquant-prod -l app=icyquant
```

### 8.2 自动回滚策略

```yaml
# Argo Rollout 配置示例
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: icyquant
  namespace: icyquant-prod
spec:
  replicas: 6
  strategy:
    canary:
      steps:
        - setWeight: 10
        - pause: { duration: 30s }
        - setWeight: 30
        - pause: { duration: 30s }
        - setWeight: 50
        - pause: { duration: 60s }
        - setWeight: 100
      canaryService: icyquant-canary
      stableService: icyquant-stable
      autoRollback:
        enabled: true
        conditions:
          - type: Failed
            limit: 2
          - type: ErrorRateIncrease
            limit: 5
          - type: LatencyIncrease
            limit: 1000
  revisionHistoryLimit: 10
  rollback:
    revision: 2
    timeout: 10m
```

### 8.3 数据库回滚

```bash
# 如果迁移后需要回滚，执行 Flyway undo
kubectl exec -it job/icyquant-db-migration-prev \
  -n icyquant-prod -- flyway undo

# 或手动执行回滚 SQL
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -d icyquant -f /rollback/V4__undo.sql
```

---

## 9. 蓝绿部署策略

### 9.1 架构

```
                    ┌──────────────────────┐
                    │   API Gateway (Nginx) │
                    │   规则：/v1/* 路由    │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
     ┌─────────────────┐  ┌─────────────────┐
     │  绿色 (Blue)    │  │  蓝色 (Green)   │
     │  v0.3.x (稳定)  │  │  v0.4.x (新版本)│
     │  Service: blue  │  │  Service: green │
     └─────────────────┘  └─────────────────┘
              │                │
              ▼                ▼
     ┌─────────────────┐  ┌─────────────────┐
     │  PostgreSQL      │  │  PostgreSQL      │
     │  (只读)          │  │  (只读)         │
     └─────────────────┘  └─────────────────┘
```

### 9.2 操作流程

```bash
# 步骤 1: 部署绿色环境
helm install icyquant-green icyquant-repo/icyquant \
  --namespace icyquant-prod \
  -f values-prod-green.yaml \
  --version 0.4.0

# 步骤 2: 冒烟测试绿色环境
./scripts/smoke-test.sh https://green.icyquant.svc.cluster.local

# 步骤 3: 切换流量（通过 Ingress 注解修改后端 Service）
kubectl patch service icyquant-green -n icyquant-prod \
  -p '{"metadata":{"annotations":{"nginx.ingress.kubernetes.io/weight":"100"}}}'

kubectl patch service icyquant-blue -n icyquant-prod \
  -p '{"metadata":{"annotations":{"nginx.ingress.kubernetes.io/weight":"0"}}}'

# 步骤 4: 全量观察 30 分钟
watch kubectl get pods -n icyquant-prod -l version=green

# 步骤 5: 确认稳定后，下线蓝色环境
helm uninstall icyquant-blue --namespace icyquant-prod
kubectl delete pvc -l app=icyquant,version=blue -n icyquant-prod
```

### 9.3 蓝绿切换条件

- **API 兼容性**：新版本 API 必须向后兼容或通过双版本并行
- **流量同步**：切换期间不丢失交易订单（双写 or 队列转发）
- **回滚时间**：切换后可在 5 分钟内回滚回旧版本

---

## 10. 金丝雀部署策略

### 10.1 架构

```
                    ┌──────────────────────┐
                    │   API Gateway (Nginx) │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    │                      │
                    ▼                      ▼
           ┌─────────────────┐    ┌─────────────────┐
           │  主集群 (v0.3)  │    │  金丝雀 (v0.4)   │
           │  replicas: 5    │    │  replicas: 1     │
           │  Service: main  │    │  Service: canary │
           └─────────────────┘    └─────────────────┘
                    │                      │
                    ▼                      ▼
           ┌─────────────────────────────────────┐
           │  共享 Kafka Topic (流量镜像)         │
           └─────────────────────────────────────┘
```

### 10.2 渐进式放量

| 阶段 | 金丝雀比例 | 持续时间 | 观察指标 | 回滚触发 |
|------|-----------|----------|----------|----------|
| 1 | 5% | 15 分钟 | 错误率 < 0.1% | 错误率 > 1% |
| 2 | 15% | 30 分钟 | P99 延迟 < 100ms | P99 > 200ms |
| 3 | 30% | 30 分钟 | 资源使用正常 | CPU > 90% |
| 4 | 50% | 60 分钟 | 业务指标正常 | 订单失败率 > 2% |
| 5 | 100% | — | 全量 | — |

### 10.3 实施步骤

```bash
# 步骤 1: 部署金丝雀实例
helm install icyquant-canary icyquant-repo/icyquant \
  --namespace icyquant-prod \
  -f values-prod-canary.yaml \
  --version 0.4.0

# 步骤 2: 配置 Nginx Ingress 流量分割
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: icyquant-ingress-canary
  namespace: icyquant-prod
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "5"
    nginx.ingress.kubernetes.io/canary-by-header: "x-canary"
    nginx.ingress.kubernetes.io/canary-by-header-value: "1"
spec:
  ingressClassName: nginx
  rules:
    - host: api.icyquant.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: icyquant-canary
                port:
                  number: 8080
EOF

# 步骤 3: 动态调整比例
kubectl annotate ingress icyquant-ingress-canary \
  -n icyquant-prod \
  nginx.ingress.kubernetes.io/canary-weight="15" --overwrite

# 步骤 4: 监控看板
# Grafana Dashboard: Production/Canary Comparison
# 对比错误率、延迟、业务指标

# 步骤 5: 全量发布
kubectl patch deployment icyquant -n icyquant-prod \
  --type=json -p='[{"op":"replace","path":"/spec/template/spec/containers/0/image","value":"harbor.company.com/icyquant:0.4.0"}]'

# 步骤 6: 清理金丝雀
helm uninstall icyquant-canary --namespace icyquant-prod
kubectl delete ingress icyquant-ingress-canary -n icyquant-prod
```

---

## 附录

### A. 部署检查清单

- [ ] 所有镜像已签名并通过 Trivy 扫描
- [ ] Kubernetes 集群版本符合要求
- [ ] 数据库迁移已在 Staging 验证通过
- [ ] 配置已通过 ConfigMap + Secret 管理
- [ ] Ingress 证书有效，TLS 配置正确
- [ ] HPA 已配置，目标指标合理
- [ ] PodDisruptionBudget 已配置
- [ ] 网络策略已生效
- [ ] 监控告警已配置
- [ ] 应急预案已准备

### B. 版本矩阵

| 组件 | 版本 | 备注 |
|------|------|------|
| Kubernetes | 1.28 | 生产稳定版 |
| Helm Charts | 0.4.0 | 主应用 |
| PostgreSQL | 15.6 | 主数据库 |
| Redis | 7.2 | 缓存 |
| Kafka | 3.6 | 消息队列 |
| TimescaleDB | 2.14 | 时序数据 |

### C. 参考链接

- [Kubernetes 官方文档](https://kubernetes.io/docs/)
- [Helm 最佳实践](https://helm.sh/docs/chart_best_practices/)
- [Nginx Ingress Canary](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/#canary)
- [Argo Rollouts](https://argoproj.github.io/argo-rollouts/)
