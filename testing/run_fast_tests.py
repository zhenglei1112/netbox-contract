"""Run pure revenue tests without bootstrapping a NetBox installation."""

from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / 'netbox_contract'
TEST_FILES = (
    'test_revenue_generation.py',
    'test_revenue_timeline.py',
    'test_revenue_portfolio.py',
    'test_revenue_view_filters.py',
    'test_datetime_utc_save.py',
    'test_detail_pagination.py',
    'test_revenue_plan_ui_visibility.py',
    'test_migration_dependencies.py',
)


def _install_namespace_package():
    """Expose plugin modules without importing its NetBox-dependent __init__."""
    package = ModuleType('netbox_contract')
    package.__path__ = [str(PACKAGE_ROOT)]
    package.__package__ = 'netbox_contract'
    package.__spec__ = ModuleSpec('netbox_contract', loader=None, is_package=True)
    sys.modules['netbox_contract'] = package


def main():
    _install_namespace_package()
    tests = [str(PACKAGE_ROOT / 'tests' / filename) for filename in TEST_FILES]
    return pytest.main(['-q', '-p', 'no:cacheprovider', *tests])


if __name__ == '__main__':
    raise SystemExit(main())
