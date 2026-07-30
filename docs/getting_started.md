# ICYQuant 入门指南

> 从零开始使用 ICYQuant 机构级量化交易平台

## 目录

- [前置条件](#前置条件)
- [快速安装](#快速安装)
  - [Docker 部署](#docker-部署)
  - [Helm (Kubernetes) 部署](#helm-kubernetes-部署)
  - [pip 安装 SDK](#pip-安装-sdk)
- [第一步](#第一步)
  - [登录平台](#登录平台)
  - [检查系统状态](#检查系统状态)
  - [运行第一个策略](#运行第一个策略)
- [基础配置](#基础配置)
- [下一步](#下一步)

---

## 前置条件

### 硬件要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 4 核 | 8+ 核 |
| 内存 | 8 GB | 16+ GB |
| 存储 | 50 GB SSD | 500 GB NVMe SSD |
| 网络 | 100 Mbps | 1 Gbps 低延迟 |

### 软件要求

| 软件 | 最低版本 | 推荐版本 |
|------|----------|----------|
| Python | 3.9 | 3.12 |
| Docker | 24.0 | 27.0+ |
| Docker Compose | 2.20 | 2.24+ |
| Kubernetes | 1.24 | 1.28+ |
| kubectl | 1.24 | 1.28+ |
| Helm | 3.14 | 3.16+ |
| PostgreSQL | 14 | 16 |
| Redis | 6 | 7 |
| Kafka (可选) | 3.4 | 3.7+ |

### 账户要求

1. **ICYQuant 账户**：访问 [https://portal.icyquant.io](https://portal.icyquant.io) 注册
2. **API 密钥**：在开发者设置中生成 API Key
3. **交易账户**：连接交易所账户（Binance、Alpaca、Interactive Brokers 等）

---

## 快速安装

### Docker 部署

Docker 是启动 ICYQuant 最快的方式，适用于开发测试和小规模生产环境。

#### 1. 克隆仓库

```bash
git clone https://github.com/icyquant/icyquant.git
cd icyquant
```

#### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 数据库
DATABASE_URL=postgresql://icyquant:password@postgres:5432/icyquant

# Redis
REDIS_URL=redis://redis:6379

# Kafka (可选)
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# JWT 密钥（生产环境请使用强随机字符串）
JWT_SECRET=<your-256-bit-secret>

# 管理员密码
ADMIN_PASSWORD=<strong-admin-password>

# 交易所 API Key (可选)
BINANCE_API_KEY=
BINANCE_API_SECRET=
```

#### 3. 启动服务

```bash
# 启动所有服务
docker compose up -d

# 查看启动日志
docker compose logs -f

# 查看服务状态
docker compose ps
```

#### 4. 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# 数据库连接检查
curl http://localhost:8000/health/database

# 指标端点
curl http://localhost:8000/metrics
```

#### 5. 预期输出

```json
// GET /health
{
  "status": "healthy",
  "version": "0.4.0",
  "uptime": "00:01:23",
  "services": {
    "database": "connected",
    "redis": "connected",
    "kafka": "connected"
  }
}
```

### Helm (Kubernetes) 部署

适用于生产级部署，支持弹性伸缩、滚动升级和高可用。

#### 1. 添加 Helm 仓库

```bash
helm repo add icyquant https://charts.icyquant.io
helm repo update
```

#### 2. 配置 Values

```bash
# 生成默认 values 文件
helm show values icyquant/icyquant > custom-values.yaml
```

编辑 `custom-values.yaml`：

```yaml
global:
  environment: production
  imageRegistry: ghcr.io/icyquant

api:
  replicaCount: 5
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

redis:
  enabled: true
  architecture: replication

postgresql:
  enabled: true
  replication:
    enabled: true

ingress:
  enabled: true
  hosts:
    - host: api.yourdomain.com
      paths:
        - path: /api/v1
          pathType: Prefix
          service: api

security:
  rbac:
    enabled: true
  secrets:
    encryption: true
```

#### 3. 安装/升级

```bash
# 安装
helm install icyquant icyquant/icyquant \
  --namespace icyquant \
  --create-namespace \
  -f custom-values.yaml

# 升级
helm upgrade icyquant icyquant/icyquant \
  --namespace icyquant \
  -f custom-values.yaml
```

#### 4. 验证部署

```bash
# 查看 Pod 状态
kubectl get pods -n icyquant

# 查看服务状态
kubectl get svc -n icyquant

# 查看 Ingress
kubectl get ingress -n icyquant

# 查看日志
kubectl logs -l app=icyquant-api -n icyquant --tail=100

# 端口转发本地测试
kubectl port-forward svc/icyquant-api 8080:8080 -n icyquant
```

#### 5. 预期输出

```
NAME                                  READY   STATUS    RESTARTS   AGE
pod/icyquant-api-7d8f6b5b9c-abcde     1/1     Running   0          2m
pod/icyquant-api-7d8f6b5b9c-fghij     1/1     Running   0          2m
pod/icyquant-ai-6c7b8d9f4d-klmno      1/1     Running   0          2m
pod/icyquant-risk-5b6c7d8e9f-pqrst    1/1     Running   0          2m
...
```

### pip 安装 SDK

适用于 Python 开发者在本地开发和测试策略。

#### 1. 创建虚拟环境

```bash
python3.12 -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate       # Windows
```

#### 2. 安装 SDK

```bash
# 基础安装
pip install icyquant-sdk

# 包含全部可选依赖
pip install icyquant-sdk[full]

# 开发模式安装（从源码）
git clone https://github.com/icyquant/icyquant.git
cd icyquant
pip install -e .
```

#### 3. 快速验证

```python
from icyquant_sdk import ICYQuantClient

client = ICYQuantClient(
    api_key="your-api-key",
    endpoint="https://api.icyquant.io"
)

# 检查连接
status = client.status()
print(status)

# 获取账户信息
account = client.account.get()
print(account)
```

---

## 第一步

### 登录平台

#### CLI 登录

```bash
# 使用 API Key 登录
icyquant auth login --api-key YOUR_API_KEY

# 验证登录状态
icyquant auth whoami
```

#### Python SDK 登录

```python
from icyquant_sdk import ICYQuantClient, JWTService

# 方式一：API Key 认证
client = ICYQuantClient(
    api_key="your-api-key",
    endpoint="https://api.icyquant.io"
)

# 方式二：用户名密码认证
client = ICYQuantClient()
client.authenticate(
    username="trader@example.com",
    password="your-password"
)

# 方式三：OAuth2 认证
client = ICYQuantClient()
client.authenticate_oauth2(
    provider="google",
    redirect_uri="http://localhost:8080/callback"
)
```

#### cURL 登录

```bash
# 获取 JWT Token
curl -X POST https://api.icyquant.io/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "trader@example.com",
    "password": "your-password"
  }'

# 使用 Token 调用 API
curl -X GET https://api.icyquant.io/api/v1/account \
  -H "Authorization: Bearer <your-jwt-token>"
```

### 检查系统状态

```bash
# CLI 方式
icyquant status

# Python SDK
status = client.status()
print(f"Platform: {status['state']}")
print(f"Version: {status['version']}")
print(f"Uptime: {status['uptime']}")

# cURL 方式
curl -s https://api.icyquant.io/api/v1/health | jq .
```

**预期输出：**

```json
{
  "state": "operational",
  "version": "0.4.0",
  "uptime": "12:34:56",
  "modules": {
    "api": "running",
    "ai": "running",
    "risk": "running",
    "oms": "running",
    "ems": "running",
    "portfolio": "running"
  },
  "exchanges": {
    "binance": "connected",
    "alpaca": "disconnected"
  }
}
```

### 运行第一个策略

#### 1. 创建策略文件

```python
# my_strategy.py
from icyquant_sdk.strategy import Strategy, Bar

class MyFirstStrategy(Strategy):
    """双均线交叉策略"""
    
    def __init__(self):
        self.fast_ma = 5
        self.slow_ma = 20
        self.position = 0
    
    async def on_bar(self, bar: Bar):
        """每根 K 线触发"""
        # 获取历史数据
        closes = await self.data.get_closes(
            symbol=bar.symbol,
            timeframe=bar.timeframe,
            limit=self.slow_ma + 1
        )
        
        if len(closes) < self.slow_ma + 1:
            return
        
        # 计算均线
        fast_ma = sum(closes[-self.fast_ma:]) / self.fast_ma
        slow_ma = sum(closes[-self.slow_ma:]) / self.slow_ma
        
        # 金叉买入
        if fast_ma > slow_ma and self.position == 0:
            order = await self.order.market_buy(
                symbol=bar.symbol,
                quantity=0.1,
                stop_loss=slow_ma * 0.98,
                take_profit=slow_ma * 1.05
            )
            self.position = order.quantity
        
        # 死叉卖出
        elif fast_ma < slow_ma and self.position > 0:
            await self.order.market_sell(
                symbol=bar.symbol,
                quantity=self.position
            )
            self.position = 0
    
    async def on_start(self):
        """策略启动时"""
        print(f"Strategy started: {self.config.name}")
    
    async def on_stop(self):
        """策略停止时"""
        print(f"Strategy stopped: {self.config.name}")
```

#### 2. 提交策略

```bash
icyquant strategy create \
  --name "my-first-strategy" \
  --file my_strategy.py \
  --symbol BTCUSDT \
  --timeframe 1h \
  --capital 100000
```

#### 3. 运行回测

```bash
icyquant backtest run \
  --strategy "my-first-strategy" \
  --symbol BTCUSDT \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 100000 \
  --commission 0.001
```

**预期输出：**

```
╭─────────────────────────────────────────────────────────────╮
│                    Backtest Results                          │
├─────────────────────────────────────────────────────────────┤
│ Strategy: my-first-strategy                                  │
│ Symbol:   BTCUSDT (1h)                                       │
│ Period:   2024-01-01 to 2024-12-31                           │
├─────────────────────────────────────────────────────────────┤
│ Total Return:      +23.45%                                   │
│ Annual Return:     +23.45%                                   │
│ Sharpe Ratio:       1.87                                    │
│ Sortino Ratio:      2.34                                    │
│ Max Drawdown:      -8.23%                                    │
│ Win Rate:          62.50%                                    │
│ Profit Factor:      2.15                                    │
│ Calmar Ratio:       2.85                                    │
│ Volatility:        12.34%                                    │
│ Trade Count:        48                                      │
╰─────────────────────────────────────────────────────────────╯
```

#### 4. 模拟盘运行

```bash
icyquant strategy paper-run \
  --strategy "my-first-strategy" \
  --symbol BTCUSDT \
  --capital 100000
```

#### 5. 生产部署

```bash
# 通过风险审批后部署
icyquant deploy strategy "my-first-strategy" \
  --environment production \
  --approval-approved
```

---

## 基础配置

### 全局配置文件

配置文件路径：`~/.icyquant/config.yaml`

```yaml
# ICYQuant 全局配置
version: "0.4.0"

# API 连接
api:
  endpoint: "https://api.icyquant.io"
  timeout: 30
  retry:
    max_attempts: 3
    backoff: exponential

# 默认交易参数
trading:
  account_id: "default"
  default_capital: 100000
  default_symbol: "BTCUSDT"
  commission: 0.001
  slippage: 0.0005
  time_in_force: "GTC"

# 风控参数
risk:
  max_drawdown: 0.20
  max_leverage: 5.0
  position_limit_pct: 0.30
  daily_loss_limit_pct: 0.05
  per_trade_loss_pct: 0.02
  circuit_breaker:
    enabled: true
    threshold: 0.10
    cooldown_minutes: 30

# 通知配置
notifications:
  email:
    enabled: true
    smtp_host: "smtp.icyquant.io"
    smtp_port: 587
    recipient: "ops@icyquant.io"
  webhook:
    enabled: false
    url: ""

# 日志配置
logging:
  level: "INFO"
  file: "~/.icyquant/logs/icyquant.log"
  max_size_mb: 100
  backup_count: 5

# 数据缓存
cache:
  enabled: true
  ttl_seconds: 3600
  max_entries: 100000
```

### 环境变量配置

```bash
# 必填
export ICYQUANT_API_KEY="your-api-key"
export ICYQUANT_ENDPOINT="https://api.icyquant.io"

# 可选
export ICYQUANT_LOG_LEVEL="DEBUG"
export ICYQUANT_CONFIG="/path/to/config.yaml"
export ICYQUANT_TIMEOUT="60"
```

### 多环境配置

```yaml
# configs/environments/production.yaml
environment: production
api:
  endpoint: "https://api.icyquant.io"
  timeout: 30
risk:
  max_drawdown: 0.15
  max_leverage: 3.0
trading:
  commission: 0.0005

---

# configs/environments/staging.yaml
environment: staging
api:
  endpoint: "https://staging.icyquant.io"
  timeout: 60
risk:
  max_drawdown: 0.25
  max_leverage: 5.0
trading:
  commission: 0.001

---

# configs/environments/development.yaml
environment: development
api:
  endpoint: "http://localhost:8000"
  timeout: 120
risk:
  max_drawdown: 0.50
  max_leverage: 10.0
trading:
  commission: 0.0
```

### 切换环境

```bash
icyquant config use production
icyquant config show
```

---

## 下一步

### 深入学习

| 文档 | 描述 |
|------|------|
| [开发者指南](developer_guide.md) | 策略开发、自定义指标、插件开发 |
| [API 参考](api_reference.md) | 全部 REST API 端点详细说明 |
| [架构深潜](architecture.md) | 系统架构、模块设计、数据流 |
| [操作手册](operator_guide.md) | 日常运维、监控告警、故障处理 |
| [部署指南](deployment.md) | Docker/K8s 部署配置详解 |
| [安全指南](security.md) | 认证授权、加密、合规 |
| [可观测性](observability.md) | 日志、指标、追踪、告警 |
| [故障排除](troubleshooting.md) | 常见问题诊断与恢复 |

### 推荐学习路径

```
入门指南 → API 参考 → 开发者指南 → 架构深潜 → 部署指南 → 安全指南
```

### 获取帮助

- **文档**：[https://docs.icyquant.io](https://docs.icyquant.io)
- **GitHub**：[https://github.com/icyquant/icyquant](https://github.com/icyquant/icyquant)
- **社区**：[https://community.icyquant.io](https://community.icyquant.io)
- **企业支持**：[enterprise@icyquant.io](mailto:enterprise@icyquant.io)

---

**文档版本**: 1.0
**创建日期**: 2026-07-30
**适用版本**: ICYQuant v0.4.0 GA