# ICYQuant 运营手册

## 1. 系统概览与架构

### 1.1 业务定位

ICYQuant 是一套面向机构客户的量化交易平台，核心业务包括：

- **行情分发**：实时接收并分发股票、期货、期权行情数据
- **交易执行**：支持多品种、多市场的订单路由与执行
- **风险监控**：实时风险识别、限额检查与熔断机制
- **AI 策略**：基于机器学习的交易信号生成与优化
- **账户管理**：资金账户、持仓、保证金统一管理

### 1.2 服务清单

| 服务名 | 命名 | 端口 | 副本数 | 优先级 | 关键级别 |
|--------|------|------|--------|--------|----------|
| API Gateway | api-gateway | 8080 | 4 | P0 | 关键 |
| 交易引擎 | trading-engine | 8081 | 6 | P0 | 关键 |
| 风控引擎 | risk-engine | 8082 | 4 | P0 | 关键 |
| AI 推理 | ai-inference | 8083 | 3 | P1 | 重要 |
| 行情服务 | market-data | 8084 | 4 | P0 | 关键 |
| 订单服务 | order-service | 8085 | 6 | P0 | 关键 |
| 账户服务 | account-service | 8086 | 4 | P0 | 关键 |
| 通知服务 | notification | 8087 | 2 | P2 | 一般 |

### 1.3 依赖关系

```
                    ┌──────────────┐
                    │  API Gateway │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │  交易引擎   │   │  订单服务   │   │  AI 推理    │
   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
          │                │                │
          ▼                ▼                ▼
   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
   │  风控引擎   │   │  账户服务   │   │  行情服务   │
   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
          │                │                │
          └────────────────┼────────────────┘
                           ▼
               ┌──────────────────────┐
               │   数据基础设施层     │
               │  PostgreSQL | Redis  │
               │  Kafka    | Timescale │
               └──────────────────────┘
```

### 1.4 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 语言 | Java | 21 LTS |
| 框架 | Spring Boot | 3.2.x |
| 数据库 | PostgreSQL | 15.6 |
| 时序库 | TimescaleDB | 2.14 |
| 缓存 | Redis | 7.2 |
| 消息队列 | Kafka | 3.6 |
| 容器 | Kubernetes | 1.28 |
| 可观测性 | Prometheus + Grafana + Loki | — |

---

## 2. 日常运营

### 2.1 健康检查

#### 自动化健康检查脚本

```bash
#!/bin/bash
# daily-health-check.sh
# 每日开盘前执行（交易所开盘前 30 分钟）

set -euo pipefail

ENV="${1:-prod}"
BASE_URL="https://api.icyquant.io"
ALERT_WEBHOOK="https://alert.company.com/webhook/icyquant"

REDIS='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "[$(date '+%H:%M:%S')] $1"
}

alert() {
    local msg="$1"
    log "${RED}ALERT: $msg${NC}"
    curl -s -X POST "$ALERT_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"[ICYQuant][${ENV}] $msg\"}" || true
}

pass() { log "${GREEN}✓ $1${NC}"; }
fail() { log "${RED}✗ $1${NC}"; alert "$1"; }
warn() { log "${YELLOW}⚠ $1${NC}"; }

# 1. API 健康检查
log "=== 1. API 服务健康 ==="
if curl -sf "$BASE_URL/actuator/health" > /dev/null 2>&1; then
    pass "API 网关健康"
else
    fail "API 网关不可用"
fi

# 2. 数据库连接
log "=== 2. 数据层健康 ==="
for comp in db redis kafka; do
    status=$(curl -sf "$BASE_URL/actuator/health/components/$comp" 2>/dev/null | jq -r '.status')
    if [ "$status" = "UP" ]; then
        pass "$comp 连接正常"
    else
        fail "$comp 状态异常: $status"
    fi
done

# 3. Broker 连接
log "=== 3. Broker 连接 ==="
broker_status=$(curl -sf "$BASE_URL/actuator/health/components/broker" 2>/dev/null | jq -r '.status')
if [ "$broker_status" = "UP" ]; then
    pass "Broker 连接正常"
else
    fail "Broker 离线"
fi

# 4. K8s 节点状态
log "=== 4. Kubernetes 集群 ==="
node_ready=$(kubectl get nodes --no-headers | grep -c " Ready")
node_total=$(kubectl get nodes --no-headers | wc -l)
log "节点就绪: $node_ready / $node_total"

pod_not_ready=$(kubectl get pods -n icyquant-prod --no-headers | grep -v " Running" | grep -v " Completed" | wc -l)
if [ "$pod_not_ready" -gt 0 ]; then
    fail "异常 Pod 数量: $pod_not_ready"
else
    pass "所有 Pod 正常"
fi

# 5. 磁盘使用
log "=== 5. 存储状态 ==="
kubectl exec -it postgresql-0 -n icyquant-prod -- df -h /var/lib/postgresql/data 2>/dev/null | tail -1

# 6. 资源使用
log "=== 6. 资源监控 ==="
kubectl top pods -n icyquant-prod --no-headers | sort -k3 -rn | head -5

# 7. 交易前检查
log "=== 7. 交易前置条件 ==="
checks=(
    "账户服务可用: $([ $(curl -sf "$BASE_URL/api/v1/health/account" 2>/dev/null | jq -r '.status') = 'UP' ] && echo OK || echo FAIL)"
    "行情推送正常: $([ $(curl -sf "$BASE_URL/api/v1/health/marketdata" 2>/dev/null | jq -r '.status') = 'UP' ] && echo OK || echo FAIL)"
    "风控引擎就绪: $([ $(curl -sf "$BASE_URL/api/v1/health/risk" 2>/dev/null | jq -r '.status') = 'UP' ] && echo OK || echo FAIL)"
)

for check in "${checks[@]}"; do
    if echo "$check" | grep -q "OK"; then
        pass "$check"
    else
        fail "$check"
    fi
done

log "=== 健康检查完成 ==="
```

### 2.2 日志审查

#### 日志级别标准

| 级别 | 含义 | 处理要求 |
|------|------|----------|
| ERROR | 需要立即处理 | 24 小时内定位根因 |
| WARN | 需要关注 | 48 小时内分析 |
| INFO | 关键业务事件 | 每日审查摘要 |
| DEBUG | 调试信息 | 按需开启 |

#### 日志查询命令

```bash
# 查看最近 1 小时的错误日志
kubectl logs -n icyquant-prod -l app=trading-engine \
  --since=1h --tail=1000 | grep -i "ERROR"

# 查看订单相关日志
kubectl logs -n icyquant-prod -l app=order-service \
  --since=30m | grep "order"

# 实时追踪风控日志
kubectl logs -n icyquant-prod -l app=risk-engine -f

# Loki 查询示例（通过 LogQL）
# 查询：过去 15 分钟内 ERROR 级别的数据库异常
{app="trading-engine"} |= "ERROR" |= "connection" | json

# 按 Trace ID 查询完整链路
{trace_id="abc123"} | json | line_format "{{.timestamp}} [{{.level}}] {{.message}}"
```

#### 日志审查清单

每日运营团队须审查以下内容：

1. **ERROR 日志数量**：统计全系统 ERROR 日志，超过阈值触发告警
2. **异常堆栈**：关注 NullPointerException、TimeoutException、ConnectException
3. **业务异常**：订单被拒、风控触发、成交异常
4. **性能退化**：GC 日志、慢查询日志、超时日志
5. **安全事件**：认证失败、权限异常、可疑请求

### 2.3 指标审查

#### 核心监控面板

运营团队每日检查以下 Grafana 面板：

| 面板名称 | 关注指标 | 阈值 |
|----------|----------|------|
| 系统概览 | CPU 使用率 | > 80% 告警 |
| 系统概览 | 内存使用率 | > 85% 告警 |
| 系统概览 | 磁盘可用率 | < 20% 告警 |
| API 网关 | P99 响应时间 | > 200ms 告警 |
| API 网关 | 错误率（5xx） | > 1% 告警 |
| 交易引擎 | 订单延迟 | > 100ms 告警 |
| 交易引擎 | 撤单率 | > 5% 告警 |
| 风控引擎 | 拦截次数突增 | 环比 > 100% 告警 |
| 消息队列 | 消费延迟 | > 5000ms 告警 |
| 数据库 | 慢查询数 | > 10/min 告警 |

#### Prometheus 查询示例

```promql
# 系统健康
up{namespace="icyquant-prod"} == 0

# CPU 使用率（按服务）
cpu_usage{namespace="icyquant-prod"} by (pod) * 100

# API 错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) 
/ sum(rate(http_requests_total[5m])) > 0.01

# Kafka 消费延迟
kafka_consumer_group_lag > 1000

# 订单执行 P99
histogram_quantile(0.99, 
  rate(order_execution_duration_seconds_bucket[5m]))

# Broker 连接状态
broker_connection_status != 1
```

---

## 3. 交易操作

### 3.1 市场开市流程

#### 开市前检查清单

```
时间：开盘前 30 分钟（交易日 08:30 / 13:00）

□ 1. 执行自动化健康检查脚本
□ 2. 确认 K8s 所有 Pod Ready（kubectl get pods -n icyquant-prod）
□ 3. 检查数据库连接池活跃数（postgres 活跃连接 < 200）
□ 4. 确认 Broker 网关登录状态（CTP/恒生已登录）
□ 5. 行情推送正常（检查 WebSocket 连接数 > 0）
□ 6. 风控引擎配置已加载（通过 API 确认版本号）
□ 7. AI 模型已加载且推理正常（curl 测试 /actuator/health）
□ 8. 预热测试：提交一笔最小金额测试订单
□ 9. 通知客户：系统已就绪，可以开始交易
□ 10. 记录开市时间戳，归档到日报
```

#### 开市操作脚本

```bash
#!/bin/bash
# market-open.sh - 一键开市脚本

set -e

echo "=== ICYQuant 开市脚本 ==="
date '+%Y-%m-%d %H:%M:%S'

# 1. 健康检查
./scripts/daily-health-check.sh prod
[ $? -ne 0 ] && echo "健康检查失败，请手动排查" && exit 1

# 2. 预热测试交易
curl -X POST "https://api.icyquant.io/api/v1/orders" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "symbol": "IC2412",
    "direction": "LONG",
    "offset": "OPEN",
    "price": 5000,
    "volume": 1,
    "accountType": "TEST"
  }' | jq '.status'

# 3. 确认行情接收
echo "=== 行情最新价 ==="
curl "https://api.icyquant.io/api/v1/marketdata/IC2412/tick" | jq '.data.lastPrice'

# 4. 推送开市通知
curl -X POST "https://notify.company.com/icyquant" \
  -d "ICYQuant 系统已开市，所有服务就绪。"

echo "=== 开市完成 ==="
```

### 3.2 市场收市流程

#### 收市操作清单

```
时间：收盘后 15 分钟（交易日 11:30 / 15:15）

□ 1. 停止新开单：设置系统状态为 "CLOSED"
□ 2. 确认未成交委托已全部撤销
□ 3. 确认所有成交已处理完成
□ 4. 执行持仓对账（参考 3.3 节）
□ 5. 生成当日交易报表
□ 6. 归档当日日志和交易数据
□ 7. 数据库归档（按备份策略执行）
□ 8. 通知客户：当日交易已结算
□ 9. 更新运营日报
```

#### 停止新开单

```bash
# 设置系统状态为 CLOSED，禁止新开仓
curl -X PUT "https://api.icyquant.io/api/v1/system/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"status": "CLOSED", "reason": "MARKET_CLOSED"}'

# 强制撤销所有未成交委托
curl -X POST "https://api.icyquant.io/api/v1/orders/cancel-all" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"accountId": "ALL"}'
```

### 3.3 持仓对账

#### 对账流程

```
步骤 1: 数据采集
  - 从交易所获取当日成交记录
  - 从本系统获取当日订单记录
  - 从本系统获取当前持仓快照

步骤 2: 数据比对
  - 逐笔成交比对（match by order_ref + price + qty）
  - 持仓数量比对（系统 vs 券商返回）
  - 资金余额比对（系统 vs 券商保证金）

步骤 3: 差异处理
  - 差异 < 最小变动价位：自动修正
  - 差异 > 阈值：人工介入，升级到运营负责人
  - 对账结果保存到 audit 表

步骤 4: 报告生成
  - 对账报告（PDF）
  - 差异详情表
  - 异常标注与处理记录
```

#### 对账脚本

```bash
#!/bin/bash
# reconciliation.sh - 每日对账

DATE="${1:-$(date +%Y-%m-%d)}"
OUTPUT_DIR="/reports/reconciliation/$DATE"
mkdir -p "$OUTPUT_DIR"

# 1. 获取系统持仓快照
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.icyquant.io/api/v1/positions/snapshot" \
  -o "$OUTPUT_DIR/system_positions.json"

# 2. 获取券商持仓
curl -s -H "Authorization: Bearer $BROKER_TOKEN" \
  "$BROKER_API/positions" \
  -o "$OUTPUT_DIR/broker_positions.json"

# 3. 比对差异
python3 <<'PYEOF'
import json
import sys

with open(sys.argv[1]) as f:
    sys_pos = json.load(f)
with open(sys.argv[2]) as f:
    broker_pos = json.load(f)

sys_by_code = {p['symbol']: p for p in sys_pos['data']}
broker_by_code = {p['symbol']: p for p in broker_pos['data']}

diff_report = []
for code in set(list(sys_by_code.keys()) + list(broker_by_code.keys())):
    s = sys_by_code.get(code, {})
    b = broker_by_code.get(code, {})
    
    if not s:
        diff_report.append({"symbol": code, "issue": "missing_in_system", "broker_qty": b.get('qty', 0)})
    elif not b:
        diff_report.append({"symbol": code, "issue": "missing_in_broker", "system_qty": s.get('qty', 0)})
    elif s.get('qty') != b.get('qty'):
        diff_report.append({
            "symbol": code,
            "issue": "quantity_mismatch",
            "system_qty": s.get('qty'),
            "broker_qty": b.get('qty')
        })

with open(sys.argv[3], 'w') as f:
    json.dump(diff_report, f, indent=2, ensure_ascii=False)

print(f"对账完成，发现 {len(diff_report)} 处差异")
for d in diff_report[:10]:
    print(f"  [{d['symbol']}] {d['issue']}")
PYEOF
```

---

## 4. 紧急操作

### 4.1 紧急停市

#### 触发条件

| 触发条件 | 级别 | 执行人 | 自动/手动 |
|----------|------|--------|-----------|
| 行情数据中断 > 30 秒 | P0 | 值班工程师 | 手动 |
| 风控引擎异常 | P0 | 值班工程师 | 自动 |
| 数据库连接池耗尽 | P0 | 值班工程师 | 自动 |
| 系统错误率 > 5% | P0 | 值班工程师 | 自动 |
| 重大技术故障 | P1 | 运营负责人 | 手动 |

#### 执行步骤

```bash
# === 紧急停市脚本 ===
# 仅在 P0 级故障时由值班工程师执行

# 1. 立即禁止所有新开仓
curl -X PUT "https://api.icyquant.io/api/v1/system/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"status": "HALTED", "reason": "EMERGENCY", "notifyAll": true}'

# 2. 撤销所有未成交订单
curl -X POST "https://api.icyquant.io/api/v1/orders/emergency-cancel" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"level": "ALL", "reason": "EMERGENCY_HALT"}'

# 3. 启用系统只读模式（仅允许查询）
curl -X PUT "https://api.icyquant.io/api/v1/system/mode" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"mode": "READ_ONLY"}'

# 4. 确认停市状态
STATUS=$(curl -s "https://api.icyquant.io/api/v1/system/status" | jq -r '.status')
echo "系统状态: $STATUS"

# 5. 通知所有人
./scripts/notify-all.sh "紧急停市已触发，系统进入只读模式"
```

#### 紧急停市确认

```bash
# 验证订单已全部撤销
PENDING=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.icyquant.io/api/v1/orders?status=PENDING" | jq '.data | length')
echo "挂单数量: $PENDING"

# 验证无新订单可以提交
curl -X POST "https://api.icyquant.io/api/v1/orders" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"symbol": "IC2412", "direction": "LONG", "volume": 1}'
# 预期返回 423 Locked: System is in read-only mode
```

### 4.2 紧急系统关闭

#### 适用场景

- 重大安全事件
- 数据泄露风险
- 监管要求强制停市
- 无法通过停市模式控制的严重故障

#### 执行步骤

```bash
# 1. 执行紧急停市（与 4.1 相同）
./scripts/emergency-halt.sh

# 2. 关闭所有交易相关 Pod（保留基础设施）
kubectl scale deployment trading-engine --replicas=0 -n icyquant-prod
kubectl scale deployment order-service --replicas=0 -n icyquant-prod
kubectl scale deployment ai-inference --replicas=0 -n icyquant-prod
kubectl scale deployment risk-engine --replicas=0 -n icyquant-prod
kubectl scale deployment market-data --replicas=0 -n icyquant-prod

# 3. 数据库进入只读模式
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "ALTER SYSTEM SET default_transaction_read_only = 'on';"
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "SELECT pg_reload_conf();"

# 4. 断开 Broker 连接
curl -X POST "https://api.icyquant.io/api/v1/broker/disconnect" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

# 5. 快照保存当前状态
kubectl get all -n icyquant-prod -o yaml > /backups/system-state-$(date +%Y%m%d-%H%M%S).yaml

# 6. 通知所有相关方
./scripts/notify-all.sh "系统已完全关闭，等待进一步通知"
```

### 4.3 停市后恢复

```bash
# === 恢复流程 ===

# 1. 问题排查完成后，确认恢复条件
./scripts/post-incident-checklist.sh

# 2. 恢复数据库读写模式
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "ALTER SYSTEM SET default_transaction_read_only = 'off';"
kubectl exec -it postgresql-0 -n icyquant-prod -- \
  psql -U $PG_USER -c "SELECT pg_reload_conf();"

# 3. 逐步恢复 Pod
kubectl scale deployment market-data --replicas=4 -n icyquant-prod
kubectl scale deployment risk-engine --replicas=4 -n icyquant-prod
kubectl scale deployment order-service --replicas=6 -n icyquant-prod
kubectl scale deployment trading-engine --replicas=6 -n icyquant-prod
kubectl scale deployment ai-inference --replicas=3 -n icyquant-prod

# 4. 等待所有 Pod Ready
kubectl rollout status deployment/trading-engine -n icyquant-prod

# 5. 恢复系统状态为 OPEN
curl -X PUT "https://api.icyquant.io/api/v1/system/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"status": "OPEN", "reason": "SYSTEM_RESTORED"}'

# 6. 执行开市前检查
./scripts/daily-health-check.sh prod

# 7. 通知客户系统恢复
./scripts/notify-all.sh "系统已恢复，可以开始交易"
```

---

## 5. 伸缩操作

### 5.1 垂直伸缩（Vertical Scaling）

#### 调整单个 Pod 资源

```yaml
# 修改 Deployment 的 resources 配置
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-engine
  namespace: icyquant-prod
spec:
  template:
    spec:
      containers:
        - name: trading-engine
          resources:
            requests:
              cpu: "4"      # 从 2 核调整到 4 核
              memory: "8Gi"  # 从 4GB 调整到 8GB
            limits:
              cpu: "8"      # 从 4 核调整到 8 核
              memory: "16Gi" # 从 8GB 调整到 16GB
```

```bash
# 使用 kubectl patch 热更新
kubectl patch deployment trading-engine -n icyquant-prod \
  --type=merge -p '
  {
    "spec": {
      "template": {
        "spec": {
          "containers": [{
            "name": "trading-engine",
            "resources": {
              "requests": {"cpu": "4", "memory": "8Gi"},
              "limits": {"cpu": "8", "memory": "16Gi"}
            }
          }]
        }
      }
    }
  }'

# 观察滚动升级
kubectl rollout status deployment/trading-engine -n icyquant-prod
```

#### 注意事项

- 垂直伸缩涉及 Pod 重启，建议在交易非窗口期执行
- 内存调大后需同步调整 JVM 参数（`-Xmx`、`-Xms`）
- 确认节点剩余资源充足（`kubectl describe node`）

### 5.2 水平伸缩（Horizontal Scaling）

#### 手动伸缩

```bash
# 立即伸缩到指定副本数
kubectl scale deployment trading-engine --replicas=10 -n icyquant-prod

# 观察伸缩过程
kubectl get pods -n icyquant-prod -l app=trading-engine -w
```

#### 自动伸缩（HPA）

```yaml
# HPA 配置示例
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: trading-engine-hpa
  namespace: icyquant-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: trading-engine
  minReplicas: 6
  maxReplicas: 20
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
          averageUtilization: 80
    - type: Pods
      pods:
        metric:
          name: packet_processing_latency
        target:
          type: AverageValue
          averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 50
          periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300  # 5 分钟稳定窗口
      policies:
        - type: Percent
          value: 25
          periodSeconds: 60
```

#### 交易时段伸缩策略

| 时段 | 自动伸缩 | 手动干预 | 目标副本数 |
|------|----------|----------|------------|
| 集合竞价（09:15-09:25） | 开启 | 禁止 | 8 |
| 连续竞价（09:30-11:30 / 13:00-15:00） | 开启 | 允许 | 6-20（动态） |
| 午休（11:30-13:00） | 开启 | 允许 | 4-6 |
| 收盘后（15:00 后） | 关闭 | 允许 | 4 |

#### 高负载预案

```bash
# 极端行情下的紧急扩容
kubectl scale deployment trading-engine --replicas=15 -n icyquant-prod
kubectl scale deployment order-service --replicas=20 -n icyquant-prod

# 同步调整 Kafka 分区数（如需要）
kafka-topics.sh --bootstrap-server kafka:9092 \
  --alter --topic icyquant-orders --partitions 32
```

---

## 6. 维护窗口

### 6.1 维护窗口规划

| 窗口类型 | 时间 | 频率 | 允许操作 |
|----------|------|------|----------|
| 日常维护窗 | 每日 15:30-17:00 | 每日 | 日志归档、非关键重启 |
| 周度维护窗 | 每周六 02:00-06:00 | 每周 | 系统更新、配置变更 |
| 月度维护窗 | 每月第一个周日 00:00-08:00 | 每月 | 数据库升级、架构变更 |
| 紧急维护窗 | 随时开放 | 按需 | 故障修复 |

### 6.2 维护通知流程

```
T-72h  —  发送维护通知给客户（邮件 + 短信）
T-24h  —  再次确认通知，附详细影响说明
T-4h   —  最后确认，执行前检查
T-0    —  暂停非紧急变更，执行维护
T+1h   —  维护完成后验证并报告
T+24h  —  跟进确认系统稳定，发布维护报告
```

### 6.3 维护前检查清单

```
□ 1. 已确认备份完成且可恢复
□ 2. 已回滚测试通过（Staging 环境）
□ 3. 已通知所有客户和相关方
□ 4. 已准备回滚预案和回滚脚本
□ 5. 已确认维护时段无重要交易
□ 6. 已分配足够的运维人员
□ 7. 已记录当前系统状态快照
□ 8. 已准备沟通模板
```

---

## 7. 沟通模板

### 7.1 维护通知模板

```
主题：[ICYQuant] 系统维护通知 - [日期]

尊敬的客户：

ICYQuant 系统将于 [日期] 进行计划性维护，具体安排如下：

📅 维护时间：[YYYY-MM-DD] [HH:MM] - [HH:MM] (GMT+8)
⏱ 预计时长：[X] 小时
🔧 影响范围：[全部服务 / 部分服务]
📊 影响级别：[无影响 / 轻微 / 中等]

详细变更内容：
1. [变更项 1]
2. [变更项 2]
3. ...

维护期间：
- [如果完全停机] 系统将无法访问，请提前安排交易计划
- [如果部分影响] 核心交易功能不受影响，[其他] 可能短暂不可用

我们将在维护完成后通过邮件通知您。如有疑问，请联系：
📧 email@icyquant.com
📞 400-XXX-XXXX

感谢您的理解与支持。

ICYQuant 运营团队
```

### 7.2 故障通知模板

```
主题：[ICYQuant][故障报告] [故障类型] - [日期]

尊敬的客户：

我们报告一起 [故障类型] 事件：

⏰ 发生时间：[YYYY-MM-DD HH:MM]
📊 影响范围：[影响的服务/功能]
🔍 根本原因：[简要描述]
🛠 当前状态：[处理中 / 已恢复 / 已缓解]
📅 预计恢复：[时间]
📈 影响评估：[严重程度、受影响用户数]

我们正在积极处理此问题，并将每 [30 分钟] 更新一次进展。

紧急联系：
📧 email@icyquant.com
📞 400-XXX-XXXX

ICYQuant 运营团队
```

### 7.3 恢复通知模板

```
主题：[ICYQuant] 系统恢复通知

尊敬的客户：

ICYQuant 系统已于 [YYYY-MM-DD HH:MM] 完全恢复运行。

✅ 已恢复的服务：
- 行情服务
- 交易执行
- 账户查询
- ...

🔍 根因分析：
[简短描述故障原因]

🛡 改进措施：
1. [措施 1]
2. [措施 2]
3. ...

📝 后续跟进：
- 我们将在 [24 小时] 内发布详细事故报告
- [7 天] 内完成改进措施实施
- [30 天] 内完成全流程复盘

感谢您的耐心等待。

ICYQuant 运营团队
```

---

## 8. 升级路径

### 8.1 值班升级矩阵

| 级别 | 响应时间 | 联系对象 | 通讯渠道 | 决策权限 |
|------|----------|----------|----------|----------|
| L1 | 5 分钟 | 值班工程师 | 电话 / 企业微信 | 重启服务、临时扩容 |
| L2 | 15 分钟 | 团队负责人 | 电话 / 视频会议 | 停市、回滚、紧急变更 |
| L3 | 30 分钟 | 技术总监 | 现场 / 视频会议 | 紧急下线、架构调整 |
| L4 | 60 分钟 | CTO / CEO | 现场会议 | 重大决策、对外沟通 |

### 8.2 职责矩阵

| 问题类型 | L1 | L2 | L3 | L4 |
|----------|----|----|----|-----|
| 服务不可用 | ✅ | ✅ | ✅ | ✅ |
| 性能退化 | ✅ | ✅ | ✅ | |
| 数据异常 | ✅ | ✅ | ✅ | ✅ |
| 安全事件 | ✅ | ✅ | ✅ | ✅ |
| Broker 故障 | ✅ | ✅ | ✅ | |
| 客户投诉 | ✅ | ✅ | | |
| 媒体舆情 | | ✅ | ✅ | ✅ |

### 8.3 升级决策流程

```
问题检测
    │
    ▼
[L1 值班工程师] ──── 5 分钟内无法解决 ────▶ [L2 团队负责人]
    │                                          │
    │  15 分钟内无法解决                        │ 30 分钟内无法解决
    │                                          │
    ▼                                          ▼
    └──── [L3 技术总监] ──── 60 分钟内无法解决 ────▶ [L4 CTO/CEO]
                                                     │
                                                     ▼
                                            执行最高级别应对
                                            启动灾难恢复预案
```

### 8.4 值班排班

```
轮班周期：2 周
值班人员：每组 2 人（主班 + 副班）
夜班：仅处理 P0 级故障，P1 级次日处理
```

| 周 | 主班 | 副班 | 响应级别 |
|----|------|------|----------|
| 第 1 周 | 张工 | 李工 | L1 |
| 第 2 周 | 王工 | 赵工 | L1 |
| 第 3 周 | ... | ... | L1 |

### 8.5 应急资源

| 资源 | 责任人 | 联系方式 | 可用时间 |
|------|--------|----------|----------|
| Broker 紧急联系人 | 李总监 | 139-XXXX-XXXX | 7x24 |
| 云厂商技术支持 | 王工 | ticket@cloud.com | 7x24 |
| 数据库专家 | 赵工 | 138-XXXX-XXXX | 工作日 |
| 安全团队 | 孙总监 | security@icyquant.com | 7x24 |
| 法务团队 | 钱总监 | legal@icyquant.com | 工作日 |

---

## 附录

### A. 运营术语表

| 术语 | 定义 |
|------|------|
| P0 | 最高优先级，影响交易核心功能 |
| P1 | 高优先级，影响非核心功能或性能严重退化 |
| P2 | 中优先级，影响有限或有绕行方案 |
| HPA | Horizontal Pod Autoscaler |
| RTO | Recovery Time Objective |
| RPO | Recovery Point Objective |
| MTTR | Mean Time To Repair |
| SLA | Service Level Agreement |

### B. 关键联系人速查表

| 角色 | 姓名 | 手机 | 邮箱 |
|------|------|------|------|
| 运营负责人 | 张总监 | 139-XXXX-XXXX | ops-lead@icyquant.com |
| 技术负责人 | 李总监 | 138-XXXX-XXXX | tech-lead@icyquant.com |
| CTO | 王总 | 137-XXXX-XXXX | cto@icyquant.com |
| 客户经理 | 赵经理 | 136-XXXX-XXXX | accounts@icyquant.com |

### C. 参考文档

- [部署指南](./deployment_guide.md)
- [故障排查](./troubleshooting.md)
- [备份与恢复](./backup_restore.md)
- [灾难恢复](./disaster_recovery.md)
- [系统维护](./maintenance.md)
