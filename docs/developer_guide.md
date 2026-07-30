# ICYQuant 开发者指南

> 策略开发、自定义指标、插件扩展与测试

## 目录

- [架构概览](#架构概览)
- [模块开发](#模块开发)
- [策略开发](#策略开发)
- [自定义指标](#自定义指标)
- [回测引擎](#回测引擎)
- [插件开发](#插件开发)
- [测试](#测试)

---

## 架构概览

### 分层架构

ICYQuant 采用六边形/洋葱架构，分为以下层次：

```
┌─────────────────────────────────────────┐
│             Presentation Layer           │
│   REST API / WebSocket / CLI / SDK      │
├─────────────────────────────────────────┤
│             Application Layer            │
│   Orchestrators / Use Cases / DTOs      │
├─────────────────────────────────────────┤
│             Domain Layer                 │
│   Entities / Aggregates / Value Objects │
│   Domain Services / Domain Events       │
├─────────────────────────────────────────┤
│             Infrastructure Layer         │
│   Database / Cache / Message Queue      │
│   External APIs / Third-party Services  │
└─────────────────────────────────────────┘
```

### 核心模块

| 模块 | 路径 | 职责 |
|------|------|------|
| **Research** | `services/research/` | 因子研究、信号生成、Alpha 挖掘 |
| **AI** | `services/ai/` | AI 模型、LLM Agent、智能决策 |
| **Backtest** | `services/backtest/` | 历史回测、参数优化、Walk-Forward |
| **OMS** | `services/oms/` | 订单管理、状态机、生命周期 |
| **EMS/Order** | `services/order/` | 订单执行、算法交易、路由 |
| **Risk** | `services/risk/` | 实时风控、限额管理、压力测试 |
| **Portfolio** | `services/portfolio/` | 组合管理、PnL 计算、净值 |
| **Lakehouse** | `services/data/` | 数据存储、特征库、行情数据 |
| **Observability** | `services/metrics/`, `services/tracing/` | 指标、追踪、日志 |
| **Security** | `services/security/`, `services/auth/` | 认证、授权、加密 |
| **Platform** | `platform/` | 编排器、插件管理、运行时 |

### 开发环境搭建

```bash
# 1. 克隆仓库
git clone https://github.com/icyquant/icyquant.git
cd icyquant

# 2. 创建虚拟环境
python3.12 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -e ".[dev,full]"

# 4. 安装 pre-commit hooks
pre-commit install

# 5. 运行测试套件
pytest tests/ -v

# 6. 启动开发环境
docker compose up -d
alembic upgrade head
uvicorn apps.api.main:app --reload
```

---

## 模块开发

### 新增业务模块

#### 1. 创建模块目录结构

```
services/my_module/
├── __init__.py          # 模块入口
├── models.py            # 领域模型/实体
├── service.py           # 业务服务
├── repository.py        # 数据访问
├── events.py            # 领域事件
├── enums.py             # 枚举类型
├── exceptions.py        # 自定义异常
└── api/
    ├── __init__.py
    └── my_module_api.py # API 端点
```

#### 2. 定义领域模型

```python
# services/my_module/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import uuid

class ModuleStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"

@dataclass
class MyEntity:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    status: ModuleStatus = ModuleStatus.CREATED
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    
    def activate(self):
        self.status = ModuleStatus.ACTIVE
        self.updated_at = datetime.utcnow()
    
    def pause(self):
        self.status = ModuleStatus.PAUSED
        self.updated_at = datetime.utcnow()
```

#### 3. 实现服务层

```python
# services/my_module/service.py
from typing import List, Optional
from .models import MyEntity, ModuleStatus
from .repository import MyEntityRepository
from .events import MyEntityCreatedEvent, MyEntityActivatedEvent

class MyModuleService:
    def __init__(
        self,
        repository: Optional[MyEntityRepository] = None,
        event_bus=None,
    ):
        self.repository = repository or MyEntityRepository()
        self.event_bus = event_bus
    
    def create(self, name: str, metadata: dict = None) -> MyEntity:
        entity = MyEntity(name=name, metadata=metadata or {})
        self.repository.save(entity)
        
        if self.event_bus:
            self.event_bus.publish(
                MyEntityCreatedEvent(
                    entity_id=entity.id,
                    name=entity.name,
                )
            )
        
        return entity
    
    def activate(self, entity_id: str) -> MyEntity:
        entity = self.repository.get(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")
        
        entity.activate()
        self.repository.save(entity)
        
        if self.event_bus:
            self.event_bus.publish(
                MyEntityActivatedEvent(entity_id=entity.id)
            )
        
        return entity
    
    def get(self, entity_id: str) -> Optional[MyEntity]:
        return self.repository.get(entity_id)
    
    def list(self, status: Optional[ModuleStatus] = None) -> List[MyEntity]:
        if status:
            return self.repository.get_by_status(status)
        return self.repository.get_all()
```

#### 4. 创建 API 端点

```python
# services/my_module/api/my_module_api.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/my-module", tags=["my-module"])

class CreateEntityRequest(BaseModel):
    name: str
    metadata: Optional[dict] = None

class EntityResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: str
    
    class Config:
        from_attributes = True

@router.post("", response_model=EntityResponse, status_code=201)
async def create_entity(request: CreateEntityRequest, service=Depends()):
    entity = service.create(name=request.name, metadata=request.metadata)
    return EntityResponse.model_validate(entity)

@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: str, service=Depends()):
    entity = service.get(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return EntityResponse.model_validate(entity)

@router.get("", response_model=List[EntityResponse])
async def list_entities(
    status: Optional[str] = None,
    service=Depends(),
):
    entities = service.list(status=status)
    return [EntityResponse.model_validate(e) for e in entities]
```

---

## 策略开发

### Strategy 接口

所有交易策略必须继承 `Strategy` 基类并实现核心方法。

#### 基础策略模板

```python
from icyquant_sdk.strategy import Strategy, Bar, Order, Position
from icyquant_sdk.enums import OrderSide, OrderType

class MyStrategy(Strategy):
    """自定义交易策略基类"""
    
    def __init__(self):
        super().__init__()
        self.config = StrategyConfig(
            name="my_strategy",
            symbol="BTCUSDT",
            timeframe="1h",
            capital=100000,
        )
    
    async def on_bar(self, bar: Bar):
        """
        每根 K 线触发的核心方法。
        
        Args:
            bar: 最新的 K 线数据
            
        必须实现，用于定义交易逻辑。
        """
        pass
    
    async def on_start(self):
        """
        策略启动时调用。
        用于初始化状态、加载历史数据等。
        """
        pass
    
    async def on_stop(self):
        """
        策略停止时调用。
        用于清理资源、保存状态等。
        """
        pass
    
    async def on_tick(self, tick):
        """
        每个 tick 触发（高频策略使用）。
        可选实现。
        """
        pass
    
    async def on_fill(self, order: Order):
        """
        订单成交回调。
        可选实现，用于更新持仓状态。
        """
        pass
    
    async def on_risk_alert(self, alert):
        """
        风险告警回调。
        可选实现，用于响应风控事件。
        """
        pass
```

### 策略示例：双均线交叉策略

```python
from icyquant_sdk.strategy import Strategy, Bar
from icyquant_sdk.indicators import SMA
from icyquant_sdk.enums import OrderSide

class DualMAStrategy(Strategy):
    """
    双均线交叉策略
    
    规则:
    - 快线上穿慢线 → 买入
    - 快线下穿慢线 → 卖出
    """
    
    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 30,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.05,
    ):
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.position_qty = 0
    
    async def on_start(self):
        """初始化指标"""
        self.fast_ma = SMA(period=self.fast_period)
        self.slow_ma = SMA(period=self.slow_period)
        self.last_fast = None
        self.last_slow = None
    
    async def on_bar(self, bar: Bar):
        """K 线触发"""
        closes = await self.data.get_closes(
            symbol=bar.symbol,
            limit=self.slow_period + 1
        )
        
        if len(closes) < self.slow_period + 1:
            return
        
        current_fast = sum(closes[-self.fast_period:]) / self.fast_period
        current_slow = sum(closes[-self.slow_period:]) / self.slow_period
        
        # 金叉：快线上穿慢线
        if (self.last_fast is not None and 
            self.last_slow is not None and
            self.last_fast <= self.last_slow and 
            current_fast > current_slow):
            
            if self.position_qty == 0:
                qty = self.config.capital * 0.1 / bar.close
                order = await self.order.market(
                    symbol=bar.symbol,
                    side=OrderSide.BUY,
                    quantity=qty,
                )
                self.position_qty = qty
        
        # 死叉：快线下穿慢线
        elif (self.last_fast is not None and 
              self.last_slow is not None and
              self.last_fast >= self.last_slow and 
              current_fast < current_slow):
            
            if self.position_qty > 0:
                await self.order.market(
                    symbol=bar.symbol,
                    side=OrderSide.SELL,
                    quantity=self.position_qty,
                )
                self.position_qty = 0
        
        # 止损止盈
        if self.position_qty > 0:
            entry_price = self._get_entry_price(bar.symbol)
            if entry_price:
                pnl_pct = (bar.close - entry_price) / entry_price
                if pnl_pct <= -self.stop_loss_pct:
                    await self.order.market(
                        symbol=bar.symbol,
                        side=OrderSide.SELL,
                        quantity=self.position_qty,
                    )
                    self.position_qty = 0
                elif pnl_pct >= self.take_profit_pct:
                    await self.order.market(
                        symbol=bar.symbol,
                        side=OrderSide.SELL,
                        quantity=self.position_qty,
                    )
                    self.position_qty = 0
        
        self.last_fast = current_fast
        self.last_slow = current_slow
    
    def _get_entry_price(self, symbol: str) -> float:
        positions = await self.portfolio.positions(symbol=symbol)
        if positions:
            return positions[0].avg_price
        return 0
```

### 策略配置

```python
from icyquant_sdk.strategy import StrategyConfig

config = StrategyConfig(
    name="dual_ma_strategy",
    symbol="BTCUSDT",
    timeframe="1h",
    capital=100000,
    # 可选配置
    max_positions=1,
    risk_per_trade=0.02,
    commission_rate=0.001,
    slippage_rate=0.0005,
    # 风控参数
    stop_loss=0.02,
    take_profit=0.05,
    trailing_stop=0.01,
    # 执行参数
    order_type="MARKET",
    time_in_force="GTC",
    max_order_quantity=1.0,
)
```

### 策略生命周期

```
CREATED ──► INITIALIZING ──► RUNNING ──► PAUSED ──► RUNNING
                                    │          │
                                    ▼          │
                                 STOPPED ◄─────┘
                                    │
                                    ▼
                                 ARCHIVED
```

| 阶段 | 说明 | 可执行操作 |
|------|------|------------|
| CREATED | 策略已创建但未初始化 | 启动、删除 |
| INITIALIZING | 正在加载历史数据和依赖 | 等待、取消 |
| RUNNING | 策略正在运行，接收行情 | 暂停、停止 |
| PAUSED | 策略已暂停，不接收行情 | 恢复、停止 |
| STOPPED | 策略已停止 | 启动（新实例）、归档 |
| ARCHIVED | 策略已归档 | 无法恢复 |

---

## 自定义指标

### 指标接口

所有自定义指标必须继承 `Indicator` 基类。

#### 自定义指标模板

```python
from icyquant_sdk.indicators import Indicator, IndicatorResult
from typing import List, Optional

class CustomIndicator(Indicator):
    """
    自定义指标基类
    
    实现自定义需要:
    1. 继承 Indicator 类
    2. 实现 calculate 方法
    3. 定义指标元数据
    """
    
    def __init__(self, period: int = 14):
        super().__init__()
        self.period = period
    
    def calculate(self, data: List[float]) -> IndicatorResult:
        """
        计算指标值
        
        Args:
            data: 输入数据数组（通常是收盘价）
            
        Returns:
            IndicatorResult: 指标计算结果
        """
        if len(data) < self.period:
            return IndicatorResult(
                value=None,
                ready=False,
                metadata={"reason": f"Need {self.period} data points"}
            )
        
        values = data[-self.period:]
        
        result = sum(values) / self.period
        
        return IndicatorResult(
            value=result,
            ready=True,
            metadata={
                "period": self.period,
                "current": result,
            }
        )
```

#### 常用指标示例

```python
# RSI 指标
class RSI(Indicator):
    """相对强弱指标"""
    
    def __init__(self, period: int = 14):
        super().__init__()
        self.period = period
    
    def calculate(self, closes: List[float]) -> IndicatorResult:
        if len(closes) < self.period + 1:
            return IndicatorResult(value=None, ready=False)
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-self.period:]) / self.period
        avg_loss = sum(losses[-self.period:]) / self.period
        
        if avg_loss == 0:
            return IndicatorResult(value=100.0, ready=True)
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return IndicatorResult(
            value=rsi,
            ready=True,
            metadata={
                "overbought": rsi > 70,
                "oversold": rsi < 30,
            }
        )

# MACD 指标
class MACD(Indicator):
    """MACD 指标"""
    
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ):
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
    
    def calculate(self, closes: List[float]) -> IndicatorResult:
        if len(closes) < self.slow_period + self.signal_period:
            return IndicatorResult(value=None, ready=False)
        
        ema_fast = self._ema(closes, self.fast_period)
        ema_slow = self._ema(closes, self.slow_period)
        
        dif = ema_fast - ema_slow
        macd_line = self._ema([dif], self.signal_period)
        histogram = dif - macd_line
        
        return IndicatorResult(
            value=macd_line,
            ready=True,
            metadata={
                "dif": dif,
                "macd": macd_line,
                "histogram": histogram,
                "bullish_cross": dif > macd_line,
                "bearish_cross": dif < macd_line,
            }
        )
    
    def _ema(self, data: List[float], period: int) -> float:
        if not data:
            return 0.0
        multiplier = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = (price - ema) * multiplier + ema
        return ema
```

---

## 回测引擎

### 运行回测

```python
from icyquant_sdk.backtest import Backtester, BacktestConfig

# 配置回测
config = BacktestConfig(
    symbol="BTCUSDT",
    start="2023-01-01",
    end="2024-12-31",
    capital=100000,
    commission=0.001,
    slippage=0.0005,
    timeframe="1h",
    # 可选
    benchmark="BTCUSDT",
    risk_free_rate=0.03,
)

# 创建回测器
backtester = Backtester(config)

# 加载策略
strategy = MyStrategy(fast_period=10, slow_period=30)

# 运行回测
result = await backtester.run(strategy)

# 查看结果
print(f"总收益率: {result.total_return:.2%}")
print(f"年化收益率: {result.annual_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2%}")
print(f"胜率: {result.win_rate:.2%}")
```

### 回测结果指标

| 指标 | 说明 | 计算公式 |
|------|------|----------|
| Total Return | 总收益率 | (期末价值 - 初始资金) / 初始资金 |
| Annual Return | 年化收益率 | (1 + Total Return)^(252/天数) - 1 |
| Sharpe Ratio | 夏普比率 | (Rp - Rf) / σp |
| Sortino Ratio | 索提诺比率 | (Rp - Rf) / σd |
| Max Drawdown | 最大回撤 | max((peak - trough) / peak) |
| Win Rate | 胜率 | 盈利交易数 / 总交易数 |
| Profit Factor | 盈亏比 | 总盈利 / 总亏损 |
| Calmar Ratio | 卡玛比率 | Annual Return / Max Drawdown |
| Volatility | 波动率 | 日收益率标准差 × √252 |
| Trade Count | 交易次数 | 买卖交易总次数 |

### 高级回测功能

#### Walk-Forward 分析

```python
from icyquant_sdk.backtest import WalkForward

wf = WalkForward(
    train_period=180,      # 训练窗口 180 天
    test_period=60,        # 测试窗口 60 天
    step=30,               # 滚动步长 30 天
    metric="sharpe_ratio", # 优化目标
)

results = await wf.run(strategy, symbol="BTCUSDT")

for i, result in enumerate(results):
    print(f"窗口 {i+1}: Sharpe={result.sharpe_ratio:.2f}, Return={result.total_return:.2%}")
```

#### 参数优化

```python
from icyquant_sdk.backtest import ParameterOptimizer

optimizer = ParameterOptimizer(
    param_grid={
        "fast_period": [5, 10, 20, 50],
        "slow_period": [20, 50, 100, 200],
        "stop_loss": [0.01, 0.02, 0.03, 0.05],
    },
    metric="sharpe_ratio",
    max_combinations=50,
)

best_params, best_result = await optimizer.optimize(strategy, config)

print(f"最优参数: {best_params}")
print(f"最优 Sharpe: {best_result.sharpe_ratio:.2f}")
```

#### 蒙特卡洛模拟

```python
from icyquant_sdk.backtest import MonteCarlo

mc = MonteCarlo(
    simulations=1000,
    confidence_level=0.95,
)

simulation_results = await mc.simulate(result)

print(f"95% 置信区间: [{simulation_results.ci_lower:.2%}, {simulation_results.ci_upper:.2%}]")
print(f"破产概率: {simulation_results.ruin_probability:.2%}")
```

---

## 插件开发

### 插件接口

所有插件必须继承 `PluginBase` 类。

#### 插件类别

| 类别 | 说明 | 标识符 |
|------|------|--------|
| Broker | 交易所适配器 | `broker` |
| Indicator | 自定义指标 | `indicator` |
| Strategy | 交易策略 | `strategy` |
| AI Model | AI 模型 | `ai_model` |
| Risk Rule | 风控规则 | `risk_rule` |
| Data Source | 数据源 | `data_source` |
| Report | 报告生成 | `report` |

#### Broker 插件示例

```python
from icyquant_sdk.plugins import PluginBase, PluginMetadata, PluginCategory
from icyquant_sdk.broker import BrokerInterface

class CustomBrokerPlugin(PluginBase):
    """自定义交易所适配器"""
    
    def __init__(self):
        super().__init__()
        self._broker = None
    
    def initialize(self, config: dict) -> bool:
        """初始化连接"""
        try:
            self._config = config
            # 建立交易所连接
            self._broker = CustomBroker(
                api_key=config["api_key"],
                api_secret=config["api_secret"],
                base_url=config.get("base_url"),
            )
            self._initialized = True
            return True
        except Exception as e:
            self._error = str(e)
            return False
    
    def start(self) -> bool:
        """启动插件"""
        if not self._initialized:
            return False
        
        try:
            # 开始接收行情
            self._broker.start_market_data()
            self._running = True
            return True
        except Exception as e:
            self._error = str(e)
            return False
    
    def stop(self) -> bool:
        """停止插件"""
        try:
            self._broker.stop_market_data()
            self._running = False
            return True
        except Exception as e:
            self._error = str(e)
            return False
    
    def health_check(self) -> bool:
        """健康检查"""
        if not self._running:
            return False
        return self._broker.ping()
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="custom_broker",
            version="1.0.0",
            category=PluginCategory.BROKER,
            author="Your Name",
            description="Custom exchange broker adapter",
        )
    
    # 自定义方法
    async def place_order(self, order: dict) -> dict:
        return await self._broker.place_order(order)
    
    async def get_balance(self) -> dict:
        return await self._broker.get_balance()
```

#### 指标插件示例

```python
class CustomIndicatorPlugin(PluginBase):
    """自定义指标插件"""
    
    def __init__(self):
        super().__init__()
        self._indicator = None
    
    def initialize(self, config: dict) -> bool:
        self._indicator = MyCustomIndicator(
            period=config.get("period", 14)
        )
        return True
    
    def start(self) -> bool:
        return True
    
    def stop(self) -> bool:
        return True
    
    def health_check(self) -> bool:
        return self._indicator is not None
    
    def calculate(self, data: list) -> float:
        result = self._indicator.calculate(data)
        return result.value
```

#### 插件注册

```python
# 方式一：自动发现
plugin_manager = PluginManager()
plugin_manager.scan_plugins("./plugins/")

# 方式二：手动注册
plugin_manager.register(MyBrokerPlugin())
plugin_manager.register(MyIndicatorPlugin())

# 方式三：通过 pip 包安装
plugin_manager.install("icyquant-broker-binance")
```

---

## 测试

### 测试框架

ICYQuant 使用 `pytest` 作为测试框架。

#### 测试目录结构

```
tests/
├── conftest.py              # 全局 fixtures
├── test_strategy.py         # 策略测试
├── test_indicators.py       # 指标测试
├── test_backtest.py         # 回测测试
├── test_risk.py             # 风控测试
├── test_orders.py           # 订单测试
├── integration/             # 集成测试
│   ├── test_full_trade_flow.py
│   └── test_risk_lifecycle.py
└── e2e/                     # 端到端测试
    └── test_strategy_lifecycle.py
```

### 单元测试

```python
# tests/test_indicators.py
import pytest
from icyquant_sdk.indicators import SMA

class TestSMA:
    def test_sma_calculation(self):
        """测试 SMA 计算正确性"""
        sma = SMA(period=3)
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        result = sma.calculate(data)
        
        assert result.ready is True
        assert result.value == 4.0  # (3+4+5)/3
    
    def test_sma_insufficient_data(self):
        """测试数据不足情况"""
        sma = SMA(period=10)
        data = [1.0, 2.0]
        
        result = sma.calculate(data)
        
        assert result.ready is False
        assert result.value is None
    
    def test_sma_single_value(self):
        """测试单值情况"""
        sma = SMA(period=1)
        data = [42.0]
        
        result = sma.calculate(data)
        
        assert result.ready is True
        assert result.value == 42.0
```

### 策略测试

```python
# tests/test_strategy.py
import pytest
from unittest.mock import AsyncMock, patch
from icyquant_sdk.strategy import Bar
from my_strategy import DualMAStrategy

@pytest.fixture
def strategy():
    return DualMAStrategy(fast_period=3, slow_period=5)

@pytest.fixture
def mock_data_provider():
    provider = AsyncMock()
    provider.get_closes = AsyncMock(return_value=[
        100.0, 102.0, 104.0, 106.0, 108.0,
        110.0, 112.0, 114.0, 116.0, 118.0,
    ])
    return provider

@pytest.mark.asyncio
async def test_strategy_start(strategy, mock_data_provider):
    """测试策略启动"""
    strategy.data = mock_data_provider
    
    await strategy.on_start()
    
    assert strategy.fast_ma is not None
    assert strategy.slow_ma is not None

@pytest.mark.asyncio
async def test_golden_cross_buy(strategy, mock_data_provider):
    """测试金叉买入信号"""
    strategy.data = mock_data_provider
    strategy.order = AsyncMock()
    strategy.order.market = AsyncMock(return_value={"id": "order-1"})
    
    await strategy.on_start()
    
    bar = Bar(
        symbol="BTCUSDT",
        open=110.0,
        high=112.0,
        low=108.0,
        close=111.0,
        volume=1000,
        timestamp="2024-01-01T00:00:00Z",
    )
    
    await strategy.on_bar(bar)
    
    assert strategy.order.market.called

@pytest.mark.asyncio
async def test_death_cross_sell(strategy, mock_data_provider):
    """测试死叉卖出信号"""
    pass
```

### 回测测试

```python
# tests/test_backtest.py
import pytest
from icyquant_sdk.backtest import Backtester, BacktestConfig

@pytest.fixture
def config():
    return BacktestConfig(
        symbol="TEST",
        start="2024-01-01",
        end="2024-01-31",
        capital=100000,
        commission=0.001,
    )

@pytest.mark.asyncio
async def test_backtest_runs(config, strategy):
    """测试回测正常运行"""
    backtester = Backtester(config)
    result = await backtester.run(strategy)
    
    assert result is not None
    assert result.total_return is not None
    assert result.sharpe_ratio is not None
    assert result.max_drawdown <= 0

@pytest.mark.asyncio
async def test_backtest_result_consistency(config, strategy):
    """测试回测结果一致性"""
    backtester = Backtester(config)
    
    result1 = await backtester.run(strategy)
    result2 = await backtester.run(strategy)
    
    assert result1.total_return == result2.total_return
    assert result1.sharpe_ratio == result2.sharpe_ratio
```

### 运行测试

```bash
# 运行全部测试
pytest tests/ -v

# 运行特定模块测试
pytest tests/risk/ -v

# 运行测试并查看覆盖率
pytest tests/ --cov=. --cov-report=term-missing

# 生成覆盖率报告
pytest tests/ --cov=. --cov-report=html --cov-report=xml

# 运行集成测试
pytest tests/integration/ -v

# 运行端到端测试
pytest tests/e2e/ -v

# 运行特定标记的测试
pytest tests/ -m "slow" -v
pytest tests/ -m "integration" -v
```

### 测试覆盖率要求

| 模块 | 最低覆盖率 | 目标覆盖率 |
|------|------------|------------|
| Research | 80% | 95% |
| AI | 75% | 90% |
| Backtest | 85% | 95% |
| OMS | 90% | 98% |
| EMS/Order | 90% | 98% |
| Risk | 90% | 98% |
| Portfolio | 85% | 95% |
| Security | 90% | 98% |
| Platform | 80% | 90% |

---

**文档版本**: 1.0
**创建日期**: 2026-07-30
**适用版本**: ICYQuant v0.4.0 GA