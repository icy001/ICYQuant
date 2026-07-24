from infrastructure.scheduler import *


def test_scheduler():

    scheduler = Scheduler()

    job = Job(

        "daily-factor",

        "factor_compute"

    )


    scheduler.submit(job)


    assert len(

        scheduler.pending()

    ) == 1