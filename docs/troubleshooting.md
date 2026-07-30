# ICYQuant 故障排除指南

> 常见问题、诊断工具、恢复流程与支持渠道

## 目录

- [常见问题](#常见问题)
- [诊断工具](#诊断工具)
- [恢复流程](#恢复流程)
- [支持升级](#支持升级)
- [FAQ](#faq)

---

## 常见问题

### 问题分类

| 类别 | 常见问题 | 参考章节 |
|------|----------|----------|
| **部署问题** | 服务启动失败、数据库连接失败、端口冲突 | [部署故障](#部署故障) |
| **网络问题** | API 超时、交易所连接断开、WebSocket 断开 | [网络故障](#网络故障) |
| **交易问题** | 订单无法创建、订单被拒绝、订单无法成交 | [交易故障](#交易故障) |
| **数据问题** | 行情数据延迟、K线数据缺失、数据不一致 | [数据故障](#数据故障) |
| **性能问题** | 响应缓慢、资源占用高、内存泄漏 | [性能故障](#性能故障) |
| **安全问题** | 认证失败、权限不足、TLS 错误 | [安全故障](#安全故障) |

---

### 部署故障

#### 1. 服务启动失败

**症状：** Pod 一直处于 CrashLoopBackOff 状态

**诊断步骤：**

```bash
# 查看 Pod 状态
kubectl get pods -n icyquant
kubectl describe pod <pod-name> -n icyquant

# 查看容器日志
kubectl logs <pod-name> -n icyquant --previous

# 常见原因
# 1. 数据库连接失败
# 2. 配置文件错误
# 3. 端口冲突
# 4. 资源不足
```

**修复方案：**

```bash
# 检查数据库连接
kubectl exec -it <pod> -- python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine('postgresql+asyncpg://user:pass@host/db')
asyncio.run(engine.connect())
"

# 检查配置文件
kubectl get configmap icyquant-config -n icyquant -o yaml

# 检查资源限制
kubectl describe pod <pod-name> -n icyquant | grep -A 5 "Limits"

# 增加资源
kubectl edit deployment <service> -n icyquant
```

#### 2. 数据库连接失败

**症状：** 日志显示 `connection refused` 或 `timeout`

**诊断步骤：**

```bash
# 检查 PostgreSQL 状态
kubectl get pods -n icyquant -l app=postgres
kubectl exec -it postgres-primary -n icyquant -- pg_isready

# 检查网络连通性
kubectl exec -it <api-pod> -- ping postgres-primary
kubectl exec -it <api-pod> -- nc -zv postgres-primary 5432

# 检查连接数
kubectl exec -it postgres-primary -n icyquant -- psql -c "
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
"

# 检查 max_connections
kubectl exec -it postgres-primary -n icyquant -- psql -c "SHOW max_connections;"
```

**修复方案：**

```bash
# 如果连接数已满，清理空闲连接
kubectl exec -it postgres-primary -n icyquant -- psql -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND duration > interval '5 minutes';
"

# 增加连接池大小
kubectl set env deployment/icyquant-api \
  DB_POOL_SIZE=100 \
  DB_MAX_OVERFLOW=50 \
  -n icyquant

# 重启服务
kubectl rollout restart deployment icyquant-api -n icyquant
```

#### 3. 端口冲突

**症状：** Pod 启动失败，日志显示 `Address already in use`

**诊断步骤：**

```bash
# 检查端口占用
kubectl get svc -n icyquant | grep <port>
ss -tlnp | grep <port>

# 检查服务配置
kubectl get deployment <service> -n icyquant -o yaml | grep port
```

**修复方案：**

```bash
# 修改服务端口
kubectl edit deployment <service> -n icyquant

# 或者终止占用进程
kubectl exec -it <pod> -- fuser -k <port>/tcp
```

---

### 网络故障

#### 1. API 请求超时

**症状：** API 请求响应时间超过 5 秒或超时

**诊断步骤：**

```bash
# 检查 API Pod 资源
kubectl top pods -n icyquant -l app=icyquant-api

# 检查 API 日志
kubectl logs -l app=icyquant-api -n icyquant --tail=500 | grep -E "timeout|slow"

# 检查网络延迟
kubectl exec -it <api-pod> -- curl -s -o /dev/null -w "%{time_total}" http://postgres:5432

# 检查 Istio 代理状态
istioctl proxy-status
istioctl proxy-config cluster <api-pod>

# 检查 Sidecar 资源
kubectl exec -it <api-pod> -- top -b -n 1 | grep istio-proxy
```

**修复方案：**

```bash
# 临时增加超时
kubectl set env deployment/icyquant-api \
  REQUEST_TIMEOUT=60 \
  -n icyquant

# 增加 API 副本数
kubectl scale deployment icyquant-api -n icyquant --replicas=15

# 检查并优化慢查询
kubectl exec -it postgres-primary -n icyquant -- psql -c "
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
"
```

#### 2. 交易所连接断开

**症状：** 行情数据中断，订单无法送达

**诊断步骤：**

```bash
# 检查 Market Gateway 状态
kubectl get pods -n icyquant -l app=icyquant-market-gateway
kubectl logs -l app=icyquant-market-gateway -n icyquant --tail=100

# 检查 WebSocket 连接状态
icyquant market status

# 检查网络连通性
kubectl exec -it <gateway-pod> -- curl -s https://api.binance.com/api/v3/ping

# 检查 DNS 解析
kubectl exec -it <gateway-pod> -- nslookup api.binance.com
```

**修复方案：**

```bash
# 重启 Market Gateway
kubectl rollout restart deployment icyquant-market-gateway -n icyquant

# 如果持续断开，检查网络策略
kubectl get networkpolicy -n icyquant
kubectl describe networkpolicy default-deny -n icyquant

# 检查外部网络
curl -s https://api.binance.com/api/v3/ping
```

#### 3. WebSocket 连接问题

**症状：** WebSocket 频繁断开或无法建立

**诊断步骤：**

```bash
# 检查 Istio 配置
istioctl proxy-config listener <pod> | grep 8080

# 检查 WebSocket 超时设置
kubectl get deployment <service> -n icyquant -o yaml | grep websocket

# 检查 Nginx Ingress 配置
kubectl get ingress -n icyquant -o yaml | grep websocket
```

**修复方案：**

```bash
# 配置 Nginx WebSocket 支持
# 在 Ingress 中添加 annotations
nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
nginx.ingress.kubernetes.io/configuration-snippet: |
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
```

---

### 交易故障

#### 1. 订单无法创建

**症状：** `POST /api/v1/orders` 返回错误

**诊断步骤：**

```bash
# 查看错误响应
curl -v -X POST https://api.icyquant.io/api/v1/orders \
  -H "Authorization: Bearer <token>" \
  -d '{"symbol":"BTCUSDT","side":"BUY","quantity":0.5}'

# 检查风控状态
icyquant risk check --order-id <order-id>

# 检查账户余额
icyquant account balance

# 检查 OMS 日志
kubectl logs -l app=icyquant-oms -n icyquant --tail=100

# 检查策略状态
icyquant strategy list
```

**常见原因与修复：**

| 原因 | 错误信息 | 修复 |
|------|----------|------|
| 余额不足 | `Insufficient funds` | 充值或减少下单量 |
| 风控拒绝 | `Risk check failed` | 调整策略参数或风控限额 |
| 交易对不可用 | `Symbol not supported` | 检查交易对配置 |
| 数量精度错误 | `Invalid quantity` | 调整数量到正确精度 |
| 重复订单 | `Duplicate order` | 使用不同的 client_order_id |

#### 2. 订单被风控拒绝

**症状：** 订单创建成功但被风控引擎拒绝

**诊断步骤：**

```bash
# 查看风控详情
icyquant risk check --order-id <order-id>

# 查看风控日志
kubectl logs -l app=icyquant-risk -n icyquant --tail=200 | grep <order-id>

# 查看当前风险限额
icyquant risk limits

# 查看组合风险状态
icyquant risk dashboard
```

**修复方案：**

```bash
# 如果是仓位限制，调整限额
icyquant risk set-limit --metric position_size --value 0.40

# 如果是杠杆限制，增加限额
icyquant risk set-limit --metric max_leverage --value 8.0

# 如果是日亏损限制，等待次日或手动重置
icyquant risk reset-daily-loss --portfolio pf_001
```

#### 3. 订单无法成交

**症状：** 订单已提交但长时间处于 PENDING 状态

**诊断步骤：**

```bash
# 查看订单状态
icyquant order show <order-id>

# 检查执行日志
kubectl logs -l app=icyquant-ems -n icyquant --tail=100 | grep <order-id>

# 检查交易所连接
icyquant market status

# 检查市场流动性
icyquant market depth BTCUSDT --limit 10
```

**修复方案：**

```bash
# 订单可能价格超出市场范围
# 使用市价单替代限价单

# 如果是流动性不足，等待价格回归或调整价格

# 取消后重新下单
icyquant order cancel <order-id>
icyquant order create --symbol BTCUSDT --side BUY --quantity 0.5 --type MARKET
```

---

### 数据故障

#### 1. 行情数据延迟

**症状：** 行情数据比交易所延迟超过 1 秒

**诊断步骤：**

```bash
# 检查 Market Gateway 日志
kubectl logs -l app=icyquant-market-gateway -n icyquant --tail=50

# 检查 WebSocket 连接延迟
kubectl exec -it <gateway-pod> -- python -c "
import websocket
ws = websocket.create_connection('wss://stream.binance.com:9443/ws/btcusdt@ticker')
# 测量延迟
"

# 检查数据处理延迟
kubectl logs -l app=icyquant-market-gateway -n icyquant | grep "processing_time"

# 检查 Kafka 消费延迟
kafka-consumer-groups.sh --describe --group market-data-processor
```

**修复方案：**

```bash
# 重启 Market Gateway
kubectl rollout restart deployment icyquant-market-gateway -n icyquant

# 增加消费者实例
kubectl scale deployment market-data-processor -n icyquant --replicas=5

# 增加 Kafka 分区
kafka-topics.sh --alter --topic market-data --partitions=64
```

#### 2. K 线数据缺失

**症状：** 获取 K 线数据时出现空洞或缺失

**诊断步骤：**

```bash
# 检查数据完整性
icyquant market candles BTCUSDT --interval 1h --limit 1000 | jq '.candles | length'

# 对比交易所原始数据
curl "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=1000" | jq 'length'

# 检查数据管道
kubectl logs -l app=icyquant-data -n icyquant --tail=100 | grep -i "error\|fail"
```

**修复方案：**

```bash
# 触发数据回填
icyquant data backfill --symbol BTCUSDT --from 2024-01-01 --to 2024-12-31 --interval 1h

# 检查数据管道配置
kubectl get configmap data-pipeline -n icyquant -o yaml
```

#### 3. 数据不一致

**症状：** 不同查询返回的数据不一致

**诊断步骤：**

```bash
# 检查事件处理延迟
kubectl logs -l app=icyquant-event-processor -n icyquant | grep "lag"

# 检查数据库复制延迟
kubectl exec -it postgres-primary -n icyquant -- psql -c "
SELECT * FROM pg_stat_replication;
"

# 对比主从数据
# 在主库
SELECT count(*) FROM orders;
# 在从库
SELECT count(*) FROM orders;
```

**修复方案：**

```bash
# 等待复制完成
# 或强制同步
kubectl exec -it postgres-primary -n icyquant -- psql -c "
SELECT pg_current_wal_lsn();
"

# 如果复制中断，重建从库
pg_basebackup -h postgres-primary -U replicator -D /var/lib/postgresql/data
```

---

### 性能故障

#### 1. API 响应缓慢

**症状：** API P95 响应时间超过 500ms

**诊断步骤：**

```bash
# 查看实时延迟
open http://grafana.icyquant.io/d/api-gateway

# 检查 Pod 资源使用
kubectl top pods -n icyquant -l app=icyquant-api

# 检查数据库查询性能
kubectl exec -it postgres-primary -n icyquant -- psql -c "
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 5;
"

# 检查 Redis 缓存命中率
kubectl exec -it redis-master -n icyquant -- redis-cli INFO stats | grep keyspace_hits
kubectl exec -it redis-master -n icyquant -- redis-cli INFO stats | grep keyspace_misses
```

**修复方案：**

```bash
# 优化数据库查询
# 添加缺失索引
kubectl exec -it postgres-primary -n icyquant -- psql -c "
CREATE INDEX CONCURRENTLY idx_orders_symbol_time
ON orders (symbol, created_at DESC);
"

# 增加缓存时间
kubectl set env deployment/icyquant-api \
  CACHE_TTL=3600 \
  -n icyquant

# 增加 API 副本
kubectl scale deployment icyquant-api -n icyquant --replicas=15
```

#### 2. 内存泄漏

**症状：** Pod 内存持续增长直至 OOM

**诊断步骤：**

```bash
# 监控内存趋势
kubectl top pods -n icyquant --containers

# 查看 OOM 事件
kubectl get events -n icyquant --field-selector reason=OOMKilling

# 内存快照
kubectl exec -it <pod> -- python -c "
import tracemalloc
tracemalloc.start()
# ... 运行一段时间 ...
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:10]:
    print(stat)
"

# 检查 GC 日志
kubectl logs <pod> --tail=200 | grep -i "gc\|memory\|leak"
```

**修复方案：**

```bash
# 临时：重启服务
kubectl rollout restart deployment <service> -n icyquant

# 临时：增加内存限制
kubectl edit deployment <service> -n icyquant
# 修改 limits.memory

# 永久：需要代码层面修复
# 分析内存快照，定位泄漏点
```

#### 3. Kafka 消费延迟

**症状：** 订单/行情处理延迟增加

**诊断步骤：**

```bash
# 检查消费者 Lag
kafka-consumer-groups.sh --bootstrap-server kafka:9092 --describe

# 检查 Broker 状态
kubectl get pods -n icyquant -l app=kafka

# 检查消费性能
kubectl top pods -n icyquant -l app=order-processor

# 检查 Kafka Topic 配置
kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic orders
```

**修复方案：**

```bash
# 增加消费者实例
kubectl scale deployment order-processor -n icyquant --replicas=10

# 增加 Topic 分区数
kafka-topics.sh --bootstrap-server kafka:9092 --alter --topic orders --partitions=32

# 优化消费者代码
# 增加批量处理大小
```

---

### 安全故障

#### 1. 认证失败

**症状：** API 返回 401 Unauthorized

**诊断步骤：**

```bash
# 检查 Token 是否有效
icyquant auth whoami

# 检查 Token 过期时间
python -c "
import jwt
payload = jwt.decode(token, options={'verify_signature': False})
print(f'Expires: {payload[\"exp\"]}')
print(f'Still valid: {payload[\"exp\"] > time.time()}')
"

# 检查 JWT 密钥是否一致
kubectl get secret icyquant-auth-secret -n icyquant -o yaml

# 检查时钟同步
kubectl exec -it <pod> -- date
kubectl exec -it postgres-primary -n icyquant -- date
```

**修复方案：**

```bash
# 重新登录获取新 Token
icyquant auth logout
icyquant auth login --api-key YOUR_API_KEY

# 如果是密钥不一致，重新部署
kubectl rollout restart deployment icyquant-api -n icyquant
```

#### 2. 权限不足

**症状：** API 返回 403 Forbidden

**诊断步骤：**

```bash
# 检查当前用户权限
icyquant auth whoami

# 检查角色配置
kubectl get configmap rbac-config -n icyquant -o yaml

# 检查特定权限
icyquant auth check-permission --permission create_order
```

**修复方案：**

```bash
# 请求增加权限（需要管理员操作）
# 管理员执行
icyquant user add-role --user usr_001 --role trader

# 检查 RBAC 配置是否正确
```

#### 3. TLS 证书错误

**症状：** HTTPS 连接返回 SSL 错误

**诊断步骤：**

```bash
# 检查证书有效期
openssl s_client -connect api.icyquant.io:443 | openssl x509 -noout -dates

# 检查证书链
openssl s_client -connect api.icyquant.io:443 -showcerts

# 检查 cert-manager 状态
kubectl get certificates -n icyquant
kubectl describe certificate icyquant-tls -n icyquant
```

**修复方案：**

```bash
# 手动触发证书更新
kubectl delete certificate icyquant-tls -n icyquant
# cert-manager 会自动重新签发

# 或直接更新 Secret
kubectl create secret tls icyquant-tls \
  --cert=tls.crt \
  --key=tls.key \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## 诊断工具

### CLI 诊断命令

```bash
# 系统诊断
icyquant diagnose system

# 网络诊断
icyquant diagnose network

# 数据库诊断
icyquant diagnose database

# 交易所连接诊断
icyquant diagnose exchanges

# 全量诊断
icyquant diagnose all --output report.json
```

### 日志诊断

```bash
# 查看最近错误
kubectl logs -l app=icyquant-api -n icyquant --tail=500 | grep "ERROR"

# 按 Trace ID 追踪
kubectl logs -n icyquant --all-containers=true | grep "trace-id"

# 按时间范围
kubectl logs -l app=icyquant-api -n icyquant --since="30m" | grep "order"

# 导出日志
kubectl logs -n icyquant -l app=icyquant-api --since="1h" > api-logs.json
```

### 指标诊断

```bash
# 查看关键指标
curl -s http://prometheus:9090/api/v1/query?query=up | jq .

# 查询特定指标
curl -s 'http://prometheus:9090/api/v1/query?query=rate(icyquant_requests_total[5m])' | jq .

# 告警状态
curl -s http://alertmanager:9093/api/v2/alerts | jq .
```

### Kubernetes 诊断

```bash
# Pod 诊断
kubectl describe pod <pod-name> -n icyquant
kubectl logs <pod-name> -n icyquant --previous
kubectl exec -it <pod-name> -n icyquant -- sh

# 节点诊断
kubectl describe node <node-name>
kubectl top nodes

# 服务诊断
kubectl get svc -n icyquant
kubectl describe svc <svc-name> -n icyquant

# Ingress 诊断
kubectl describe ingress -n icyquant
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
```

### Istio 诊断

```bash
# 代理状态
istioctl proxy-status

# 代理配置
istioctl proxy-config cluster <pod>
istioctl proxy-config listener <pod>
istioctl proxy-config route <pod>

# 熔断状态
istioctl proxy-config clusters <pod> | grep -A5 circuit_breaker

# 流量跟踪
istioctl analyze
```

---

## 恢复流程

### 服务恢复

#### 单服务重启

```bash
# 滚动重启（零停机）
kubectl rollout restart deployment <service> -n icyquant

# 强制重启
kubectl delete pod -l app=<service> -n icyquant

# 扩缩容
kubectl scale deployment <service> -n icyquant --replicas=N
```

#### 数据库故障恢复

```bash
# 步骤 1：确认主从状态
kubectl exec -it postgres-primary -n icyquant -- psql -c "SELECT * FROM pg_stat_replication;"

# 步骤 2：提升从库（如果主库故障）
kubectl exec -it postgres-replica -n icyquant -- pg_ctl promote

# 步骤 3：重建主从关系
# 在新主库上执行
kubectl exec -it postgres-new-primary -n icyquant -- psql -c "
SELECT pg_create_physical_replication_slot('replica_slot');
"

# 步骤 4：更新应用配置
kubectl set env deployment/icyquant-api \
  DATABASE_URL="postgresql://user:pass@new-primary:5432/db" \
  -n icyquant

# 步骤 5：重建旧主库为从库
kubectl exec -it postgres-old-primary -n icyquant -- bash -c "
rm -rf /var/lib/postgresql/data/*
pg_basebackup -h new-primary -U replicator -D /var/lib/postgresql/data
"
```

#### 缓存恢复

```bash
# 重启 Redis
kubectl rollout restart statefulset redis-cluster -n icyquant

# 从 RDB 恢复数据
# 1. 停止 Redis
kubectl exec -it redis-master -n icyquant -- redis-cli shutdown
# 2. 替换 dump.rdb
kubectl cp backup/dump.rdb redis-master:/var/lib/redis/dump.rdb
# 3. 启动 Redis
kubectl exec -it redis-master -n icyquant -- redis-server /etc/redis/redis.conf

# 验证数据
kubectl exec -it redis-master -n icyquant -- redis-cli DBSIZE
```

#### 灾难恢复

```bash
# 1. 评估影响范围
# 确认故障范围和影响时间

# 2. 激活备用集群
kubectl config use-context secondary-cluster
helm install icyquant icyquant/icyquant -f values-secondary.yaml

# 3. 切换 DNS
aws route53 change-resource-record-sets ...

# 4. 恢复数据
# 从备份恢复数据库
pg_restore -h postgres -U icyquant -d icyquant backup.dump

# 5. 验证服务
curl https://secondary.icyquant.io/health

# 6. 通知用户
发送服务中断通知
```

---

## 支持升级

### 支持渠道

| 渠道 | 响应时间 | 适用场景 |
|------|----------|----------|
| **企业控制台** | 实时 | P0/P1 紧急故障 |
| **电话支持** | < 5 分钟 | P0 紧急故障 |
| **邮件支持** | < 4 小时 | P2/P3 问题 |
| **社区论坛** | < 24 小时 | 通用问题 |
| **GitHub Issues** | < 48 小时 | Bug 报告 |

### 升级流程

```
Level 1: 自助解决
  → 查阅文档
  → 使用诊断工具
  → 查看 FAQ
  ↓ 未解决

Level 2: 社区支持
  → GitHub Issues
  → 社区论坛
  → Stack Overflow
  ↓ 未解决

Level 3: 邮件支持
  → 发送邮件到 support@icyquant.io
  → 提供诊断报告
  → 等待工程师回复
  ↓ 未解决

Level 4: 企业支持
  → 企业控制台提交工单
  → 分配专属工程师
  → 电话沟通
  ↓ 未解决

Level 5: 紧急响应
  → 电话通知值班工程师
  → 启动紧急响应流程
  → 现场支持（如需要）
```

### 提交问题时请提供

```markdown
## 问题描述
<!-- 简明描述问题 -->

## 环境信息
- ICYQuant 版本: 0.4.0
- 部署方式: Docker / Kubernetes / Helm
- Kubernetes 版本: 1.28
- 数据库版本: PostgreSQL 16
- 操作系统: Ubuntu 22.04

## 复现步骤
1. 执行 `...`
2. 观察 `...`
3. 预期 `...`

## 诊断信息
```bash
icyquant diagnose all --output report.json
kubectl logs <pod> --tail=200
kubectl describe pod <pod>
```

## 日志片段
<!-- 粘贴相关日志 -->

## 截图
<!-- 粘贴相关截图 -->
```

---

## FAQ

### 注册与账户

**Q: 如何创建 ICYQuant 账户？**
A: 访问 [https://portal.icyquant.io](https://portal.icyquant.io) 注册。企业用户可联系 enterprise@icyquant.io 申请企业账户。

**Q: 忘记密码怎么办？**
A: 在登录页面点击"忘记密码"，通过注册邮箱接收重置链接。

### 安装与部署

**Q: 最低硬件要求是什么？**
A: 4 核 CPU、8GB 内存、50GB SSD。生产环境推荐 8+ 核、16+ GB、500GB NVMe。

**Q: 支持哪些操作系统？**
A: 支持 Linux（Ubuntu 20.04+、CentOS 8+）、macOS 12+、Windows Server 2019+。推荐使用 Linux。

**Q: Docker 和 Helm 部署如何选择？**
A: 单机测试用 Docker Compose；生产环境使用 Kubernetes + Helm。

### 交易相关

**Q: 支持哪些交易所？**
A: Binance、Alpaca、Interactive Brokers、MT5、CTP。更多交易所可通过插件扩展。

**Q: 支持哪些交易对？**
A: 取决于连接的交易所。ICyQuant 支持所有交易所提供的现货和合约交易对。

**Q: 最小下单量是多少？**
A: 取决于交易所规则。ICyQuant 会自动检查订单精度并调整。

**Q: 可以同时运行多少个策略？**
A: 取决于系统资源。单集群建议 10-50 个并发策略。

### 安全相关

**Q: 数据加密吗？**
A: 所有数据传输使用 TLS 1.3 加密，静态敏感数据使用 AES-256-GCM 加密。

**Q: API Key 如何保护？**
A: API Key 仅显示一次，存储时使用 SHA-256 哈希。密钥通过 HashiCorp Vault 或 AWS KMS 管理。

**Q: 支持双因素认证吗？**
A: 支持 TOTP 双因素认证，可在账户设置中启用。

**Q: 合规性如何？**
A: ICYQuant 平台已通过 SOC2 Type II 和 ISO 27001 认证，支持 SEC、CFTC、MiFID II 等监管报告。

### 计费相关

**Q: 如何计费？**
A: 按订阅模式计费，分为社区版、专业版和企业版。交易相关费用按交易量计费。

**Q: 支持哪些支付方式？**
A: 支持信用卡、银行转账、USDT 等。

**Q: 如何升级版本？**
A: 在用户控制台选择升级计划，或联系 sales@icyquant.io。

### 技术支持

**Q: 如何获取技术支持？**
A: 社区用户通过 GitHub Issues 或论坛获取支持。企业用户享受 7×24 小时优先级支持。

**Q: 响应时间是多少？**
A: P0 紧急问题 < 5 分钟，P1 < 30 分钟，P2 < 4 小时，P3 < 24 小时。

**Q: 是否提供专业服务？**
A: 提供部署咨询、定制开发、培训、架构设计等专业服务。

---

**文档版本**: 1.0
**创建日期**: 2026-07-30
**适用版本**: ICYQuant v0.4.0 GA