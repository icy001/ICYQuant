from infrastructure.workflow import *


def test_workflow_dag():

    dag = WorkflowDAG()


    task = Task(

        "risk-check",

        "validate"

    )


    dag.add_task(task)


    assert (

        "risk-check"

        in dag.nodes

    )