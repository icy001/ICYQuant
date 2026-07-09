from services.reconciliation.replay_engine import ReplayEngine


def test_event_replay():
    events = [
        {
            "type": "BUY",
            "quantity": 100,
        },
        {
            "type": "SELL",
            "quantity": 30,
        },
    ]

    result = ReplayEngine().replay(events)

    assert result == 70


def test_event_replay_multiple_trades():
    events = [
        {"type": "BUY", "quantity": 50},
        {"type": "BUY", "quantity": 30},
        {"type": "SELL", "quantity": 20},
        {"type": "BUY", "quantity": 100},
        {"type": "SELL", "quantity": 50},
    ]

    result = ReplayEngine().replay(events)

    assert result == 110


def test_event_replay_empty():
    events = []

    result = ReplayEngine().replay(events)

    assert result == 0
