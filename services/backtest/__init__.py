from .event import MarketEvent, SignalEvent
from .replay import MarketReplay
from .dispatcher import EventDispatcher
from .portfolio import Portfolio
from .execution import ExecutionSimulator
from .cost import TransactionCost
from .slippage import SlippageModel
from .result import BacktestResult
from .service import BacktestService

# -- auto-restored exports (test-collection repair) --
from services.backtest.alpha import AlphaCalculator
from services.backtest.engine import BacktestEngine
from services.backtest.experiment import BacktestExperiment
from services.backtest.session import BacktestSession
from services.backtest.backtest_snapshot import BacktestSnapshot
from services.backtest.benchmark import BenchmarkComparator
from services.backtest.bootstrap_sampler import BootstrapSampler
from services.backtest.commission import CommissionCalculator
from services.backtest.dependency_validator import DependencyValidator
from services.backtest.distributed_task import DistributedTask
from services.backtest.equity import EquityCalculator
from services.backtest.matching import MatchingEngine
from services.backtest.optimizer import ParameterOptimizer
from services.backtest.pipeline_stage import PipelineStage
from services.backtest.position_limit import PositionLimitChecker
from services.backtest.replay_tick import ReplayTick
from services.backtest.splitter import RollingWindowSplitter
from services.backtest.strategy_registry import StrategyRegistry
from services.backtest.strategy_runner import StrategyRunner
from services.backtest.trade_record import TradeRecord
from services.backtest.virtual_oms import VirtualOMS
