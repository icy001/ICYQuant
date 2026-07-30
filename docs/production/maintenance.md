# ICYQuant 系统维护指南

## 1. 计划维护窗口

### 1.1 维护窗口规划

| 窗口类型 | 时间 | 频率 | 允许操作 | 需客户通知 |
|----------|------|------|----------|------------|
| 日常维护 | 每日 16:00-17:00 | 每日 | 日志归档、指标清理、非关键重启 | 否 |
| 周度维护 | 每周六 02:00-06:00 | 每周 | 系统更新、配置变更、补丁安装 | 是（T-72h） |
| 月度维护 | 每月第一个周日 00:00-08:00 | 每月 | 数据库升级、K8s 版本升级、架构变更 | 是（T-72h） |
| 季度维护 | 每季度第一个周六 00:00-08:00 | 每季 | 大型版本升级、基础设施优化 | 是（T-7d） |
| 紧急维护 | 随时开放 | 按需 | 安全补丁、P0 级修复 | 是（尽量提前） |

### 1.2 维护分类

| 操作类别 | 停机要求 | 风险等级 | 执行时段 |
|----------|----------|----------|----------|
| 配置热更新 | 否 | 低 | 任意时段 |
| 应用滚动重启 | 否 | 低 | 交易时段 |
| 应用滚动升级 | 否 | 中 | 非交易时段 |
| 数据库参数调整 | 可能（需重启） | 中 | 维护窗 |
| 数据库版本升级 | 是 | 高 | 月度维护窗 |
| K8s 版本升级 | 滚动（节点） | 高 | 月度维护窗 |
| 网络设备升级 | 可能 | 高 | 季度维护窗 |

### 1.3 维护前检查

```bash
#!/bin/bash
# maintenance-precheck.sh - 维护前检查

set -e

echo "=== 维护前检查 ==="
DATE=$(date +%Y-%m-%d)

# 1. 备份确认
echo "检查备份..."
LATEST_BACKUP=$(aws s3 ls "s3://icyquant-backups/prod/postgresql/full/" --recursive | \
  sort | tail -1 | awk '{print $4}')
if [ -z "$LATEST_BACKUP" ]; then
  echo "✗ 无可用备份，取消维护"
  exit 1
fi
echo "✓ 最近备份: $LATEST_BACKUP"

# 2. 集群健康
echo "检查集群健康..."
kubectl get nodes -n icyquant-prod
kubectl get pods -n icyquant-prod | grep -v "Running\|Completed" || echo "✓ 所有 Pod 正常"

# 3. 资源余量
echo "检查资源余量..."
CPU_FREE=$(kubectl top nodes --no-headers | awk '{print $3}' | cut -d'%' -f1 | sort -n | head -1)
MEM_FREE=$(kubectl top nodes --no-headers | awk '{print $5}' | cut -d'%' -f1 | sort -n | head -1)
echo "剩余 CPU: ${CPU_FREE}%, 剩余内存: ${MEM_FREE}%"
[ "$CPU_FREE" -lt 20 ] && echo "✗ CPU 余量不足" && exit 1
[ "$MEM_FREE" -lt 20 ] && echo "✗ 内存余量不足" && exit 1

# 4. 应用健康
echo "检查应用健康..."
curl -s "https://api.icyquant.io/actuator/health" | jq '.status' | grep -q "UP" || {
  echo "✓ 应用健康"
} || {
  echo "✗ 应用异常，取消维护"
  exit 1
}

# 5. 通知团队
echo "发送维护通知..."
curl -X POST "https://notify.company.com/icyquant" \
  -d "维护窗口 $DATE 已开启，准备执行..."

echo "=== 维护前检查完成，可以执行维护 ==="
```

---

## 2. 系统更新程序

### 2.1 更新流程概览

```
评估变更 → 制定计划 → 测试验证 → 客户通知 → 执行维护 → 验证 → 归档
   │          │          │          │          │         │       │
   ▼          ▼          ▼          ▼          ▼         ▼       ▼
 影响分析   回滚方案   Staging测试  T-72h通知  维护窗内  冒烟测试 生成报告
 风险评估   验证步骤   性能验证   T-24h确认  执行变更  全量验证 更新文档
```

### 2.2 应用更新步骤

```bash
#!/bin/bash
# app_update.sh - 应用更新脚本

set -euo pipefail

VERSION="${1:?用法: $0 <版本号>}"
NAMESPACE="icyquant-prod"
IMAGE="harbor.company.com/icyquant"

echo "=== ICYQuant 应用更新 v$VERSION ==="
echo "开始时间: $(date)"

# 阶段 1: 预检查
echo "--- 阶段 1: 预检查 ---"
./maintenance-precheck.sh

# 阶段 2: 镜像验证
echo "--- 阶段 2: 镜像验证 ---"
docker pull "$IMAGE:$VERSION"
docker scan "$IMAGE:$VERSION" > "/reports/scan-$VERSION.txt"
# 安全扫描通过方可继续
if grep -q "CRITICAL" "/reports/scan-$VERSION.txt"; then
  echo "✗ 安全扫描发现严重漏洞，取消更新"
  exit 1
fi
echo "✓ 镜像安全扫描通过"

# 阶段 3: 变更说明
echo "--- 阶段 3: 变更说明 ---"
cat << CHANGELOG
版本 $VERSION 变更摘要:
- [功能/修复 1]
- [功能/修复 2]
- [功能/修复 3]

影响范围:
- 服务: [trading-engine, order-service]
- 数据库: [需要/不需要迁移]
- 配置: [需要/不需要变更]
CHANGELOG

# 阶段 4: 数据库迁移（如需要）
echo "--- 阶段 4: 数据库迁移 ---"
if [ -f "db/migrations/V$(echo $VERSION | tr '.' '_')__*.sql" ]; then
  cat <<'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: icyquant-db-migration
  namespace: $NAMESPACE
spec:
  template:
    spec:
      containers:
        - name: migrator
          image: $IMAGE:$VERSION
          command: ["flyway", "migrate"]
      restartPolicy: Never
EOF
  kubectl wait --for=condition=complete job/icyquant-db-migration \
    -n $NAMESPACE --timeout=10m
  echo "✓ 数据库迁移完成"
else
  echo "无需数据库迁移"
fi

# 阶段 5: 滚动更新
echo "--- 阶段 5: 滚动更新 ---"

# 逐步更新各个 Deployment
for DEPLOYMENT in api-gateway trading-engine risk-engine order-service \
                   market-data ai-inference account-service notification; do
  echo "更新 $DEPLOYMENT..."
  
  kubectl set image "deployment/$DEPLOYMENT" "$DEPLOYMENT=$IMAGE:$VERSION" \
    -n "$NAMESPACE"
  
  kubectl rollout status "deployment/$DEPLOYMENT" -n "$NAMESPACE" \
    --timeout=5m
  
  echo "  ✓ $DEPLOYMENT 更新完成"
done

# 阶段 6: 验证
echo "--- 阶段 6: 功能验证 ---"
./scripts/smoke-test.sh prod

# 阶段 7: 归档
echo "--- 阶段 7: 归档 ---"
helm history icyquant --namespace "$NAMESPACE" > \
  "/reports/helm-history-$(date +%Y%m%d).txt"
kubectl get pods -n "$NAMESPACE" > \
  "/reports/pod-status-$(date +%Y%m%d).txt"

echo "=== 更新完成 ==="
echo "版本: $VERSION"
echo "完成时间: $(date)"
```

### 2.3 数据库升级

```bash
#!/bin/bash
# pg_upgrade.sh - PostgreSQL 升级脚本

set -euo pipefail

NEW_VERSION="${1:?用法: $0 <新版本>}"
CURRENT_VERSION=$(kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "SHOW server_version;" | grep -o '[0-9]\+\.[0-9]\+')

echo "=== PostgreSQL 升级: $CURRENT_VERSION → $NEW_VERSION ==="

# 阶段 1: 升级前准备
echo "--- 阶段 1: 升级前准备 ---"

# 1. 停止所有写入
kubectl scale deployment trading-engine --replicas=0 -n icyquant-prod
kubectl scale deployment order-service --replicas=0 -n icyquant-prod

# 2. 创建数据备份
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  pg_dumpall -U "$PG_USER" > /backups/pg_pre_upgrade.sql

# 3. 检查兼容性
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U "$PG_USER" -c "SELECT * FROM pg_upgrade_checks;"

# 阶段 2: 执行升级
echo "--- 阶段 2: 执行升级 ---"

# 如果是大版本升级（如 14 → 15）
if [ "$(echo "$NEW_VERSION" | cut -d. -f1)" != "$(echo "$CURRENT_VERSION" | cut -d. -f1)" ]; then
  echo "大版本升级，使用 pg_upgrade"
  
  # 初始化新版本
  kubectl exec -it postgresql-0 -n icyquant-prod -- \
    initdb -D /var/lib/postgresql/data_new
  
  # 运行 pg_upgrade
  kubectl exec -it postgresql-0 -n icyquant-prod -- \
    pg_upgrade \
    -b /usr/lib/postgresql/$CURRENT_VERSION/bin \
    -B /usr/lib/postgresql/$NEW_VERSION/bin \
    -d /var/lib/postgresql/data \
    -D /var/lib/postgresql/data_new
  
  # 切换数据目录
  kubectl exec -it postgresql-0 -n icyquant-prod -- \
    bash -c "
      mv /var/lib/postgresql/data /var/lib/postgresql/data_old
      mv /var/lib/postgresql/data_new /var/lib/postgresql/data
    "
  
  # 重启使用新版本
  kubectl rollout restart statefulset postgresql -n icyquant-prod
else
  # 小版本升级，直接替换二进制
  echo "小版本升级，滚动更新"
  kubectl set image statefulset postgresql \
    postgresql="postgres:$NEW_VERSION" -n icyquant-prod
  kubectl rollout status statefulset postgresql -n icyquant-prod
fi

# 阶段 3: 升级后处理
echo "--- 阶段 3: 升级后处理 ---"

# 清理统计信息
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "ANALYZE;"

# 重建索引
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "REINDEX DATABASE icyquant;"

# 恢复应用
kubectl scale deployment trading-engine --replicas=6 -n icyquant-prod
kubectl scale deployment order-service --replicas=6 -n icyquant-prod

# 阶段 4: 验证
echo "--- 阶段 4: 验证 ---"
curl -s "https://api.icyquant.io/actuator/health" | jq '.'

echo "=== PostgreSQL 升级完成 ==="
```

### 2.4 K8s 版本升级

```bash
#!/bin/bash
# k8s_upgrade.sh - Kubernetes 集群升级

set -euo pipefail

NEW_VERSION="${1:?用法: $0 <新版本>}"

echo "=== Kubernetes 升级到 $NEW_VERSION ==="

# 阶段 1: 升级主节点
echo "--- 阶段 1: 升级主节点 ---"

# 升级第一个主节点
kubectl cordon master-1
kubectl drain master-1 --delete-emptydir-data --ignore-daemonsets
# 在 master-1 上升级 kubeadm, kubelet
# 重复直到所有主节点升级

# 阶段 2: 升级工作节点
echo "--- 阶段 2: 升级工作节点 ---"

for NODE in $(kubectl get nodes -l node-role.kubernetes.io/worker -o name); do
  echo "升级 $NODE..."
  kubectl cordon "$NODE"
  kubectl drain "$NODE" --delete-emptydir-data --ignore-daemonsets
  # 在节点上升级 kubeadm, kubelet, cni
  # 验证节点就绪
  kubectl uncordon "$NODE"
  kubectl wait --for=condition=Ready node/"$NODE" --timeout=5m
  echo "  ✓ $NODE 升级完成"
done

# 阶段 3: 验证
echo "--- 阶段 3: 验证 ---"
kubectl version
kubectl get nodes

# 阶段 4: 核心组件更新
kubectl apply -f k8s-components/coredns.yaml
kubectl apply -f k8s-components/ingress-nginx.yaml

echo "=== Kubernetes 升级完成 ==="
```

---

## 3. 安全补丁管理

### 3.1 补丁分类

| 类别 | 描述 | SLA | 优先级 |
|------|------|-----|--------|
| 紧急 (Critical) | 远程代码执行、权限提升 | 24 小时内 | P0 |
| 高 (High) | 敏感信息泄露、认证绕过 | 72 小时内 | P1 |
| 中 (Medium) | DoS、信息泄露 | 2 周内 | P2 |
| 低 (Low) | 低风险信息泄露 | 下一个维护窗 | P3 |

### 3.2 补丁流程

```bash
#!/bin/bash
# security_patch.sh - 安全补丁管理

set -euo pipefail

PATCH_FILE="${1:?用法: $0 <补丁包路径>}"
SEVERITY="${2:-Medium}"

echo "=== 安全补丁应用 ==="
echo "补丁文件: $PATCH_FILE"
echo "严重级别: $SEVERITY"

# 阶段 1: 风险评估
echo "--- 阶段 1: 风险评估 ---"

VULN_INFO=$(jq -r '.vulnerabilities' "$PATCH_FILE")
echo "补丁包含漏洞修复:"
echo "$VULN_INFO"

# 评估风险
RISK_LEVEL=$(echo "$VULN_INFO" | jq -r '[.[] | .cvss_score] | max')
echo "最高 CVSS 评分: $RISK_LEVEL"

if (( $(echo "$RISK_LEVEL > 7.0" | bc -l) )); then
  echo "⚠ 高危补丁，需紧急处理"
  NOTIFY="CRITICAL"
fi

# 阶段 2: 在 Staging 环境测试
echo "--- 阶段 2: Staging 测试 ---"

# 应用补丁到 Staging
kubectl apply -f "$PATCH_FILE" -n icyquant-stg
kubectl rollout status deployment/trading-engine -n icyquant-stg

# 冒烟测试
./scripts/smoke-test.sh staging

# 回归测试
./scripts/regression-test.sh staging

if [ $? -ne 0 ]; then
  echo "✗ Staging 测试失败，回滚补丁"
  kubectl rollout undo deployment/trading-engine -n icyquant-stg
  exit 1
fi

echo "✓ Staging 测试通过"

# 阶段 3: 通知与计划
echo "--- 阶段 3: 通知与计划 ---"

# 生成变更通知
cat > "/reports/change-notice-$(date +%Y%m%d).md" << EOF
# 变更通知

## 变更信息
- **变更类型**: 安全补丁
- **补丁文件**: $PATCH_FILE
- **严重级别**: $SEVERITY
- **CVSS 评分**: $RISK_LEVEL

## 影响评估
- **影响服务**: [列表]
- **影响范围**: [描述]
- **回滚方案**: [描述]

## 执行计划
- **计划时间**: $EXEC_TIME
- **执行时段**: 维护窗内
- **执行人**: XXX

## 验证方案
- [ ] 功能冒烟测试通过
- [ ] 核心交易流程正常
- [ ] 性能无退化
- [ ] 安全漏洞已修复
EOF

# 阶段 4: 生产环境应用
echo "--- 阶段 4: 生产应用 ---"

# 按服务分批应用
SERVICES=("api-gateway" "market-data" "order-service" 
          "trading-engine" "risk-engine" "ai-inference")

for SVKICE in "${SERVICES[@]}"; do
  echo "更新 $SERVICE..."
  
  kubectl apply -f "$PATCH_FILE" -n icyquant-prod
  kubectl rollout status "deployment/$SERVICE" -n icyquant-prod \
    --timeout=5m
  
  echo "  ✓ $SERVICE 更新完成"
done

# 阶段 5: 验证
echo "--- 阶段 5: 生产验证 ---"

./scripts/smoke-test.sh prod
./scripts/regression-test.sh prod

# 扫描确认漏洞已修复
docker scan "harbor.company.com/icyquant:latest" > "/reports/scan-after-patch.txt"

# 阶段 6: 归档
echo "--- 阶段 6: 归档 ---"

aws s3 cp "$PATCH_FILE" "s3://icyquant-backups/patches/$(date +%Y%m%d)/"
git add -A . && git commit -m "security: apply patch $PATCH_FILE ($SEVERITY)"

echo "=== 安全补丁应用完成 ==="
```

### 3.3 漏洞管理

```bash
# 定期安全扫描
# 每日: 扫描所有镜像
for IMAGE in $(kubectl get images -n icyquant-prod); do
  docker scan "$IMAGE" >> "/reports/daily-scan-$(date +%Y%m%d).txt"
done

# 每周: 依赖审计
# 使用 Trivy 或 Grype
trivy fs /app --format json > "/reports/dependency-audit-$(date +%Y%m%d).json"

# 漏洞跟踪仪表板
# Grafana Dashboard: Security/Vulnerabilities
# - 活跃漏洞数
# - 按严重级别分布
# - 修复率趋势
```

---

## 4. 性能调优指南

### 4.1 JVM 调优

#### JVM 参数模板

```yaml
# values-prod.yaml - JVM 参数配置
app:
  env:
    JAVA_OPTS: >-
      -Xms8g
      -Xmx16g
      -Xss1m
      -XX:+UseG1GC
      -XX:MaxGCPauseMillis=100
      -XX:G1HeapRegionSize=4m
      -XX:+ParallelRefProcEnabled
      -XX:+UseNUMA
      -XX:+DisableExplicitGC
      -XX:+HeapDumpOnOutOfMemoryError
      -XX:HeapDumpPath=/logs/heapdump.hprof
      -Djava.security.egd=file:/dev/urandom
      -Dsun.net.inetaddr.ttl=30
      -XX:+FlightRecorder
      -XX:FlightRecorderOptions=disk=true,maxsize=500m
```

#### GC 日志分析

```bash
# 启用 GC 日志
JAVA_OPTS="$JAVA_OPTS -Xlog:gc*:file=/logs/gc.log:time,uptime,level,tags"

# 分析 GC 日志
kubectl logs -n icyquant-prod -l app=trading-engine --since=1h | grep "GC"

# 关注指标:
# - Full GC 次数: 应 < 1/小时
# - GC 总时间占比: 应 < 5%
# - 最大停顿时间: 应 < 200ms
# - 对象分配速率: 异常高可能有泄漏
```

### 4.2 数据库调优

#### PostgreSQL 参数调优

```sql
-- 针对交易系统的 PostgreSQL 优化

-- 内存分配
shared_buffers = 8GB          -- 物理内存的 25%
effective_cache_size = 24GB   -- 物理内存的 75%
work_mem = 64MB               -- 每个查询的工作内存
maintenance_work_mem = 2GB    -- VACUUM, CREATE INDEX

-- 写入性能
wal_buffers = 64
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB

-- 并行处理
max_worker_processes = 8
max_parallel_workers_per_gather = 2
max_parallel_maintenance_workers = 2

-- 连接池
max_connections = 500
superuser_reserved_connections = 5

-- 自动维护
autovacuum = on
autovacuum_max_workers = 4
autovacuum_naptime = 30s

-- 查询优化
random_page_cost = 1.1
effective_io_concurrency = 200
default_toast_compression = lz4
```

#### 慢查询分析

```sql
-- 查找最慢的查询
SELECT 
  query,
  calls,
  ROUND(total_exec_time::numeric, 2) as total_ms,
  ROUND(mean_exec_time::numeric, 2) as mean_ms,
  RANK() OVER (ORDER BY mean_exec_time DESC) as rank
FROM pg_stat_statements
WHERE calls > 100
ORDER BY mean_exec_time DESC
LIMIT 20;

-- 高频慢查询
SELECT query, calls, mean_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY calls * mean_exec_time DESC
LIMIT 10;

-- 索引使用分析
SELECT 
  schemaname,
  relname as table,
  count(*) as index_scans
FROM pg_stat_user_indexes
WHERE idx_scan = 0
GROUP BY schemaname, relname
ORDER BY index_scans ASC;
```

### 4.3 Redis 调优

```redis
# Redis 交易场景优化

# 内存限制
maxmemory 16gb
maxmemory-policy allkeys-lru
maxmemory-samples 10

# 持久化策略
save 3600 1
save 300 100
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes

# 网络优化
tcp-backlog 65536
timeout 0
tcp-keepalive 300
protected-mode yes

# 慢日志
slowlog-log-slower-than 10000
slowlog-max-len 128

# 惰性释放
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes
lazyfree-lazy-user-del yes

# AOF 优化
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

### 4.4 Kafka 调优

```properties
# Kafka Broker 配置
broker.id=1
num.network.threads=16
num.io.threads=8
socket.send.buffer.bytes=102400
socket.receive.buffer.bytes=102400
socket.request.max.bytes=104857600

# 日志配置
log.dirs=/data/kafka/logs
log.retention.hours=168
log.segment.bytes=1073741824
log.retention.check.interval.ms=300000

# 复制
default.replication.factor=3
min.insync.replicas=2
unclean.leader.election.enable=false

# 压缩
compression.type=zstd
compression.level=3

# 消费者配置
fetch.min.bytes=1
fetch.max.wait.ms=500
max.partition.fetch.bytes=1048576
```

---

## 5. 容量规划

### 5.1 当前容量评估

| 资源 | 当前使用 | 总容量 | 使用率 | 告警阈值 |
|------|----------|--------|--------|----------|
| CPU (集群) | 48 核 | 128 核 | 37.5% | > 70% |
| 内存 (集群) | 96 GB | 256 GB | 37.5% | > 75% |
| 存储 (SSD) | 800 GB | 2 TB | 40% | > 80% |
| PostgreSQL 连接 | 180 | 500 | 36% | > 70% |
| Kafka Topic 数 | 15 | — | — | — |
| 在线用户数 | 2000 | 5000 | 40% | > 80% |

### 5.2 容量预测

#### 基于历史趋势

```python
# capacity_forecast.py

import pandas as pd
from datetime import datetime, timedelta

# 历史数据（月粒度）
historical_data = {
    'month': ['2024-01', '2024-02', '2024-03', '2024-04', 
              '2024-05', '2024-06', '2024-07'],
    'trades': [120000, 135000, 148000, 162000, 178000, 195000, 210000],
    'users': [800, 950, 1100, 1250, 1400, 1600, 1800],
    'cpu_avg': 25, 28, 30, 33, 35, 37, 40
}

df = pd.DataFrame(historical_data)

# 增长率计算
growth_rate = {
    'trades': (210000 - 120000) / 120000 / 6 * 100,  # %/月
    'users': (1800 - 800) / 800 / 6 * 100,
    'cpu': (40 - 25) / 25 / 6 * 100
}

# 6 个月预测
projection = {}
for metric in growth_rate:
    current = df[metric].iloc[-1]
    rate = growth_rate[metric]
    projection[metric] = {
        'current': current,
        '6_month': current * (1 + rate) ** 6,
        '12_month': current * (1 + rate) ** 12
    }

print("容量预测:")
for metric, values in projection.items():
    print(f"{metric}:")
    print(f"  当前: {values['current']:.0f}")
    print(f"  6月后: {values['6_month']:.0f} ({growth_rate[metric]*100:.1f}%/月)")
    print(f"  12月后: {values['12_month']:.0f}")

# 资源需求推算
def estimate_resources(trades_per_day, users):
    cpu_needed = max(8, trades_per_day / 5000 * 2 + users / 200)
    memory_needed = max(16, trades_per_day / 3000 * 4 + users / 100)
    storage_needed = trades_per_day * 365 * 2 / 1024  # GB
    return {
        'cpu_cores': cpu_needed,
        'memory_gb': memory_needed,
        'storage_gb': storage_needed
    }

future_6 = projection['trades']['6_month'] / 252  # 交易日
future_12 = projection['trades']['12_month'] / 252

print("\n资源需求预测:")
print(f"6月后: {estimate_resources(future_6, projection['users']['6_month'])}")
print(f"12月后: {estimate_resources(future_12, projection['users']['12_month'])}")
```

### 5.3 扩容计划

| 时间 | 预测交易/日 | 预测用户 | CPU 需求 | 内存需求 | 存储需求 |
|------|-------------|----------|----------|----------|----------|
| 当前 | 8,333 | 1,800 | 48 核 | 96 GB | 800 GB |
| 6 月 | 14,000 | 3,200 | 80 核 | 160 GB | 1.4 TB |
| 12 月 | 24,000 | 5,500 | 140 核 | 280 GB | 2.4 TB |
| 18 月 | 41,000 | 9,500 | 240 核 | 480 GB | 4.1 TB |

#### 扩容执行清单

```
6 个月扩容计划：
□ 1. 新增 K8s 工作节点（从 6 → 10 节点）
□ 2. 扩容 PostgreSQL（垂直扩展 + 读写分离）
□ 3. 扩容 Redis 集群（分片数从 8 → 12）
□ 4. 扩容 Kafka（Broker 从 3 → 5 节点，分区数 +50%）
□ 5. 扩容 AI 推理服务（GPU 从 4 → 8 卡）
□ 6. 扩容存储空间（增加 1 TB NVMe）
□ 7. 更新 HPA 配置（调整 minReplicas 和 maxReplicas）
□ 8. 重新压测容量边界
```

---

## 6. 系统下线与退役

### 6.1 下线决策流程

```
评估阶段：
  ├─ 评估业务影响
  ├─ 评估技术依赖
  ├─ 评估数据迁移需求
  └─ 制定下线计划

执行阶段：
  ├─ 停止新功能开发
  ├─ 进入维护模式
  ├─ 通知所有相关方
  └─ 执行迁移

验证阶段：
  ├─ 数据完整性验证
  ├─ 业务连续性验证
  ├─ 性能回归测试
  └─ 监控观察

清理阶段：
  ├─ 删除代码和配置
  ├─ 归档历史数据
  ├─ 释放基础设施资源
  └─ 更新文档
```

### 6.2 退役检查清单

```bash
#!/bin/bash
# decommission-checklist.sh - 系统退役检查

COMPONENT="${1:?用法: $0 <组件名>}"

echo "=== 系统退役检查: $COMPONENT ==="

# 1. 依赖分析
echo "--- 依赖分析 ---"
# 检查谁在使用此组件
kubectl get deployments -n icyquant-prod -o yaml | \
  grep -A5 "$COMPONENT" > "/reports/deps-$COMPONENT.txt"

# 检查服务引用
SERVICE_USERS=$(kubectl get service -n icyquant-prod -o yaml | \
  grep "$COMPONENT" | wc -l)
echo "服务引用数: $SERVICE_USERS"

# 检查 API 调用
API_CALLERS=$(grep -r "$COMPONENT" src/ --include="*.java" | wc -l)
echo "API 调用点: $API_CALLERS"

# 2. 数据归档
echo "--- 数据归档 ---"
ARCHIVE_DATE=$(date +%Y%m%d)
aws s3 cp \
  "s3://icyquant-backups/prod/$COMPONENT/" \
  "s3://icyquant-archive/$COMPONENT/$ARCHIVE_DATE/" \
  --recursive

# 3. 配置清理
echo "--- 配置清理 ---"
# 备份配置
kubectl get configmap -n icyquant-prod "$COMPONENT" -o yaml | \
  aws s3 cp - "s3://icyquant-archive/config/$COMPONENT/"

# 4. 执行下线
echo "--- 执行下线 ---"
kubectl scale "deployment/$COMPONENT" --replicas=0 -n icyquant-prod
kubectl delete "deployment/$COMPONENT" -n icyquant-prod

# 5. 验证
echo "--- 验证 ---"
curl -s "https://api.icyquant.io/actuator/health" | jq '.'

# 6. 更新文档
echo "--- 文档更新 ---"
# 更新架构图
# 更新 API 文档
# 更新运维手册

echo "=== 系统退役完成 ==="
```

---

## 7. 审计与合规

### 7.1 审计日志

#### 关键操作审计

| 操作类型 | 审计内容 | 保留期 | 存储位置 |
|----------|----------|--------|----------|
| 登录/登出 | 用户、IP、时间、结果 | 90 天 | PostgreSQL audit 表 |
| 配置变更 | 变更内容、操作人、时间 | 7 年 | Git + 对象存储 |
| 订单操作 | 下单、撤单、修改详情 | 7 年 | PostgreSQL + Kafka |
| 资金操作 | 入金、出金、划转 | 7 年 | PostgreSQL |
| 风控决策 | 规则、阈值、触发条件 | 7 年 | PostgreSQL |
| 权限变更 | 角色、权限调整 | 7 年 | PostgreSQL |
| 数据访问 | 查询表、行数、时间 | 30 天 | PostgreSQL audit |
| 系统变更 | 部署、配置更新 | 7 年 | Git + 对象存储 |

#### 审计表结构

```sql
-- 通用审计表
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    action VARCHAR(20) NOT NULL,
    user_id VARCHAR(100),
    user_role VARCHAR(50),
    ip_address INET,
    user_agent TEXT,
    old_value JSONB,
    new_value JSONB,
    metadata JSONB,
    event_time TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_log_event_time ON audit_log(event_time DESC);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_event_type ON audit_log(event_type);

-- 分区（按月）
CREATE TABLE audit_log_2024_01 PARTITION OF audit_log
  FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE audit_log_2024_02 PARTITION OF audit_log
  FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
```

#### 审计日志查询

```sql
-- 查询特定用户操作
SELECT * FROM audit_log 
WHERE user_id = 'user_123' 
  AND event_time BETWEEN '2024-01-01' AND '2024-01-31'
ORDER BY event_time DESC;

-- 查询敏感操作
SELECT * FROM audit_log 
WHERE event_type IN ('CONFIG_CHANGE', 'PERMISSION_CHANGE', 'WITHDRAW')
  AND event_time > now() - interval '7 days'
ORDER BY event_time DESC;

-- 统计操作频率
SELECT 
    event_type,
    action,
    count(*) as count,
    count(DISTINCT user_id) as unique_users
FROM audit_log
WHERE event_time > now() - interval '30 days'
GROUP BY event_type, action
ORDER BY count DESC;

-- IP 异常检测
SELECT 
    user_id,
    ip_address,
    count(*) as login_count
FROM audit_log
WHERE event_type = 'LOGIN'
  AND result = 'SUCCESS'
  AND event_time > now() - interval '1 day'
GROUP BY user_id, ip_address
HAVING count(*) > 50;
```

### 7.2 合规检查清单

#### 监管合规

| 要求 | 标准 | 检查频率 | 责任人 |
|------|------|----------|--------|
| 交易记录保存 | 7 年 | 每月 | 合规官 |
| 客户身份验证 | KYC/AML | 实时 | 风控团队 |
| 数据本地化 | 境内存储 | 每季 | 架构师 |
| 系统容灾 | 两地三中心 | 每季 | SRE 负责人 |
| 密钥管理 | HSM/加密 | 每月 | 安全团队 |
| 访问控制 | 最小权限 | 每月 | DBA |
| 漏洞扫描 | 每月 | 每月 | 安全团队 |
| 渗透测试 | 每年 | 每年 | 安全团队 |

#### 内部审计

```bash
#!/bin/bash
# compliance-audit.sh - 合规审计脚本

echo "=== 合规审计 ==="
DATE=$(date +%Y-%m-%d)

# 1. 权限审计
echo "--- 1. 权限审计 ---"
# 检查过度权限
kubectl get clusterrolebinding -o yaml | \
  grep -A5 "cluster-admin" > "/reports/audit-$DATE/permissions.txt"

# 检查 Service Account
kubectl get serviceaccount -A | \
  grep -v "kube-system\|kube-public" > "/reports/audit-$DATE/service-accounts.txt"

# 2. 数据安全
echo "--- 2. 数据安全 ---"
# 检查未加密的敏感数据
psql -c "
  SELECT column_name, data_type 
  FROM information_schema.columns 
  WHERE table_schema = 'public' 
    AND data_type IN ('password', 'text')
    AND column_name LIKE '%password%'
    OR column_name LIKE '%secret%'
    OR column_name LIKE '%token%'
;" > "/reports/audit-$DATE/sensitive-data.txt"

# 3. 审计日志完整性
echo "--- 3. 审计日志 ---"
psql -c "
  SELECT 
    date_trunc('day', event_time) as day,
    count(*) as events
  FROM audit_log
  WHERE event_time > now() - interval '30 days'
  GROUP BY 1
  ORDER BY 1 DESC
;" > "/reports/audit-$DATE/audit-volume.txt"

# 4. 备份合规
echo "--- 4. 备份合规 ---"
# 检查备份覆盖范围
echo "备份清单:" > "/reports/audit-$DATE/backup-list.txt"
aws s3 ls "s3://icyquant-backups/" --recursive | \
  awk '{print $4}' >> "/reports/audit-$DATE/backup-list.txt"

# 5. 报告生成
echo "--- 5. 生成报告 ---"
cat > "/reports/audit-$DATE/audit-report.md" << EOF
# 合规审计报告 - $DATE

## 审计范围
- [x] 权限管理
- [x] 数据安全
- [x] 审计日志
- [x] 备份合规
- [ ] 漏洞扫描
- [ ] 渗透测试

## 发现的问题
1. [问题描述]
2. [问题描述]

## 合规状态
- 符合要求: XX 项
- 需要改进: X 项

## 整改计划
| 编号 | 问题 | 责任人 | 完成时限 |
|------|------|--------|----------|
| 1 | ... | XX | ... |
| 2 | ... | XX | ... |

审计人签字: _______________
EOF

echo "=== 合规审计完成 ==="
```

### 7.3 年度审计计划

| 季度 | 审计内容 | 参与方 | 完成时间 |
|------|----------|--------|----------|
| Q1 | 权限管理、数据安全、灾备验证 | 安全 + SRE + DBA | 3 月 31 日 |
| Q2 | 交易记录完整性、客户数据保护 | 合规 + DBA + 风控 | 6 月 30 日 |
| Q3 | 系统变更管理、配置审计 | SRE + DevOps | 9 月 30 日 |
| Q4 | 全面审计 + 外部审计 | 外部审计机构 + 内部 | 12 月 31 日 |

---

## 附录

### A. 维护操作快速参考

| 操作 | 命令 | 影响 | 紧急程度 |
|------|------|------|----------|
| 滚动重启 Pod | `kubectl rollout restart deploy/<name>` | 零停机 | 低 |
| 扩缩副本 | `kubectl scale deploy/<name> --replicas=N` | 零停机 | 低 |
| 刷新配置 | `curl POST /actuator/refresh` | 无影响 | 低 |
| 清理日志 | `kubectl logs -c <container>` | 无影响 | 低 |
| 重建索引 | `REINDEX DATABASE` | 短暂锁定 | 中 |
| 数据库 VACUUM | `VACUUM ANALYZE` | 资源占用 | 中 |
| 热更新参数 | `SELECT pg_reload_conf()` | 无影响 | 低 |
| 冷更新参数 | 修改 postgresql.conf + 重启 | 需重启 | 高 |

### B. 参考文档

- [部署指南](./deployment_guide.md)
- [运营手册](./operation_manual.md)
- [故障排查](./troubleshooting.md)
- [备份与恢复](./backup_restore.md)
- [灾难恢复](./disaster_recovery.md)
