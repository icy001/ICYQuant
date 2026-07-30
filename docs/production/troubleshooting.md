# ICYQuant 故障排查手册

## 1. 通用排查流程

### 1.1 故障分类

| 类别 | 现象 | 影响 | 紧急程度 |
|------|------|------|----------|
| 行情故障 | 行情数据中断或延迟 | 无法交易 | P0 |
| 交易故障 | 订单无法执行或延迟 | 交易受阻 | P0 |
| 风控故障 | 风控引擎误判或失效 | 风险失控/交易受阻 | P0 |
| AI 故障 | 模型推理失败或异常 | 策略失效 | P1 |
| 数据库故障 | 连接失败或性能下降 | 数据不可用 | P0 |
| 消息队列故障 | 消息积压或丢失 | 系统阻塞 | P1 |
| 基础设施 | 内存泄漏或资源耗尽 | 系统不稳定 | P1 |

### 1.2 通用排查步骤

```
步骤 1: 确认故障
  ├─ 监控告警是否已触发
  ├─ 影响范围（单用户/全部用户）
  ├─ 影响时间（瞬时/持续）
  └─ 业务影响（金额/交易笔数）

步骤 2: 收集信息
  ├─ 查看 Grafana 监控面板
  ├─ 分析 Loki 日志
  ├─ 检查 K8s Pod 状态
  ├─ 查看 Prometheus 指标
  └─ 询问用户反馈

步骤 3: 定位范围
  ├─ 基础设施层问题？
  ├─ 数据层问题？
  ├─ 应用层问题？
  └─ 外部依赖问题？

步骤 4: 诊断根因
  ├─ 使用排查手册对应章节
  ├─ 运行诊断脚本
  ├─ 分析 Trace 链路
  └─ 必要时启用详细日志

步骤 5: 实施修复
  ├─ 临时缓解（治标）
  ├─ 根因修复（治本）
  └─ 验证修复效果

步骤 6: 事后复盘
  ├─ 记录故障时间线
  ├─ 分析根因
  ├─ 制定改进措施
  └─ 更新排查手册
```

---

## 2. 故障排查详细手册

### 2.1 行情数据中断

#### 现象

- 用户反馈无法看到实时行情
- 行情服务 CPU 使用率骤降（无数据处理）
- WebSocket 连接数异常减少
- Broker 网关连接状态异常

#### 诊断步骤

```bash
# 步骤 1: 检查行情服务 Pod 状态
kubectl get pods -n icyquant-prod -l app=market-data
kubectl describe pod -l app=market-data -n icyquant-prod

# 步骤 2: 检查 Broker 网关连接
curl -s "https://api.icyquant.io/actuator/health/components/broker" | jq .
# 关注: broker.status, broker.details.gatewayConnected

# 步骤 3: 查看行情服务日志
kubectl logs -n icyquant-prod -l app=market-data --tail=500 | grep -E "ERROR|WARN|disconnect|timeout"

# 步骤 4: 检查 CTP 网关日志
# CTP 网关进程日志（在宿主机或专用 Pod）
kubectl logs -n icyquant-prod -l app=ctp-gateway --tail=200

# 步骤 5: 检查 Kafka 行情主题
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group market-data-group

# 步骤 6: 检查 Redis 行情缓存
kubectl exec -it redis-master-0 -n icyquant-prod -- redis-cli LLEN marketdata:IC2412
```

#### 常见原因与解决方案

| 原因 | 排查点 | 解决方案 |
|------|--------|----------|
| Broker 网关断连 | CTP Session 状态 | 重启 CTP 网关进程：`systemctl restart ctp-gateway` |
| 网络中断 | 网关与 Broker 网络延迟 | 检查 VPN/专线状态，必要时切换备用链路 |
| 行情服务崩溃 | Pod 状态 CrashLoopBackOff | `kubectl rollout restart deployment/market-data` |
| Kafka 分区不均衡 | 消费延迟过大 | 调整分区数或消费者数量 |
| 内存溢出 | Pod OOMKilled | 增加 Pod 内存限制或修复内存泄漏 |

#### 紧急修复

```bash
# 快速恢复行情
kubectl rollout restart deployment market-data -n icyquant-prod

# 如果 CTP 网关需要重启
# 登录 CTP 网关服务器
ssh ctp-gateway-server
# 检查网关进程
ps aux | grep ctp
# 重启网关
./restart_ctp_gateway.sh
# 验证行情恢复
tail -f /var/log/ctp-gateway/market-data.log
```

#### 验证恢复

```bash
# 订阅行情验证
curl -X GET "https://api.icyquant.io/api/v1/marketdata/subscribe?symbol=IC2412" \
  -H "Authorization: Bearer $TOKEN"

# 检查最新价是否在更新
PRICE=$(curl -s "https://api.icyquant.io/api/v1/marketdata/IC2412/tick" | jq '.data.lastPrice')
sleep 2
PRICE2=$(curl -s "https://api.icyquant.io/api/v1/marketdata/IC2412/tick" | jq '.data.lastPrice')
echo "价格变化: $PRICE -> $PRICE2"
```

### 2.2 订单执行延迟

#### 现象

- 用户下单后长时间未收到确认
- 订单状态卡在 PENDING
- 成交回执延迟 > 1 秒
- 风控检查耗时过长

#### 诊断步骤

```bash
# 步骤 1: 检查订单队列积压
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group order-processor-group
# 关注 lag 值，正常应 < 100

# 步骤 2: 检查订单处理延迟
# Prometheus 查询
# histogram_quantile(0.99, rate(order_processing_duration_seconds_bucket[5m]))
# 目标: P99 < 100ms

# 步骤 3: 检查交易引擎日志
kubectl logs -n icyquant-prod -l app=trading-engine --since=5m | grep -i "timeout\|slow\|delayed"

# 步骤 4: 检查 Redis 延迟
kubectl exec -it redis-master-0 -n icyquant-prod -- redis-cli INFO stats
# 关注 instantaneous_ops_per_sec, blocked_clients

# 步骤 5: 检查数据库查询性能
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c \
  "SELECT query, calls, mean_exec_time, total_exec_time 
   FROM pg_stat_statements 
   WHERE query ILIKE '%order%' 
   ORDER BY mean_exec_time DESC LIMIT 10;"

# 步骤 6: Thread Dump
kubectl exec -it deployment/trading-engine -n icyquant-prod -- \
  jstack 1 > /tmp/thread-dump.txt
# 检查线程阻塞情况
```

#### 常见原因与解决方案

| 原因 | 排查点 | 解决方案 |
|------|--------|----------|
| Kafka 消费者慢 | 消费延迟指标 | 增加消费者实例数或优化处理逻辑 |
| Redis 阻塞 | blocked_clients > 0 | 检查 Redis 命令执行，慢命令可能阻塞 |
| 数据库慢查询 | mean_exec_time > 50ms | 添加索引，优化 SQL 或引入缓存 |
| 线程池耗尽 | thread dump 大量 BLOCKED | 增加线程池大小或排查锁竞争 |
| Broker 响应慢 | CTP 响应时间 | 检查网络和 Broker 端状态 |
| JVM GC 停顿 | GC 日志 Full GC | 调整 GC 参数或增加堆内存 |

#### 紧急修复

```bash
# 快速扩容订单服务
kubectl scale deployment order-service --replicas=12 -n icyquant-prod

# 如果 Redis 慢查询
# 分析慢查询
kubectl exec -it redis-master-0 -n icyquant-prod -- redis-cli SLOWLOG GET 10
# 如果是缓存穿透，添加热点 key 保护

# 如果数据库慢
# 临时增加连接池
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "SELECT pg_reload_conf();"
# 或重建统计信息
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "ANALYZE;"
```

### 2.3 风控引擎误报

#### 现象

- 正常订单被风控规则拦截
- 大量订单因风控规则被拒
- 用户反馈下单失败但无明确原因
- 风控拦截率突增

#### 诊断步骤

```bash
# 步骤 1: 检查风控日志
kubectl logs -n icyquant-prod -l app=risk-engine --since=15m | grep "BLOCKED\|REJECTED"

# 步骤 2: 检查风控规则配置
curl -s "https://api.icyquant.io/api/v1/risk/rules" \
  -H "Authorization: Bearer $TOKEN" | jq '.data.rules'

# 步骤 3: 分析拦截原因分布
kubectl logs -n icyquant-prod -l app=risk-engine --since=1h | grep "BLOCKED" | \
  awk -F 'reason="' '{print $2}' | awk -F '"' '{print $1}' | sort | uniq -c | sort -rn

# 步骤 4: 检查风控指标
# Prometheus:
# sum(rate(risk_rejected_total[5m])) by (rule_id, reason)
# sum(rate(risk_evaluated_total[5m])) by (rule_id)

# 步骤 5: 检查实时风控规则版本
curl -s "https://api.icyquant.io/api/v1/risk/version" \
  -H "Authorization: Bearer $TOKEN"
```

#### 常见原因与解决方案

| 原因 | 解决方案 |
|------|----------|
| 风控规则版本过旧 | 更新规则：`POST /api/v1/risk/rules/refresh` |
| 阈值配置不合理 | 临时放宽阈值（需 L2 审批），根因后重新校准 |
| 数据异常（持仓/资金） | 执行对账流程，修正数据 |
| 客户等级配置错误 | 检查客户风险等级配置 |
| 系统误判 | 分析风控决策日志，更新规则引擎 |

#### 紧急修复

```bash
# 临时放宽风控阈值（需 L2 以上授权）
curl -X PUT "https://api.icyquant.io/api/v1/risk/rule/threshold" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "ruleId": "max_daily_loss",
    "threshold": 0.08,  // 从 5% 临时放宽到 8%
    "effectiveTime": "now",
    "reason": "临时调整，待根因分析"
  }'

# 或者对特定账户豁免
curl -X POST "https://api.icyquant.io/api/v1/risk/exempt" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "accountId": "xxx",
    "ruleIds": ["max_position_value"],
    "expiry": "2024-12-31T23:59:59"
  }'
```

### 2.4 AI 模型推理失败

#### 现象

- AI 推理服务 503 错误
- 策略服务无法获取信号
- 模型推理超时
- GPU 资源不足

#### 诊断步骤

```bash
# 步骤 1: 检查 AI 推理服务状态
kubectl get pods -n icyquant-prod -l app=ai-inference
kubectl logs -n icyquant-prod -l app=ai-inference --tail=100

# 步骤 2: 检查模型加载状态
curl -s "http://ai-inference:8083/actuator/health" | jq '.components'
# 关注 model.* 组件状态

# 步骤 3: 检查 GPU 使用率
kubectl exec -it ai-inference-xxx -n icyquant-prod -- nvidia-smi
# 关注 GPU 利用率、显存使用、温度

# 步骤 4: 检查推理延迟
# Prometheus:
# histogram_quantile(0.95, rate(ai_inference_duration_seconds_bucket[5m]))
# 目标: P95 < 500ms

# 步骤 5: 检查模型版本
curl -s "http://ai-inference:8083/api/v1/models" | jq '.'
# 确认加载的是预期版本

# 步骤 6: 查看服务日志
kubectl logs -n icyquant-prod -l app=ai-inference --since=30m | \
  grep -E "ERROR|timeout|fail|model" | tail -30
```

#### 常见原因与解决方案

| 原因 | 解决方案 |
|------|----------|
| 模型加载失败 | 检查模型文件路径和完整性，重新加载模型 |
| GPU 显存不足 | 切换到 CPU 推理或优化模型（量化/剪枝） |
| 推理超时 | 增加超时时间或优化批量处理大小 |
| 模型版本不兼容 | 检查模型与服务版本兼容性 |
| GPU 驱动异常 | 检查 nvidia-driver，必要时重启 GPU 节点 |
| 并发请求过多 | 增加副本数或启用请求限流 |

#### 紧急修复

```bash
# 重启 AI 推理服务
kubectl rollout restart deployment ai-inference -n icyquant-prod

# 切换到备用模型
curl -X PUT "http://ai-inference:8083/api/v1/models/active" \
  -H "Content-Type: application/json" \
  -d '{"model": "fallback_v2", "version": "stable"}'

# 紧急扩容 GPU 节点
kubectl scale deployment ai-inference --replicas=5 -n icyquant-prod

# 临时禁用 AI 策略（确保核心交易不受影响）
curl -X PUT "https://api.icyquant.io/api/v1/strategies/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"enabled": false, "reason": "AI inference degraded"}'
```

### 2.5 数据库连接问题

#### 现象

- 应用日志出现 ConnectionTimeout
- 数据库连接池耗尽
- 查询响应缓慢
- PostgreSQL 主从同步延迟

#### 诊断步骤

```bash
# 步骤 1: 检查数据库 Pod 状态
kubectl get pods -n icyquant-prod -l app=postgresql
kubectl describe pod -l app=postgresql -n icyquant-prod
# 关注: CPU、内存、磁盘使用

# 步骤 2: 检查活动连接数
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# 步骤 3: 检查连接池配置
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c \
  "SHOW max_connections;"
# 对比应用连接池配置

# 步骤 4: 检查慢查询
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c \
  "SELECT query, calls, mean_exec_time, total_exec_time 
   FROM pg_stat_statements 
   ORDER BY total_exec_time DESC LIMIT 20;"

# 步骤 5: 检查锁等待
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c \
  "SELECT * FROM pg_locks WHERE NOT granted;"

# 步骤 6: 检查复制延迟
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c \
  "SELECT * FROM pg_stat_replication;"
```

#### 常见原因与解决方案

| 原因 | 解决方案 |
|------|----------|
| 连接数耗尽 | 终止空闲会话或增加 max_connections |
| 慢查询阻塞 | 终止慢查询，添加索引 |
| 磁盘满 | 清理历史数据或增加存储 |
| 主从延迟 | 检查网络，必要时切换到同步复制 |
| 连接泄漏 | 排查应用代码关闭连接 |
| 资源不足 | 垂直伸缩数据库 Pod |

#### 紧急修复

```bash
# 终止所有空闲会话
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c \
  "SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle' AND query_start < now() - interval '30 minutes';"

# 紧急增加最大连接数
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c \
  "ALTER SYSTEM SET max_connections = 300;"
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "SELECT pg_reload_conf();"

# 检查并终止阻塞查询
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c \
  "SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE wait_event = 'Lock';"
```

### 2.6 消息队列积压

#### 现象

- Kafka Consumer Lag 持续增长
- 订单处理延迟增加
- 行情数据延迟
- Redis 队列堆积

#### 诊断步骤

```bash
# 步骤 1: 检查 Kafka Consumer Group 延迟
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --all-groups --state

# 步骤 2: 检查消费者 Pod 状态
kubectl get pods -n icyquant-prod -l app=order-processor

# 步骤 3: 检查消费者日志
kubectl logs -n icyquant-prod -l app=order-processor --since=10m | \
  grep -E "ERROR|lag|slow|backlog"

# 步骤 4: 检查 Broker 磁盘使用
kafka-topics.sh --bootstrap-server kafka:9092 \
  --describe --topic icyquant-orders

# 步骤 5: 检查分区分配
kafka-topics.sh --bootstrap-server kafka:9092 \
  --describe --topic icyquant-orders

# 步骤 6: 检查 Kafka Broker 资源
kubectl get pods -n kafka --no-headers | \
  while read line; do
    pod=$(echo "$line" | awk '{print $1}')
    kubectl exec -it "$pod" -n kafka -- kafka-log-dirs.sh \
      --bootstrap-server kafka:9092 --describe --topic-list icyquant-orders
  done
```

#### 常见原因与解决方案

| 原因 | 解决方案 |
|------|----------|
| 消费者处理慢 | 增加消费者数量或优化处理逻辑 |
| 分区数不足 | 增加 Topic 分区数 |
| Broker 性能问题 | 增加 Broker 资源或清理磁盘 |
| Rebalance 风暴 | 检查消费者配置，避免频繁 Rebalance |
| 消息膨胀 | 检查消息大小，必要时启用压缩 |
| 上游生产慢 | 检查生产者端是否异常 |

#### 紧急修复

```bash
# 增加消费者实例
kubectl scale deployment order-processor --replicas=10 -n icyquant-prod

# 增加 Topic 分区（无数据丢失，但新分区可能导致乱序）
kafka-topics.sh --bootstrap-server kafka:9092 \
  --alter --topic icyquant-orders --partitions 32

# 紧急扩容 Kafka Broker（垂直）
kubectl scale statefulset kafka --replicas=5 -n kafka

# 临时调整消费者配置（加快 Rebalance）
kubectl exec -it deployment/order-processor -n icyquant-prod -- \
  cat /etc/kafka/consumer.properties | \
  grep -E "session.timeout|max.poll.interval|heartbeat"
# 修改为更短的超时时间
```

### 2.7 内存泄漏

#### 现象

- Pod 内存使用率持续增长不释放
- OOMKilled 频繁发生
- GC 日志显示 Full GC 频率增加
- 系统运行时间越长性能越差

#### 诊断步骤

```bash
# 步骤 1: 确认内存趋势
kubectl top pods -n icyquant-prod --no-headers | sort -k4 -rn

# 步骤 2: 连续采样内存使用
for i in $(seq 1 10); do
  kubectl top pods -n icyquant-prod | grep trading-engine
  sleep 60
done

# 步骤 3: 获取 JVM Heap Dump
kubectl exec -it deployment/trading-engine -n icyquant-prod -- \
  jcmd 1 GC.heap_dump /tmp/heap-dump-$(date +%s).hprof

# 步骤 4: 分析 Heap Dump
# 使用 MAT / VisualVM 分析
scp user@cluster:/tmp/heap-dump-*.hprof ./
# 在本地使用 MAT 工具分析

# 步骤 5: 查看 JVM 参数
kubectl exec -it deployment/trading-engine -n icyquant-prod -- \
  jcmd 1 VM.flags

# 步骤 6: 查看 GC 统计
kubectl exec -it deployment/trading-engine -n icyquant-prod -- \
  jstat -gcutil 1 1000 10
```

#### 常见原因与解决方案

| 原因 | 解决方案 |
|------|----------|
| 对象未释放 | 代码审查，检查集合、缓存、连接 |
| 线程本地存储泄漏 | 检查 ThreadLocal 使用，确保及时 remove |
| 缓存无上限 | 配置合理的 TTL 和最大容量 |
| 第三方库泄漏 | 排查依赖版本，升级或替换 |
| 数据库连接泄漏 | 确认连接在 finally 中关闭 |
| 事件监听未取消 | 确保 EventListener 正确移除 |

#### 紧急修复

```bash
# 重启服务（临时缓解，需后续修复根因）
kubectl rollout restart deployment trading-engine -n icyquant-prod

# 增加内存限制（临时）
kubectl patch deployment trading-engine -n icyquant-prod \
  --type=merge -p '
  {
    "spec": {
      "template": {
        "spec": {
          "containers": [{
            "name": "trading-engine",
            "resources": {
              "limits": {"memory": "24Gi"},
              "requests": {"memory": "12Gi"}
            }
          }]
        }
      }
    }
  }'

# 如果是生产紧急情况，可以考虑临时关闭功能模块
curl -X PUT "https://api.icyquant.io/api/v1/features/memory-intensive" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "reason": "内存泄漏紧急缓解"}'
```

---

## 3. 诊断工具速查

### 3.1 一键诊断脚本

```bash
#!/bin/bash
# quick-diagnose.sh - 一键诊断脚本

set -e

echo "=== ICYQuant 快速诊断 ==="
echo "时间: $(date)"
echo ""

# 1. Pod 状态
echo "--- Pod 状态 ---"
kubectl get pods -n icyquant-prod -o wide | grep -v Running

# 2. 资源使用
echo ""
echo "--- 资源使用率 Top 5 ---"
kubectl top pods -n icyquant-prod --no-headers | sort -k3 -rn | head -5
kubectl top pods -n icyquant-prod --no-headers | sort -k4 -rn | head -5

# 3. 最近错误日志
echo ""
echo "--- 最近错误日志 ---"
for app in trading-engine order-service risk-engine market-data ai-inference; do
  echo "[$app] $(kubectl logs -n icyquant-prod -l app=$app --since=5m 2>/dev/null | grep -c "ERROR") ERRORs"
done

# 4. 数据库连接
echo ""
echo "--- 数据库连接数 ---"
kubectl exec -it postgresql-0 -n icyquant-prod -- psql -U $PG_USER \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;" 2>/dev/null

# 5. Kafka 延迟
echo ""
echo "--- Kafka 消费延迟 ---"
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --all-groups 2>/dev/null | grep -E "GROUP|LAG"

# 6. Broker 状态
echo ""
echo "--- Broker 连接状态 ---"
curl -s "https://api.icyquant.io/actuator/health/components/broker" 2>/dev/null | jq '.details.gatewayConnected'

echo ""
echo "=== 诊断完成 ==="
```

### 3.2 常用排查命令

```bash
# 查看特定 Pod 的完整事件
kubectl describe pod <pod-name> -n icyquant-prod | grep -A 20 "Events:"

# 实时追踪日志（多 Pod）
kubectl logs -n icyquant-prod -l app=trading-engine -f --max-log-requests=10

# 查看历史日志（崩溃容器）
kubectl logs <pod-name> -n icyquant-prod --previous

# 进入 Pod 内部调试
kubectl exec -it <pod-name> -n icyquant-prod -- /bin/bash

# 查看 Pod 的所有环境变量
kubectl exec <pod-name> -n icyquant-prod -- env

# 查看 Pod 的挂载卷
kubectl exec <pod-name> -n icyquant-prod -- mount | grep /var

# 端口转发调试
kubectl port-forward <pod-name> 8080:8080 -n icyquant-prod

# 查看 Service 端点
kubectl get endpoints <service-name> -n icyquant-prod
```

### 3.3 调试接口

| 接口 | 用途 | 调用方式 |
|------|------|----------|
| `/actuator/health` | 系统健康状态 | GET |
| `/actuator/health/{component}` | 单组件健康 | GET |
| `/actuator/metrics` | Prometheus 指标 | GET |
| `/actuator/loggers` | 日志级别管理 | GET/POST |
| `/actuator/heapdump` | Heap Dump 下载 | GET |
| `/actuator/threaddump` | 线程堆栈 | GET |
| `/actuator/env` | 环境变量 | GET |
| `/actuator/refresh` | 配置刷新 | POST |
| `/actuator/restart` | 重启上下文 | POST |

#### 示例：动态调整日志级别

```bash
# 临时开启 DEBUG 日志（仅针对交易引擎）
curl -X POST "http://trading-engine:8081/actuator/loggers" \
  -H "Content-Type: application/json" \
  -d '{"configuredLevel": "DEBUG"}'

# 获取特定 Logger 级别
curl "http://trading-engine:8081/actuator/loggers/com.icyquant.trading" | jq '.'

# 恢复到 INFO 级别
curl -X POST "http://trading-engine:8081/actuator/loggers" \
  -H "Content-Type: application/json" \
  -d '{"configuredLevel": "INFO"}'
```

---

## 4. 升级指引

### 4.1 何时升级

| 场景 | 升级级别 | 执行人 |
|------|----------|--------|
| 行情中断 > 1 分钟 | L1 → 立即处理 | 值班工程师 |
| 订单系统不可用 > 5 分钟 | L1 → L2 | 值班工程师 + 团队负责人 |
| 数据库不可用 > 10 分钟 | L2 → L3 | 团队负责人 + 技术总监 |
| 大面积客户反馈 | L2 → L4 | 团队负责人 + CTO |
| 安全事件确认 | L3 → L4 | 技术总监 + CTO |
| 无法在 30 分钟内恢复 | 必须升级 | 按升级矩阵 |

### 4.2 升级时需提供的信息

升级到 L2+ 时，必须提供：

```
【故障升级报告】
1. 故障描述：简要说明现象
2. 影响范围：受影响的服务/用户
3. 开始时间：故障发生时间
4. 当前状态：正在执行的操作
5. 已尝试的操作：列出已执行的排查步骤
6. 初步判断：可能的根因方向
7. 紧急程度：P0/P1/P2
8. 期望支持：需要 L2+ 提供什么帮助
```

### 4.3 故障沟通规范

- **第一时间**：确认故障并通知团队
- **每 15 分钟**：同步进展（无论是否有新发现）
- **故障恢复后**：立即更新状态为已恢复
- **24 小时内**：提交完整事故报告

---

## 附录

### A. 监控告警规则

| 告警名称 | 触发条件 | 级别 | 处理时限 |
|----------|----------|------|----------|
| API 服务不可用 | up{job="api-gateway"} == 0 | P0 | 5 分钟 |
| 订单失败率 > 1% | rate(order_failed[5m]) > 0.01 | P0 | 10 分钟 |
| 数据库连接池耗尽 | db_connections_available < 10 | P0 | 10 分钟 |
| Kafka 消费延迟 > 10000 | kafka_consumer_lag > 10000 | P1 | 30 分钟 |
| 内存使用率 > 90% | container_memory_usage > 0.9 | P1 | 1 小时 |
| 磁盘使用率 > 85% | node_filesystem_usage > 0.85 | P2 | 24 小时 |

### B. 参考文档

- [部署指南](./deployment_guide.md)
- [运营手册](./operation_manual.md)
- [备份与恢复](./backup_restore.md)
- [灾难恢复](./disaster_recovery.md)
- [系统维护](./maintenance.md)
