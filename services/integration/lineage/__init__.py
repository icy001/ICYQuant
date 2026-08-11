"""Lineage package — Control Lineage & Decision Audit Chain.

Modules are loaded lazily to avoid circular import issues during test
bootstrap.
"""


def __getattr__(name: str):
    """Lazy-load submodules on first access."""
    _imports: dict[str, str] = {
        "LineageError": ".lineage_errors",
        "LineageNodeNotFoundError": ".lineage_errors",
        "LineageEdgeNotFoundError": ".lineage_errors",
        "LineageCycleError": ".lineage_errors",
        "LineageIntegrityError": ".lineage_errors",
        "LineageBrokenLinkError": ".lineage_errors",
        "LineageMissingEventError": ".lineage_errors",
        "LineageInconsistencyError": ".lineage_errors",
        "NodeType": ".lineage_node",
        "LineageNode": ".lineage_node",
        "EdgeType": ".lineage_edge",
        "LineageEdge": ".lineage_edge",
        "LifecycleEventType": ".lineage_event",
        "LineageEvent": ".lineage_event",
        "ParentReference": ".lineage_reference",
        "LineageReferenceChain": ".lineage_reference",
        "DecisionSnapshot": ".lineage_snapshot",
        "LineageGraph": ".lineage_graph",
        "LineageBuilder": ".lineage_builder",
        "LineageResolver": ".lineage_resolver",
        "LineageValidator": ".lineage_validator",
        "LineageQuery": ".lineage_query",
    }
    if name in _imports:
        import importlib

        mod = importlib.import_module(_imports[name], __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
