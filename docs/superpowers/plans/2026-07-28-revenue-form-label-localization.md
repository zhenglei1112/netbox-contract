# Revenue Form Label Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the remaining English labels on all revenue-model forms with the approved Chinese labels without changing field order or behavior.

**Architecture:** Extend the existing runtime `verbose_name` mapping for seven business fields. Introduce a revenue-only `RevenueModelForm` base class that localizes NetBox's injected `changelog_message` field after form initialization, then use it for all dynamic and specialized revenue forms.

**Tech Stack:** Python, Django forms and model metadata, NetBox 4.6 plugin forms, pytest, Django test runner

---

## File map

- Modify `netbox_contract/models.py`: add seven missing business-field labels to `_apply_revenue_verbose_names()`.
- Modify `netbox_contract/forms.py`: add the shared revenue form base and apply it to every revenue form.
- Modify `netbox_contract/tests/test_revenue_plan_ui_visibility.py`: add a NetBox-independent source regression test.
- Modify `netbox_contract/tests/test_revenue_models.py`: test real runtime labels and field ordering under NetBox.

These files already contain broad pre-existing revenue subsystem work. Do not stage or commit the implementation files in the current dirty worktree unless their complete existing contents are explicitly approved.

### Task 1: Add failing localization tests

**Files:**
- Modify: `netbox_contract/tests/test_revenue_plan_ui_visibility.py`
- Modify: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Add the local source regression test**

Append to `netbox_contract/tests/test_revenue_plan_ui_visibility.py`:

```python
def test_revenue_forms_localize_remaining_english_labels():
    model_source = (PACKAGE_ROOT / 'models.py').read_text(encoding='utf-8-sig')
    form_source = (PACKAGE_ROOT / 'forms.py').read_text(encoding='utf-8-sig')

    for field_name, label in {
        'trigger_offset_days': '触发后天数',
        'billing_rule': '计费规则',
        'receivable_plan': '应收计划',
        'receivable_date': '应收日期',
        'due_date': '到期日期',
        'receipt': '回款',
        'receivable_line': '应收明细',
    }.items():
        assert f"'{field_name}': '{label}'" in model_source

    assert 'class RevenueModelForm(NetBoxModelForm):' in form_source
    assert "changelog_field = self.fields.get('changelog_message')" in form_source
    assert "changelog_field.label = _('变更说明')" in form_source
    assert "(RevenueModelForm,)" in form_source
    assert 'class RevenueOrderForm(RevenueModelForm):' in form_source
    assert 'class RevenueContractLineForm(RevenueModelForm):' in form_source
```

- [ ] **Step 2: Run the local fast suite and observe RED**

Run:

```powershell
.\.venv\Scripts\python.exe testing\run_fast_tests.py
```

Expected: one failure in `test_revenue_forms_localize_remaining_english_labels` because the seven mappings and `RevenueModelForm` are absent; the previous 67 tests pass.

- [ ] **Step 3: Add the NetBox runtime test**

Change the import in `netbox_contract/tests/test_revenue_models.py` to:

```python
from django.test import RequestFactory, SimpleTestCase, TestCase
```

Add this class before `RevenueModelValidationTestCase`:

```python
class RevenueFormLabelLocalizationTestCase(SimpleTestCase):
    expected_business_labels = {
        (RevenueBillingRule, 'trigger_offset_days'): '触发后天数',
        (RevenueTriggerRecord, 'billing_rule'): '计费规则',
        (RevenueReceivableLine, 'receivable_plan'): '应收计划',
        (RevenueReceivableLine, 'receivable_date'): '应收日期',
        (RevenueReceivableLine, 'due_date'): '到期日期',
        (RevenueReceiptAllocation, 'receipt'): '回款',
        (RevenueReceiptAllocation, 'receivable_line'): '应收明细',
    }

    def test_business_and_changelog_labels_are_localized(self):
        for (model, field_name), expected_label in self.expected_business_labels.items():
            self.assertEqual(
                str(model._meta.get_field(field_name).verbose_name),
                expected_label,
            )
            form_class = getattr(forms, f'{model.__name__}Form')
            self.assertEqual(str(form_class().fields[field_name].label), expected_label)

        for model in forms._REVENUE_FORM_MODELS:
            form_class = getattr(forms, f'{model.__name__}Form')
            self.assertTrue(issubclass(form_class, forms.RevenueModelForm))
            form = form_class()
            self.assertEqual(
                str(form.fields['changelog_message'].label),
                '变更说明',
            )
            field_names = tuple(form.fields)
            self.assertLess(
                field_names.index('tags'),
                field_names.index('changelog_message'),
            )
            self.assertNotIn('custom_field_data', field_names)

        self.assertFalse(issubclass(forms.ContractForm, forms.RevenueModelForm))
```

- [ ] **Step 4: Run the runtime test remotely and observe RED**

Open an interactive SSH session so credentials remain prompt-only:

```powershell
& 'C:\Program Files\PuTTY\plink.exe' -t -ssh zhenglei@192.168.30.178
```

On the server run:

```sh
sudo /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py test netbox_contract.tests.test_revenue_models.RevenueFormLabelLocalizationTestCase --keepdb -v 2
```

Expected: FAIL or ERROR because at least one runtime label is English and `forms.RevenueModelForm` does not exist.

### Task 2: Localize the seven business fields

**Files:**
- Modify: `netbox_contract/models.py:1586-1704`
- Test: `netbox_contract/tests/test_revenue_plan_ui_visibility.py`
- Test: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Extend the existing verbose-name mappings**

Update the four existing model sections to contain these complete mappings:

```python
RevenueBillingRule: {
    'contract_line': '合同项',
    'contract_version': '合同版本',
    'rule_type': '计费方式',
    'trigger_event': '触发节点',
    'trigger_offset_days': '触发后天数',
    'billing_cycle': '计费周期',
    'billing_direction': '计费方向',
    'bill_generation_day': '账单生成日',
    'proration_rule': '折算规则',
    'rounding_precision': '舍入精度',
    'is_active': '是否启用',
    'status': '状态',
},
```

```python
RevenueTriggerRecord: {
    'plan': '应收计划',
    'billing_rule': '计费规则',
    'plan_version': '计划版本',
    'trigger_event': '触发节点',
    'actual_trigger_date': '实际触发日期',
    'status': '状态',
    'source_system': '来源系统',
    'external_id': '外部系统ID',
    'notes': '说明',
},
```

```python
RevenueReceivableLine: {
    'bill': '应收账单',
    'contract_line': '合同项',
    'billing_rule': '计费规则',
    'receivable_plan': '应收计划',
    'start_date': '计费开始',
    'end_date': '计费结束',
    'receivable_date': '应收日期',
    'due_date': '到期日期',
    'amount': '原始金额',
    'adjusted_amount': '修正金额',
    'net_amount': '应收净额',
    'risk_status': '风险状态',
    'idempotent_key': '幂等键',
},
```

```python
RevenueReceiptAllocation: {
    'receipt': '回款',
    'receivable_line': '应收明细',
    'invoice_mapping': '发票映射',
    'allocated_amount': '分配金额',
    'allocation_type': '分配类型',
    'status': '状态',
    'operator': '经办人',
    'approval_batch_no': '审批批次号',
},
```

- [ ] **Step 2: Run the runtime test and confirm only the framework-label assertion remains RED**

In the SSH session run:

```sh
sudo /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py test netbox_contract.tests.test_revenue_models.RevenueFormLabelLocalizationTestCase --keepdb -v 2
```

Expected: the seven business-label assertions pass; the test still errors or fails because `RevenueModelForm` or the “变更说明” label is missing.

### Task 3: Localize the revenue changelog field

**Files:**
- Modify: `netbox_contract/forms.py:774-944`
- Test: `netbox_contract/tests/test_revenue_plan_ui_visibility.py`
- Test: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Add the shared revenue form base**

Insert immediately before `_REVENUE_FORM_FIELDS`:

```python
class RevenueModelForm(NetBoxModelForm):
    """Apply revenue-only presentation conventions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        changelog_field = self.fields.get('changelog_message')
        if changelog_field is not None:
            changelog_field.label = _('变更说明')
```

- [ ] **Step 2: Use the base for dynamic revenue forms**

Change:

```python
globals()[f'{_revenue_model.__name__}Form'] = type(
    f'{_revenue_model.__name__}Form',
    (NetBoxModelForm,),
    {'Meta': _meta},
)
```

to:

```python
globals()[f'{_revenue_model.__name__}Form'] = type(
    f'{_revenue_model.__name__}Form',
    (RevenueModelForm,),
    {'Meta': _meta},
)
```

- [ ] **Step 3: Use the base for specialized forms**

Change the declarations to:

```python
class RevenueOrderForm(RevenueModelForm):
```

```python
class RevenueContractLineForm(RevenueModelForm):
```

Do not modify any non-revenue form.

- [ ] **Step 4: Run the local suite and observe GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe testing\run_fast_tests.py
```

Expected: all tests pass, with the total increased from 67 to 68.

- [ ] **Step 5: Run the focused runtime test and observe GREEN**

In the SSH session run:

```sh
sudo /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py test netbox_contract.tests.test_revenue_models.RevenueFormLabelLocalizationTestCase --keepdb -v 2
```

Expected: `Ran 1 test` and `OK`.

- [ ] **Step 6: Inspect the implementation diff without staging**

Run:

```powershell
git diff --check -- netbox_contract/models.py netbox_contract/forms.py netbox_contract/tests/test_revenue_plan_ui_visibility.py netbox_contract/tests/test_revenue_models.py
git diff -- netbox_contract/models.py netbox_contract/forms.py netbox_contract/tests/test_revenue_plan_ui_visibility.py netbox_contract/tests/test_revenue_models.py
```

Expected: no whitespace errors; relevant changes consist only of seven mappings, one common form class, three inheritance updates, and two tests. Leave these files uncommitted because they overlap existing dirty work.

### Task 4: Verify and reload the remote application

**Files:**
- Verify: `netbox_contract/models.py`
- Verify: `netbox_contract/forms.py`
- Verify: `netbox_contract/tests/test_revenue_plan_ui_visibility.py`
- Verify: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Run the complete revenue runtime module**

In the SSH session run:

```sh
sudo /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py test netbox_contract.tests.test_revenue_models --keepdb -v 1
```

Expected: all tests pass and the command ends with `OK`.

- [ ] **Step 2: Confirm that no migration was introduced**

In the SSH session run:

```sh
sudo /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py makemigrations netbox_contract --check --dry-run
```

Expected: `No changes detected in app 'netbox_contract'`.

- [ ] **Step 3: Restart NetBox workers**

In the SSH session run:

```sh
sudo systemctl restart netbox netbox-rq
sudo systemctl is-active netbox netbox-rq
```

Expected: both services report `active`.

- [ ] **Step 4: Check application health**

In the SSH session run:

```sh
curl -I http://127.0.0.1/
```

Expected: an HTTP response from NetBox, normally `302 Found` for an unauthenticated root request.

- [ ] **Step 5: Audit all 21 pages in an authenticated browser**

Check these existing edit pages:

```text
/plugins/contracts/revenue/customers/4/edit/
/plugins/contracts/revenue/projects/6/edit/
/plugins/contracts/revenue/contracts/6/edit/
/plugins/contracts/revenue/contract-projects/6/edit/
/plugins/contracts/revenue/orders/1/edit/
/plugins/contracts/revenue/contract-versions/6/edit/
/plugins/contracts/revenue/contract-lines/11/edit/
/plugins/contracts/revenue/billing-rules/11/edit/
/plugins/contracts/revenue/billing-segments/11/edit/
/plugins/contracts/revenue/receivable-bills/6/edit/
/plugins/contracts/revenue/receivable-lines/11/edit/
/plugins/contracts/revenue/invoices/6/edit/
/plugins/contracts/revenue/invoice-lines/11/edit/
/plugins/contracts/revenue/invoice-mappings/11/edit/
/plugins/contracts/revenue/receipts/7/edit/
/plugins/contracts/revenue/receipt-allocations/7/edit/
/plugins/contracts/revenue/sync-logs/6/edit/
```

Check add pages for models currently without records:

```text
/plugins/contracts/revenue/receivable-plans/add/
/plugins/contracts/revenue/receivable-plan-versions/add/
/plugins/contracts/revenue/trigger-records/add/
/plugins/contracts/revenue/adjustment-records/add/
```

Expected on every page: normal rendering, no raw `Custom field data`, “标签” followed by “变更说明”, and none of the seven approved business labels remains in English.

- [ ] **Step 6: Check browser console errors**

Expected: no new JavaScript console errors on the audited pages.

- [ ] **Step 7: Record final scope**

Run:

```powershell
git status --short
```

Expected: implementation files remain uncommitted alongside the user's existing revenue changes. Report the four implementation files modified for this task and do not claim an implementation commit.
