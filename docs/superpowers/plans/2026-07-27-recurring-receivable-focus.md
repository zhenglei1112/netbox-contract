# Recurring Receivable Focus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make recurring revenue contracts open on a focused receivable timeline containing overdue, pending-trigger, and next-30-day items, while leaving the periodic matrix as the full-year view.

**Architecture:** Extend the pure timeline service with one compositional `attention` filter, then let the revenue contract context choose that filter only for recurring contracts. Put presentation strings and empty-state text in the context so the shared template remains contract-type-aware without duplicating markup.

**Tech Stack:** Python 3, Django/NetBox views and templates, pytest/unittest, Ruff.

---

## File Structure

- `netbox_contract/services/revenue_timeline.py`: owns supported timeline filters, membership rules, counts, and filtered totals.
- `netbox_contract/tests/test_revenue_timeline.py`: pure unit coverage for the new filter boundaries and aggregation.
- `netbox_contract/views.py`: chooses contract-type defaults, recovers from invalid query parameters, builds filter links, and supplies presentation metadata.
- `netbox_contract/tests/test_revenue_models.py`: NetBox-integrated context tests for recurring and non-recurring contracts.
- `netbox_contract/templates/netbox_contract/revenue_contract.html`: renders the dynamic title, scope explanation, current-filter label, and contextual empty state.
- `netbox_contract/tests/test_revenue_plan_ui_visibility.py`: fast source-level template regression checks that run without NetBox.

### Task 1: Add the pure `attention` timeline filter

**Files:**
- Modify: `netbox_contract/services/revenue_timeline.py:6`
- Modify: `netbox_contract/services/revenue_timeline.py:419-437`
- Test: `netbox_contract/tests/test_revenue_timeline.py`

- [ ] **Step 1: Write the failing service test**

Add this method to `RevenueTimelineTests`:

```python
def test_attention_filter_combines_overdue_pending_and_next_30_days(self):
    events = [
        _event(
            'overdue-open',
            receivable_date=date(2026, 7, 1),
            due_date=date(2026, 7, 14),
            net=100,
            received=20,
        ),
        _event(
            'overdue-paid',
            receivable_date=date(2026, 7, 1),
            due_date=date(2026, 7, 14),
            net=100,
            received=100,
            status='paid',
            risk='success',
        ),
        _event(
            'today',
            receivable_date=self.today,
            due_date=self.today,
            net=40,
            received=10,
        ),
    ]
    tracks = [
        _track(
            'day30',
            planned_date=date(2026, 8, 14),
            effective_due_date=date(2026, 8, 14),
            amount=30,
        ),
        _track(
            'day31',
            planned_date=date(2026, 8, 15),
            effective_due_date=date(2026, 8, 15),
            amount=31,
        ),
        _track('pending', trigger_type='trigger_offset', amount=50),
    ]

    result = build_revenue_timeline(
        events,
        {'tracks': tracks},
        today=self.today,
        filter_key='attention',
    )

    identities = {
        node.get('event_key') or node['plan'].plan_code
        for node in result['nodes']
    }
    self.assertEqual(identities, {'overdue-open', 'today', 'day30', 'pending'})
    self.assertEqual(result['filter_counts']['attention'], 4)
    self.assertEqual(result['visible_totals']['receivable_amount'], Decimal('140'))
    self.assertEqual(result['visible_totals']['unreceived_amount'], Decimal('110'))
    self.assertEqual(result['visible_totals']['planned_amount'], Decimal('80'))
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider netbox_contract/tests/test_revenue_timeline.py::RevenueTimelineTests::test_attention_filter_combines_overdue_pending_and_next_30_days
```

Expected: FAIL with `ValueError: Unsupported timeline filter: attention`.

- [ ] **Step 3: Implement the minimal filter**

Change the filter set and `_matches_filter`:

```python
FILTER_KEYS = frozenset({
    'all',
    'attention',
    'overdue',
    'next_30_days',
    'next_90_days',
    'pending_trigger',
})


def _matches_filter(node, filter_key, today):
    if filter_key == 'all':
        return True
    if filter_key == 'pending_trigger':
        return node['date_certainty'] == 'pending_trigger'
    if filter_key == 'attention':
        return (
            _matches_filter(node, 'overdue', today)
            or _matches_filter(node, 'pending_trigger', today)
            or _matches_filter(node, 'next_30_days', today)
        )

    timeline_date = node['timeline_date']
    if timeline_date is None:
        return False
    if filter_key == 'overdue':
        due_date = node['due_date']
        return (
            node['kind'] == 'formed'
            and due_date is not None
            and due_date < today
            and node['unreceived_amount'] > ZERO
        )

    days = (timeline_date - today).days
    if filter_key == 'next_30_days':
        return 0 <= days <= 30
    return 0 <= days <= 90
```

- [ ] **Step 4: Run service tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider netbox_contract/tests/test_revenue_timeline.py
```

Expected: all timeline tests pass.

- [ ] **Step 5: Commit the service behavior**

```powershell
git add -- netbox_contract/services/revenue_timeline.py netbox_contract/tests/test_revenue_timeline.py
git commit -m "feat: add focused receivable timeline filter"
```

### Task 2: Select the recurring-contract default in the view context

**Files:**
- Modify: `netbox_contract/views.py:2020-2057`
- Test: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Write failing context tests**

Add these methods to the existing revenue contract test class that owns `self.contract`:

```python
def test_recurring_contract_defaults_to_attention_timeline(self):
    self.contract.contract_type = 'recurring'
    self.contract.save(update_fields=['contract_type'])

    context = views._revenue_contract_context(
        RequestFactory().get('/'),
        self.contract,
    )
    timeline = context['revenue_timeline']

    self.assertEqual(timeline['active_filter'], 'attention')
    self.assertEqual(timeline['title'], '近期应收动态')
    self.assertEqual(timeline['summary_label'], '当前筛选汇总')
    self.assertEqual(timeline['filters'][0]['key'], 'attention')
    self.assertTrue(timeline['filters'][0]['is_active'])


def test_non_recurring_contract_keeps_all_timeline_default(self):
    self.contract.contract_type = 'milestone'
    self.contract.save(update_fields=['contract_type'])

    context = views._revenue_contract_context(
        RequestFactory().get('/'),
        self.contract,
    )
    timeline = context['revenue_timeline']

    self.assertEqual(timeline['active_filter'], 'all')
    self.assertEqual(timeline['title'], '综合应收时间轴')
    self.assertNotIn('attention', [item['key'] for item in timeline['filters']])


def test_invalid_recurring_timeline_filter_returns_to_attention(self):
    self.contract.contract_type = 'recurring'
    self.contract.save(update_fields=['contract_type'])

    context = views._revenue_contract_context(
        RequestFactory().get('/?timeline_window=invalid'),
        self.contract,
    )

    self.assertEqual(context['revenue_timeline']['active_filter'], 'attention')
```

- [ ] **Step 2: Run the context tests and verify RED**

Run on the configured NetBox environment:

```bash
python manage.py test netbox_contract.tests.test_revenue_models.RevenueModelValidationTestCase.test_recurring_contract_defaults_to_attention_timeline netbox_contract.tests.test_revenue_models.RevenueModelValidationTestCase.test_non_recurring_contract_keeps_all_timeline_default netbox_contract.tests.test_revenue_models.RevenueModelValidationTestCase.test_invalid_recurring_timeline_filter_returns_to_attention
```

Expected: failures showing recurring contracts still use `all` and the presentation keys are absent.

- [ ] **Step 3: Implement contract-type defaults and metadata**

Replace the timeline-filter setup in `_revenue_contract_context` with:

```python
is_recurring_contract = instance.contract_type == 'recurring'
default_timeline_filter = 'attention' if is_recurring_contract else 'all'
timeline_filter = request.GET.get('timeline_window') or default_timeline_filter
try:
    unified_timeline = build_revenue_timeline(
        workspace['chain_rows'],
        {},
        filter_key=timeline_filter,
        contract_lines=workspace['contract_lines'],
        billing_rules=workspace['billing_rules'],
        trigger_records=workspace['trigger_records'],
    )
except ValueError:
    timeline_filter = default_timeline_filter
    unified_timeline = build_revenue_timeline(
        workspace['chain_rows'],
        {},
        filter_key=timeline_filter,
        contract_lines=workspace['contract_lines'],
        billing_rules=workspace['billing_rules'],
        trigger_records=workspace['trigger_records'],
    )

timeline_filters = [
    ('all', '全部'),
    ('overdue', '已逾期'),
    ('next_30_days', '未来30天'),
    ('next_90_days', '未来90天'),
    ('pending_trigger', '待触发'),
]
if is_recurring_contract:
    timeline_filters.insert(0, ('attention', '需关注'))

unified_timeline.update({
    'title': '近期应收动态' if is_recurring_contract else '综合应收时间轴',
    'description': (
        '集中查看逾期、待触发及未来30天应收；完整年度计划请查看周期账单矩阵。'
        if is_recurring_contract
        else ''
    ),
    'summary_label': '当前筛选汇总',
    'empty_filter_message': (
        '当前没有逾期、待触发或未来30天应收；可切换到“全部”查看完整计划。'
        if is_recurring_contract and timeline_filter == 'attention'
        else '当前筛选范围内暂无应收节点。'
    ),
})
unified_timeline['filters'] = []
for key, label in timeline_filters:
    query = request.GET.copy()
    query['timeline_window'] = key
    unified_timeline['filters'].append({
        'key': key,
        'label': label,
        'count': unified_timeline['filter_counts'][key],
        'is_active': key == timeline_filter,
        'query_string': query.urlencode(),
    })
```

- [ ] **Step 4: Run the focused context tests and verify GREEN**

Run:

```bash
python manage.py test netbox_contract.tests.test_revenue_models.RevenueModelValidationTestCase.test_recurring_contract_defaults_to_attention_timeline netbox_contract.tests.test_revenue_models.RevenueModelValidationTestCase.test_non_recurring_contract_keeps_all_timeline_default netbox_contract.tests.test_revenue_models.RevenueModelValidationTestCase.test_invalid_recurring_timeline_filter_returns_to_attention
```

Expected: all three tests pass.

- [ ] **Step 5: Commit the context behavior**

```powershell
git add -- netbox_contract/views.py netbox_contract/tests/test_revenue_models.py
git commit -m "feat: focus recurring contract timeline"
```

### Task 3: Explain timeline scope in the shared template

**Files:**
- Modify: `netbox_contract/templates/netbox_contract/revenue_contract.html:211-267`
- Modify: `netbox_contract/tests/test_revenue_plan_ui_visibility.py`

- [ ] **Step 1: Write the failing fast template test**

Add:

```python
def test_revenue_timeline_uses_contextual_scope_labels():
    template = (
        PACKAGE_ROOT / 'templates' / 'netbox_contract' / 'revenue_contract.html'
    ).read_text(encoding='utf-8-sig')

    assert '{{ timeline.title }}' in template
    assert '{{ timeline.description }}' in template
    assert '{{ timeline.summary_label }}' in template
    assert '{{ timeline.empty_filter_message }}' in template
    assert '<h5 class="card-title mb-0">综合应收时间轴</h5>' not in template
```

- [ ] **Step 2: Run the template test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider netbox_contract/tests/test_revenue_plan_ui_visibility.py::test_revenue_timeline_uses_contextual_scope_labels
```

Expected: FAIL because the title and labels are still hard-coded or absent.

- [ ] **Step 3: Render the context-driven title, description, summary label, and empty state**

Change the timeline header and body to use:

```django
<h5 class="card-title mb-0">{{ timeline.title }}</h5>
<div class="revenue-subtle">{{ timeline.totals.formed_count }}笔已形成 / {{ timeline.totals.planned_count }}笔待形成 / {{ timeline.totals.pending_trigger_count }}笔待条件触发</div>
{% if timeline.description %}
  <div class="revenue-subtle">{{ timeline.description }}</div>
{% endif %}
```

Immediately before the KPI grid, add:

```django
<div class="revenue-subtle mb-2">{{ timeline.summary_label }}</div>
```

Replace the filtered empty state with:

```django
{% elif timeline.has_data %}
  <div class="card-body text-muted">{{ timeline.empty_filter_message }}</div>
```

- [ ] **Step 4: Run fast tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe testing\run_fast_tests.py
```

Expected: all fast revenue tests pass.

- [ ] **Step 5: Commit the template behavior**

```powershell
git add -- netbox_contract/templates/netbox_contract/revenue_contract.html netbox_contract/tests/test_revenue_plan_ui_visibility.py
git commit -m "feat: clarify recurring timeline scope"
```

### Task 4: Verify regression safety and deploy

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: Run the complete local fast suite**

```powershell
.\.venv\Scripts\python.exe testing\run_fast_tests.py
```

Expected: all tests pass with zero failures.

- [ ] **Step 2: Run Ruff on every changed Python file**

```powershell
.\.venv\Scripts\python.exe -m ruff check netbox_contract/services/revenue_timeline.py netbox_contract/views.py netbox_contract/tests/test_revenue_timeline.py netbox_contract/tests/test_revenue_models.py netbox_contract/tests/test_revenue_plan_ui_visibility.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Review the final patch scope**

```powershell
git diff --check
git status --short
git log -4 --oneline
```

Expected: no whitespace errors; only the intended timeline commits are new. Existing unrelated dirty files remain untouched.

- [ ] **Step 4: Update the remote checkout and run NetBox-integrated tests**

After the intended commits are available to the remote checkout, run:

```bash
cd /opt/netbox/netbox
/opt/netbox/venv/bin/python manage.py test netbox_contract.tests.test_revenue_models
/opt/netbox/venv/bin/python manage.py check
```

Expected: revenue model tests pass and system check reports no issues. This change has no migration.

- [ ] **Step 5: Restart application services and smoke-test contract detail pages**

```bash
sudo systemctl restart netbox netbox-rq
sudo systemctl is-active netbox netbox-rq nginx postgresql redis-server
```

Expected: each service reports `active`. Open at least one recurring and one non-recurring revenue contract detail page; verify the recurring page defaults to “需关注” and the non-recurring page retains “全部”.
