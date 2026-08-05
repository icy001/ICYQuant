"""Production-grade plugin loader package for ICYQuant.

This subpackage provides a comprehensive, production-ready plugin
loader with the following components:

- :class:`PluginLoader`        : Unified async entry point.
- :class:`DirectoryScanner`    : Filesystem discovery of plugin manifests.
- :class:`PluginImporter`      : Dynamic module import with caching.
- :class:`DependencyResolver2`: Dependency resolution with cycle
                                 detection and topological sort.
- :class:`PluginInstaller`     : Plugin installation from directories
                                 and ZIP packages.
- :class:`PluginUninstaller`   : Plugin removal and cleanup.
- :class:`PluginReloader`      : Hot-reload of plugins.
- :class:`FileWatcher`         : Polling-based file change watcher.
- :class:`PluginVerifier`      : Comprehensive plugin verification.
- :class:`LoaderCache`         : Bounded cache for metadata, imports,
                                 and resolutions.
- :class:`LoaderMetrics`       : Operational metrics collection.
- :class:`LoaderDiagnostics`   : Diagnostic event tracking.
- :class:`LoaderValidator`     : Manifest and entrypoint validation.

Usage::

    from infrastructure.plugins.loader import PluginLoader

    loader = PluginLoader()
    manifests = await loader.discover(["./plugins"])
    result = await loader.load("my.plugin")
"""

from __future__ import annotations

from .cache import LoaderCache
from .diagnostics import LoaderDiagnostics
from .importer import PluginImporter
from .installer import PluginInstaller
from .loader import PluginLoader
from .metrics import LoaderMetrics
from .reloader import PluginReloader
from .resolver import DependencyResolver2
from .scanner import DirectoryScanner
from .uninstaller import PluginUninstaller
from .validator import LoaderValidator
from .verifier import PluginVerifier
from .watcher import FileWatcher

__all__ = [
    "PluginLoader",
    "DirectoryScanner",
    "PluginImporter",
    "DependencyResolver2",
    "PluginInstaller",
    "PluginUninstaller",
    "PluginReloader",
    "FileWatcher",
    "PluginVerifier",
    "LoaderCache",
    "LoaderMetrics",
    "LoaderDiagnostics",
    "LoaderValidator",
]