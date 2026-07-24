from production_platform.dependency import *


class Database:


    pass



def test_dependency():

    container = DependencyContainer()


    container.register(

        "database",

        Provider(Database)

    )


    db = container.resolve(

        "database"

    )


    assert isinstance(

        db,

        Database

    )