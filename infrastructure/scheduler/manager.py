class SchedulerManager:


    def __init__(

        self,

        scheduler,

        registry,

    ):

        self.scheduler = scheduler

        self.registry = registry



    def schedule(

        self,

        job,

    ):

        self.registry.register(job)

        self.scheduler.submit(job)