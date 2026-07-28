# Revenue Form Field Whitelists Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `fields = '__all__'` on every revenue model edit form with an explicit business-field whitelist so the raw `custom_field_data` JSON field is never rendered.

**Architecture:** Keep the existing dynamic form factory, but drive it from one ordered model-to-fields mapping modeled after the external-purchase `ContractForm`. Specialized order and contract-line forms reuse the same mapping while retaining their dynamic selectors; `NetBoxModelForm` remains responsible for injecting configured custom fields.

**Tech Stack:** Python, Django ModelForm metadata, NetBox `NetBoxModelForm`, pytest.

---

## File Structure

- `netbox_contract/forms.py`: define the authoritative revenue form field mapping and use it in dynamic and specialized forms.
- `netbox_contract/tests/test_revenue_plan_ui_visibility.py`: add a fast source regression test that runs without NetBox.
- `netbox_contract/tests/test_revenue_models.py`: instantiate every form under NetBox and validate the whitelist and specialized selectors.

### Task 1: Define and apply explicit revenue form field whitelists

**Files:**
- Modify: `netbox_contract/forms.py:774-841`
- Modify: `netbox_contract/tests/test_revenue_plan_ui_visibility.py`
- Modify: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Write the failing fast source test**

Append to `netbox_contract/tests/test_revenue_plan_ui_visibility.py`:

```python
def test_revenue_forms_use_explicit_business_field_whitelists():
    source = (PACKAGE_ROOT / 'forms.py').read_text(encoding='utf-8-sig')
    revenue_source = source.split('_REVENUE_FORM_FIELDS =', 1)[1]

    assert '_REVENUE_FORM_FIELDS = {' in source
    assert "'fields': '__all__'" not in revenue_source
    assert "fields = '__all__'" not in revenue_source
    assert "'fields': _REVENUE_FORM_FIELDS[_revenue_model]" in revenue_source
    assert 'fields = _REVENUE_FORM_FIELDS[RevenueOrder]' in revenue_source
    assert 'fields = _REVENUE_FORM_FIELDS[RevenueContractLine]' in revenue_source
```

- [ ] **Step 2: Run the fast suite and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe testing\run_fast_tests.py
```

Expected: FAIL because `_REVENUE_FORM_FIELDS` is absent and the three `__all__` declarations remain.

- [ ] **Step 3: Add the complete business-field mapping**

Replace `_REVENUE_FORM_MODELS` with this ordered mapping and derive the model list from it:

```python
_REVENUE_FORM_FIELDS = {
    RevenueCustomer: (
        'name', 'short_name', 'usci', 'finance_code', 'eip_code',
        'customer_type', 'sales_owner', 'business_owner', 'is_risk',
        'address_phone', 'bank_account', 'tags',
    ),
    RevenueProject: (
        'name', 'customer', 'project_manager', 'sales_owner',
        'business_owner', 'project_type', 'status',
        'accumulated_receivable', 'accumulated_invoice',
        'accumulated_receipt', 'tags',
    ),
    RevenueContract: (
        'contract_code', 'name', 'customer', 'contract_type', 'projects',
        'our_party', 'customer_party', 'sign_date', 'start_date', 'end_date',
        'total_amount', 'is_framework', 'status', 'sales_owner',
        'business_owner', 'source_system', 'external_id', 'sync_status',
        'sync_log', 'tags',
    ),
    RevenueContractProject: ('contract', 'project', 'tags'),
    RevenueOrder: (
        'order_code', 'contract', 'project', 'name', 'amount', 'start_date',
        'end_date', 'status', 'source_system', 'external_id', 'tags',
    ),
    RevenueContractVersion: (
        'contract', 'version_code', 'change_type', 'start_date', 'end_date',
        'status', 'tags',
    ),
    RevenueContractLine: (
        'contract', 'contract_version', 'project', 'revenue_order',
        'order_id', 'product_category', 'charge_item', 'unit_price',
        'quantity', 'unit', 'valid_from', 'valid_to', 'status', 'tags',
    ),
    RevenueBillingRule: (
        'contract_line', 'contract_version', 'rule_type', 'trigger_event',
        'trigger_offset_days', 'billing_cycle', 'billing_direction',
        'bill_generation_day', 'proration_rule', 'rounding_precision',
        'is_active', 'status', 'tags',
    ),
    RevenueBillingSegment: (
        'contract_line', 'billing_rule', 'segment_start', 'segment_end',
        'unit_price', 'quantity', 'amount', 'change_trigger',
        'billing_rule_snapshot', 'tags',
    ),
    RevenueReceivablePlan: (
        'plan_code', 'contract', 'contract_line', 'billing_rule',
        'charge_item', 'order_id', 'status', 'tags',
    ),
    RevenueReceivablePlanVersion: (
        'plan', 'version_no', 'trigger_type', 'trigger_event', 'offset_days',
        'planned_date', 'planned_amount', 'effective_from', 'change_reason',
        'is_current', 'tags',
    ),
    RevenueTriggerRecord: (
        'plan', 'billing_rule', 'plan_version', 'trigger_event',
        'actual_trigger_date', 'status', 'source_system', 'external_id',
        'notes', 'tags',
    ),
    RevenueAdjustmentRecord: (
        'plan', 'receivable_line', 'adjustment_type', 'adjustment_date',
        'amount', 'reason', 'source_system', 'external_id', 'status', 'tags',
    ),
    RevenueReceivableBill: (
        'bill_code', 'customer', 'contract', 'project', 'billing_period',
        'receivable_date', 'due_date', 'amount', 'adjusted_amount',
        'net_amount', 'invoiced_amount', 'receipted_amount', 'confirm_status',
        'invoice_status', 'receipt_status', 'ageing_status', 'risk_status',
        'tags',
    ),
    RevenueReceivableLine: (
        'bill', 'contract_line', 'billing_rule', 'receivable_plan',
        'start_date', 'end_date', 'receivable_date', 'due_date', 'amount',
        'adjusted_amount', 'net_amount', 'risk_status', 'idempotent_key',
        'tags',
    ),
    RevenueInvoice: (
        'invoice_code', 'customer', 'invoice_type', 'invoice_date', 'amount',
        'source_system', 'external_id', 'sync_status', 'sync_log', 'tags',
    ),
    RevenueInvoiceLine: (
        'invoice', 'line_no', 'external_line_id', 'item_name', 'amount',
        'tags',
    ),
    RevenueInvoiceMapping: (
        'receivable_line', 'invoice_line', 'mapped_amount', 'status',
        'operator', 'approval_batch_no', 'tags',
    ),
    RevenueReceipt: (
        'customer', 'receipt_date', 'amount', 'allocated_total',
        'unallocated_amount', 'bank_flow_no', 'payer_name', 'status',
        'source_system', 'external_id', 'sync_status', 'sync_log', 'tags',
    ),
    RevenueReceiptAllocation: (
        'receipt', 'receivable_line', 'invoice_mapping', 'allocated_amount',
        'allocation_type', 'status', 'operator', 'approval_batch_no', 'tags',
    ),
    RevenueSyncLog: (
        'source_system', 'entity_type', 'entity_id', 'external_id',
        'sync_direction', 'sync_status', 'request_payload',
        'response_payload', 'error_message', 'tags',
    ),
}

_REVENUE_FORM_MODELS = tuple(_REVENUE_FORM_FIELDS)
```

- [ ] **Step 4: Make the dynamic forms consume the mapping**

Change:

```python
_meta = type('Meta', (), {'model': _revenue_model, 'fields': '__all__'})
```

to:

```python
_meta = type(
    'Meta',
    (),
    {
        'model': _revenue_model,
        'fields': _REVENUE_FORM_FIELDS[_revenue_model],
    },
)
```

- [ ] **Step 5: Make the specialized forms consume the same mapping**

Change `RevenueOrderForm.Meta` to:

```python
class Meta:
    model = RevenueOrder
    fields = _REVENUE_FORM_FIELDS[RevenueOrder]
```

Change `RevenueContractLineForm.Meta` to:

```python
class Meta:
    model = RevenueContractLine
    fields = _REVENUE_FORM_FIELDS[RevenueContractLine]
```

- [ ] **Step 6: Run the fast suite and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe testing\run_fast_tests.py
```

Expected: all fast tests pass.

### Task 2: Verify every form through NetBox

**Files:**
- Modify: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Write the NetBox-integrated form test before remote execution**

Add this method to `RevenueModelValidationTestCase`:

```python
def test_all_revenue_forms_use_business_field_whitelists(self):
    from netbox_contract import forms

    self.assertEqual(
        tuple(forms._REVENUE_FORM_FIELDS),
        tuple(forms._REVENUE_FORM_MODELS),
    )
    for model, expected_fields in forms._REVENUE_FORM_FIELDS.items():
        form_class = getattr(forms, f'{model.__name__}Form')
        self.assertEqual(tuple(form_class._meta.fields), expected_fields)
        self.assertNotIn('custom_field_data', expected_fields)
        self.assertNotIn('custom_field_data', form_class().fields)

    self.assertIn('contract', forms.RevenueOrderForm().fields)
    self.assertIn('project', forms.RevenueOrderForm().fields)
    contract_line_fields = forms.RevenueContractLineForm().fields
    self.assertIn('contract', contract_line_fields)
    self.assertIn('contract_version', contract_line_fields)
    self.assertIn('project', contract_line_fields)
    self.assertIn('revenue_order', contract_line_fields)
```

- [ ] **Step 2: Run the focused test on the remote NetBox environment**

Run:

```bash
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py test \
  netbox_contract.tests.test_revenue_models.RevenueModelValidationTestCase.test_all_revenue_forms_use_business_field_whitelists \
  --keepdb
```

Expected: PASS. If the database role still cannot create a test database, run the same assertions through a read-only `manage.py shell` process and report the test-database limitation without granting additional privileges.

- [ ] **Step 3: Verify no migration was introduced**

Run:

```bash
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py makemigrations netbox_contract --check --dry-run
```

Expected: `No changes detected in app 'netbox_contract'`.

- [ ] **Step 4: Run local checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check netbox_contract/tests/test_revenue_plan_ui_visibility.py
.\.venv\Scripts\python.exe -m ruff check --select F821,F822,F823 netbox_contract/forms.py netbox_contract/tests/test_revenue_models.py
.\.venv\Scripts\python.exe -m py_compile netbox_contract/forms.py netbox_contract/tests/test_revenue_models.py
git diff --check
```

Expected: the focused checks pass and no whitespace errors are reported. Existing unrelated repository-wide lint debt is outside this change.

- [ ] **Step 5: Commit only when the dirty baseline permits**

Before staging, confirm that the three files do not contain unrelated user changes. If they remain part of the larger untracked revenue implementation, leave them uncommitted and report the constraint.

When an established tracked baseline exists:

```powershell
git add -- netbox_contract/forms.py netbox_contract/tests/test_revenue_plan_ui_visibility.py netbox_contract/tests/test_revenue_models.py
git commit -m "fix: hide raw custom field data from revenue forms"
```

### Task 3: Deploy and smoke-test edit pages

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: Run the NetBox system check**

```bash
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 2: Request representative add/edit pages**

Use a signed-in client or browser to request revenue contract, order, contract-line, billing-rule, receivable-bill, invoice, and receipt add/edit pages.

For every response verify:

```text
HTTP 200
No "Custom field data" label
No "custom_field_data" textarea
Expected business fields remain visible
```

- [ ] **Step 3: Restart and verify services**

```bash
sudo systemctl restart netbox netbox-rq
systemctl is-active netbox netbox-rq nginx postgresql redis-server
```

Expected: all five services report `active`.
