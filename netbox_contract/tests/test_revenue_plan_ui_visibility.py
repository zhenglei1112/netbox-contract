from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_revenue_contract_hides_receivable_plan_primary_actions():
    template = (
        PACKAGE_ROOT / 'templates' / 'netbox_contract' / 'revenue_contract.html'
    ).read_text(encoding='utf-8-sig')

    assert '应收计划' not in template
    assert '计划—当前—实际三线' not in template
    assert 'receivable-plan-tracks' not in template
    assert 'revenuereceivableplan_add' not in template
    assert '生成应收' in template


def test_revenue_navigation_hides_plan_and_version_entries():
    navigation = (PACKAGE_ROOT / 'navigation.py').read_text(encoding='utf-8-sig')

    assert "('revenuereceivableplan'," not in navigation
    assert "('revenuereceivableplanversion'," not in navigation
    assert "('revenuetriggerrecord'," in navigation
    assert "('revenueadjustmentrecord'," in navigation


def test_revenue_contract_context_uses_timeline_view_profile():
    views = (PACKAGE_ROOT / 'views.py').read_text(encoding='utf-8-sig')

    assert 'build_timeline_view_profile' in views
    assert 'default_timeline_filter' in views
    assert 'unified_timeline.update(timeline_profile)' in views


def test_revenue_timeline_uses_contextual_scope_labels():
    template = (
        PACKAGE_ROOT / 'templates' / 'netbox_contract' / 'revenue_contract.html'
    ).read_text(encoding='utf-8-sig')

    assert '{{ timeline.title }}' in template
    assert '{{ timeline.description }}' in template
    assert '{{ timeline.summary_label }}' in template
    assert '{{ timeline.empty_filter_message }}' in template


def test_revenue_contract_status_badge_uses_choice_color():
    template = (
        PACKAGE_ROOT / 'templates' / 'netbox_contract' / 'revenue_contract.html'
    ).read_text(encoding='utf-8-sig')

    assert '{% badge object.get_status_display bg_color=object.get_status_color %}' in template
    assert 'class="badge text-bg-secondary">{{ object.get_status_display' not in template


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


def test_revenue_forms_use_explicit_business_field_whitelists():
    source = (PACKAGE_ROOT / 'forms.py').read_text(encoding='utf-8-sig')

    assert '_REVENUE_FORM_FIELDS = {' in source
    revenue_source = source.split('_REVENUE_FORM_FIELDS =', 1)[1]
    assert "'fields': '__all__'" not in revenue_source
    assert "fields = '__all__'" not in revenue_source
    assert "'fields': _REVENUE_FORM_FIELDS[_revenue_model]" in revenue_source
    assert 'fields = _REVENUE_FORM_FIELDS[RevenueOrder]' in revenue_source
    assert 'fields = _REVENUE_FORM_FIELDS[RevenueContractLine]' in revenue_source


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
    assert 'def _localize_framework_labels(self):' in form_source
    assert 'self._localize_framework_labels()' in form_source
    assert "changelog_field = self.fields.get('changelog_message')" in form_source
    assert "changelog_field.label = _('变更说明')" in form_source
    assert '(RevenueModelForm,)' in form_source
    assert 'class RevenueOrderForm(RevenueModelForm):' in form_source
    assert 'class RevenueContractLineForm(RevenueModelForm):' in form_source
