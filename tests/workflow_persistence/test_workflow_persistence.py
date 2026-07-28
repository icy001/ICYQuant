from services.workflow_persistence import *


def test_snapshot():

    repo = WorkflowRepository()

    service = WorkflowPersistenceService(repo)

    snapshot = WorkflowSnapshot(
        "WF001",
        "CHECKPOINT_1",
        {"step": 3}
    )

    service.save_snapshot(snapshot)

    loaded = service.load_snapshot("WF001")

    assert loaded.payload["step"] == 3
