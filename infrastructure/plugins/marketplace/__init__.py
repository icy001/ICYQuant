"""Plugin marketplace package for ICYQuant.

Provides a comprehensive plugin marketplace with repository
management, publisher registration, package creation, installation,
updates, rollbacks, release channels, and search capabilities.

Usage::

    from infrastructure.plugins.marketplace import PluginMarketplace

    marketplace = PluginMarketplace()
    await marketplace.initialize()
    results = await marketplace.search_plugins("momentum")
    await marketplace.shutdown()
"""

from __future__ import annotations

from .marketplace import PluginMarketplace
from .repository import MarketplaceRepository
from .registry import MarketplaceRegistry
from .publisher import MarketplacePublisher
from .package import MarketplacePackage
from .installer import MarketplaceInstaller
from .updater import MarketplaceUpdater
from .rollback import MarketplaceRollback
from .channels import MarketplaceChannels
from .compatibility import MarketplaceCompatibility
from .dependency import MarketplaceDependency
from .resolver import MarketplaceResolver
from .search import MarketplaceSearch
from .downloader import MarketplaceDownloader
from .signature import MarketplaceSignature
from .validator import MarketplaceValidator
from .cache import MarketplaceCache
from .audit import MarketplaceAudit
from .metrics import MarketplaceMetrics
from .health import MarketplaceHealth
from .diagnostics import MarketplaceDiagnostics

__all__ = [
    "PluginMarketplace",
    "MarketplaceRepository",
    "MarketplaceRegistry",
    "MarketplacePublisher",
    "MarketplacePackage",
    "MarketplaceInstaller",
    "MarketplaceUpdater",
    "MarketplaceRollback",
    "MarketplaceChannels",
    "MarketplaceCompatibility",
    "MarketplaceDependency",
    "MarketplaceResolver",
    "MarketplaceSearch",
    "MarketplaceDownloader",
    "MarketplaceSignature",
    "MarketplaceValidator",
    "MarketplaceCache",
    "MarketplaceAudit",
    "MarketplaceMetrics",
    "MarketplaceHealth",
    "MarketplaceDiagnostics",
]