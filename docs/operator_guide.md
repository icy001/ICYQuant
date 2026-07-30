# ICYQuant 操作手册

> 生产环境运维、监控、扩展、备份与故障恢复

## 目录

- [部署架构](#部署架构)
- [日常运维](#日常运维)
  - [监控检查](#监控检查)
  - [告警管理](#告警管理)
  - [日志查看](#日志查看)
  - [性能指标](#性能指标)
- [扩缩容](#扩缩容)
- [备份与恢复](#备份与恢复)
- [应急响应](#应急响应)
- [常见问题排查](#常见问题排查)

---

## 部署架构

### 系统架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        外部接入层                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Nginx   │  │  Istio    │  │  Cloud   │  │ WAF/DDoS │             │
│  │ Ingress  │  │ Gateway  │  │  Load Bal│  │          │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┘             │
└───────┼──────────────┼──────────────┼───────────────────────────────┘
        │              │              │
┌───────▼──────────────▼──────────────▼───────────────────────────────┐
│                        API 网关层                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    ICYQuant API Gateway (x5)                  │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────────┐  │    │
│  │  │ Auth    │ │ RateLimit│ │  Routing │ │  Middleware      │  │    │
│  │  └─────────┘ └─────────┘ └─────────┘ └──────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
        │              │              │              │
┌───────▼──────────────▼──────────────▼──────────────▼───────────────┐
│                        微服务层                                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │
│  │  AI  │ │ Risk │ │ OMS  │ │ EMS  │ │Port- │ │ Strat│ │ Rec- │     │
│  │      │ │      │ │      │ │      │ │folio │ │  _eg │ │ onc  │     │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘     │
└─────────────────────────────────────────────────────────────────────┘
        │              │              │              │
┌───────▼──────────────▼──────────────▼──────────────▼───────────────┐
│                        数据层                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │PostgreSQL│  │  Redis   │  │  Kafka   │  │Lakehouse │             │
│  │ (主从)   │  │ (集群)   │  │  (KRaft) │  │          │             │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────────┐
│                        可观测性层                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │Prometheus│  │ Grafana  │  │  Jaeger  │  │ AlertMgr │             │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### 网络拓扑

| 网段 | CIDR | 用途 | 安全级别 |
|------|------|------|----------|
| DMZ | 10.0.0.0/24 | 外部接入、Ingress | 公网可达 |
| App | 10.0.1.0/24 | 应用服务 | 仅内部 |
| Data | 10.0.2.0/24 | 数据库、缓存 | 严格限制 |
| Mgmt | 10.0.3.0/24 | 管理、监控 | 堡垒机访问 |

### 服务端口映射

| 服务 | 内部端口 | 外部暴露 | 协议 |
|------|----------|----------|------|
| API Gateway | 8080 | 443 (TLS) | HTTPS |
| AI Service | 8081 | 否 | gRPC |
| Risk Engine | 8082 | 否 | gRPC |
| Market Gateway | 8083 | 否 | WebSocket |
| Portfolio | 8084 | 否 | gRPC |
| Strategy Engine | 8085 | 否 | gRPC |
| Execution | 8086 | 否 | gRPC |
| Prometheus | 9090 | 9090 (内部) | HTTP |
| Grafana | 3000 | 3000 (内部) | HTTP |
| PostgreSQL | 5432 | 否 | TCP |
| Redis | 6379 | 否 | TCP |
| Kafka | 9092 | 否 | TCP |

---

## 日常运维

### 监控检查

#### 健康检查 API

```bash
# 全量健康检查
curl -s https://api.icyquant.io/health | jq .

# 组件健康检查
curl -s https://api.icyquant.io/health/components | jq .

# 依赖健康检查
curl -s https://api.icyquant.io/health/dependencies | jq .
```

**健康状态映射：**

| 状态 | 说明 | 操作 |
|------|------|------|
| `healthy` | 所有组件正常 | 无需操作 |
| `degraded` | 部分组件降级 | 检查降级组件 |
| `unhealthy` | 核心组件异常 | 立即响应 |
| `down` | 服务不可用 | 紧急启动预案 |

#### Kubernetes Pod 检查

```bash
# Pod 状态
kubectl get pods -n icyquant -o wide

# 异常 Pod 诊断
kubectl describe pod <pod-name> -n icyquant

# Pod 资源使用
kubectl top pods -n icyquant

# 节点状态
kubectl get nodes
kubectl top nodes
```

#### 数据库检查

```bash
# PostgreSQL 连接数
psql -h localhost -U icyquant -c "SELECT count(*) FROM pg_stat_activity WHERE state='active';"

# 数据库大小
psql -h localhost -U icyquant -c "SELECT pg_size_pretty(pg_database_size('icyquant'));"

# 慢查询
psql -h localhost -U icyquant -c "SELECT query, calls, total_time, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Redis 内存
redis-cli INFO memory

# Redis 慢查询
redis-cli SLOWLOG GET 10
```

#### Kafka 检查

```bash
# Topic 列表
kafka-topics.sh --bootstrap-server kafka:9092 --list

# Consumer Group Lag
kafka-consumer-groups.sh --bootstrap-server kafka:9092 --describe --group order-processor

# Topic 分区状态
kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic orders
```

### 告警管理

#### 告警级别

| 级别 | 响应时间 | 处理要求 | 通知方式 |
|------|----------|----------|----------|
| **P0 - Critical** | < 5 分钟 | 立即处理 | 电话 + 短信 + 邮件 |
| **P1 - High** | < 15 分钟 | 30 分钟内解决 | 短信 + 邮件 |
| **P2 - Medium** | < 1 小时 | 4 小时内解决 | 邮件 + Slack |
| **P3 - Low** | < 4 小时 | 次日解决 | 邮件 |

#### 告警规则示例

```yaml
# Alertmanager 规则
groups:
  - name: icyquant-critical
    rules:
      - alert: ServiceDown
        expr: up{job=~"icyquant-.*"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"
          description: "{{ $labels.instance }} of job {{ $labels.job }} has been down for more than 1 minute."

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is above 5% for 5 minutes."

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
        for: 10m
        labels:
          severity: high
        annotations:
          summary: "High API latency detected"

      - alert: DrawdownLimitBreach
        expr: icyquant_portfolio_drawdown > 0.15
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Portfolio drawdown exceeds limit"
```

#### 告警处理流程

```
1. 收到告警通知
   ↓
2. 确认告警有效性（避免误报）
   ↓
3. 评估影响范围
   - 单服务 / 多服务 / 全局
   - 影响用户数
   - 影响业务功能
   ↓
4. 启动应急预案
   ↓
5. 执行修复操作
   ↓
6. 验证修复效果
   ↓
7. 关闭告警
   ↓
8. 事后复盘
```

### 日志查看

#### 日志级别

| 级别 | 说明 | 生产环境 |
|------|------|----------|
| `DEBUG` | 详细调试信息 | 关闭 |
| `INFO` | 关键业务事件 | 开启 |
| `WARNING` | 警告信息 | 开启 |
| `ERROR` | 错误信息 | 开启 |
| `CRITICAL` | 严重错误 | 开启 |

#### 查看服务日志

```bash
# 实时查看 API 日志
kubectl logs -l app=icyquant-api -n icyquant --tail=100 -f

# 查看错误日志
kubectl logs -l app=icyquant-api -n icyquant --tail=500 | grep "ERROR"

# 查看特定 Pod 日志
kubectl logs <pod-name> -n icyquant --previous

# 按时间范围筛选
kubectl logs -l app=icyquant-risk -n icyquant --since="1h"

# 导出日志到文件
kubectl logs -l app=icyquant-api -n icyquant > api-logs-$(date +%Y%m%d).log
```

#### 日志聚合查询

```bash
# Loki 查询示例
{app="icyquant-api"} |= "ERROR" |= "timeout"
{app="icyquant-risk"} |= "blocked" | json | logfmt
{app="icyquant-oms"} |=~ "order.*(reject|cancel)"
```

### 性能指标

#### 关键性能指标 (KPI)

| 指标 | 目标值 | 告警阈值 |
|------|--------|----------|
| API P95 响应时间 | < 200ms | > 500ms |
| API P99 响应时间 | < 500ms | > 1000ms |
| 系统吞吐量 | > 1000 QPS | < 500 QPS |
| 错误率 | < 0.1% | > 1% |
| CPU 利用率 | < 70% | > 85% |
| 内存利用率 | < 80% | > 90% |
| 数据库连接池使用率 | < 70% | > 90% |
| Redis 内存使用率 | < 75% | > 90% |
| Kafka 消费延迟 | < 1000 条 | > 10000 条 |

#### Grafana 仪表板

```bash
# 打开 Grafana
open http://grafana.icyquant.io

# 查看仪表板列表
curl -s http://grafana.icyquant.io/api/dashboards | jq '.[] | {title: .title, url: .url}'
```

**核心仪表板：**

| 仪表板 | 包含内容 |
|--------|----------|
| 系统总览 | 所有服务健康状态、资源使用 |
| API 网关 | 请求量、延迟、错误率 |
| 交易监控 | 订单流、成交量、PnL |
| 风险管理 | 风险指标、限额状态、告警 |
| AI 服务 | 模型推理延迟、GPU 使用、任务队列 |
| 数据库 | 连接数、慢查询、复制延迟 |

---

## 扩缩容

### 手动扩缩容

#### 水平扩展 API 服务

```bash
# 增加 API 副本到 10
kubectl scale deployment icyquant-api -n icyquant --replicas=10

# 验证扩展
kubectl get pods -n icyquant -l app=icyquant-api
```

#### 垂直扩展资源

```bash
# 编辑资源限制
kubectl edit deployment icyquant-api -n icyquant

# 修改 resources 部分
resources:
  requests:
    cpu: 1000m
    memory: 2Gi
  limits:
    cpu: 4
    memory: 8Gi
```

### 自动扩缩容 (HPA)

#### 基于 CPU 的自动伸缩

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

#### 基于自定义指标的伸缩

```yaml
# 基于订单队列深度
metrics:
  - type: External
    external:
      metric:
        name: redis_queue_length
      target:
        type: AverageValue
        averageValue: "100"
```

#### KEDA 事件驱动伸缩

```yaml
# keda-scaler.yaml
apiVersion: v1
kind: ScaledObject
metadata:
  name: icyquant-order-processor
  namespace: icyquant
spec:
  scaleTargetRef:
    name: icyquant-order-processor
  minReplicaCount: 2
  maxReplicaCount: 100
  triggers:
    - type: redis
      metadata:
        address: redis://icyquant-redis:6379
        listName: orders
        minLength: "100"
    - type: kafka
      metadata:
        bootstrapServers: kafka:9092
        consumerGroup: order-processor
        topic: orders
        lagThreshold: "1000"
```

### 数据库扩展

#### PostgreSQL 读写分离

```yaml
# 主库 (已有)
postgresql:
  primary:
    persistence:
      size: 500Gi
    resources:
      requests:
        cpu: 4
        memory: 16Gi

# 添加只读副本
postgresql:
  replication:
    enabled: true
    replicaCount: 3
    persistence:
      size: 500Gi
```

#### Redis 集群

```yaml
redis:
  architecture: cluster
  cluster:
    nodes: 6
    persistence:
      enabled: true
      size: 100Gi
```

---

## 备份与恢复

### 备份策略

| 数据类型 | 备份频率 | 保留周期 | 备份方式 |
|----------|----------|----------|----------|
| PostgreSQL | 每日全量 + WAL 实时 | 30 天 | pg_dump + WAL 归档 |
| Redis | 每小时 RDB | 7 天 | SAVE/BGSAVE |
| Kafka | 保留期自动 | 按主题配置 | 副本机制 |
| 配置文件 | 变更时 | 永久 | Git 版本控制 |
| 日志 | 每日归档 | 90 天 | 日志轮转 |
| 对象存储 | 每日全量 | 30 天 | 存储快照 |

### PostgreSQL 备份

#### 全量备份

```bash
# 手动备份
pg_dump -h postgres-primary -U icyquant -d icyquant \
  -Fc -Z 9 -f backup-$(date +%Y%m%d).dump

# 压缩备份
pg_dump -h postgres-primary -U icyquant -d icyquant \
  | gzip > backup-$(date +%Y%m%d).sql.gz

# 并行备份大表
pg_dump -h postgres-primary -U icyquant -d icyquant \
  -j 4 -Fc -f backup-$(date +%Y%m%d).dump
```

#### WAL 归档

```bash
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'rsync -a %p backup_host:/backups/wal/%f'
max_wal_senders = 10
wal_keep_size = 10GB
```

#### 定时备份 CronJob

```yaml
# backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: icyquant-db-backup
  namespace: icyquant
spec:
  schedule: "0 2 * * *"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: postgres:16
              command:
                - /bin/sh
                - -c
                - |
                  pg_dump -h postgres-primary -U icyquant -d icyquant -Fc | \
                  aws s3 cp - s3://backups/icyquant/db/$(date +%Y%m%d).dump
              env:
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: postgres-secret
                      key: password
          restartPolicy: OnFailure
```

### 恢复操作

#### PostgreSQL 恢复

```bash
# 恢复全量备份
pg_restore -h postgres -U icyquant -d icyquant backup-20260730.dump

# 恢复到新数据库
createdb -h postgres -U icyquant icyquant_restored
pg_restore -h postgres -U icyquant -d icyquant_restored backup-20260730.dump

# 时间点恢复 (PITR)
# 1. 恢复基础备份
pg_restore -h postgres -U icyquant -d icyquant backup-20260729.dump
# 2. 重放 WAL 到指定时间
pg_waldump backup_host/wal/000000010000000100000050 \
  --start 2026-07-30 10:00:00 --end 2026-07-30 12:00:00
```

#### Redis 恢复

```bash
# 从 RDB 文件恢复
# 1. 停止 Redis
redis-cli shutdown
# 2. 替换 dump.rdb
cp /backups/redis/dump-20260730.rdb /var/lib/redis/dump.rdb
# 3. 启动 Redis
redis-server /etc/redis/redis.conf
```

#### 数据验证

```bash
# 验证表完整性
psql -h postgres -U icyquant -c "
  SELECT
    table_name,
    row_estimate,
    pg_size_pretty(pg_total_relation_size(table_schema || '.' || table_name)) as size
  FROM information_schema.tables
  WHERE table_schema = 'public'
  ORDER BY pg_total_relation_size(table_schema || '.' || table_name) DESC;
"

# 验证数据一致性
psql -h postgres -U icyquant -c "
  SELECT
    'orders' as table_name, count(*) as cnt FROM orders
  UNION ALL
  SELECT 'positions', count(*) FROM positions
  UNION ALL
  SELECT 'trades', count(*) FROM trades
  UNION ALL
  SELECT 'portfolio_snapshots', count(*) FROM portfolio_snapshots;
"
```

---

## 应急响应

### 应急响应级别

| 级别 | 场景示例 | 响应团队 | 决策权限 |
|------|----------|----------|----------|
| **L1 - 紧急** | 服务不可用、数据丢失、安全漏洞 | 运维 + 开发 | 值班工程师 |
| **L2 - 严重** | 性能严重下降、交易异常 | 运维 + 量化 | 运维负责人 |
| **L3 - 警告** | 非核心功能异常、延迟增加 | 运维 | 值班工程师 |
| **L4 - 信息** | 信息性通知 | - | - |

### 应急预案

#### 方案 1：服务不可用

```
1. 确认范围
   - 单服务 / 全平台
   - 是否影响交易
   ↓
2. 切换流量到备用集群
   - 激活 DR 副本
   - 更新 DNS 指向
   ↓
3. 诊断根因
   - 查看崩溃日志
   - 检查资源使用
   - 检查依赖服务
   ↓
4. 重启服务
   kubectl rollout restart deployment <service> -n icyquant
   ↓
5. 验证恢复
   - 健康检查通过
   - 核心功能测试
   ↓
6. 切换回主集群
   ↓
7. 事后复盘
```

#### 方案 2：数据库故障

```
1. 确认影响
   - 写入不可用 / 读取不可用
   - 影响服务列表
   ↓
2. 切换到备用数据库
   - 激活只读副本为主库
   - 更新连接字符串
   ↓
3. 恢复主库
   - 重建主从复制
   - 数据同步
   ↓
4. 切回主库
   ↓
5. 验证数据完整性
```

#### 方案 3：交易异常

```
1. 立即暂停所有交易
   icyquant risk circuit-breaker --reason "交易异常检测"
   ↓
2. 确认影响
   - 异常交易数量
   - 涉及金额
   - 客户影响
   ↓
3. 分析异常原因
   - 检查策略逻辑
   - 检查行情数据
   - 检查风控规则
   ↓
4. 修复问题
   ↓
5. 恢复交易
   - 小流量灰度
   - 逐步恢复
```

#### 方案 4：安全事件

```
1. 立即隔离
   - 禁用受影响账户
   - 吊销受影响密钥
   - 封锁可疑 IP
   ↓
2. 评估影响
   - 数据泄露范围
   - 入侵路径
   - 影响时间窗口
   ↓
3. 通知相关方
   - 客户通知
   - 监管报告
   - 保险公司
   ↓
4. 修复加固
   - 修复漏洞
   - 轮换密钥
   - 增强监控
   ↓
5. 取证分析
   - 保留日志
   - 分析攻击路径
   - 生成报告
```

### 应急联系清单

| 角色 | 联系人 | 联系方式 | 响应时间 |
|------|--------|----------|----------|
| 值班工程师 | - | - | 5 分钟 |
| 运维负责人 | - | - | 15 分钟 |
| 开发负责人 | - | - | 30 分钟 |
| 交易负责人 | - | - | 15 分钟 |
| 安全负责人 | - | - | 30 分钟 |
| CEO/CTO | - | - | 按需 |

---

## 常见问题排查

### 问题诊断流程图

```
问题报告
  ↓
能否访问 API？ ──否──→ 检查网络/DNS/Ingress
  ↓是
API 返回错误？ ──是──→ 检查应用日志/依赖服务
  ↓否
性能下降？ ──是──→ 检查资源使用/数据库性能
  ↓否
数据异常？ ──是──→ 检查数据一致性/同步状态
  ↓否
交易异常？ ──是──→ 检查策略/风控/行情
  ↓否
  深入分析
```

### 常见问题 1：API 超时

**症状：** API 请求超时或响应缓慢

**诊断步骤：**

```bash
# 1. 检查 API Pod 资源
kubectl top pods -n icyquant -l app=icyquant-api

# 2. 检查 API 日志
kubectl logs -l app=icyquant-api -n icyquant --tail=200 | grep "timeout"

# 3. 检查数据库连接
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# 4. 检查网络延迟
kubectl exec -it <api-pod> -- curl -s -o /dev/null -w "%{time_total}" http://postgres:5432

# 5. 检查依赖服务
for svc in ai risk redis; do
  echo "=== $svc ==="
  kubectl get pods -n icyquant -l app=icyquant-$svc
done
```

**修复方案：**

```bash
# 临时增加资源
kubectl scale deployment icyquant-api --replicas=10 -n icyquant

# 如果是数据库问题，增加连接池
kubectl edit deployment icyquant-api -n icyquant
# 修改环境变量 DB_POOL_SIZE=50
```

### 常见问题 2：订单无法成交

**症状：** 策略产生信号但订单被拒绝

**诊断步骤：**

```bash
# 1. 检查风控状态
icyquant risk check --order-id <order-id>

# 2. 检查风控日志
kubectl logs -l app=icyquant-risk -n icyquant --tail=100 | grep <order-id>

# 3. 检查 OMS 状态
kubectl logs -l app=icyquant-oms -n icyquant --tail=100 | grep <order-id>

# 4. 检查账户余额
icyquant account balance

# 5. 检查交易所连接
icyquant market status
```

**修复方案：**

```bash
# 如果是风控限制，调整限额
icyquant risk set-limit --metric position_size --value 1.0

# 如果是余额不足，充值
icyquant account deposit --amount <amount>

# 如果是连接问题，重启网关
kubectl rollout restart deployment icyquant-market-gateway -n icyquant
```

### 常见问题 3：数据库连接池耗尽

**症状：** 日志中出现 `connection pool exhausted` 错误

**诊断步骤：**

```bash
# 1. 检查 PostgreSQL 连接数
psql -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# 2. 检查最大连接数
psql -c "SHOW max_connections;"

# 3. 检查应用连接池配置
kubectl get deployment icyquant-api -n icyquant -o yaml | grep pool

# 4. 检查是否有连接泄漏
psql -c "SELECT pid, state, query, duration FROM pg_stat_activity WHERE state='idle in transaction';"
```

**修复方案：**

```bash
# 临时杀掉空闲连接
psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle in transaction' AND duration > interval '5 minutes';"

# 增加连接池大小
kubectl set env deployment/icyquant-api DB_POOL_SIZE=100 -n icyquant

# 优化慢查询
psql -c "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 5;"
```

### 常见问题 4：Kafka 消费延迟

**症状：** 订单处理延迟增加

**诊断步骤：**

```bash
# 1. 检查消费者 Lag
kafka-consumer-groups.sh --describe --group order-processor

# 2. 检查 Broker 状态
kafka-broker-api-versions.sh --bootstrap-server kafka:9092

# 3. 检查 Topic 配置
kafka-topics.sh --describe --topic orders

# 4. 检查消费性能
kubectl top pods -n icyquant -l app=order-processor
```

**修复方案：**

```bash
# 增加消费者实例
kubectl scale deployment order-processor -n icyquant --replicas=10

# 增加分区数（需要停机）
kafka-topics.sh --alter --topic orders --partitions=32
```

### 常见问题 5：内存泄漏

**症状：** Pod 内存持续增长直至 OOM

**诊断步骤：**

```bash
# 1. 监控内存趋势
kubectl top pods -n icyquant --containers

# 2. 内存快照
kubectl exec -it <pod> -- python -c "
import tracemalloc
tracemalloc.start()
# ... 运行 ...
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:10]:
    print(stat)
"

# 3. 检查 GC 日志
kubectl logs <pod> --tail=100 | grep -i "gc\|memory\|leak"
```

**修复方案：**

```bash
# 重启受影响服务（临时）
kubectl rollout restart deployment <service> -n icyquant

# 永久修复需要代码层面处理
```

---

**文档版本**: 1.0
**创建日期**: 2026-07-30
**适用版本**: ICYQuant v0.4.0 GA