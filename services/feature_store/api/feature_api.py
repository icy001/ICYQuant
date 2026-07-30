"""Feature Store REST API.

Endpoints:
    POST   /api/v1/features/register       - Register a new feature
    GET    /api/v1/features/{name}         - Get feature definition
    GET    /api/v1/features/{name}/versions - List versions
    POST   /api/v1/features/{name}/publish  - Publish a version
    GET    /api/v1/features/online/{symbol} - Get online features
    POST   /api/v1/features/online/{symbol} - Set online features
    POST   /api/v1/features/validate        - Validate feature data
    POST   /api/v1/features/drift/check     - Check feature drift
    GET    /api/v1/features/drift/status/{name} - Get drift status
    GET    /api/v1/features/lineage/{name}  - Get feature lineage
    POST   /api/v1/features/lineage/node    - Add lineage node
    POST   /api/v1/features/lineage/edge    - Add lineage edge
    POST   /api/v1/features/offline/write   - Write offline data
    POST   /api/v1/features/offline/read    - Read offline data
    GET    /api/v1/features/stats           - Feature store statistics
    GET    /api/v1/features/categories      - List categories
    POST   /api/v1/features/categories      - Create category
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from services.feature_store.feature_service import FeatureService
from services.feature_store.registry import FeatureStatus
from services.feature_store.lineage import NodeType
from services.feature_store.versioning import VersionStage
from services.feature_store.monitor import DriftStatus
from services.feature_store.offline_store import PartitionUnit
from services.feature_store.online_store import StoreTTL

router = APIRouter(prefix="/api/v1/features", tags=["Feature Store"])

_feature_service = FeatureService()


# ---- Feature Registry ----

@router.post("/register")
async def register_feature(
    feature_name: str = Query(..., description="Feature identifier"),
    version: str = Query("v1", description="Version string"),
    owner: str = Query("research", description="Owner team"),
    dtype: str = Query("float64", description="Data type"),
    frequency: str = Query("1d", description="Data frequency"),
    description: str = Query("", description="Description"),
    category: Optional[str] = Query(None, description="Category name"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    source: str = Query("", description="Data source"),
) -> Dict[str, Any]:
    """Register a new feature.

    Request example::

        POST /api/v1/features/register?feature_name=ema20&version=v1&owner=research
    """
    tag_list = tags.split(",") if tags else []
    definition = _feature_service.register_feature(
        feature_name=feature_name,
        version=version,
        owner=owner,
        dtype=dtype,
        frequency=frequency,
        description=description,
        category=category,
        tags=tag_list,
        source=source,
    )
    return {
        "feature_name": definition.feature_name,
        "version": definition.version,
        "status": definition.status.value,
        "owner": definition.owner,
        "dtype": definition.dtype,
        "frequency": definition.frequency,
        "registered_at": definition.registered_at,
    }


@router.get("/{name}")
async def get_feature(
    name: str,
    version: Optional[str] = Query(None, description="Specific version"),
) -> Dict[str, Any]:
    """Get feature definition.

    Example response::

        {"feature": "ema20", "latest": "v3", "owner": "research"}
    """
    try:
        definition = _feature_service.registry.get(name, version)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "feature_name": definition.feature_name,
        "version": definition.version,
        "status": definition.status.value,
        "owner": definition.owner,
        "dtype": definition.dtype,
        "frequency": definition.frequency,
        "description": definition.description,
        "category": definition.category,
        "tags": definition.tags,
        "source": definition.source,
        "registered_at": definition.registered_at,
        "updated_at": definition.updated_at,
    }


@router.get("/{name}/versions")
async def list_versions(name: str) -> Dict[str, Any]:
    """List all versions of a feature."""
    try:
        versions = _feature_service.registry.list_versions(name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "feature_name": name,
        "versions": [
            {
                "version": v.version,
                "status": v.status.value,
                "owner": v.owner,
                "registered_at": v.registered_at,
            }
            for v in versions
        ],
    }


# ---- Feature Publishing ----

@router.post("/{name}/publish")
async def publish_feature(
    name: str,
    version: str = Query(..., description="Version to publish"),
    changelog: str = Query("", description="Changelog"),
) -> Dict[str, Any]:
    """Publish a feature version."""
    try:
        # Ensure registered first
        _feature_service.registry.get(name, version)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Feature '{name}' version '{version}' not registered.",
        )

    fv = _feature_service.publish_feature(name, version, changelog)
    return {
        "feature_name": fv.feature_name,
        "version": fv.version,
        "stage": fv.stage.value,
        "changelog": fv.changelog,
        "created_at": fv.created_at,
    }


# ---- Online Store ----

@router.get("/online/{symbol}")
async def get_online_features(symbol: str) -> Dict[str, Any]:
    """Get online features for a symbol.

    Example response::

        {"symbol": "NVDA", "ema20": 182.31, "atr14": 4.82}
    """
    features = _feature_service.get_online_features(symbol)
    if features is None:
        raise HTTPException(status_code=404, detail=f"No features for symbol '{symbol}'")
    return {"symbol": symbol, **features}


@router.post("/online/{symbol}")
async def set_online_features(
    symbol: str,
    features: Dict[str, float],
    ttl: str = Query("medium", description="TTL: realtime, short, medium, long"),
) -> Dict[str, Any]:
    """Set online features for a symbol."""
    try:
        store_ttl = StoreTTL(ttl)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid TTL: {ttl}")

    record = _feature_service.set_online(symbol, features, ttl=store_ttl)
    return {
        "symbol": record.entity_id,
        "feature_count": len(record.features),
        "ttl": record.ttl.value,
        "expires_at": record.expires_at,
    }


# ---- Validation ----

@router.post("/validate")
async def validate_feature(
    feature_name: str = Query(..., description="Feature name"),
    values: List[float] = Query(..., description="Feature values"),
    version: str = Query("v1", description="Version"),
    timestamps: Optional[List[float]] = Query(None, description="Timestamps"),
    reference_ts: Optional[List[float]] = Query(None, description="Reference timestamps for lookahead check"),
) -> Dict[str, Any]:
    """Validate feature data."""
    report = _feature_service.validate_feature(
        feature_name=feature_name,
        values=values,
        timestamps=timestamps,
        version=version,
        reference_timestamps=reference_ts,
    )
    return {
        "feature_name": report.feature_name,
        "version": report.version,
        "passed": report.passed,
        "issue_count": len(report.issues),
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
        "issues": [
            {
                "rule": i.rule.value,
                "severity": i.severity.value,
                "message": i.message,
            }
            for i in report.issues
        ],
    }


# ---- Drift Monitoring ----

@router.post("/drift/check")
async def check_drift(
    feature_name: str = Query(..., description="Feature name"),
    training_values: List[float] = Query(..., description="Training distribution"),
    production_values: List[float] = Query(..., description="Production distribution"),
) -> Dict[str, Any]:
    """Check feature drift."""
    report = _feature_service.check_drift(feature_name, training_values, production_values)
    return {
        "feature_name": report.feature_name,
        "status": report.status.value,
        "psi": report.psi_value,
        "ks_statistic": report.ks_statistic,
        "ks_pvalue": report.ks_pvalue,
        "training_stats": report.training_stats,
        "production_stats": report.production_stats,
        "details": report.drift_details,
    }


@router.get("/drift/status/{name}")
async def get_drift_status(name: str) -> Dict[str, Any]:
    """Get latest drift status for a feature."""
    status = _feature_service.get_drift_status(name)
    if status is None:
        raise HTTPException(status_code=404, detail=f"No drift data for '{name}'")
    return {"feature_name": name, "status": status.value}


@router.get("/drift/list")
async def list_drifted_features() -> Dict[str, Any]:
    """List features with active drift."""
    return {"drifted_features": _feature_service.list_drifted_features()}


# ---- Lineage ----

@router.get("/lineage/{name}")
async def get_lineage(name: str) -> Dict[str, Any]:
    """Get feature lineage graph."""
    graph = _feature_service.get_feature_lineage(name)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"No lineage for '{name}'")

    return {
        "feature_name": name,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "nodes": [
            {
                "node_id": n.node_id,
                "node_type": n.node_type.value,
                "description": n.description,
            }
            for n in graph.nodes.values()
        ],
        "edges": [{"from": e[0], "to": e[1]} for e in graph.edges],
        "root_nodes": graph.root_nodes,
    }


@router.post("/lineage/node")
async def add_lineage_node(
    node_id: str = Query(..., description="Node identifier"),
    node_type: str = Query("feature", description="Node type"),
    description: str = Query("", description="Description"),
    parents: Optional[str] = Query(None, description="Comma-separated parent node IDs"),
) -> Dict[str, Any]:
    """Add a lineage node."""
    try:
        nt = NodeType(node_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid node type: {node_type}")

    parent_list = parents.split(",") if parents else []
    node = _feature_service.track_lineage(
        node_id=node_id,
        node_type=nt,
        parents=parent_list,
        description=description,
    )
    return {
        "node_id": node.node_id,
        "node_type": node.node_type.value,
        "description": node.description,
    }


@router.post("/lineage/edge")
async def add_lineage_edge(
    from_node: str = Query(..., description="Upstream node"),
    to_node: str = Query(..., description="Downstream node"),
) -> Dict[str, Any]:
    """Add a lineage edge."""
    try:
        _feature_service.lineage.add_edge(from_node, to_node)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "from": from_node,
        "to": to_node,
        "status": "created",
    }


# ---- Offline Store ----

@router.post("/offline/write")
async def write_offline(
    feature_name: str = Query(..., description="Feature name"),
    partition_key: str = Query(..., description="Partition key"),
    rows: List[Dict[str, Any]] = Query(..., description="Data rows"),
    partition_unit: str = Query("month", description="Partition unit"),
) -> Dict[str, Any]:
    """Write offline feature data."""
    try:
        pu = PartitionUnit(partition_unit)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid partition unit: {partition_unit}")

    dataset = _feature_service.write_offline(feature_name, partition_key, rows, pu)
    return {
        "feature_name": dataset.feature_name,
        "partition_key": dataset.partition_key,
        "partition_unit": dataset.partition_unit.value,
        "row_count": dataset.row_count,
    }


@router.post("/offline/read")
async def read_offline(
    feature_name: str = Query(..., description="Feature name"),
    partition_key: Optional[str] = Query(None, description="Specific partition"),
    start_time: Optional[float] = Query(None, description="Start timestamp"),
    end_time: Optional[float] = Query(None, description="End timestamp"),
    limit: int = Query(100000, description="Max rows"),
) -> Dict[str, Any]:
    """Read offline feature data."""
    data = _feature_service.read_offline(
        feature_name=feature_name,
        partition_key=partition_key,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    return {
        "feature_name": feature_name,
        "row_count": len(data),
        "truncated": len(data) >= limit,
        "data": data[:100],  # Limit response size
    }


# ---- Categories ----

@router.get("/categories")
async def list_categories() -> Dict[str, Any]:
    """List feature categories."""
    cats = _feature_service.catalog.list_categories()
    return {
        "categories": [
            {
                "name": c.name,
                "description": c.description,
                "parent": c.parent,
                "created_at": c.created_at,
            }
            for c in cats
        ],
        "tree": _feature_service.get_category_tree(),
    }


@router.post("/categories")
async def create_category(
    name: str = Query(..., description="Category name"),
    description: str = Query("", description="Description"),
    parent: Optional[str] = Query(None, description="Parent category"),
) -> Dict[str, Any]:
    """Create a feature category."""
    try:
        cat = _feature_service.create_category(name, description, parent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "name": cat.name,
        "description": cat.description,
        "parent": cat.parent,
        "created_at": cat.created_at,
    }


# ---- Statistics ----

@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get feature store statistics."""
    return _feature_service.stats()
