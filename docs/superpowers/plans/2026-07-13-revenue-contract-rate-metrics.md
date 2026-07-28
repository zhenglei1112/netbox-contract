# Revenue Contract Rate Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the contract overview show whole-contract invoice progress and clearly named receivable collection performance.

**Architecture:** Keep existing amount aggregation and local calendar/timeline rates unchanged. Change only the contract workspace overview invoice-rate denominator and the two overview labels, with focused context and template regression tests.

**Tech Stack:** Python, Django TestCase, Django templates

---

### Task 1: Add failing overview regression tests

**Files:**
- Modify: `netbox_contract/tests/test_revenue_models.py`
- Test: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Write the failing calculation assertions**

In `test_contract_context_builds_structured_workspace`, set the business example amounts before building context:

```python
self.contract.total_amount = Decimal('720000.00')
self.contract.save(update_fields=['total_amount'])
self.bill.amount = Decimal('225000.00')
self.bill.net_amount = Decimal('225000.00')
self.bill.invoiced_amount = Decimal('225000.00')
self.bill.receipted_amount = Decimal('200000.00')
self.bill.save(update_fields=['amount', 'net_amount', 'invoiced_amount', 'receipted_amount'])
```

Then assert:

```python
overview = context['revenue_contract_workspace']['overview']
self.assertEqual(overview['invoice_rate'], '31.3%')
self.assertEqual(overview['receipt_rate'], '88.9%')
```

Percentage display uses conventional financial half-up rounding, so `225000 / 720000` renders as `31.3%`.

- [ ] **Step 2: Write the failing label test**

Add `Path` and `settings` imports, then:

```python
def test_revenue_contract_template_uses_unambiguous_rate_labels(self):
    template_path = Path(settings.BASE_DIR) / 'netbox_contract' / 'templates' / 'netbox_contract' / 'revenue_contract.html'
    template = template_path.read_text(encoding='utf-8')
    self.assertIn('合同开票进度', template)
    self.assertIn('应收回款率', template)
    self.assertNotIn('<div class="label">开票率</div>', template)
    self.assertNotIn('<div class="label">回款率</div>', template)
```

- [ ] **Step 3: Verify RED**

Run `python -m pytest netbox_contract/tests/test_revenue_models.py -k "contract_context_builds_structured_workspace or template_uses_unambiguous_rate_labels" -v`.

Expected: the calculation fails because the old denominator is receivables, and the label test fails because the old labels remain.

### Task 2: Implement the overview-only change

**Files:**
- Modify: `netbox_contract/views.py:1539`
- Modify: `netbox_contract/templates/netbox_contract/revenue_contract.html:68`

- [ ] **Step 1: Change the overview calculation**

```python
'invoice_rate': _money_percent(invoiced_total, contract_amount),
'receipt_rate': _money_percent(receipt_total, receivable_total),
```

Do not change `_build_revenue_contract_calendar` or `_build_revenue_contract_timeline`.

- [ ] **Step 2: Change the overview labels**

```html
<div class="revenue-kpi"><div class="label">合同开票进度</div><div class="value">{{ overview.invoice_rate }}</div></div>
<div class="revenue-kpi"><div class="label">应收回款率</div><div class="value">{{ overview.receipt_rate }}</div></div>
```

- [ ] **Step 3: Verify GREEN**

Run the focused pytest command from Task 1. Expected: both tests pass.

- [ ] **Step 4: Run regression tests**

Run `python -m pytest netbox_contract/tests/test_revenue_models.py -v`. Expected: all tests pass without new errors.

- [ ] **Step 5: Review the diff**

Run `git diff --check` and inspect only the three scoped files. Expected: only the overview calculation, labels, and regression tests change.
