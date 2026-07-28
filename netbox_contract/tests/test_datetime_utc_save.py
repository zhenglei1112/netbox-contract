import ast
import datetime
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo


MODELS_PATH = Path(__file__).resolve().parents[1] / 'models.py'
TARGET_MODELS = {
    'ContractType',
    'AccountingDimension',
    'ServiceProvider',
    'ContractAssignment',
    'Contract',
    'Invoice',
    'InvoiceLine',
    'RevenueCustomer',
    'RevenueProject',
    'RevenueContract',
    'RevenueContractProject',
    'RevenueContractVersion',
    'RevenueContractLine',
    'RevenueBillingRule',
    'RevenueBillingSegment',
    'RevenueReceivableBill',
    'RevenueReceivableLine',
    'RevenueInvoice',
    'RevenueInvoiceLine',
    'RevenueInvoiceMapping',
    'RevenueReceipt',
    'RevenueReceiptAllocation',
    'RevenueSyncLog',
}


class FakeDateTimeField:
    def __init__(self, name):
        self.name = name


class FakeField:
    def __init__(self, name):
        self.name = name


def normalize_datetime_fields(instance):
    for field in instance._meta.fields:
        if isinstance(field, FakeDateTimeField):
            value = getattr(instance, field.name)
            if isinstance(value, datetime.datetime) and value.tzinfo is not None:
                setattr(instance, field.name, value.astimezone(datetime.timezone.utc))


class FakeInstance:
    def __init__(self):
        self._meta = type('Meta', (), {
            'fields': [
                FakeDateTimeField('started_at'),
                FakeDateTimeField('naive_at'),
                FakeDateTimeField('finished_at'),
                FakeField('name'),
            ],
        })()


class DateTimeUTCSaveTestCase(unittest.TestCase):
    def test_normalization_converts_aware_datetimes_only(self):
        local_value = datetime.datetime(2026, 7, 13, 12, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
        naive_value = datetime.datetime(2026, 7, 13, 12, 0)
        instance = FakeInstance()
        instance.started_at = local_value
        instance.naive_at = naive_value
        instance.finished_at = None
        instance.name = 'contract'

        normalize_datetime_fields(instance)

        self.assertEqual(
            instance.started_at,
            datetime.datetime(2026, 7, 13, 4, 0, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(instance.started_at.timestamp(), local_value.timestamp())
        self.assertEqual(instance.naive_at, naive_value)
        self.assertIsNone(instance.finished_at)
        self.assertEqual(instance.name, 'contract')

    def test_all_business_models_use_abstract_utc_normalizing_base(self):
        source = MODELS_PATH.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(MODELS_PATH))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }

        base_model = classes.get('ContractBaseModel')
        self.assertIsNotNone(base_model, 'ContractBaseModel is not defined')

        meta = next(
            (node for node in base_model.body if isinstance(node, ast.ClassDef) and node.name == 'Meta'),
            None,
        )
        self.assertIsNotNone(meta, 'ContractBaseModel.Meta is not defined')
        meta_source = ast.unparse(meta)
        self.assertIn('abstract = True', meta_source)

        save_method = next(
            (node for node in base_model.body if isinstance(node, ast.FunctionDef) and node.name == 'save'),
            None,
        )
        self.assertIsNotNone(save_method, 'ContractBaseModel.save() is not defined')
        save_source = ast.unparse(save_method)
        self.assertIn('DateTimeField', save_source)
        self.assertIn('astimezone', save_source)
        self.assertIn('datetime.timezone.utc', save_source)
        self.assertIn('timezone.is_aware', save_source)
        self.assertIn('super().save', save_source)

        missing = set()
        for model_name in TARGET_MODELS:
            model = classes[model_name]
            base_names = {
                base.id
                for base in model.bases
                if isinstance(base, ast.Name)
            }
            if 'ContractBaseModel' not in base_names:
                missing.add(model_name)

        self.assertEqual(missing, set())


if __name__ == '__main__':
    unittest.main()
