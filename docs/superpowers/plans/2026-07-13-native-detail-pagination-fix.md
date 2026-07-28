# Native Detail Pagination Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace native `django_tables2` pagination on contract and invoice detail sub-tables with independent NetBox-style pagination.

**Architecture:** Add focused parsing/configuration helpers in `views.py`, then explicitly paginate each detail sub-table with a unique page parameter and shared validated page size. Add a reusable pagination include so both detail templates render consistent controls while preserving sibling table state.

**Tech Stack:** Python, Django, django-tables2, Django templates, NetBox plugin views, unittest/pytest.

---

## File Map

- Create `netbox_contract/tests/test_detail_pagination.py`: focused regression tests for parsing, table configuration, and template wiring.
- Modify `netbox_contract/views.py`: page-size validation and explicit independent pagination for `ContractView` and `InvoiceView`.
- Create `netbox_contract/templates/netbox_contract/inc/detail_table_pagination.html`: shared NetBox pagination footer.
- Modify `netbox_contract/templates/netbox_contract/contract.html`: table containers and pagination footers for four nested tables.
- Modify `netbox_contract/templates/netbox_contract/invoice.html`: table containers and pagination footers for two nested tables.

### Task 1: Pagination helper behavior

**Files:**
- Create: `netbox_contract/tests/test_detail_pagination.py`
- Modify: `netbox_contract/views.py`

- [ ] **Step 1: Write failing helper tests**

```python
from django.test import SimpleTestCase

from netbox_contract.views import _detail_per_page, _detail_page


class DetailPaginationParameterTestCase(SimpleTestCase):
    def test_per_page_accepts_supported_values(self):
        self.assertEqual(_detail_per_page({'per_page': '100'}), 100)

    def test_per_page_rejects_invalid_and_unsupported_values(self):
        for value in ('invalid', '0', '-25', '26'):
            with self.subTest(value=value):
                self.assertEqual(_detail_per_page({'per_page': value}), 25)

    def test_page_accepts_positive_integer_and_defaults_invalid_values(self):
        self.assertEqual(_detail_page({'assignments_page': '3'}, 'assignments_page'), 3)
        for value in ('invalid', '0', '-1'):
            with self.subTest(value=value):
                self.assertEqual(_detail_page({'assignments_page': value}, 'assignments_page'), 1)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest netbox_contract/tests/test_detail_pagination.py -q`

Expected: collection fails because `_detail_per_page` and `_detail_page` do not exist.

- [ ] **Step 3: Add minimal parsing helpers near the imports in `views.py`**

```python
DETAIL_PAGE_SIZES = (25, 50, 100, 250, 500)


def _detail_per_page(params):
    try:
        value = int(params.get('per_page', 25))
    except (TypeError, ValueError):
        return 25
    return value if value in DETAIL_PAGE_SIZES else 25


def _detail_page(params, key):
    try:
        value = int(params.get(key, 1))
    except (TypeError, ValueError):
        return 1
    return value if value > 0 else 1
```

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python -m pytest netbox_contract/tests/test_detail_pagination.py -q`

Expected: 3 tests pass.

### Task 2: Independent backend pagination

**Files:**
- Modify: `netbox_contract/tests/test_detail_pagination.py`
- Modify: `netbox_contract/views.py:198-235,307-324`

- [ ] **Step 1: Add source-level regression assertions**

```python
from pathlib import Path


class DetailPaginationWiringTestCase(SimpleTestCase):
    def test_detail_views_use_independent_page_parameters(self):
        source = (Path(__file__).parents[1] / 'views.py').read_text(encoding='utf-8')
        for key in (
            'invoice_lines_page', 'assignments_page', 'children_page',
            'invoices_page', 'contracts_page',
        ):
            self.assertIn(f"_detail_page(request.GET, '{key}')", source)
        self.assertIn("'detail_per_page': per_page", source)
        self.assertIn("'detail_page_sizes': DETAIL_PAGE_SIZES", source)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest netbox_contract/tests/test_detail_pagination.py::DetailPaginationWiringTestCase -q`

Expected: failure because explicit independent pagination is absent.

- [ ] **Step 3: Explicitly paginate each table**

For each table in `ContractView.get_extra_context()` and `InvoiceView.get_extra_context()`, retain existing column hiding and replace `table.configure(request)` with:

```python
table.configure(request, paginate=False)
table.paginate(page=_detail_page(request.GET, '<table_page_key>'), per_page=per_page)
```

Initialize once per view and expose shared template state:

```python
per_page = _detail_per_page(request.GET)

# return context additions
'detail_per_page': per_page,
'detail_page_sizes': DETAIL_PAGE_SIZES,
```

Use the exact keys from the design. Do not modify revenue-contract context code or unrelated view classes.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `python -m pytest netbox_contract/tests/test_detail_pagination.py -q`

Expected: all helper and wiring tests pass.

### Task 3: Shared NetBox pagination footer

**Files:**
- Modify: `netbox_contract/tests/test_detail_pagination.py`
- Create: `netbox_contract/templates/netbox_contract/inc/detail_table_pagination.html`

- [ ] **Step 1: Add failing template contract test**

```python
class DetailPaginationTemplateTestCase(SimpleTestCase):
    def test_shared_footer_contains_netbox_controls(self):
        path = Path(__file__).parents[1] / 'templates/netbox_contract/inc/detail_table_pagination.html'
        text = path.read_text(encoding='utf-8')
        self.assertIn('table.page.has_previous', text)
        self.assertIn('table.page.start_index', text)
        self.assertIn('table.paginator.count', text)
        self.assertIn('detail_page_sizes', text)
        self.assertIn('page_param', text)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest netbox_contract/tests/test_detail_pagination.py::DetailPaginationTemplateTestCase -q`

Expected: failure because the include does not exist.

- [ ] **Step 3: Create the shared footer**

Create a `card-footer` guarded by `{% if table.page %}`. Render previous/next controls and page numbers using `table.page` and `table.paginator.page_range`; build links from `page_param`, `detail_per_page`, and explicit sibling page values passed by each include call. Render `显示 start-end 共 count` and a dropdown iterating `detail_page_sizes`. Page-size links keep only `per_page`, intentionally resetting all page numbers.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `python -m pytest netbox_contract/tests/test_detail_pagination.py::DetailPaginationTemplateTestCase -q`

Expected: pass.

### Task 4: Wire contract and invoice templates

**Files:**
- Modify: `netbox_contract/tests/test_detail_pagination.py`
- Modify: `netbox_contract/templates/netbox_contract/contract.html`
- Modify: `netbox_contract/templates/netbox_contract/invoice.html`

- [ ] **Step 1: Add failing template wiring tests**

```python
    def test_detail_templates_hide_native_pagination_and_use_unique_parameters(self):
        root = Path(__file__).parents[1] / 'templates/netbox_contract'
        contract = (root / 'contract.html').read_text(encoding='utf-8')
        invoice = (root / 'invoice.html').read_text(encoding='utf-8')
        self.assertIn('.detail-table-container ul.pagination', contract)
        self.assertIn('.detail-table-container ul.pagination', invoice)
        for key in ('invoice_lines_page', 'assignments_page', 'children_page', 'invoices_page'):
            self.assertIn(f'page_param=\"{key}\"', contract)
        for key in ('invoice_lines_page', 'contracts_page'):
            self.assertIn(f'page_param=\"{key}\"', invoice)
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest netbox_contract/tests/test_detail_pagination.py::DetailPaginationTemplateTestCase::test_detail_templates_hide_native_pagination_and_use_unique_parameters -q`

Expected: failure because containers and includes are absent.

- [ ] **Step 3: Update both templates**

Add an `extra_styles` block hiding `.detail-table-container > .table-responsive + ul.pagination` or the verified native pagination selector. Wrap every nested `{% render_table %}` in a uniquely identified `.detail-table-container`, then include `netbox_contract/inc/detail_table_pagination.html` immediately afterward with `table=<context table>` and the correct `page_param`. Pass current sibling page numbers so navigation in one table retains the others.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest netbox_contract/tests/test_detail_pagination.py -q`

Expected: all pagination regression tests pass.

### Task 5: Verification

**Files:**
- Verify only; no planned production changes.

- [ ] **Step 1: Check syntax**

Run: `python -m py_compile netbox_contract/views.py netbox_contract/tests/test_detail_pagination.py`

Expected: exit code 0.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest netbox_contract/tests/test_detail_pagination.py -q`

Expected: all tests pass with no warnings introduced by this change.

- [ ] **Step 3: Run view regression tests**

Run: `python -m pytest netbox_contract/tests/test_views.py -q`

Expected: all existing view tests pass. If the local NetBox test environment is unavailable, record the exact environment/import failure and retain the successful syntax and standalone checks.

- [ ] **Step 4: Inspect the scoped diff**

Run: `git diff --check && git diff -- netbox_contract/views.py netbox_contract/templates/netbox_contract/contract.html netbox_contract/templates/netbox_contract/invoice.html netbox_contract/templates/netbox_contract/inc/detail_table_pagination.html netbox_contract/tests/test_detail_pagination.py`

Expected: no whitespace errors; diff contains only the planned pagination changes within already-modified files.

- [ ] **Step 5: Commit only pagination files if requested**

```powershell
git add -- netbox_contract/views.py netbox_contract/templates/netbox_contract/contract.html netbox_contract/templates/netbox_contract/invoice.html netbox_contract/templates/netbox_contract/inc/detail_table_pagination.html netbox_contract/tests/test_detail_pagination.py
git commit -m "fix: 修正详情页原生分页"
```

Because `views.py` already contains unrelated user changes, do not stage or commit it wholesale without first isolating the pagination hunks or receiving explicit approval.
