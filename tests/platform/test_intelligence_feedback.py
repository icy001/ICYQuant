from services.platform.intelligence import (
    ModelEvolutionManager,
)


def test_model_evolution():

    manager = ModelEvolutionManager()

    version = manager.evolve()

    assert version == 2