class RuntimeManager:


    def __init__(

        self,

        container,

    ):

        self.container = container



    def start_service(

        self,

        service,

    ):

        service.status = "RUNNING"



    def stop_service(

        self,

        service,

    ):

        service.status = "STOPPED"