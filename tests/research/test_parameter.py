from services.research import (
    ExperimentParameter,
    ParameterGroup,
    ParameterSnapshot,
    ParameterService,
    ParameterComparator,
)


def test_save_parameter_snapshot():
    service = ParameterService()

    snapshot = ParameterSnapshot(
        experiment_id="exp-001",
        version="v1",
        group=ParameterGroup(
            group_name="default",
            parameters=[
                ExperimentParameter(
                    name="window",
                    value="20",
                    parameter_type="int",
                )
            ],
        ),
    )

    service.save(snapshot)

    assert service.load("v1") == snapshot


def test_experiment_parameter():
    param = ExperimentParameter(
        name="window",
        value="20",
        parameter_type="int",
    )

    assert param.name == "window"
    assert param.value == "20"
    assert param.parameter_type == "int"


def test_parameter_group():
    group = ParameterGroup(
        group_name="strategy_params",
        parameters=[
            ExperimentParameter("window", "20", "int"),
            ExperimentParameter("threshold", "0.5", "float"),
        ],
    )

    assert group.group_name == "strategy_params"
    assert len(group.parameters) == 2


def test_parameter_comparator():
    comparator = ParameterComparator()

    snapshot1 = ParameterSnapshot(
        experiment_id="exp-001",
        version="v1",
        group=ParameterGroup(
            group_name="default",
            parameters=[ExperimentParameter("window", "20", "int")],
        ),
    )

    snapshot2 = ParameterSnapshot(
        experiment_id="exp-001",
        version="v2",
        group=ParameterGroup(
            group_name="default",
            parameters=[ExperimentParameter("window", "20", "int")],
        ),
    )

    result = comparator.compare(snapshot1, snapshot2)

    assert result["same"] is True
    assert result["left"] == "v1"
    assert result["right"] == "v2"