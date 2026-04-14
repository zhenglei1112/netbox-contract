from django.test import TestCase

from netbox_contract.models import ContractType
from scripts.import_contract_types import ensure_contract_types


class ImportContractTypesTestCase(TestCase):
    def test_ensure_contract_types_creates_missing_and_skips_existing(self):
        ContractType.objects.create(name='公共-房屋租赁', color='ffffff')

        result = ensure_contract_types(
            names=('公共-房屋租赁', '福利-商业保险'),
            commit=True,
        )

        self.assertEqual(result['created'], ['福利-商业保险'])
        self.assertEqual(result['existing'], ['公共-房屋租赁'])
        self.assertEqual(ContractType.objects.filter(name='公共-房屋租赁').count(), 1)
        self.assertEqual(ContractType.objects.filter(name='福利-商业保险').count(), 1)

    def test_ensure_contract_types_dry_run_does_not_create_records(self):
        result = ensure_contract_types(
            names=('专项-法务服务',),
            commit=False,
        )

        self.assertEqual(result['created'], ['专项-法务服务'])
        self.assertEqual(result['existing'], [])
        self.assertFalse(ContractType.objects.filter(name='专项-法务服务').exists())
