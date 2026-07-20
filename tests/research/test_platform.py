from services.research import (
    ResearchContainer,
    ResearchPlatform,
    ResearchBootstrap,
    ResearchServiceRegistry,
    ResearchInitializer,
    ResearchHealthCheck,
)


def test_platform_start():
    container = ResearchContainer()

    platform = ResearchPlatform(container)

    assert platform.start() is True


def test_research_container():
    container = ResearchContainer()

    container.register("service1", {"key": "value"})

    result = container.resolve("service1")

    assert result == {"key": "value"}


def test_research_bootstrap():
    bootstrap = ResearchBootstrap()

    container = ResearchContainer()

    result = bootstrap.initialize(container)

    assert result == container


def test_research_service_registry():
    registry = ResearchServiceRegistry()

    registry.add("module1")

    assert len(registry._modules) == 1


def test_research_initializer():
    initializer = ResearchInitializer()

    registry = ResearchServiceRegistry()

    result = initializer.initialize(registry)

    assert result == registry


def test_health_check():
    health = ResearchHealthCheck()

    result = health.check()

    assert result["status"] == "UP"