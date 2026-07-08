import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / 'scripts' / 'check-contract-data-quality.py'
spec = importlib.util.spec_from_file_location('check_contract_data_quality', SCRIPT_PATH)
check_contract_data_quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_contract_data_quality)


def test_procurement_mapping_includes_outdoor_open_space_lease():
    assert check_contract_data_quality.PROCUREMENT_DIMENSION_MAPPING['室外空地租赁'] == '室外空地'
