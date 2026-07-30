# ICYQuant CLI

> 机构级量化交易平台命令行工具

## 概述

ICYQuant CLI 是 ICYQuant 平台的官方命令行工具，提供策略管理、回测执行、风险监控、部署运维等全流程操作能力。

## 安装

### 通过 pip 安装

```bash
pip install icyquant-cli
```

### 从源码安装

```bash
git clone https://github.com/icyquant/icyquant.git
cd icyquant/release/packages/cli
pip install -e .
```

### 验证安装

```bash
icyquant --version
# icyquant-cli v0.4.0
```

## 快速开始

### 1. 初始化配置

```bash
icyquant init --name my-fund --template default
```

### 2. 登录平台

```bash
icyquant auth login --api-key YOUR_API_KEY --endpoint https://api.icyquant.io
```

### 3. 运行策略

```bash
icyquant strategy run --strategy my_strategy --symbol BTCUSDT --capital 100000
```

### 4. 查看状态

```bash
icyquant status
```

## 命令参考

### 全局选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--verbose`, `-v` | 详细输出模式 | `false` |
| `--quiet`, `-q` | 静默模式，仅输出错误 | `false` |
| `--output`, `-o` | 输出格式 (`json`, `table`, `yaml`) | `table` |
| `--config` | 指定配置文件路径 | `~/.icyquant/config.yaml` |
| `--endpoint` | API 端点 URL | `http://localhost:8000` |
| `--timeout` | 请求超时时间（秒） | `30` |

### auth 命令

管理认证凭证。

```bash
# 登录
icyquant auth login --api-key KEY [--endpoint URL]

# 使用用户名密码登录
icyquant auth login --username USER --password PASS

# 使用 OAuth2 登录
icyquant auth login --oauth2 --provider google

# 登出
icyquant auth logout

# 查看当前会话
icyquant auth whoami
```

**参数说明：**

| 参数 | 必需 | 说明 |
|------|------|------|
| `--api-key` | 否 | API 密钥 |
| `--username` | 否 | 用户名 |
| `--password` | 否 | 密码（建议使用环境变量 `ICYQUANT_PASSWORD`） |
| `--oauth2` | 否 | 使用 OAuth2 认证 |
| `--provider` | 否 | OAuth2 提供者 (`google`, `github`, `microsoft`) |

### strategy 命令

策略生命周期管理。

```bash
# 创建策略
icyquant strategy create --name my_strategy --type custom --file strategy.py

# 列出所有策略
icyquant strategy list [--status STATUS] [--format FORMAT]

# 查看策略详情
icyquant strategy show <strategy_id>

# 启动策略
icyquant strategy start <strategy_id> [--capital AMOUNT] [--symbol SYMBOL]

# 停止策略
icyquant strategy stop <strategy_id> [--reason REASON]

# 暂停策略
icyquant strategy pause <strategy_id>

# 恢复策略
icyquant strategy resume <strategy_id>

# 克隆策略
icyquant strategy clone <strategy_id> --name new_strategy

# 删除策略
icyquant strategy delete <strategy_id> [--force]

# 查看策略日志
icyquant strategy logs <strategy_id> [--lines N] [--follow]
```

**策略状态流转：**

```
CREATED → RUNNING → PAUSED → RUNNING
                         ↓
                      STOPPED → ARCHIVED
```

### backtest 命令

历史数据回测。

```bash
# 运行回测
icyquant backtest run \
  --strategy STRATEGY_ID \
  --symbol BTCUSDT \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 100000 \
  --commission 0.001 \
  --slippage 0.0005

# 列出回测任务
icyquant backtest list [--status STATUS]

# 查看回测结果
icyquant backtest show <backtest_id>

# 比较多个回测结果
icyquant backtest compare <id1> <id2> <id3>

# 导出回测报告
icyquant backtest export <backtest_id> --format PDF --output report.pdf

# 参数优化
icyquant backtest optimize \
  --strategy STRATEGY_ID \
  --param-fast-ma 5,10,20,50 \
  --param-slow-ma 20,50,100,200 \
  --metric sharpe_ratio \
  --max-combinations 50
```

**回测输出指标：**

| 指标 | 说明 |
|------|------|
| Total Return | 总收益率 |
| Annual Return | 年化收益率 |
| Sharpe Ratio | 夏普比率 |
| Sortino Ratio | 索提诺比率 |
| Max Drawdown | 最大回撤 |
| Win Rate | 胜率 |
| Profit Factor | 盈亏比 |
| Calmar Ratio | 卡玛比率 |
| Volatility | 波动率 |
| Trade Count | 交易次数 |

### risk 命令

风险监控与管理。

```bash
# 查看风险仪表盘
icyquant risk dashboard

# 检查当前风险状态
icyquant risk check [--portfolio PORTFOLIO_ID]

# 查看风险限额
icyquant risk limits [--scope SCOPE]

# 设置风险限额
icyquant risk set-limit \
  --metric METRIC \
  --value VALUE \
  --action ACTION

# 压力测试
icyquant risk stress \
  --strategy STRATEGY_ID \
  --scenario SCENARIO

# 风险报告
icyquant risk report [--format FORMAT] [--output FILE]

# 紧急熔断
icyquant risk circuit-breaker --reason "市场异常波动"
```

### order 命令

订单管理。

```bash
# 下单
icyquant order create \
  --symbol BTCUSDT \
  --side BUY \
  --quantity 0.5 \
  --type MARKET \
  [--price PRICE] \
  [--time-in-force GTC]

# 列出订单
icyquant order list [--status STATUS] [--symbol SYMBOL] [--from DATE] [--to DATE]

# 查看订单详情
icyquant order show <order_id>

# 取消订单
icyquant order cancel <order_id> [--reason REASON]

# 批量取消
icyquant order cancel-all [--symbol SYMBOL]

# 修改订单
icyquant order modify <order_id> --quantity NEW_QTY [--price NEW_PRICE]
```

### portfolio 命令

组合与持仓管理。

```bash
# 查看组合概览
icyquant portfolio show [--portfolio PORTFOLIO_ID]

# 查看持仓
icyquant portfolio positions [--symbol SYMBOL]

# PnL 分析
icyquant portfolio pnl [--from DATE] [--to DATE] [--group-by DIMENSION]

# 净值曲线
icyquant portfolio nav [--from DATE] [--to DATE]

# 风险指标
icyquant portfolio risk-metrics

# 组合优化
icyquant portfolio optimize \
  --objective max_sharpe \
  --constraints constraints.yaml \
  --output optimized_weights.yaml
```

### market 命令

行情数据查询。

```bash
# 获取实时行情
icyquant market quote <symbol>

# 获取 K 线数据
icyquant market candles <symbol> \
  --interval INTERVAL \
  [--limit N] \
  [--from DATE] \
  [--to DATE]

# 订阅实时行情
icyquant market subscribe <symbol> [--interval INTERVAL]

# 查看市场深度
icyquant market depth <symbol> [--limit N]

# 查看资金费率
icyquant market funding <symbol>

# 查看持仓量
icyquant market open-interest <symbol>
```

### deploy 命令

部署与发布管理。

```bash
# 部署策略到生产
icyquant deploy strategy <strategy_id> --environment production

# 列出部署
icyquant deploy list [--environment ENV]

# 查看部署状态
icyquant deploy status <deployment_id>

# 回滚部署
icyquant deploy rollback <deployment_id> [--version VERSION]

# 灰度发布
icyquant deploy canary <strategy_id> --percentage 10

# 蓝绿部署
icyquant deploy blue-green <strategy_id>
```

### config 命令

配置管理。

```bash
# 查看配置
icyquant config show

# 设置配置项
icyquant config set <key> <value>

# 重置配置
icyquant config reset [--key KEY]

# 导入配置
icyquant config import config.yaml

# 导出配置
icyquant config export [--output FILE] [--format FORMAT]

# 配置模板
icyquant config template [--name NAME] [--output FILE]
```

### plugin 命令

插件管理。

```bash
# 列出已安装插件
icyquant plugin list

# 安装插件
icyquant plugin install <plugin_name> [--version VERSION]

# 卸载插件
icyquant plugin uninstall <plugin_name>

# 启用插件
icyquant plugin enable <plugin_name>

# 禁用插件
icyquant plugin disable <plugin_name>

# 创建插件脚手架
icyquant plugin create --name my_plugin --category indicator
```

### pipeline 命令

研究到生产的流水线。

```bash
# 创建研究流水线
icyquant pipeline create --name my_pipeline --template default

# 运行流水线
icyquant pipeline run <pipeline_id>

# 查看流水线状态
icyquant pipeline status <pipeline_id>

# 流水线步骤
icyquant pipeline steps <pipeline_id>

# 审批流水线
icyquant pipeline approve <pipeline_id> --step STEP

# 回退流水线
icyquant pipeline rollback <pipeline_id> --step STEP
```

## 配置文件

### 配置文件位置

默认配置文件路径：`~/.icyquant/config.yaml`

### 配置文件示例

```yaml
# ICYQuant CLI 配置
version: "0.4.0"

# API 连接配置
api:
  endpoint: "https://api.icyquant.io"
  api_key: "${ICYQUANT_API_KEY}"
  timeout: 30
  retry:
    max_attempts: 3
    backoff_factor: 1.0

# 默认交易配置
trading:
  default_capital: 100000
  default_symbol: "BTCUSDT"
  commission_rate: 0.001
  slippage_rate: 0.0005

# 风控配置
risk:
  max_drawdown: 0.20
  max_leverage: 5.0
  position_limit: 0.30
  daily_loss_limit: 0.05

# 通知配置
notifications:
  email:
    enabled: true
    smtp_host: "smtp.icyquant.io"
    smtp_port: 587
    recipient: "ops@icyquant.io"
  slack:
    enabled: false
    webhook_url: "${SLACK_WEBHOOK_URL}"

# 日志配置
logging:
  level: "INFO"
  file: "~/.icyquant/logs/cli.log"
  max_size: "100MB"
  backup_count: 5

# 输出配置
output:
  format: "table"
  color: true
  timestamp: true
```

## 环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `ICYQUANT_API_KEY` | API 密钥 | 否 |
| `ICYQUANT_ENDPOINT` | API 端点覆盖 | 否 |
| `ICYQUANT_PASSWORD` | 密码（避免在命令行暴露） | 否 |
| `ICYQUANT_CONFIG` | 配置文件路径 | 否 |
| `ICYQUANT_LOG_LEVEL` | 日志级别覆盖 | 否 |

## 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 配置错误 |
| 3 | 认证失败 |
| 4 | 网络错误 |
| 5 | 权限不足 |
| 6 | 资源不存在 |
| 7 | 风险限制 |
| 8 | 超时 |

## Shell 补全

ICYQuant CLI 支持 Bash、Zsh、Fish 和 PowerShell 的命令补全。

### Bash

```bash
# 添加到 ~/.bashrc
eval "$(icyquant completion bash)"
```

### Zsh

```bash
# 添加到 ~/.zshrc
eval "$(icyquant completion zsh)"
```

### PowerShell

```powershell
# 添加到 $PROFILE
icyquant completion powershell | Out-String | Invoke-Expression
```

## 故障排除

### 连接超时

```bash
# 增加超时时间
icyquant --timeout 60 status

# 检查网络连接
curl -I https://api.icyquant.io/health
```

### 认证失败

```bash
# 验证 API Key
icyquant auth whoami

# 重新登录
icyquant auth logout
icyquant auth login --api-key NEW_KEY
```

### 配置文件损坏

```bash
# 重置为默认配置
icyquant config reset

# 从模板重新生成
icyquant config template --output ~/.icyquant/config.yaml
```

## License

MIT License. See LICENSE file.