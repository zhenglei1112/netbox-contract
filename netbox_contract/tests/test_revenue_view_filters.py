from decimal import Decimal
from types import SimpleNamespace

import pytest

from netbox_contract.services.revenue_view_filters import (
    build_timeline_view_profile,
    filter_mixed_lanes,
    filter_order_lanes,
    filter_periodic_matrix,
    filter_stage_timeline,
)


D = Decimal


def test_recurring_timeline_profile_defaults_to_attention():
    profile = build_timeline_view_profile('recurring')

    assert profile['default_filter'] == 'attention'
    assert profile['filters'][0] == ('attention', '需关注')
    assert profile['title'] == '近期应收动态'
    assert '未来30天' in profile['description']
    assert profile['summary_label'] == '当前筛选汇总'
    assert '切换到“全部”' in profile['empty_filter_message']


def test_non_recurring_timeline_profile_keeps_all_default():
    profile = build_timeline_view_profile('milestone')

    assert profile['default_filter'] == 'all'
    assert ('attention', '需关注') not in profile['filters']
    assert profile['title'] == '综合应收时间轴'
    assert profile['description'] == ''
    assert profile['empty_filter_message'] == '当前筛选范围内暂无应收节点。'


def test_recurring_non_attention_empty_state_uses_generic_message():
    profile = build_timeline_view_profile('recurring', active_filter='all')

    assert profile['empty_filter_message'] == '当前筛选范围内暂无应收节点。'


def cell(period, amount, *, status='generated', risk='muted'):
    return {
        'billing_period': period,
        'status': status,
        'risk_level': risk,
        'receivable_total': D(amount),
        'invoiced_total': D(amount),
        'receipt_total': D('0'),
        'adjustment_total': D('0'),
        'overdue_total': D(amount) if status == 'overdue' else D('0'),
        'planned_amount': D('0'),
        'event_count': 1,
        'events': [{'id': period, 'event_dom_id': f'event-{period}'}],
    }


MONTHS = [
    {'billing_period': '2026-01', 'label': '1月'},
    {'billing_period': '2026-02', 'label': '2月'},
]


def test_periodic_matrix_anomaly_filter_keeps_only_risk_cells_and_recalculates_totals():
    source = {
        'months': MONTHS,
        'rows': [
            {
                'charge_item': 'A',
                'cells': [cell('2026-01', '10'), cell('2026-02', '20', status='overdue', risk='danger')],
            },
            {'charge_item': 'B', 'cells': [cell('2026-01', '30'), cell('2026-02', '40')]},
        ],
    }

    result = filter_periodic_matrix(source, anomalies_only=True)

    assert result['active_count'] == 1
    assert [month['billing_period'] for month in result['months']] == ['2026-02']
    assert len(result['rows']) == 1
    assert result['totals']['receivable_total'] == D('20')
    assert result['totals']['risk_cells'] == 1
    assert len(source['rows'][0]['cells']) == 2


def test_periodic_matrix_all_mode_recalculates_all_visible_cells():
    source = {'months': MONTHS, 'rows': [{'cells': [cell('2026-01', '10'), cell('2026-02', '20')]}]}
    result = filter_periodic_matrix(source)
    assert result['active_count'] == 2
    assert result['totals']['receivable_total'] == D('30')


def test_periodic_anomaly_filter_aligns_each_row_to_union_of_risk_months():
    source = {
        'months': MONTHS,
        'rows': [
            {
                'charge_item': 'A',
                'cells': [cell('2026-01', '10', status='overdue', risk='danger'), cell('2026-02', '20')],
            },
            {
                'charge_item': 'B',
                'cells': [cell('2026-01', '30'), cell('2026-02', '40', status='overdue', risk='danger')],
            },
        ],
    }
    result = filter_periodic_matrix(source, anomalies_only=True)
    assert [month['billing_period'] for month in result['months']] == ['2026-01', '2026-02']
    assert [[cell['billing_period'] for cell in row['cells']] for row in result['rows']] == [
        ['2026-01', '2026-02'],
        ['2026-01', '2026-02'],
    ]
    assert result['active_count'] == 4
    assert result['totals']['receivable_total'] == D('100')


@pytest.mark.parametrize(('mode', 'expected'), [('all', 3), ('pending', 1), ('risk', 1)])
def test_stage_timeline_modes(mode, expected):
    nodes = [
        {
            'status': 'completed',
            'date_certainty': 'actual',
            'risk_level': 'success',
            'planned_amount': D('10'),
            'receivable_total': D('10'),
            'invoiced_total': D('10'),
            'receipt_total': D('10'),
            'unreceived_total': D('0'),
        },
        {
            'status': 'waiting',
            'date_certainty': 'pending_trigger',
            'risk_level': 'muted',
            'planned_amount': D('20'),
            'receivable_total': D('0'),
            'invoiced_total': D('0'),
            'receipt_total': D('0'),
            'unreceived_total': D('20'),
        },
        {
            'status': 'overdue',
            'date_certainty': 'actual',
            'risk_level': 'danger',
            'planned_amount': D('30'),
            'receivable_total': D('30'),
            'invoiced_total': D('30'),
            'receipt_total': D('0'),
            'unreceived_total': D('30'),
        },
    ]
    result = filter_stage_timeline({'nodes': nodes}, mode=mode)
    assert result['active_count'] == expected
    assert result['totals']['planned_amount'] == {'all': D('60'), 'pending': D('20'), 'risk': D('30')}[mode]


def test_stage_timeline_rejects_unknown_mode():
    with pytest.raises(ValueError):
        filter_stage_timeline({'nodes': []}, mode='late')


def order_lane(order_id, project_id, status, amount):
    project = SimpleNamespace(pk=project_id, name=f'P{project_id}')
    order = SimpleNamespace(status=status)
    return {
        'order_id': order_id,
        'order': order,
        'projects': [project],
        'status': 'executing',
        'status_label': '执行中',
        'order_status_label': status,
        'order_amount': D(amount),
        'receivable_total': D(amount),
        'invoiced_total': D('0'),
        'receipt_total': D('0'),
        'unreceived_total': D(amount),
        'overdue_total': D('0'),
        'is_unfiled': False,
        'is_legacy': False,
    }


def test_order_lanes_filter_by_project_and_order_status_and_update_limit():
    source = {
        'lanes': [order_lane('O1', 1, 'active', '100'), order_lane('O2', 2, 'closed', '250')],
        'framework_limit': D('1000'),
    }
    result = filter_order_lanes(source, project='2', order_status='closed')
    assert result['active_count'] == 1
    assert result['lanes'][0]['order_id'] == 'O2'
    assert result['ordered_amount'] == D('250')
    assert result['remaining_limit'] == D('750')
    assert {x['value'] for x in result['filter_options']['projects']} == {'1', '2'}
    assert {x['value'] for x in result['filter_options']['order_statuses']} == {'active', 'closed'}


def mixed_lane(charge_item, order_id, jan, feb):
    cells = [cell('2026-01', jan), cell('2026-02', feb)]
    return {
        'charge_item': charge_item,
        'order_id': order_id,
        'cells': cells,
        'receivable_total': D(jan) + D(feb),
        'invoiced_total': D(jan) + D(feb),
        'receipt_total': D('0'),
        'adjustment_total': D('0'),
        'pending_trigger_count': 0,
    }


def mixed_source():
    return {
        'months': MONTHS,
        'lanes': [mixed_lane('A', 'O1', '10', '20'), mixed_lane('B', 'O1', '30', '40')],
    }


def test_mixed_charge_item_projection_filters_lane():
    result = filter_mixed_lanes(mixed_source(), view_by='charge_item', selected='B')
    assert result['active_count'] == 1
    assert result['lanes'][0]['charge_item'] == 'B'
    assert result['totals']['receivable_total'] == D('70')


def test_mixed_order_projection_groups_lanes_and_cells():
    result = filter_mixed_lanes(mixed_source(), view_by='order', selected='O1')
    assert result['active_count'] == 1
    assert result['lanes'][0]['source_lane_count'] == 2
    assert result['lanes'][0]['cells'][0]['receivable_total'] == D('40')
    assert result['lanes'][0]['cells'][0]['primary_event_dom_id'] == 'event-2026-01'
    assert result['totals']['receivable_total'] == D('100')


def test_mixed_month_projection_uses_only_selected_visible_month():
    result = filter_mixed_lanes(mixed_source(), view_by='month', selected='2026-02')
    assert result['active_count'] == 1
    assert result['lanes'][0]['billing_period'] == '2026-02'
    assert result['totals']['receivable_total'] == D('60')
    assert result['lanes'][0]['cells'][0]['primary_event_dom_id'] == 'event-2026-02'
    assert result['months'] == [{'month': None, 'label': '应收汇总', 'billing_period': 'summary'}]
    assert {x['value'] for x in result['filter_options']['months']} == {'2026-01', '2026-02'}


def test_mixed_month_projection_without_selection_uses_one_summary_column():
    result = filter_mixed_lanes(mixed_source(), view_by='month')
    assert result['active_count'] == 2
    assert [lane['billing_period'] for lane in result['lanes']] == ['2026-01', '2026-02']
    assert [lane['receivable_total'] for lane in result['lanes']] == [D('40'), D('60')]
    assert all(len(lane['cells']) == 1 for lane in result['lanes'])
    assert result['months'] == [{'month': None, 'label': '应收汇总', 'billing_period': 'summary'}]
    assert {x['value'] for x in result['filter_options']['months']} == {'2026-01', '2026-02'}
    assert result['totals']['receivable_total'] == D('100')


def test_mixed_projection_rejects_unknown_dimension():
    with pytest.raises(ValueError):
        filter_mixed_lanes(mixed_source(), view_by='project')
