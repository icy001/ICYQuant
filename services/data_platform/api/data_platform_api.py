"""ICYQuant Data Platform REST API.

REST API endpoints for the institutional data platform:
    - GET  /api/v1/data/catalog      — Query metadata catalog
    - GET  /api/v1/data/lineage      — Trace data lineage
    - GET  /api/v1/data/time-travel  — Time-travel query
    - GET  /api/v1/data/quality      — Quality check results
    - POST /api/v1/data/ingest       — Ingest data
    - POST /api/v1/data/query        — Query data
    - GET  /api/v1/data/governance   — Governance compliance
    - GET  /api/v1/data/schema       — Schema registry
    - POST /api/v1/data/snapshot     — Create snapshot
    - GET  /api/v1/data/stats        — Platform statistics

Usage::

    from fastapi import FastAPI
    from services.data_platform.api.data_platform_api import router

    app = FastAPI()
    app.include_router(router)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from services.data_platform.service import DataPlatformService
from services.data_platform.config import (
    DataPlatformConfig,
    CatalogEntryType,
    DataClassification,
)
from services.data_platform.lakehouse import WriteMode


# ============================================================================
# API Types
# ============================================================================


@dataclass
class APIResponse:
    """Standard API response wrapper."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    message: str = ""
    request_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }


@dataclass
class IngestRequest:
    """Data ingest request."""

    dataset: str
    data: List[Dict[str, Any]]
    producer: str = "api"
    mode: str = "append"  # append, overwrite, merge, upsert
    validate_quality: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryRequest:
    """Data query request."""

    dataset: str
    consumer: str = "api"
    as_of: Optional[str] = None  # ISO timestamp
    partition: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: Optional[int] = None
    columns: Optional[List[str]] = None


@dataclass
class TimeTravelRequest:
    """Time-travel query request."""

    dataset: str
    timestamp: str  # ISO format: "2026-07-28T22:00:00"


@dataclass
class SnapshotRequest:
    """Snapshot creation request."""

    dataset: str
    description: str = ""


@dataclass
class SchemaRegisterRequest:
    """Schema registration request."""

    name: str
    description: str = ""
    fields: List[Dict[str, Any]] = field(default_factory=list)
    primary_key: List[str] = field(default_factory=list)
    version: int = 1


# ============================================================================
# Data Platform API
# ============================================================================


class DataPlatformAPI:
    """Data Platform REST API.

    Provides endpoints for all data platform operations.

    Usage::

        api = DataPlatformAPI(DataPlatformService(DataPlatformConfig()))
        response = api.get_catalog(query="tick")
        response = api.ingest_data(IngestRequest(dataset="tick", data=[...]))
    """

    def __init__(self, service: Optional[DataPlatformService] = None) -> None:
        self.service = service or DataPlatformService(DataPlatformConfig())
        self.service.initialize()

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def get_catalog(
        self,
        query: Optional[str] = None,
        entry_type: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> APIResponse:
        """GET /api/v1/data/catalog

        Query the metadata catalog.
        """
        try:
            if query:
                et = CatalogEntryType(entry_type) if entry_type else None
                result = self.service.search_catalog(query, entry_type=et)
                return APIResponse(
                    success=True,
                    data={
                        "entries": [e.to_dict() for e in result.entries],
                        "total_matches": result.total_matches,
                    },
                    message=f"Found {result.total_matches} entries for '{query}'",
                )

            entries = self.service.catalog.list_all(
                entry_type=CatalogEntryType(entry_type) if entry_type else None,
                owner=owner,
            )
            return APIResponse(
                success=True,
                data={
                    "entries": [e.to_dict() for e in entries],
                    "total": len(entries),
                },
            )

        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def get_catalog_entry(self, name: str) -> APIResponse:
        """GET /api/v1/data/catalog/{name}

        Get a specific catalog entry.
        """
        try:
            entry = self.service.catalog.get(name)
            if not entry:
                return APIResponse(success=False, error=f"Entry '{name}' not found")

            return APIResponse(
                success=True,
                data={"entry": entry.to_dict()},
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Lineage
    # ------------------------------------------------------------------

    def get_lineage(
        self,
        dataset: str,
        direction: str = "downstream",
        max_depth: Optional[int] = None,
    ) -> APIResponse:
        """GET /api/v1/data/lineage

        Trace data lineage for a dataset.
        """
        try:
            chain = self.service.trace_lineage(dataset, direction)
            return APIResponse(
                success=True,
                data={
                    "dataset": dataset,
                    "direction": direction,
                    "chain": chain.to_dict(),
                    "path_description": chain.get_path_description(),
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def get_lineage_impact(self, dataset: str) -> APIResponse:
        """GET /api/v1/data/lineage/impact

        Analyze impact of dataset changes.
        """
        try:
            impact = self.service.analyze_impact(dataset)
            return APIResponse(
                success=True,
                data={
                    "dataset": impact.dataset,
                    "affected_downstream": impact.affected_downstream,
                    "affected_upstream": impact.affected_upstream,
                    "total_affected": impact.total_affected,
                    "severity": impact.severity,
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Time Travel
    # ------------------------------------------------------------------

    def time_travel_query(self, request: TimeTravelRequest) -> APIResponse:
        """GET /api/v1/data/time-travel

        Query data as of a historical timestamp.
        """
        try:
            timestamp = datetime.fromisoformat(request.timestamp)
            result = self.service.query_as_of(request.dataset, timestamp)

            return APIResponse(
                success=True,
                data={
                    "dataset": result.dataset,
                    "timestamp": result.timestamp.isoformat(),
                    "snapshot_id": result.snapshot_id,
                    "is_exact_match": result.is_exact_match,
                    "row_count": result.row_count,
                    "data": result.data[:100],  # Limit response size
                },
                message=f"Retrieved {result.row_count} rows as of {request.timestamp}",
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------

    def get_quality(self, dataset: Optional[str] = None) -> APIResponse:
        """GET /api/v1/data/quality

        Get quality check results.
        """
        try:
            if dataset:
                report = self.service.quality_engine.get_latest_report(dataset)
                score = self.service.quality_engine.get_quality_score(dataset)

                return APIResponse(
                    success=True,
                    data={
                        "dataset": dataset,
                        "quality_score": score,
                        "latest_report": report.to_dict() if report else None,
                    },
                )
            else:
                stats = self.service.quality_engine.get_overall_stats()
                return APIResponse(success=True, data=stats)

        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Governance
    # ------------------------------------------------------------------

    def get_governance(self, dataset: Optional[str] = None) -> APIResponse:
        """GET /api/v1/data/governance

        Get governance compliance status.
        """
        try:
            if dataset:
                report = self.service.check_compliance(dataset)
                return APIResponse(success=True, data=report.to_dict())
            else:
                summary = self.service.governance.get_compliance_summary()
                return APIResponse(success=True, data=summary)

        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def get_schema(
        self, name: str, version: Optional[int] = None
    ) -> APIResponse:
        """GET /api/v1/data/schema

        Get schema definition.
        """
        try:
            if version:
                schema = self.service.schema_registry.get_version(name, version)
            else:
                schema = self.service.schema_registry.get_latest(name)

            if not schema:
                return APIResponse(success=False, error=f"Schema '{name}' not found")

            return APIResponse(
                success=True,
                data={
                    "schema": schema.to_dict(),
                    "versions_available": len(self.service.schema_registry.list_versions(name)),
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def list_schemas(self) -> APIResponse:
        """GET /api/v1/data/schemas

        List all registered schemas.
        """
        try:
            schemas = self.service.schema_registry.list_all()
            return APIResponse(
                success=True,
                data={
                    "schemas": [s.to_dict() for s in schemas],
                    "total": len(schemas),
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Ingest / Query
    # ------------------------------------------------------------------

    def ingest_data(self, request: IngestRequest) -> APIResponse:
        """POST /api/v1/data/ingest

        Ingest data into the platform.
        """
        try:
            mode = WriteMode(request.mode)
            result = self.service.ingest(
                dataset=request.dataset,
                data=request.data,
                producer=request.producer,
                mode=mode,
                validate_quality=request.validate_quality,
            )

            return APIResponse(
                success=result.success,
                data={
                    "rows_affected": result.rows_affected,
                    "quality_report": result.quality_report.to_dict() if result.quality_report else None,
                },
                error=result.error,
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def query_data(self, request: QueryRequest) -> APIResponse:
        """POST /api/v1/data/query

        Query data from the platform.
        """
        try:
            as_of = datetime.fromisoformat(request.as_of) if request.as_of else None

            result = self.service.query(
                dataset=request.dataset,
                consumer=request.consumer,
                as_of=as_of,
                partition=request.partition,
                filters=request.filters,
                limit=request.limit,
            )

            return APIResponse(
                success=result.success,
                data={
                    "rows": result.rows_affected,
                    "data": result.data[:100] if result.data else [],
                    "lineage": [n.to_dict() for n in result.lineage_nodes] if result.lineage_nodes else [],
                },
                error=result.error,
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def create_snapshot(self, request: SnapshotRequest) -> APIResponse:
        """POST /api/v1/data/snapshot

        Create a data snapshot.
        """
        try:
            version = self.service.create_version(
                request.dataset, request.description
            )
            return APIResponse(
                success=True,
                data=version.to_dict(),
                message=f"Snapshot created: {version.version_id}",
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Platform Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> APIResponse:
        """GET /api/v1/data/stats

        Get comprehensive platform statistics.
        """
        try:
            stats = self.service.get_platform_stats()
            return APIResponse(success=True, data=stats)
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def get_health(self) -> APIResponse:
        """GET /api/v1/data/health

        Get platform health status.
        """
        try:
            health = self.service.get_platform_health()
            return APIResponse(success=True, data=health)
        except Exception as e:
            return APIResponse(success=False, error=str(e))
