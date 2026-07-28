# Remove Contract Receivable Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the monthly receivable calendar from every revenue contract detail page while preserving all underlying monthly aggregation data and the remaining receivable views.

**Architecture:** Make this a template-only behavior change. A fast source-level regression test defines the removed and retained template contracts; no view, service, model, API, or migration code changes.

**Tech Stack:** Django templates, Python, pytest.

---

## File Structure

- `netbox_contract/templates/netbox_contract/revenue_contract.html`: remove both the hybrid monthly-summary branch and the non-hybrid receivable-calendar branch.
- `netbox_contract/tests/test_revenue_plan_ui_visibility.py`: add a fast regression test that proves all calendar variants are absent and important adjacent modules remain.
- `netbox_contract/tests/test_revenue_models.py`: update the existing template-structure assertions so they no longer require the hybrid calendar.

### Task 1: Remove all contract-detail monthly calendars

**Files:**
- Modify: `netbox_contract/templates/netbox_contract/revenue_contract.html:523-596`
- Modify: `netbox_contract/tests/test_revenue_plan_ui_visibility.py`
- Modify: `netbox_contract/tests/test_revenue_models.py:724-731`

- [ ] **Step 1: Write the failing fast regression test**

Append to `netbox_contract/tests/test_revenue_plan_ui_visibility.py`:

```python
def test_revenue_contract_hides_all_monthly_receivable_calendars():
    template = (
        PACKAGE_ROOT / 'templates' / 'netbox_contract' / 'revenue_contract.html'
    ).read_text(encoding='utf-8-sig')

    assert 'id="hybrid-month-calendar"' not in template
    assert 'ws.calendar.months' not in template
    assert 'ws.hybrid_month_summary.months' not in template
    assert '{{ timeline.title }}' in template
    assert 'display.periodic_matrix' in template
    assert 'id="contract-chain"' in template
```

- [ ] **Step 2: Run the fast suite and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe testing\run_fast_tests.py
```

Expected: the new test fails because `hybrid-month-calendar`, `ws.calendar.months`, and `ws.hybrid_month_summary.months` are still present.

- [ ] **Step 3: Delete the complete calendar template branch**

In `netbox_contract/templates/netbox_contract/revenue_contract.html`, delete the entire block beginning with:

```django
{% if object.contract_type == 'hybrid' %}
```

and ending at the matching `{% endif %}` immediately before:

```django
<div class="card mb-3">
  <div class="card-header">
    <ul class="nav nav-tabs card-header-tabs" role="tablist">
```

The retained boundary after deletion must be:

```django
  {% endif %}

  <div class="card mb-3">
    <div class="card-header">
      <ul class="nav nav-tabs card-header-tabs" role="tablist">
```

The first `{% endif %}` above closes the preceding order-lanes component. Do not remove the order-lanes component itself.

- [ ] **Step 4: Update the existing integrated template assertions**

In `test_revenue_contract_template_uses_unambiguous_rate_labels` within `netbox_contract/tests/test_revenue_models.py`, replace:

```python
self.assertIn('hybrid-month-calendar', template)
self.assertIn('ws.hybrid_month_summary', template)
self.assertIn('<details class="card mb-3" id="hybrid-month-calendar">', template)
self.assertNotIn('<details class="card mb-3" id="hybrid-month-calendar" open', template)
```

with:

```python
self.assertNotIn('hybrid-month-calendar', template)
self.assertNotIn('ws.hybrid_month_summary.months', template)
self.assertNotIn('ws.calendar.months', template)
```

Keep the existing assertions for `display.mixed_lanes`, `display.periodic_matrix`, the full-chain detail, and the absence of receivable-plan actions.

- [ ] **Step 5: Run the fast suite and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe testing\run_fast_tests.py
```

Expected: all fast tests pass.

- [ ] **Step 6: Run static checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m ruff check netbox_contract/tests/test_revenue_plan_ui_visibility.py
.\.venv\Scripts\python.exe -m ruff check --select F821,F822,F823 netbox_contract/tests/test_revenue_models.py
git diff --check
```

Expected: both Ruff commands report `All checks passed!`; `git diff --check` reports no whitespace errors.

- [ ] **Step 7: Commit only the calendar-removal change when repository baseline permits**

Before staging, confirm that these files do not contain unrelated user changes. If the files are still wholly untracked as part of the larger revenue-contract implementation, leave them uncommitted and report that constraint instead of committing unrelated work.

When the files have an established tracked baseline, run:

```powershell
git add -- netbox_contract/templates/netbox_contract/revenue_contract.html netbox_contract/tests/test_revenue_plan_ui_visibility.py netbox_contract/tests/test_revenue_models.py
git commit -m "feat: remove contract receivable calendar"
```

### Task 2: Verify every contract type remotely

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: Run the NetBox system check**

Run on the remote server:

```bash
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 2: Render one detail page for each contract type**

Use a read-only Django test client or the existing signed-in browser session to request one `milestone`, `recurring`, `framework`, `order`, and `hybrid` contract detail page.

For each response, verify:

```text
HTTP 200
No "hybrid-month-calendar" element
No "周期应收日历" or "混合计费月度汇总" heading
The receivable timeline and full-chain detail remain present
```

- [ ] **Step 3: Restart and verify services**

Run:

```bash
sudo systemctl restart netbox netbox-rq
systemctl is-active netbox netbox-rq nginx postgresql redis-server
```

Expected: all five services report `active`.
