# Revenue Contract Status Color Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make revenue contract status badges use the colors declared by `RevenueContractStatusChoices`, including green for effective contracts.

**Architecture:** Add the standard NetBox choice-color method to `RevenueContract`. Keep the table and templates unchanged so `ChoiceFieldColumn` obtains the color through NetBox's normal `get_<field>_color()` convention.

**Tech Stack:** Python, Django models, NetBox 4.6 `ChoiceSet` and `ChoiceFieldColumn`, unittest/pytest.

---

### Task 1: Add a failing revenue contract status-color regression test

**Files:**
- Modify: `netbox_contract/tests/test_revenue_models.py`
- Test: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Write the failing test**

Add this test to the existing no-database `RevenueFormLabelLocalizationTestCase`:

```python
def test_revenue_contract_status_colors_follow_choice_set(self):
    contract = RevenueContract()

    for status, _label, expected_color in RevenueContractStatusChoices.CHOICES:
        with self.subTest(status=status):
            contract.status = status
            self.assertEqual(contract.get_status_color(), expected_color)

    contract.status = 'effective'
    self.assertEqual(contract.get_status_color(), 'green')
```

Import `RevenueContractStatusChoices` from `netbox_contract.models` in the existing model import block.

- [ ] **Step 2: Run the focused test and verify RED**

Run on the remote NetBox runtime:

```bash
/opt/netbox/venv/bin/python manage.py test \
  netbox_contract.tests.test_revenue_models.RevenueFormLabelLocalizationTestCase.test_revenue_contract_status_colors_follow_choice_set \
  --keepdb -v 2
```

Expected: FAIL with `AttributeError: 'RevenueContract' object has no attribute 'get_status_color'`.

### Task 2: Add the standard NetBox model color interface

**Files:**
- Modify: `netbox_contract/models.py`
- Test: `netbox_contract/tests/test_revenue_models.py`

- [ ] **Step 1: Implement the minimal model method**

Add the method to `RevenueContract` near `get_absolute_url()`:

```python
def get_status_color(self):
    return RevenueContractStatusChoices.colors.get(self.status)
```

- [ ] **Step 2: Run the focused test and verify GREEN**

Run:

```bash
/opt/netbox/venv/bin/python manage.py test \
  netbox_contract.tests.test_revenue_models.RevenueFormLabelLocalizationTestCase.test_revenue_contract_status_colors_follow_choice_set \
  --keepdb -v 2
```

Expected: PASS.

- [ ] **Step 3: Run local regression checks**

Run:

```powershell
.\.venv\Scripts\python.exe testing\run_fast_tests.py
python -m py_compile netbox_contract\models.py netbox_contract\tests\test_revenue_models.py
git diff --check -- netbox_contract/models.py netbox_contract/tests/test_revenue_models.py
```

Expected: all commands exit zero.

- [ ] **Step 4: Run remote NetBox regression checks**

Run:

```bash
/opt/netbox/venv/bin/python manage.py test netbox_contract.tests.test_revenue_models --keepdb -v 1
/opt/netbox/venv/bin/python manage.py check
/opt/netbox/venv/bin/python manage.py makemigrations netbox_contract --check --dry-run
```

Expected: the full test module passes, the system check reports no issues, and no migration changes are detected.

- [ ] **Step 5: Verify the rendered badge**

Restart `netbox` and `netbox-rq`, open the revenue contract list, and inspect an effective contract.

Expected: the badge text is `生效` and its class includes `text-bg-green`; the other six states follow `RevenueContractStatusChoices`.

- [ ] **Step 6: Preserve the shared dirty worktree**

Do not stage or commit `models.py` or the untracked revenue tests unless the user explicitly requests a combined commit. Report the exact modified files and verification evidence.
