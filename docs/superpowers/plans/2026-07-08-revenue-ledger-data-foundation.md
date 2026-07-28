# Revenue Ledger Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first-stage Revenue namespace data foundation for income contracts, receivables, invoices, receipts, prepayments, adjustments, sync logs, CRUD pages, filters, navigation, API, and core validation.

**Architecture:** Keep the implementation inside the existing `netbox_contract` plugin and follow its current large-file NetBox plugin patterns. Add new `Revenue*` models independent from existing `Contract` and `Invoice` models, then expose them through the same NetBox generic view, table, filter, form, URL, navigation, and API conventions already used by the plugin.

**Tech Stack:** Django models/migrations, NetBoxModel, django-filter, django-tables2, NetBox generic views, DRF NetBoxModelSerializer/ViewSet, pytest.

---

### Task 1: Revenue Model Layer

**Files:**
- Modify: `netbox_contract/models.py`
- Create: `netbox_contract/migrations/0048_revenue_data_foundation.py`
- Test: `netbox_contract/tests/test_revenue_models.py`

- [ ] Add choice sets for all Revenue statuses and types.
- [ ] Add models from the approved design using `Revenue` prefixes.
- [ ] Add database constraints for unique keys, amount non-negativity, relationship consistency, and conditional billing-rule fields.
- [ ] Add `clean()` validation for cross-row amount limits that cannot be represented by simple `CheckConstraint`.
- [ ] Add tests for invoice line closure, invoice mapping limits, receipt allocation limits, prepayment allocation limits, and field mutual exclusion.

### Task 2: Forms, Tables, Filters, Views, URLs

**Files:**
- Modify: `netbox_contract/forms.py`
- Modify: `netbox_contract/tables.py`
- Modify: `netbox_contract/filtersets.py`
- Modify: `netbox_contract/views.py`
- Modify: `netbox_contract/urls.py`
- Modify: `netbox_contract/navigation.py`

- [ ] Add basic NetBox model forms for each Revenue model.
- [ ] Add list tables with high-signal columns and action buttons.
- [ ] Add filter sets and filter forms for common lookup fields.
- [ ] Add generic object/list/edit/delete/bulk views.
- [ ] Add URL routes and changelog routes.
- [ ] Add navigation group entries under the existing Contracts plugin menu.

### Task 3: API Layer

**Files:**
- Modify: `netbox_contract/api/serializers.py`
- Modify: `netbox_contract/api/views.py`
- Modify: `netbox_contract/api/urls.py`

- [ ] Add nested serializers for frequently referenced Revenue objects.
- [ ] Add full serializers for all Revenue models.
- [ ] Add NetBoxModelViewSet classes and router registrations.
- [ ] Keep serializers simple in phase one; use model `clean()` for business invariants.

### Task 4: Verification

**Files:**
- Modify: `netbox_contract/tests/test_revenue_models.py`

- [ ] Run the focused Revenue model tests.
- [ ] Run existing plugin tests that cover model imports and views.
- [ ] Run Python compile checks if the full NetBox test environment is unavailable.
- [ ] Fix any failures caused by imports, URL names, or serializer references.

### Self-Review

Coverage: The plan implements the approved first-stage data foundation, not automatic billing jobs, external sync jobs, approval workflows, or dashboards.

Placeholders: None. Deferred features are explicitly outside phase one.

Type consistency: All new runtime objects use the `Revenue` prefix and remain independent from existing purchase/expense-side `Contract` and `Invoice` models.
