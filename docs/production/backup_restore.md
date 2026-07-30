# ICYQuant 备份与恢复指南

## 1. 备份策略

### 1.1 备份类型

| 类型 | 频率 | 保留期 | 恢复速度 | 存储位置 |
|------|------|--------|----------|----------|
| 全量备份 | 每周日 02:00 | 30 天 | 慢 | 主存储 + 异地 |
| 增量备份 | 每日 03:00 | 14 天 | 中 | 主存储 + 异地 |
| 差量备份 | 每小时 | 7 天 | 快 | 主存储 |
| 日志归档 | 实时 | 7 天 | — | 对象存储 |

### 1.2 备份范围

```
┌────────────────────────────────────────────────────┐
│  ICYQuant 数据备份范围                              │
├────────────────────────────────────────────────────┤
│                                                    │
│  📁 需要备份的资产：                                │
│  ├─ PostgreSQL 数据库（全库）                      │
│  ├─ TimescaleDB 时序数据（行情、指标）             │
│  ├─ Redis 持久化数据（AOF + RDB）                  │
│  ├─ Kafka Topic 消息（订单、成交）                 │
│  ├─ 配置文件（ConfigMap, Secret）                  │
│  ├─ 交易日志（订单、成交、风控决策）               │
│  └─ AI 模型文件（权重、推理缓存）                  │
│                                                    │
│  ❌ 不备份的资产：                                  │
│  ├─ 临时文件、临时数据                              │
│  ├─ 可从源头重建的数据                             │
│  └─ 非关键的中间结果                               │
│                                                    │
└────────────────────────────────────────────────────┘
```

### 1.3 RPO/RTO 目标

| 系统 | RPO (恢复点目标) | RTO (恢复时间目标) |
|------|------------------|-------------------|
| PostgreSQL | ≤ 5 分钟 | ≤ 1 小时 |
| TimescaleDB | ≤ 1 小时 | ≤ 2 小时 |
| Redis | ≤ 1 分钟 | ≤ 15 分钟 |
| Kafka | ≤ 5 分钟 | ≤ 30 分钟 |
| 配置/密钥 | 实时 | ≤ 5 分钟 |

---

## 2. 备份日程与保留

### 2.1 备份日程表

| 时间 | 类型 | 对象 | 执行方式 | 存储位置 |
|------|------|------|----------|----------|
| 周日 02:00 | 全量 | PostgreSQL 全库 | pg_dumpall + 压缩 | S3 冷存储 + 异地 |
| 周日 02:30 | 全量 | TimescaleDB | pg_dump + timescaledb-tools | S3 冷存储 + 异地 |
| 周日 03:00 | 全量 | Redis RDB | BGSAVE + 压缩 | S3 标准存储 |
| 每日 03:00 | 增量 | PostgreSQL 增量 | WAL 归档 + PITR | S3 标准存储 |
| 每小时 | 差量 | PostgreSQL WAL | archive_command | 本地 + S3 |
| 实时 | 日志 | Kafka | MirrorMaker + 冷存储 | S3 标准存储 |
| 每次变更 | 配置 | ConfigMap/Secret | GitOps + OPA | Git 仓库 + 加密存储 |

### 2.2 保留策略

```
保留层级：

Hot Storage (S3 标准) — 最近 7 天
  ├─ 每日增量备份
  ├─ 小时级 WAL
  └─ 最近的全量备份

Warm Storage (S3 低频访问) — 7-30 天
  ├─ 每周全量备份
  └─ 历史增量备份

Cold Storage (S3 Glacier) — 30-365 天
  ├─ 历史全量备份
  └─ 重要时点快照

Archive Storage (S3 深度归档) — 365 天+
  └─ 年度归档（监管要求）
```

#### 保留配置示例

```yaml
# S3 生命周期策略
VersioningConfiguration:
  Status: Enabled
Rules:
  - ID: "hot-to-warm"
    Prefix: "backups/"
    Status: Enabled
    Filter:
      Prefix: "backups/"
    Transitions:
      - Days: 7
        StorageClass: STANDARD_IA
  - ID: "warm-to-cold"
    Status: Enabled
    Filter:
      Prefix: "backups/"
    Transitions:
      - Days: 30
        StorageClass: GLACIER
    Expiration:
      Days: 365
  - ID: "temp-cleanup"
    Status: Enabled
    Filter:
      Prefix: "temp/"
    Expiration:
      Days: 1
```

### 2.3 命名规范

```
备份文件命名规则：
{system}_{type}_{date}_{time}_{env}.{ext}

示例：
pg_full_20240107_020000_prod.tar.gz
pg_wal_20240107_030000_prod.tar.gz
redis_rdb_20240107_030000_prod.rdb.gz
timescale_full_20240107_023000_prod.tar.gz
kafka_mirror_20240107_000000_prod.tar.gz
```

---

## 3. 备份实施

### 3.1 PostgreSQL 全量备份

```bash
#!/bin/bash
# pg_full_backup.sh - PostgreSQL 全量备份

set -euo pipefail

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/postgresql/full/${BACKUP_DATE}"
S3_PATH="s3://icyquant-backups/prod/postgresql/full/${BACKUP_DATE}"

mkdir -p "$BACKUP_DIR"

# 使用 pg_dumpall 进行全量备份
echo "开始 PostgreSQL 全量备份..."

kubectl exec -it postgresql-0 -n icyquant-prod -- \
  pg_dumpall \
  -U "$PG_USER" \
  --clean \
  --if-exists \
  --encoding=UTF8 \
  > "$BACKUP_DIR/all-databases.sql"

# 压缩备份
gzip -9 "$BACKUP_DIR/all-databases.sql"

# 获取备份元数据
cat > "$BACKUP_DIR/metadata.json" << EOF
{
  "backup_type": "full",
  "database": "all",
  "timestamp": "$(date -Iseconds)",
  "postgresql_version": "$(kubectl exec -it postgresql-0 -n icyquant-prod -- psql -U $PG_USER -c 'SELECT version();')",
  "size": "$(du -h $BACKUP_DIR/all-databases.sql.gz | cut -f1)"
}
EOF

# 上传到 S3
aws s3 cp "$BACKUP_DIR/" "$S3_PATH/" --recursive
aws s3 cp "$BACKUP_DIR/all-databases.sql.gz" "s3://icyquant-backups-异地/prod/postgresql/full/${BACKUP_DATE}/"

# 生成 SHA256 校验码
sha256sum "$BACKUP_DIR/all-databases.sql.gz" > "$BACKUP_DIR/checksums.txt"
aws s3 cp "$BACKUP_DIR/checksums.txt" "$S3_PATH/"

echo "PostgreSQL 全量备份完成: $BACKUP_DIR"
```

### 3.2 PostgreSQL 增量备份（WAL 归档）

```bash
# 配置 WAL 归档
# postgresql.conf
archive_mode = on
archive_command = 'date +%s > /tmp/archived_wal_time && cp %p /backups/wal/%f'
archive_timeout = 300

# 设置 WAL 归档调度
crontab -e
# 每小时检查归档状态
0 * * * * /scripts/check_wal_archive.sh >> /var/log/wal_archive.log 2>&1

# WAL 归档上传脚本
#!/bin/bash
# wal_archive_upload.sh

set -e

BACKUP_DIR="/backups/postgresql/wal"
S3_PATH="s3://icyquant-backups/prod/postgresql/wal/$(date +%Y%m%d)"

find "$BACKUP_DIR" -name "*.gz" -newer "$BACKUP_DIR/.last_upload" -exec \
  aws s3 cp {} "$S3_PATH/" \;

touch "$BACKUP_DIR/.last_upload"
```

### 3.3 Redis 备份

```bash
#!/bin/bash
# redis_backup.sh - Redis 备份

set -e

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/backups/redis/dump_${BACKUP_DATE}.rdb"

# 触发 BGSAVE
kubectl exec -it redis-master-0 -n icyquant-prod -- redis-cli BGSAVE

# 等待 BGSAVE 完成
while true; do
  LAST_SAVE=$(kubectl exec -it redis-master-0 -n icyquant-prod -- redis-cli LASTSAVE)
  CURRENT_TIME=$(date +%s)
  if [ $((CURRENT_TIME - LAST_SAVE)) -lt 60 ]; then
    break
  fi
  sleep 5
done

# 复制 RDB 文件
kubectl cp icyquant-prod/redis-master-0:/data/dump.rdb "$BACKUP_FILE"

# 压缩并上传
gzip -9 "$BACKUP_FILE"
aws s3 cp "${BACKUP_FILE}.gz" "s3://icyquant-backups/prod/redis/dump_${BACKUP_DATE}.rdb.gz"
aws s3 cp "${BACKUP_FILE}.gz" "s3://icyquant-backups-异地/prod/redis/dump_${BACKUP_DATE}.rdb.gz"

# 清理本地超过 7 天的备份
find /backups/redis -name "*.rdb.gz" -mtime +7 -delete

echo "Redis 备份完成: ${BACKUP_FILE}.gz"
```

### 3.4 TimescaleDB 备份

```bash
#!/bin/bash
# timescaledb_backup.sh - TimescaleDB 备份

set -e

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/timescaledb/${BACKUP_DATE}"

mkdir -p "$BACKUP_DIR"

# TimescaleDB 全量备份
kubectl exec -it timescaledb-0 -n icyquant-prod -- \
  ts_dump \
  -U "$PG_USER" \
  -h localhost \
  -d icyquant_metrics \
  --data-only \
  --format=tar \
  > "$BACKUP_DIR/timescaledb_backup.tar"

# 压缩
gzip -9 "$BACKUP_DIR/timescaledb_backup.tar"

# 上传
aws s3 cp "${BACKUP_DIR}/timescaledb_backup.tar.gz" \
  "s3://icyquant-backups/prod/timescaledb/${BACKUP_DATE}/"

# 校验
echo "PostgreSQL 全量备份完成: $BACKUP_DIR"
```

### 3.5 Kafka 备份

```bash
#!/bin/bash
# kafka_backup.sh - Kafka Topic 备份

set -e

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)

# 方法 1: 使用 MirrorMaker 镜像到备份集群
kafka-mirror-maker.sh \
  --bootstrap-server kafka:9092 \
  --whitelist "icyquant-orders,icyquant-trades,icyquant-marketdata" \
  --target.cluster.bootstrap.servers kafka-backup:9092

# 方法 2: 导出到文件（冷备份）
for TOPIC in icyquant-orders icyquant-trades icyquant-marketdata; do
  echo "导出 Topic: $TOPIC"
  
  kafka-console-consumer.sh \
    --bootstrap-server kafka:9092 \
    --topic "$TOPIC" \
    --from-beginning \
    --max-messages 1000000 \
    --timeout-ms 30000 \
    > "/backups/kafka/${TOPIC}_${BACKUP_DATE}.json"
  
  gzip -9 "/backups/kafka/${TOPIC}_${BACKUP_DATE}.json"
  aws s3 cp "/backups/kafka/${TOPIC}_${BACKUP_DATE}.json.gz" \
    "s3://icyquant-backups/prod/kafka/${BACKUP_DATE}/"
done
```

### 3.6 配置备份

```bash
#!/bin/bash
# config_backup.sh - 配置文件备份

set -e

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/config/${BACKUP_DATE}"

mkdir -p "$BACKUP_DIR"

# 备份 ConfigMap
kubectl get configmaps -n icyquant-prod -o yaml > "$BACKUP_DIR/configmaps.yaml"

# 备份 Secret（导出时需加密）
kubectl get secrets -n icyquant-prod -o yaml | \
  kubeseal --format=yaml > "$BACKUP_DIR/secrets-sealed.yaml"

# 备份 Helm Release
helm get values icyquant --namespace icyquant-prod > "$BACKUP_DIR/helm-values.yaml"
helm history icyquant --namespace icyquant-prod > "$BACKUP_DIR/helm-history.txt"

# 备份 CRD 和自定义资源
kubectl get crd > "$BACKUP_DIR/crds.yaml"
kubectl get customresourcedefinition > "$BACKUP_DIR/crds.yaml"

# 加密并上传
tar czf "$BACKUP_DIR/backup.tar.gz" -C "$BACKUP_DIR" .
openssl enc -aes-256-cbc -salt -pbkdf2 \
  -in "$BACKUP_DIR/backup.tar.gz" \
  -out "$BACKUP_DIR/backup.tar.gz.enc" \
  -pass env:BACKUP_ENCRYPTION_KEY

aws s3 cp "$BACKUP_DIR/backup.tar.gz.enc" \
  "s3://icyquant-backups/prod/config/${BACKUP_DATE}/"

echo "配置备份完成: $BACKUP_DIR"
```

---

## 4. 备份验证

### 4.1 验证流程

```
步骤 1: 完整性校验
  - SHA256 校验和匹配
  - 文件大小在预期范围内
  - 压缩文件可正常解压

步骤 2: 可读性校验
  - SQL 文件可以正常解析（pg_restore --list）
  - RDB 文件可以被 Redis 加载
  - 配置文件 YAML 语法正确

步骤 3: 抽样恢复
  - 在 Staging 环境恢复
  - 验证关键表数据完整性
  - 检查行数、主键索引

步骤 4: 业务验证
  - 恢复后启动应用
  - 执行核心业务冒烟测试
  - 确认数据一致性
```

### 4.2 自动化验证脚本

```bash
#!/bin/bash
# verify_backup.sh - 备份验证脚本

set -e

BACKUP_PATH="${1:-s3://icyquant-backups/prod/postgresql/full}"
ENV="${2:-staging}"

echo "=== 备份验证 ==="

# 1. 下载最新备份
LATEST_BACKUP=$(aws s3 ls "$BACKUP_PATH/" --recursive | \
  sort | tail -1 | awk '{print $4}')
echo "验证备份: $LATEST_BACKUP"

# 2. 下载并校验
TEMP_DIR=$(mktemp -d)
aws s3 cp "$LATEST_BACKUP" "$TEMP_DIR/" --recursive

# SHA256 校验
if [ -f "$TEMP_DIR/checksums.txt" ]; then
  cd "$TEMP_DIR" && sha256sum -c checksums.txt
  cd -
else
  echo "警告: 无校验和文件"
fi

# 3. 解压验证
for f in "$TEMP_DIR"/*.gz; do
  echo "解压: $f"
  gunzip -k "$f"
done

# 4. SQL 可读性检查
for f in "$TEMP_DIR"/*.sql; do
  if pg_restore --list "$f" > /dev/null 2>&1; then
    echo "✓ $f 格式正确"
  else
    echo "✗ $f 格式错误"
  fi
done

# 5. 恢复到 Staging 环境
echo "恢复到 Staging 环境..."
cat "$TEMP_DIR/all-databases.sql" | \
  kubectl exec -i postgresql-0 -n icyquant-stg -- \
  psql -U "$PG_USER" -d postgres

# 6. 验证数据
echo "数据抽样验证..."
kubectl exec -it postgresql-0 -n icyquant-stg -- \
  psql -U "$PG_USER" -c "
    SELECT 'accounts', count(*) FROM accounts
    UNION ALL
    SELECT 'orders', count(*) FROM orders
    UNION ALL
    SELECT 'positions', count(*) FROM positions
    UNION ALL
    SELECT 'trades', count(*) FROM trades;
  "

# 7. 清理
rm -rf "$TEMP_DIR"

echo "=== 备份验证完成 ==="
```

### 4.3 验证频率

| 验证类型 | 频率 | 范围 |
|----------|------|------|
| 自动化完整性校验 | 每次备份后 | 全量 |
| 抽样恢复验证 | 每周 | 随机选择最近备份 |
| 全量恢复演练 | 每季度 | 完整恢复 + 业务验证 |
| 灾难恢复演练 | 每半年 | 跨区域全量恢复 |

---

## 5. 恢复程序

### 5.1 配置恢复

#### 步骤

```bash
# 1. 下载配置备份
BACKUP_DATE="20240107_020000"
aws s3 cp "s3://icyquant-backups/prod/config/${BACKUP_DATE}/backup.tar.gz.enc" .

# 2. 解密
openssl enc -aes-256-cbc -d -salt -pbkdf2 \
  -in backup.tar.gz.enc \
  -out backup.tar.gz \
  -pass env:BACKUP_ENCRYPTION_KEY

# 3. 解压
tar xzf backup.tar.gz

# 4. 恢复 ConfigMap
kubectl apply -f configmaps.yaml -n icyquant-prod

# 5. 恢复 Secret（使用 Sealed Secrets 解密）
kubeseal --unseal -f secrets-sealed.yaml | kubectl apply -f -

# 6. 重启应用使配置生效
kubectl rollout restart deployment trading-engine -n icyquant-prod
kubectl rollout restart deployment order-service -n icyquant-prod
kubectl rollout restart deployment risk-engine -n icyquant-prod

# 7. 验证配置
kubectl get configmaps -n icyquant-prod
kubectl describe configmap icyquant-config -n icyquant-prod
```

### 5.2 数据库恢复

#### PostgreSQL 全量恢复

```bash
#!/bin/bash
# pg_restore.sh - PostgreSQL 恢复脚本

set -euo pipefail

BACKUP_DATE="${1:?用法: $0 <备份日期>}"
BACKUP_PATH="s3://icyquant-backups/prod/postgresql/full/${BACKUP_DATE}"

echo "=== PostgreSQL 恢复 ==="

# 1. 停止应用写入
kubectl scale deployment trading-engine --replicas=0 -n icyquant-prod
kubectl scale deployment order-service --replicas=0 -n icyquant-prod
kubectl scale deployment risk-engine --replicas=0 -n icyquant-prod
kubectl scale deployment market-data --replicas=0 -n icyquant-prod

# 2. 下载备份
TEMP_DIR="/restore/pg-${BACKUP_DATE}"
mkdir -p "$TEMP_DIR"
aws s3 cp "$BACKUP_PATH" "$TEMP_DIR/" --recursive

# 3. 恢复数据库
cat "$TEMP_DIR/all-databases.sql.gz" | gunzip | \
  kubectl exec -i postgresql-0 -n icyquant-prod -- \
  psql -U "$PG_USER" -d postgres

# 4. 恢复 WAL（增量）
# 按顺序回放 WAL 文件
for wal_file in $(aws s3 ls "s3://icyquant-backups/prod/postgresql/wal/" | \
  sort | awk '{print $4}'); do
  echo "回放 WAL: $wal_file"
  # 使用 pg_waldump 或 PITR
done

# 5. 重建索引和统计信息
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U "$PG_USER" -c "REINDEX DATABASE icyquant;"
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U "$PG_USER" -c "ANALYZE;"

# 6. 验证数据完整性
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U "$PG_USER" -c "
    SELECT 
      'accounts' as table_name, count(*) as row_count FROM accounts
    UNION ALL
    SELECT 'orders', count(*) FROM orders
    UNION ALL
    SELECT 'trades', count(*) FROM trades
    UNION ALL
    SELECT 'positions', count(*) FROM positions
    UNION ALL
    SELECT 'risk_events', count(*) FROM risk_events;
  "

# 7. 恢复应用
kubectl scale deployment market-data --replicas=4 -n icyquant-prod
kubectl scale deployment risk-engine --replicas=4 -n icyquant-prod
kubectl scale deployment order-service --replicas=6 -n icyquant-prod
kubectl scale deployment trading-engine --replicas=6 -n icyquant-prod

echo "=== PostgreSQL 恢复完成 ==="
```

#### Redis 恢复

```bash
#!/bin/bash
# redis_restore.sh - Redis 恢复脚本

set -euo pipefail

BACKUP_DATE="${1:?用法: $0 <备份日期>}"

# 1. 停止 Redis 写入
kubectl exec -it redis-master-0 -n icyquant-prod -- redis-cli CONFIG SET maxmemory-policy noeviction
kubectl exec -it redis-master-0 -n icyquant-prod -- redis-cli DEBUG FLUSHALL

# 2. 下载备份
TEMP_FILE="/restore/redis_${BACKUP_DATE}.rdb"
aws s3 cp "s3://icyquant-backups/prod/redis/dump_${BACKUP_DATE}.rdb.gz" .
gunzip -c "dump_${BACKUP_DATE}.rdb.gz" > "$TEMP_FILE"

# 3. 替换 RDB 文件并重启 Redis
kubectl cp "$TEMP_FILE" icyquant-prod/redis-master-0:/data/dump.rdb
kubectl rollout restart statefulset redis -n icyquant-prod

# 4. 等待 Redis 恢复
kubectl rollout status statefulset redis -n icyquant-prod

# 5. 验证数据
kubectl exec -it redis-master-0 -n icyquant-prod -- redis-cli INFO keyspace
kubectl exec -it redis-master-0 -n icyquant-prod -- redis-cli DBSIZE

echo "=== Redis 恢复完成 ==="
```

### 5.3 状态恢复

#### 交易状态恢复

```bash
#!/bin/bash
# state_recovery.sh - 交易状态恢复

set -e

BACKUP_DATE="${1:?用法: $0 <备份日期>}"

echo "=== 状态恢复 ==="

# 1. 确认数据库已恢复到目标时点
echo "数据库状态验证..."
curl -s "https://api.icyquant.io/actuator/health" | jq '.'

# 2. 恢复交易系统状态
echo "恢复交易系统状态..."

# 检查并恢复持仓一致性
curl -s "https://api.icyquant.io/api/v1/positions/reconcile" \
  -X POST -H "Authorization: Bearer $TOKEN"

# 恢复未完成订单
curl -s "https://api.icyquant.io/api/v1/orders/recovery" \
  -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"targetDate\": \"$BACKUP_DATE\"}"

# 恢复资金账户
curl -s "https://api.icyquant.io/api/v1/accounts/recovery" \
  -X POST -H "Authorization: Bearer $TOKEN"

# 3. 验证交易状态
echo "交易状态验证..."

# 检查持仓
POSITIONS=$(curl -s "https://api.icyquant.io/api/v1/positions" \
  -H "Authorization: Bearer $TOKEN" | jq '.data | length')
echo "持仓数量: $POSITIONS"

# 检查资金
BALANCE=$(curl -s "https://api.icyquant.io/api/v1/accounts/balance" \
  -H "Authorization: Bearer $TOKEN" | jq '.data.totalBalance')
echo "账户余额: $BALANCE"

# 4. 生成恢复报告
cat > "/restore/recovery_report_${BACKUP_DATE}.md" << EOF
# 恢复报告

- **恢复时间**: $(date)
- **目标时点**: $BACKUP_DATE
- **数据库状态**: VERIFIED
- **交易状态**: VERIFIED
- **持仓数量**: $POSITIONS
- **账户余额**: $BALANCE
- **执行人**: $(whoami)
EOF

echo "=== 状态恢复完成 ==="
```

---

## 6. 时点恢复（PITR）

### 6.1 适用场景

| 场景 | 说明 |
|------|------|
| 误删数据 | 误执行 DROP/DELETE，需恢复到删除前 |
| 错误更新 | 批量更新错误，需回滚 |
| 应用 Bug | Bug 写入错误数据 |
| 恶意操作 | 数据被恶意篡改 |

### 6.2 PITR 步骤

```bash
#!/bin/bash
# pitr_restore.sh - 时点恢复脚本

set -euo pipefail

TARGET_TIME="${1:?用法: $0 <目标时间, YYYY-MM-DDTHH:MM:SS>}"

echo "=== 时点恢复 (PITR) ==="
echo "目标时间: $TARGET_TIME"

# 1. 备份当前状态（安全起见）
./pg_full_backup.sh

# 2. 查找最近的全量备份
BASE_BACKUP=$(aws s3 ls "s3://icyquant-backups/prod/postgresql/full/" --recursive | \
  grep -E '[0-9]{8}_[0-9]{6}' | awk '{print $4}' | sort | head -1)

echo "基础备份: $BASE_BACKUP"

# 3. 下载全量备份
TEMP_DIR="/restore/pitr-${TARGET_TIME}"
mkdir -p "$TEMP_DIR"
aws s3 cp "$BASE_BACKUP" "$TEMP_DIR/" --recursive

# 4. 创建恢复实例
kubectl create pvc pitr-pg-restore -n icyquant-prod \
  --size=500Gi \
  --storage-class=ssd

# 5. 从全量备份恢复到新实例
cat "$TEMP_DIR/all-databases.sql.gz" | gunzip | \
  kubectl exec -i pitr-pg-restore-pod -n icyquant-prod -- \
  psql -U "$PG_USER" -d postgres

# 6. 回放 WAL 到目标时间
# 在恢复实例上配置 recovery_target_time
kubectl exec -it pitr-pg-restore-pod -n icyquant-prod -- \
  bash -c "
    echo 'restore_command = cp /wal_archive/%f %p' >> /var/lib/postgresql/data/postgresql.auto.conf
    echo 'recovery_target_time = \"$TARGET_TIME\"' >> /var/lib/postgresql/data/postgresql.auto.conf
    echo 'recovery_target_action = promote' >> /var/lib/postgresql/data/postgresql.auto.conf
  "

# 7. 启动恢复实例
kubectl exec -it pitr-pg-restore-pod -n icyquant-prod -- \
  pg_ctl start -D /var/lib/postgresql/data

# 8. 等待恢复完成并验证
while true; do
  STATUS=$(kubectl exec -it pitr-pg-restore-pod -n icyquant-prod -- \
    psql -U "$PG_USER" -c "SELECT pg_is_in_recovery();" | grep -o "f")
  if [ "$STATUS" = "f" ]; then
    echo "PITR 恢复完成"
    break
  fi
  echo "等待恢复中..."
  sleep 10
done

# 9. 验证数据完整性
echo "验证恢复结果..."
kubectl exec -it pitr-pg-restore-pod -n icyquant-prod -- \
  psql -U "$PG_USER" -c "SELECT count(*) FROM accounts;"

# 10. 切换生产到恢复实例
# 注意：这一步需要谨慎，建议在低峰期执行
./switch_to_restore_instance.sh pitr-pg-restore

echo "=== PITR 完成 ==="
```

---

## 7. 跨区域备份

### 7.1 架构

```
┌──────────────────────┐         ┌──────────────────────┐
│  主区域 (华东1)       │         │  备区域 (华北2)       │
│                      │         │                      │
│  ┌────────────────┐  │  异步   │  ┌────────────────┐  │
│  │  主集群        │──┼────────┼──▶│  灾备集群      │  │
│  └────────────────┘  │  同步   │  └────────────────┘  │
│         │            │         │         │            │
│         ▼            │         │         ▼            │
│  ┌────────────────┐  │  双向   │  ┌────────────────┐  │
│  │  S3 存储        │──┼────────┼──▶│  S3 存储        │  │
│  │  (主)          │  │  复制   │  │  (异地)        │  │
│  └────────────────┘  │         │  └────────────────┘  │
└──────────────────────┘         └──────────────────────┘
```

### 7.2 跨区域复制配置

```bash
# AWS S3 跨区域复制
aws s3api put-replication-configuration \
  --bucket icyquant-backups-prod \
  --replication-configuration '{
    "Role": "arn:aws:iam::123456789:role/s3-replication-role",
    "Rules": [
      {
        "ID": "replicate-all-backups",
        "Status": "Enabled",
        "Filter": {
          "Prefix": "backups/"
        },
        "Destination": {
          "Bucket": "arn:aws:s3:::icyquant-backups-dr",
          "StorageClass": "STANDARD_IA",
          "ReplicationTime": {
            "Status": "Enabled",
            "Time": {
              "Minutes": 15
            }
          },
          "Metrics": {
            "Status": "Enabled",
            "EventThreshold": {
              "Minutes": 15
            }
          }
        }
      }
    ]
  }'

# PostgreSQL 跨区域物理复制
# 在主库配置
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U "$PG_USER" -c \
  "SELECT pg_create_physical_replication_slot('dr_slot');"

# 在备库配置 primary_conninfo
kubectl exec -it postgresql-dr-0 -n icyquant-prod -- \
  bash -c "
    echo \"primary_conninfo = 'host=primary.example.com port=5432 user=replicator password=xxx application_name=dr'\" >> postgresql.auto.conf
    echo 'primary_slot_name = dr_slot' >> postgresql.auto.conf
  "

# TimescaleDB 跨区域复制
timescaledb-replication-add-node \
  --host dr-node.example.com \
  --port 5432 \
  --user repl_user \
  --password 'xxx'
```

### 7.3 异地备份清单

| 数据类型 | 主存储 | 异地存储 | 复制延迟 | 保留期 |
|----------|--------|----------|----------|--------|
| PostgreSQL 全量 | S3 标准 | S3 低频 | < 15 分钟 | 30 天 |
| PostgreSQL WAL | 本地 + S3 | S3 低频 | < 5 分钟 | 7 天 |
| TimescaleDB | S3 标准 | S3 低频 | < 30 分钟 | 30 天 |
| Redis RDB | 本地 + S3 | S3 低频 | < 15 分钟 | 14 天 |
| Kafka 消息 | 本地 | 异地集群 | 实时 | 7 天 |
| 配置文件 | Git | Git 镜像 | 实时 | 永久 |

---

## 8. 恢复测试计划

### 8.1 测试频率与范围

| 测试类型 | 频率 | 范围 | 负责团队 |
|----------|------|------|----------|
| 单表恢复测试 | 每周 | 随机表恢复到 Staging | DBA |
| 全量恢复测试 | 每月 | 全库恢复到独立环境 | DBA + DevOps |
| PITR 测试 | 每季度 | 时点恢复演练 | DBA |
| 跨区域恢复 | 每半年 | 灾备切换演练 | SRE |
| 灾难恢复演练 | 每年 | 完整 DR 流程 | SRE + 全团队 |

### 8.2 恢复测试检查清单

```
测试前：
□ 1. 已通知相关团队测试时间
□ 2. 已准备测试环境
□ 3. 已确认最近备份可用
□ 4. 已准备恢复脚本
□ 5. 已指定测试观察员

测试执行：
□ 1. 记录开始时间
□ 2. 执行恢复脚本
□ 3. 记录恢复完成时间
□ 4. 计算 RTO（实际恢复时间）
□ 5. 验证数据完整性
□ 6. 执行业务冒烟测试
□ 7. 记录发现的问题

测试后：
□ 1. 生成测试报告
□ 2. 归档测试日志
□ 3. 更新 RTO/RPO 实际值
□ 4. 制定改进计划（如有问题）
□ 5. 更新文档
```

### 8.3 恢复测试报告模板

```
# ICYQuant 恢复测试报告

## 基本信息
- **测试日期**: YYYY-MM-DD
- **测试类型**: [全量恢复 / PITR / 跨区域恢复]
- **执行人**: XXX
- **参与团队**: [DBA, DevOps, SRE]

## 测试目标
- 验证 RTO ≤ X 小时
- 验证 RPO ≤ X 分钟
- 验证数据完整性
- 验证业务可用性

## 测试过程
### 步骤 1: 备份选择
- 备份日期: YYYY-MM-DD HH:MM:SS
- 备份类型: [全量 / 增量]
- 校验和验证: PASS/FAIL

### 步骤 2: 恢复执行
- 开始时间: HH:MM:SS
- 完成时间: HH:MM:SS
- 实际 RTO: X 小时 X 分钟
- 与目标对比: [达标 / 未达标]

### 步骤 3: 数据验证
- 表数量: PASS/FAIL
- 行数一致性: PASS/FAIL
- 主键完整性: PASS/FAIL
- 索引完整性: PASS/FAIL

### 步骤 4: 业务验证
- 行情接收: PASS/FAIL
- 下单执行: PASS/FAIL
- 持仓查询: PASS/FAIL
- 风控检查: PASS/FAIL

## 发现的问题
1. [问题描述]
2. [问题描述]

## 改进措施
1. [改进项]
2. [改进项]

## 结论
- 测试结果: [通过 / 有条件通过 / 未通过]
- 审批人签字: XXX
```

---

## 附录

### A. 备份监控指标

| 指标 | 说明 | 告警阈值 |
|------|------|----------|
| backup_success_rate | 备份成功率 | < 99% 告警 |
| backup_duration | 备份耗时 | > 4 小时告警 |
| backup_size | 备份大小 | 突增/突降告警 |
| restore_duration | 恢复耗时 | > RTO 告警 |
| backup_age | 最近备份年龄 | > 26 小时告警 |
| cross_region_lag | 跨区域复制延迟 | > 30 分钟告警 |

### B. 参考文档

- [部署指南](./deployment_guide.md)
- [运营手册](./operation_manual.md)
- [故障排查](./troubleshooting.md)
- [灾难恢复](./disaster_recovery.md)
- [系统维护](./maintenance.md)
