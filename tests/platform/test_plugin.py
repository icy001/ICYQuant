"""
Tests for ICYQuant Platform Plugins and SDKs.
"""

import pytest

from platform.plugin_manager import PluginManager, PluginType, PluginInfo
from platform.sdk.strategy_sdk import StrategySDK, StrategyPlugin, StrategyType, SignalAction, StrategySignal
from platform.sdk.data_sdk import DataSDK, DataProviderPlugin, DataProviderType, DataSnapshot
from platform.sdk.broker_sdk import BrokerSDK, BrokerAdapterPlugin, OrderSide, BrokerOrder
from platform.sdk.ai_sdk import AISDK, AIModelPlugin, AIModelType, AIModelPrediction
from platform.sdk import PluginBase, PluginMetadata, PluginCategory


class MockStrategy(StrategyPlugin):
    def __init__(self):
        super().__init__(StrategyType.CUSTOM)

    def on_bar(self, symbol, bar):
        return StrategySignal(symbol=symbol, action=SignalAction.BUY, confidence=0.8)

    def on_tick(self, symbol, tick):
        return None

    def on_order_fill(self, order):
        pass


class MockDataProvider(DataProviderPlugin):
    def __init__(self):
        super().__init__(DataProviderType.MARKET)

    def fetch(self, symbols, fields, start, end):
        return DataSnapshot(provider="mock", data_type="market", symbols=symbols)

    def get_latest(self, symbol, fields):
        return DataSnapshot(provider="mock", data_type="market", symbols=[symbol])


class MockBroker(BrokerAdapterPlugin):
    def __init__(self):
        super().__init__("TestBroker")

    def submit_order(self, order):
        order.status = order.status.SUBMITTED
        self._orders[order.order_id] = order
        return order.order_id

    def cancel_order(self, order_id):
        return order_id in self._orders

    def get_positions(self):
        return list(self._positions.values())

    def get_balance(self):
        return 100000.0


class MockAIModel(AIModelPlugin):
    def __init__(self):
        super().__init__(AIModelType.CLASSIFIER)

    def train(self, data, labels=None):
        self._state.is_trained = True
        self._state.accuracy = 0.95
        return 0.95

    def predict(self, data):
        return AIModelPrediction(
            model_name=self.__class__.__name__,
            model_version="1.0.0",
            input_data=data,
            prediction="bullish",
            confidence=0.85,
        )

    def evaluate(self, data, labels):
        return {"accuracy": 0.95}


class TestPluginManager:
    """Test plugin registration and lifecycle."""

    def test_register_plugin(self):
        pm = PluginManager()
        info = pm.register_plugin(
            "TestPlugin", PluginType.STRATEGY,
            version="1.0.0", description="Test",
        )
        assert info.name == "TestPlugin"
        assert info.plugin_type == PluginType.STRATEGY

    def test_register_duplicate(self):
        pm = PluginManager()
        pm.register_plugin("Test", PluginType.STRATEGY)
        with pytest.raises(ValueError):
            pm.register_plugin("Test", PluginType.STRATEGY)

    def test_load_plugin(self):
        pm = PluginManager()
        pm.register_plugin("Test", PluginType.STRATEGY)
        assert pm.load_plugin("Test") is True
        info = pm.get_plugin("Test")
        assert info.state == pm._plugins["Test"].state.LOADED

    def test_start_stop_plugin(self):
        pm = PluginManager()
        pm.register_plugin("Test", PluginType.STRATEGY)
        pm.load_plugin("Test")
        assert pm.start_plugin("Test") is True
        assert pm.stop_plugin("Test") is True

    def test_reload_plugin(self):
        pm = PluginManager()
        pm.register_plugin("Test", PluginType.STRATEGY)
        pm.load_plugin("Test")
        assert pm.reload_plugin("Test") is True

    def test_get_by_type(self):
        pm = PluginManager()
        pm.register_plugin("p1", PluginType.STRATEGY)
        pm.register_plugin("p2", PluginType.STRATEGY)
        pm.register_plugin("p3", PluginType.BROKER)
        strategies = pm.get_by_type(PluginType.STRATEGY)
        assert len(strategies) == 2

    def test_list_names(self):
        pm = PluginManager()
        pm.register_plugin("a", PluginType.STRATEGY)
        pm.register_plugin("b", PluginType.BROKER)
        names = pm.list_names()
        assert "a" in names
        assert "b" in names

    def test_status(self):
        pm = PluginManager()
        pm.register_plugin("test", PluginType.STRATEGY)
        status = pm.get_status()
        assert status["total"] == 1


class TestStrategySDK:
    """Test strategy SDK functionality."""

    def test_register_strategy(self):
        sdk = StrategySDK()
        strategy = MockStrategy()
        name = sdk.register(strategy)
        assert name == "MockStrategy"

    def test_get_strategy(self):
        sdk = StrategySDK()
        strategy = MockStrategy()
        sdk.register(strategy)
        retrieved = sdk.get_strategy("MockStrategy")
        assert retrieved is strategy

    def test_list_strategies(self):
        sdk = StrategySDK()
        sdk.register(MockStrategy())
        names = sdk.list_strategies()
        assert "MockStrategy" in names

    def test_generate_signal(self):
        sdk = StrategySDK()
        signal = sdk.generate_signal("Test", "AAPL", SignalAction.BUY, 100, 0.8)
        assert signal.symbol == "AAPL"
        assert signal.action == SignalAction.BUY
        assert signal.quantity == 100

    def test_recent_signals(self):
        sdk = StrategySDK()
        sdk.generate_signal("Test", "AAPL", SignalAction.BUY)
        sdk.generate_signal("Test", "GOOG", SignalAction.SELL)
        signals = sdk.get_recent_signals()
        assert len(signals) == 2

    def test_strategy_plugin_lifecycle(self):
        strategy = MockStrategy()
        assert strategy.initialize({"active": True}) is True
        assert strategy.start() is True
        assert strategy.is_running() is True
        assert strategy.stop() is True
        assert strategy.is_healthy() if hasattr(strategy, 'health_check') else True


class TestDataSDK:
    """Test data SDK functionality."""

    def test_register_provider(self):
        sdk = DataSDK()
        provider = MockDataProvider()
        name = sdk.register(provider)
        assert name == "MockDataProvider"

    def test_fetch_data(self):
        sdk = DataSDK()
        provider = MockDataProvider()
        sdk.register(provider)
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=1)
        snapshot = sdk.fetch("MockDataProvider", ["AAPL"], ["price"], start, end)
        assert snapshot is not None
        assert snapshot.provider == "mock"

    def test_list_providers(self):
        sdk = DataSDK()
        sdk.register(MockDataProvider())
        names = sdk.list_providers()
        assert len(names) == 1


class TestBrokerSDK:
    """Test broker SDK functionality."""

    def test_register_broker(self):
        sdk = BrokerSDK()
        broker = MockBroker()
        name = sdk.register(broker)
        assert name == "MockBroker"

    def test_submit_order(self):
        sdk = BrokerSDK()
        broker = MockBroker()
        sdk.register(broker)
        order_id = sdk.submit_order("MockBroker", "AAPL", OrderSide.BUY, 100)
        assert order_id is not None

    def test_list_brokers(self):
        sdk = BrokerSDK()
        sdk.register(MockBroker())
        names = sdk.list_brokers()
        assert len(names) == 1


class TestAISDK:
    """Test AI SDK functionality."""

    def test_register_model(self):
        sdk = AISDK()
        model = MockAIModel()
        name = sdk.register(model)
        assert name == "MockAIModel"

    def test_train_model(self):
        sdk = AISDK()
        model = MockAIModel()
        sdk.register(model)
        accuracy = sdk.train_model("MockAIModel", {"data": [1, 2, 3]})
        assert accuracy == 0.95

    def test_predict(self):
        sdk = AISDK()
        model = MockAIModel()
        sdk.register(model)
        prediction = sdk.predict("MockAIModel", {"data": [1, 2, 3]})
        assert prediction is not None
        assert prediction.prediction == "bullish"

    def test_list_models(self):
        sdk = AISDK()
        sdk.register(MockAIModel())
        names = sdk.list_models()
        assert len(names) == 1


class TestPluginBase:
    """Test plugin base class."""

    def test_plugin_metadata(self):
        meta = PluginMetadata(
            name="TestPlugin",
            version="1.0.0",
            category=PluginCategory.STRATEGY,
        )
        assert meta.name == "TestPlugin"
        data = meta.to_dict()
        assert data["name"] == "TestPlugin"

    def test_plugin_base_abstract(self):
        with pytest.raises(TypeError):
            PluginBase()
