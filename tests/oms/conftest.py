"""Shared conftest for OMS tests — registers all OMS packages.

This avoids duplicating the bootstrap in every test file.
"""
from __future__ import annotations

import os
import sys
import types
import importlib.util

_ws = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_oms_dir = os.path.join(_ws, 'services', 'oms')

_subdirs = [
    'domain', 'errors', 'events', 'event_store', 'projection', 'recovery',
    'commands', 'handlers', 'validation', 'results',
    'execution', 'delivery', 'timeout',
    'recovery', 'reconciliation', 'repair', 'dead_letter', 'observability',
]

# Register namespace packages
if 'services' not in sys.modules:
    _svc = types.ModuleType('services')
    _svc.__path__ = [os.path.join(_ws, 'services')]
    sys.modules['services'] = _svc

if 'services.oms' not in sys.modules:
    _mod = types.ModuleType('services.oms')
    _mod.__path__ = [_oms_dir]
    sys.modules['services.oms'] = _mod

for _sub in _subdirs:
    _sub_dir = os.path.join(_oms_dir, _sub)
    _mod_name = f'services.oms.{_sub}'
    if _mod_name not in sys.modules and os.path.isdir(_sub_dir):
        _pkg = types.ModuleType(_mod_name)
        _pkg.__path__ = [_sub_dir]
        sys.modules[_mod_name] = _pkg

# Load all .py files in each subdirectory
for _sub in _subdirs:
    _sub_dir = os.path.join(_oms_dir, _sub)
    if not os.path.isdir(_sub_dir):
        continue
    for _fname in os.listdir(_sub_dir):
        if not _fname.endswith('.py') or _fname == '__init__.py':
            continue
        _mod_name = f'services.oms.{_sub}.{_fname[:-3]}'
        if _mod_name in sys.modules:
            continue
        _fp = os.path.join(_sub_dir, _fname)
        _spec = importlib.util.spec_from_file_location(_mod_name, _fp)
        _m = importlib.util.module_from_spec(_spec)
        sys.modules[_mod_name] = _m
        try:
            _spec.loader.exec_module(_m)
        except Exception:
            pass  # some modules may fail to load due to missing deps
