# ICYQuant 可观测性指南

> 日志、指标、追踪、告警、仪表板与 AI 监控

## 目录

- [日志](#日志)
- [指标](#指标)
- [分布式追踪](#分布式追踪)
- [告警](#告警)
- [仪表板](#仪表板)
- [AI 模型监控](#ai-模型监控)
- [成本分析](#成本分析)
- [SLA/SLO 管理](#slaslo-管理)

---

## 日志

### 日志框架

ICYQuant 使用 Python 标准 logging 模块，采用结构化日志格式。

#### 日志配置

```python
# configs/logging/production.yaml
version: 1
formatters:
  structured:
    format: '{"timestamp":"%(asctime)s","level":"%(levelname)s","service":"%(name)s","module":"%(module)s","message":"%(message)s","trace_id":"%(trace_id)s","data":%(extra)s}'
  human:
    format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    formatter: structured
    level: INFO
  file:
    class: logging.handlers.RotatingFileHandler
    filename: /var/log/icyquant/app.log
    maxBytes: 104857600  # 100MB
    backupCount: 5
    formatter: structured
    level: INFO
  elasticsearch:
    class: elasticsearch_logging.handlers.ElasticsearchHandler
    hosts: ["elasticsearch:9200"]
    index: icyquant-logs-%{yyyy}.%{mm}.%{dd}
    level: WARNING

loggers:
  icyquant:
    level: INFO
    handlers: [console, file, elasticsearch]
    propagate: false
  icyquant.api:
    level: INFO
  icyquant.risk:
    level: WARNING
  icyquant.oms:
    level: INFO
  icyquant.ai:
    level: WARNING

root:
  level: WARNING
  handlers: [console]
```

#### 日志级别

| 级别 | 说明 | 使用场景 |
|------|------|----------|
| `DEBUG` | 详细调试信息 | 开发调试、问题诊断 |
| `INFO` | 关键业务事件 | 订单创建、成交、策略启动 |
| `WARNING` | 警告信息 | 风控接近限额、延迟增加 |
| `ERROR` | 错误信息 | 订单被拒、数据库错误 |
| `CRITICAL` | 严重错误 | 服务不可用、数据丢失 |

#### 结构化日志示例

```json
{
  "timestamp": "2026-07-30T10:00:00.000Z",
  "level": "INFO",
  "service": "icyquant-api",
  "module": "oms",
  "event": "order.created",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "data": {
    "order_id": "ord_20260730_001",
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 0.5,
    "price": 67000.00,
    "status": "PENDING"
  },
  "user_id": "usr_001",
  "strategy_id": "strat_001",
  "message": "Order created successfully"
}
```

### 日志查询

#### Loki 查询

```bash
# 查看错误日志
{app="icyquant-api"} |= "ERROR"

# 按模块筛选
{app="icyquant-api", module="oms"} |= "order"

# 按 Trace ID 追踪
{trace_id="4bf92f3577b34da6a3ce929d0e0e4736"}

# 时间范围筛选
{app="icyquant-api"} |= "ERROR" | json | line_format "{{.level}} {{.message}}"

# 聚合统计
sum(count_over_time({app="icyquant-api"} |= "ERROR" [5m]))
```

#### Elasticsearch 查询

```json
// 查询最近 1 小时的错误日志
GET icyquant-logs-*/_search
{
  "query": {
    "bool": {
      "must": [
        {"match": {"level": "ERROR"}},
        {"range": {"@timestamp": {"gte": "now-1h"}}}
      ]
    }
  },
  "sort": [{"@timestamp": "desc"}],
  "size": 100
}

// 按模块聚合错误
GET icyquant-logs-*/_search
{
  "aggs": {
    "by_module": {
      "terms": {"field": "module.keyword"},
      "aggs": {
        "by_level": {
          "terms": {"field": "level.keyword"}
        }
      }
    }
  }
}
```

### 日志保留

| 级别 | 存储位置 | 保留周期 |
|------|----------|----------|
| DEBUG | - | 不存储 |
| INFO | 本地文件 | 7 天 |
| INFO | Elasticsearch | 30 天 |
| WARNING | Elasticsearch | 90 天 |
| ERROR | Elasticsearch | 90 天 |
| CRITICAL | Elasticsearch | 永久 |

---

## 指标

### Prometheus 指标

ICYQuant 通过 `/metrics` 端点暴露 Prometheus 格式指标。

#### 指标命名规范

```
icyquant{domain}_{metric}_{type}

# 示例:
icyquant_requests_total       (计数器 - 请求总数)
icyquant_request_duration_seconds (直方图 - 请求耗时)
icyquant_portfolio_total_value  (仪表盘 - 组合总值)
icyquant_risk_alerts_total     (计数器 - 风控告警)
```

#### 核心指标清单

| 指标 | 类型 | 标签 | 说明 |
|------|------|------|------|
| `icyquant_requests_total` | Counter | method, path, status | API 请求总数 |
| `icyquant_request_duration_seconds` | Histogram | method, path | API 请求耗时 |
| `icyquant_requests_in_flight` | Gauge | path | 进行中请求数 |
| `icyquant_portfolio_total_value` | Gauge | portfolio | 组合总值 |
| `icyquant_portfolio_pnl` | Gauge | portfolio, type | 组合 PnL |
| `icyquant_orders_total` | Counter | symbol, side, status | 订单总数 |
| `icyquant_orders_in_flight` | Gauge | symbol, strategy | 进行中订单数 |
| `icyquant_risk_alerts_total` | Counter | level, metric | 风控告警总数 |
| `icyquant_risk_check_duration_seconds` | Histogram | service | 风险检查耗时 |
| `icyquant_ai_inference_duration_seconds` | Histogram | model | AI 推理耗时 |
| `icyquant_ai_token_usage_total` | Counter | model, type | Token 使用量 |
| `icyquant_execution_slippage` | Histogram | algorithm | 执行滑点 |
| `icyquant_database_connections` | Gauge | pool | 数据库连接数 |
| `icyquant_redis_operations_total` | Counter | operation | Redis 操作总数 |
| `icyquant_kafka_lag` | Gauge | consumer_group, topic | Kafka 消费延迟 |
| `icyquant_strategy_status` | Gauge | strategy, status | 策略状态 |
| `icyquant_exchange_connectivity` | Gauge | exchange | 交易所连接状态 |

#### 指标示例

```
# HELP icyquant_requests_total Total API requests
# TYPE icyquant_requests_total counter
icyquant_requests_total{method="GET",path="/api/v1/health",status="200"} 1024
icyquant_requests_total{method="POST",path="/api/v1/orders",status="201"} 150
icyquant_requests_total{method="GET",path="/api/v1/portfolio",status="200"} 500

# HELP icyquant_request_duration_seconds Request duration
# TYPE icyquant_request_duration_seconds histogram
icyquant_request_duration_seconds_bucket{le="0.01"} 500
icyquant_request_duration_seconds_bucket{le="0.05"} 900
icyquant_request_duration_seconds_bucket{le="0.1"} 1000
icyquant_request_duration_seconds_bucket{le="0.5"} 1023
icyquant_request_duration_seconds_bucket{le="1.0"} 1023
icyquant_request_duration_seconds_sum 25.5
icyquant_request_duration_seconds_count 1023

# HELP icyquant_portfolio_total_value Total portfolio value
# TYPE icyquant_portfolio_total_value gauge
icyquant_portfolio_total_value{portfolio="pf_001"} 1005000.00

# HELP icyquant_risk_alerts_total Total risk alerts
# TYPE icyquant_risk_alerts_total counter
icyquant_risk_alerts_total{level="critical",metric="drawdown"} 2
icyquant_risk_alerts_total{level="warning",metric="leverage"} 15
icyquant_risk_alerts_total{level="info",metric="exposure"} 45
```

### 自定义指标

```python
from prometheus_client import Counter, Histogram, Gauge, generate_labels

# 定义指标
ORDER_TOTAL = Counter(
    'icyquant_orders_total',
    'Total orders',
    ['symbol', 'side', 'status', 'strategy']
)

ORDER_DURATION = Histogram(
    'icyquant_order_duration_seconds',
    'Order processing duration',
    ['type'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
)

PORTFOLIO_VALUE = Gauge(
    'icyquant_portfolio_total_value',
    'Total portfolio value',
    ['portfolio']
)

# 使用指标
ORDER_TOTAL.labels(
    symbol="BTCUSDT",
    side="BUY",
    status="FILLED",
    strategy="dual_ma"
).inc()

with ORDER_DURATION.labels(type="market_order").time():
    process_order()

PORTFOLIO_VALUE.labels(portfolio="pf_001").set(1005000.00)
```

### Prometheus 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: us-east-1
    environment: production

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  - job_name: 'icyquant-api'
    scheme: https
    tls_config:
      cert_file: /certs/client.crt
      key_file: /certs/client.key
    kubernetes_sd_configs:
      - role: pod
        selectors:
          - role: label
            label: app=icyquant-api
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: "true"
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        target_label: __address__
        regex: ([^:]+)(?::\d+)?
        replacement: $1:${2}
  
  - job_name: 'icyquant-ai'
    scheme: https
    kubernetes_sd_configs:
      - role: pod
        selectors:
          - role: label
            label: app=icyquant-ai
  
  - job_name: 'icyquant-risk'
    scheme: https
    kubernetes_sd_configs:
      - role: pod
        selectors:
          - role: label
            label: app=icyquant-risk

  - job_name: 'node-exporter'
    static_configs:
      - targets:
          - node-exporter:9100

  - job_name: 'postgres-exporter'
    static_configs:
      - targets:
          - pg-exporter:9187

  - job_name: 'redis-exporter'
    static_configs:
      - targets:
          - redis-exporter:9121

  - job_name: 'kafka-exporter'
    static_configs:
      - targets:
          - kafka-exporter:9308

remote_write:
  - url: https://mimir.icyquant.io/api/v1/push
    headers:
      X-Scope-OrgID: icyquant
    batch_send_deadline: 5s
    max_samples_per_batch: 200000

remote_read:
  - url: https://mimir.icyquant.io/api/v1/read
    headers:
      X-Scope-OrgID: icyquant
```

---

## 分布式追踪

### OpenTelemetry 集成

ICYQuant 使用 OpenTelemetry 进行分布式追踪。

#### 追踪配置

```python
# otel_config.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.kafka import KafkaInstrumentor

def setup_tracing(service_name: str = "icyquant-api"):
    """配置 OpenTelemetry 追踪"""
    
    # Jaeger Exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger-agent",
        agent_port=6831,
    )
    
    # 创建 TracerProvider
    provider = TracerProvider()
    processor = BatchSpanProcessor(jaeger_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    
    # 自动检测
    tracer = trace.get_tracer(service_name)
    
    return tracer

def instrument_app(app, db_engine=None, redis_client=None):
    """自动检测各组件"""
    
    FastAPIInstrumentor.instrument_app(app)
    HTTPXInstrumentor().instrument()
    
    if db_engine:
        SQLAlchemyInstrumentor().instrument(engine=db_engine)
    
    if redis_client:
        RedisInstrumentor().instrument()
    
    KafkaInstrumentor().instrument()
```

#### 创建 Span

```python
from opentelemetry import trace

tracer = trace.get_tracer("icyquant-oms")

async def process_order(order: Order):
    with tracer.start_as_current_span(
        "process_order",
        attributes={
            "order_id": order.id,
            "symbol": order.symbol,
            "side": order.side,
        }
    ) as span:
        try:
            result = await _execute_order(order)
            span.set_status(trace.StatusCode.OK)
            return result
        except Exception as e:
            span.set_status(trace.StatusCode.ERROR)
            span.record_exception(e)
            raise
```

#### 追踪上下文传播

```python
# 服务间传播
from opentelemetry.propagate import inject
from opentelemetry.context import Context

context = Context.get_current()
headers = {}
inject(headers, context)

# 传递到下游服务
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://risk-service/check",
        headers={**headers, "Authorization": f"Bearer {token}"},
        json=order_data,
    )
```

### Jaeger 查询

#### 查看追踪

```bash
# 打开 Jaeger UI
open http://jaeger.icyquant.io

# 按服务名搜索
# 选择 service: "icyquant-api"
# 查看最近的追踪

# 按 trace ID 查询
curl "http://jaeger.icyquant.io/api/traces?traceID=4bf92f3577b34da6a3ce929d0e0e4736"

# 按时间范围查询
curl "http://jaeger.icyquant.io/api/traces?operation=process_order&limit=10&start=1722369600000&end=1722373200000"
```

#### 采样策略

| 策略 | 说明 | 使用场景 |
|------|------|----------|
| AlwaysOn | 100% 采样 | 开发环境 |
| AlwaysOff | 0% 采样 | - |
| TraceIDRatioBased | 基于 Trace ID 哈希 | 生产环境 |
| ParentBased | 基于父 Span 决策 | 推荐 |

```python
# 采样配置
from opentelemetry.sdk.trace.export import TraceIdRatioBasedSampler

# 生产环境: 10% 采样率
sampler = TraceIdRatioBasedSampler(0.1)

# 对关键操作使用 AlwaysOn
# 通过注解/标签区分
```

---

## 告警

### 告警规则

#### API 告警

```yaml
groups:
  - name: api-alerts
    rules:
      - alert: APIServiceDown
        expr: up{job="icyquant-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "API 服务不可用"
          description: "API 服务 {{ $labels.instance }} 已停止超过 1 分钟"

      - alert: HighErrorRate
        expr: rate(icyquant_requests_total{status=~"5.."}[5m]) / rate(icyquant_requests_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "API 错误率超过 1%"
          description: "5xx 错误率 {{ $value | humanizePercentage }}，持续 5 分钟"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(icyquant_request_duration_seconds_bucket[5m])) > 0.5
        for: 10m
        labels:
          severity: high
        annotations:
          summary: "API P95 延迟超过 500ms"

      - alert: HighLatencyP99
        expr: histogram_quantile(0.99, rate(icyquant_request_duration_seconds_bucket[5m])) > 1.0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "API P99 延迟超过 1s"
```

#### 交易告警

```yaml
  - name: trading-alerts
    rules:
      - alert: OrderRejected
        expr: rate(icyquant_orders_total{status="REJECTED"}[5m]) > 0
        for: 1m
        labels:
          severity: high
        annotations:
          summary: "订单被拒绝"
          description: "交易对 {{ $labels.symbol }} 的订单被风控拒绝"

      - alert: HighSlippage
        expr: histogram_quantile(0.95, rate(icyquant_execution_slippage_bucket[5m])) > 0.005
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "执行滑点过大"

      - alert: ExchangeDisconnected
        expr: icyquant_exchange_connectivity == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "交易所连接断开"
          description: "与 {{ $labels.exchange }} 的连接已断开"
```

#### 风控告警

```yaml
  - name: risk-alerts
    rules:
      - alert: MaxDrawdownBreach
        expr: icyquant_portfolio_drawdown > 0.15
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "组合回撤超过 15%"
          description: "当前回撤 {{ $value | humanizePercentage }}，已超过限额"

      - alert: LeverageExceeded
        expr: icyquant_portfolio_leverage > 5.0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "杠杆超过 5 倍"

      - alert: PositionLimitBreach
        expr: icyquant_position_weight > 0.30
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "单一持仓超过 30%"

      - alert: DailyLossLimitBreach
        expr: icyquant_portfolio_daily_loss > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "日亏损超过 5%"

      - alert: CircuitBreakerTriggered
        expr: increase(icyquant_risk_alerts_total{metric="circuit_breaker"}[1m]) > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "熔断器已触发"
```

#### 基础设施告警

```yaml
  - name: infrastructure-alerts
    rules:
      - alert: DatabaseDown
        expr: pg_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "数据库不可用"

      - alert: DatabaseReplicationLag
        expr: pg_replication_lag > 60
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "数据库复制延迟超过 60 秒"

      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_total_bytes > 0.9
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Redis 内存使用率超过 90%"

      - alert: KafkaConsumerLag
        expr: kafka_consumergroup_lag > 10000
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "Kafka 消费延迟超过 10000 条"

      - alert: HighCPUUsage
        expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "CPU 使用率超过 85%"

      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "内存使用率超过 90%"
```

### Alertmanager 配置

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.icyquant.io:587'
  smtp_from: 'alerts@icyquant.io'
  smtp_auth_username: 'alerts@icyquant.io'
  smtp_auth_password: '${SMTP_PASSWORD}'

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'default'
  routes:
    - match: {severity: critical}
      receiver: 'critical'
      repeat_interval: 5m
    - match: {severity: high}
      receiver: 'high'
      repeat_interval: 15m

receivers:
  - name: 'default'
    email_configs:
      - to: 'ops@icyquant.io'
        send_resolved: true

  - name: 'critical'
    email_configs:
      - to: 'oncall@icyquant.io'
        send_resolved: true
    webhook_configs:
      - url: 'https://hooks.slack.com/services/XXX'
        send_resolved: true
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}Level: {{ .Labels.severity }}\nSummary: {{ .Annotations.summary }}\nDescription: {{ .Annotations.description }}\n{{ end }}'

  - name: 'high'
    email_configs:
      - to: 'team@icyquant.io'
        send_resolved: true
    webhook_configs:
      - url: 'https://hooks.slack.com/services/YYY'
        send_resolved: true

inhibit_rules:
  - source_match: {severity: 'critical'}
    target_match: {severity: 'warning'}
    equal: ['alertname']
```

---

## 仪表板

### Grafana 仪表板

#### 系统总览仪表板

| 面板 | 内容 |
|------|------|
| 服务健康 | 所有服务状态指示灯 |
| 请求量 QPS | 各 API 端点实时 QPS |
| 响应延迟 | P50/P95/P99 延迟趋势 |
| 错误率 | 按状态码分类的错误率 |
| CPU/内存 | 各 Pod 资源使用 |
| 网络流量 | 入站/出站流量 |

#### 交易监控仪表板

| 面板 | 内容 |
|------|------|
| 实时订单流 | 订单创建/成交/取消实时流 |
| 成交量统计 | 按交易对/策略的成交量 |
| PnL 曲线 | 实时盈亏曲线 |
| 持仓分布 | 按交易对的持仓分布饼图 |
| 策略绩效 | 各策略 Sharpe/回撤 |
| 交易所状态 | 各交易所连接状态 |

#### 风险仪表板

| 面板 | 内容 |
|------|------|
| 风险仪表盘 | VaR/CVaR/最大回撤 |
| 限额状态 | 各风险指标限额使用情况 |
| 实时告警 | 未处理的风险告警列表 |
| 压力测试 | 历史压力测试结果 |
| 敞口分析 | 按资产类别的敞口分布 |
| 杠杆监控 | 账户/组合杠杆实时监控 |

#### AI 服务仪表板

| 面板 | 内容 |
|------|------|
| 模型延迟 | 各 AI 模型推理延迟 |
| GPU 使用 | GPU 利用率和显存使用 |
| Token 使用 | 按模型的 Token 消耗 |
| 任务队列 | 待处理/正在处理的 AI 任务 |
| Agent 决策 | AI Agent 决策准确率 |
| 成本趋势 | AI 服务成本日/周/月趋势 |

---

## AI 模型监控

### AI 特定指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `icyquant_ai_inference_duration_seconds` | Histogram | 模型推理延迟 |
| `icyquant_ai_token_usage_total` | Counter | Token 消耗量 |
| `icyquant_ai_requests_total` | Counter | AI 请求总数 |
| `icyquant_ai_errors_total` | Counter | AI 错误总数 |
| `icyquant_ai_gpu_utilization` | Gauge | GPU 利用率 |
| `icyquant_ai_gpu_memory_usage` | Gauge | GPU 显存使用 |
| `icyquant_ai_model_drift` | Gauge | 模型漂移分数 |
| `icyquant_ai_decision_accuracy` | Gauge | 决策准确率 |
| `icyquant_ai_cost_per_request` | Gauge | 每次请求成本 |

### 模型漂移检测

```python
# 模型漂移监控
class DriftMonitor:
    def calculate_drift(self, reference_data, current_data):
        """计算数据漂移"""
        # KS 检验
        ks_stat, p_value = ks_2samp(reference_data, current_data)
        
        # PSI (Population Stability Index)
        psi = self._calculate_psi(reference_data, current_data)
        
        return {
            "ks_statistic": ks_stat,
            "ks_p_value": p_value,
            "psi": psi,
            "drift_detected": psi > 0.25,
        }
```

### AI 告警规则

```yaml
  - name: ai-alerts
    rules:
      - alert: HighAIInferenceLatency
        expr: histogram_quantile(0.95, rate(icyquant_ai_inference_duration_seconds_bucket[5m])) > 2.0
        for: 10m
        labels:
          severity: high
        annotations:
          summary: "AI 推理延迟超过 2 秒"

      - alert: HighAIErrorRate
        expr: rate(icyquant_ai_errors_total[5m]) / rate(icyquant_ai_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "AI 错误率超过 5%"

      - alert: GPUMemoryHigh
        expr: icyquant_ai_gpu_memory_usage / icyquant_ai_gpu_memory_total > 0.9
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "GPU 显存使用率超过 90%"

      - alert: ModelDriftDetected
        expr: icyquant_ai_model_drift > 0.25
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "检测到模型漂移"
```

---

## 成本分析

### 成本指标

| 指标 | 说明 |
|------|------|
| `icyquant_cost_total` | 总成本 |
| `icyquant_cost_by_service` | 按服务成本 |
| `icyquant_cost_by_resource` | 按资源类型成本 |
| `icyquant_ai_cost` | AI 服务成本 |
| `icyquant_infrastructure_cost` | 基础设施成本 |
| `icyquant_trading_cost` | 交易成本（手续费等） |

### 成本仪表板

| 面板 | 内容 |
|------|------|
| 总成本概览 | 日/周/月总成本趋势 |
| 服务成本分布 | 按服务的成本饼图 |
| AI 成本分析 | 按模型/任务的 AI 成本 |
| 资源成本分析 | CPU/内存/GPU/存储成本 |
| 成本预测 | 基于历史的成本预测 |
| ROI 分析 | 成本 vs 收益对比 |

### 成本优化建议

| 优化方向 | 措施 | 预期节省 |
|----------|------|----------|
| GPU 使用 | 模型量化、批处理优化 | 30-50% |
| API 调用 | 缓存、批量请求 | 20-40% |
| 存储 | 冷热数据分层、压缩 | 40-60% |
| 数据库 | 查询优化、连接池调整 | 15-25% |
| 自动伸缩 | 基于负载动态扩缩 | 20-30% |

---

## SLA/SLO 管理

### SLA 定义

| SLA 指标 | 目标值 | 测量方法 |
|----------|--------|----------|
| 可用性 | 99.99% | 正常运行时间 / 总时间 |
| API P95 延迟 | < 200ms | Prometheus 直方图 |
| API P99 延迟 | < 500ms | Prometheus 直方图 |
| 订单处理延迟 | < 100ms | 从创建到发送 |
| 风险检查延迟 | < 10ms | 从请求到响应 |
| 数据新鲜度 | < 500ms | 从成交到入账 |
| 故障恢复时间 | < 5 分钟 | MTTR |
| 数据丢失 | 0 | RPO = 0 |

### SLO 层级

| 层级 | 目标 | 错误预算 |
|------|------|----------|
| **关键交易** | 99.99% | 0.01% (年 ~52 分钟) |
| **API 服务** | 99.9% | 0.1% (年 ~8.76 小时) |
| **分析服务** | 99.5% | 0.5% (年 ~43.8 小时) |
| **管理功能** | 99% | 1% (年 ~87.6 小时) |

### SLI 指标

```yaml
# SLI 定义
slis:
  availability:
    description: "服务可用性"
    query: "sum(rate(icyquant_requests_total{status=~'2..'}[5m])) / sum(rate(icyquant_requests_total[5m]))"
    target: 0.9999
  
  latency:
    description: "P95 API 延迟"
    query: "histogram_quantile(0.95, rate(icyquant_request_duration_seconds_bucket[5m]))"
    target: 0.2
  
  error_rate:
    description: "错误率"
    query: "sum(rate(icyquant_requests_total{status=~'5..'}[5m])) / sum(rate(icyquant_requests_total[5m]))"
    target: 0.001
  
  throughput:
    description: "系统吞吐量"
    query: "sum(rate(icyquant_requests_total[5m]))"
    target: 1000
```

### 错误预算管理

```
错误预算 = 1 - SLO 目标

示例:
  SLO 可用性 = 99.99%
  错误预算 = 0.01% = 52 分钟/年

消耗速率:
  当前 30 天错误预算消耗: 15 分钟
  剩余预算: 37 分钟
  消耗速率: 0.5 分钟/天

如果消耗速率 > 预算:
  → 冻结新功能发布
  → 优先修复可靠性问题
```

### SLA 仪表板

| 面板 | 内容 |
|------|------|
| SLA 总览 | 所有 SLI 状态仪表 |
| 错误预算 | 各 SLO 错误预算消耗 |
| 可用性趋势 | 实时可用性趋势 |
| 延迟趋势 | P50/P95/P99 延迟 |
| 事件时间线 | SLA 违规事件时间线 |
| 改进追踪 | 可靠性改进追踪 |

---

**文档版本**: 1.0
**创建日期**: 2026-07-30
**适用版本**: ICYQuant v0.4.0 GA