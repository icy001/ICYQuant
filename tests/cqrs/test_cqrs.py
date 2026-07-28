from services.cqrs import *


def test_cqrs():
    service = CQRSService()

    command = Command(
        "CMD001",
        "CREATE_ORDER",
        {
            "symbol": "NVDA"
        }
    )

    result = service.execute_command(command)

    assert result["status"] == "ACCEPTED"


    query = Query(
        "Q001",
        "POSITION",
        {}
    )

    result2 = service.execute_query(query)

    assert result2["query"] == "Q001"
