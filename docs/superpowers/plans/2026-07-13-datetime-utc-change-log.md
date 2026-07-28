# Datetime UTC Change Log Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize all aware model datetime values to UTC before NetBox captures pre-save audit snapshots.

**Architecture:** Add one abstract `ContractBaseModel` between NetBoxModel and every plugin business model. Its save method normalizes concrete DateTimeField attributes before delegating to NetBoxModel, while existing model-specific save methods and mixins remain unchanged.

**Tech Stack:** Python, Django ORM, NetBoxModel, unittest/AST regression tests

---

### Task 1: Add failing UTC normalization regression tests

**Files:**
- Create: `netbox_contract/tests/test_datetime_utc_save.py`
- Test: `netbox_contract/tests/test_datetime_utc_save.py`

- [ ] **Step 1: Add a behavioral normalization test**

Create a standalone unittest that builds fake field metadata containing DateTimeField-like and non-datetime fields. Verify an Asia/Shanghai aware value becomes UTC without changing its timestamp, while naive values, `None`, and strings remain unchanged.

```python
local_value = datetime.datetime(2026, 7, 13, 12, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
normalize_datetime_fields(instance)
self.assertEqual(instance.started_at, datetime.datetime(2026, 7, 13, 4, 0, tzinfo=datetime.timezone.utc))
self.assertEqual(instance.started_at.timestamp(), local_value.timestamp())
self.assertEqual(instance.naive_at, naive_value)
self.assertIsNone(instance.finished_at)
self.assertEqual(instance.name, 'contract')
```

- [ ] **Step 2: Add an AST inheritance test**

Parse `netbox_contract/models.py` and assert `ContractBaseModel` exists, is abstract, overrides `save()` with DateTimeField/astimezone/UTC/super calls, and all 23 named business models inherit it:

```python
TARGET_MODELS = {
    'ContractType', 'AccountingDimension', 'ServiceProvider', 'ContractAssignment',
    'Contract', 'Invoice', 'InvoiceLine', 'RevenueCustomer', 'RevenueProject',
    'RevenueContract', 'RevenueContractProject', 'RevenueContractVersion',
    'RevenueContractLine', 'RevenueBillingRule', 'RevenueBillingSegment',
    'RevenueReceivableBill', 'RevenueReceivableLine', 'RevenueInvoice',
    'RevenueInvoiceLine', 'RevenueInvoiceMapping', 'RevenueReceipt',
    'RevenueReceiptAllocation', 'RevenueSyncLog',
}
```

- [ ] **Step 3: Verify RED**

Run `python -m unittest netbox_contract.tests.test_datetime_utc_save -v`.

Expected: inheritance test fails because `ContractBaseModel` does not exist and all target models still inherit `NetBoxModel`.

### Task 2: Implement pre-save UTC normalization

**Files:**
- Modify: `netbox_contract/models.py:1-23`
- Modify: `netbox_contract/models.py:87-1208`

- [ ] **Step 1: Add the abstract base model**

```python
import datetime

from django.utils import timezone

class ContractBaseModel(NetBoxModel):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        for field in self._meta.fields:
            if isinstance(field, models.DateTimeField):
                value = getattr(self, field.name)
                if isinstance(value, datetime.datetime) and timezone.is_aware(value):
                    setattr(self, field.name, value.astimezone(datetime.timezone.utc))
        super().save(*args, **kwargs)
```

- [ ] **Step 2: Replace every direct NetBoxModel base**

Change all 23 target classes to inherit `ContractBaseModel`; preserve `class ServiceProvider(ContactsMixin, ContractBaseModel)` and `class Contract(ContactsMixin, ContractBaseModel)` ordering.

- [ ] **Step 3: Verify GREEN**

Run `python -m unittest netbox_contract.tests.test_datetime_utc_save -v`.

Expected: all UTC normalization and inheritance tests pass.

- [ ] **Step 4: Run model regression tests**

Run `python -m pytest netbox_contract/tests/test_revenue_models.py netbox_contract/tests/test_views.py -v` in the configured NetBox environment.

Expected: all tests pass; no migration is generated because the base class is abstract.

- [ ] **Step 5: Verify syntax and scope**

Run `python -m py_compile netbox_contract/models.py netbox_contract/tests/test_datetime_utc_save.py` and `git diff --check -- netbox_contract/models.py netbox_contract/tests/test_datetime_utc_save.py`.

Expected: both commands exit successfully and no signal, form, view, or migration file changes are present.
