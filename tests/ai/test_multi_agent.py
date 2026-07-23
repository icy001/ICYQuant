from services.ai import TaskScheduler


def test_scheduler():

    scheduler = TaskScheduler()

    scheduler.submit("research")

    assert scheduler.next() == "research"