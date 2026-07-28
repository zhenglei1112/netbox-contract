from datetime import date, timedelta
from decimal import Decimal


ZERO = Decimal('0')


def _sum(values):
    return sum(values, ZERO)


def _schedule_label(version):
    if not version:
        return '未建档'
    if version.trigger_type == 'trigger_offset':
        trigger_label = version.get_trigger_event_display()
        return f'{trigger_label}后{version.offset_days}天到期'
    if version.planned_date:
        prefix = '预计' if version.trigger_type == 'estimated_date' else '固定'
        return f'{prefix}日期 {version.planned_date:%Y-%m-%d}'
    return '日期未确定'


def _track_status(*, current_version, actual_trigger_date, due_date, receivable_total, receipt_total, today):
    if receivable_total > ZERO and receipt_total >= receivable_total:
        return 'paid', '已结清', 'success'
    if due_date and due_date < today and receipt_total < receivable_total:
        return 'overdue', '逾期未收', 'danger'
    if receivable_total > ZERO:
        return 'receivable', '已形成应收', 'info'
    if actual_trigger_date:
        return 'triggered', '已触发待形成应收', 'warning'
    if current_version and current_version.trigger_type == 'trigger_offset':
        return 'pending_trigger', '待条件触发', 'muted'
    return 'planned', '计划中', 'muted'


def build_receivable_plan_tracks(
    plans,
    plan_versions,
    trigger_records,
    adjustment_records,
    event_rows,
    *,
    today=None,
    url_for=None,
):
    """Build original/current/actual tracks without inventing unknown dates."""
    today = today or date.today()
    url_for = url_for or (lambda _obj: '')
    plans = list(plans)

    versions_by_plan = {}
    for version in plan_versions:
        versions_by_plan.setdefault(version.plan_id, []).append(version)
    triggers_by_plan = {}
    for trigger in trigger_records:
        if trigger.status == 'confirmed':
            triggers_by_plan.setdefault(trigger.plan_id, []).append(trigger)
    adjustments_by_plan = {}
    adjustments_by_line = {}
    for adjustment in adjustment_records:
        if adjustment.status != 'confirmed':
            continue
        if adjustment.plan_id:
            adjustments_by_plan.setdefault(adjustment.plan_id, []).append(adjustment)
        if adjustment.receivable_line_id:
            adjustments_by_line.setdefault(adjustment.receivable_line_id, []).append(adjustment)

    plans_by_rule = {}
    for plan in plans:
        plans_by_rule.setdefault(plan.billing_rule_id, []).append(plan)

    events_by_plan = {}
    unassigned_events_by_rule = {}
    for event in event_rows:
        line = event.get('line')
        rule = event.get('billing_rule')
        if line and line.receivable_plan_id:
            events_by_plan.setdefault(line.receivable_plan_id, []).append(event)
        elif rule:
            unassigned_events_by_rule.setdefault(rule.pk, []).append(event)

    ambiguous_unassigned_events = [
        event
        for rule_id, events in unassigned_events_by_rule.items()
        if len(plans_by_rule.get(rule_id, ())) > 1
        for event in events
    ]

    tracks = []
    for plan in plans:
        versions = sorted(versions_by_plan.get(plan.pk, []), key=lambda item: item.version_no)
        original_version = versions[0] if versions else None
        current_version = next(
            (version for version in versions if version.is_current),
            versions[-1] if versions else None,
        )
        triggers = sorted(triggers_by_plan.get(plan.pk, []), key=lambda item: item.actual_trigger_date)
        actual_trigger = triggers[0] if triggers else None
        actual_trigger_date = actual_trigger.actual_trigger_date if actual_trigger else None
        plan_events = list(events_by_plan.get(plan.pk, ()))
        if len(plans_by_rule.get(plan.billing_rule_id, ())) == 1:
            plan_events.extend(unassigned_events_by_rule.get(plan.billing_rule_id, ()))
        events = sorted(
            plan_events,
            key=lambda event: (event.get('receivable_date') or date.max, event['event_key']),
        )
        receivable_dates = [event['receivable_date'] for event in events if event.get('receivable_date')]
        due_dates = [event['due_date'] for event in events if event.get('due_date')]
        actual_receivable_date = min(receivable_dates) if receivable_dates else None
        actual_due_date = min(due_dates) if due_dates else None
        calculated_due_date = None
        if (
            current_version
            and current_version.trigger_type == 'trigger_offset'
            and actual_trigger_date
            and current_version.offset_days is not None
        ):
            calculated_due_date = actual_trigger_date + timedelta(days=current_version.offset_days)
        effective_due_date = actual_due_date or calculated_due_date

        plan_adjustments = list(adjustments_by_plan.get(plan.pk, []))
        seen_adjustment_ids = {adjustment.pk for adjustment in plan_adjustments}
        for event in events:
            for adjustment in adjustments_by_line.get(event['line'].pk, []):
                if adjustment.pk not in seen_adjustment_ids:
                    plan_adjustments.append(adjustment)
                    seen_adjustment_ids.add(adjustment.pk)
        plan_adjustments.sort(key=lambda item: (item.adjustment_date, item.pk))

        receivable_total = _sum(event['net_amount'] for event in events)
        invoiced_total = _sum(event['mapped_amount'] for event in events)
        receipt_total = _sum(event['receipted_amount'] for event in events)
        confirmed_adjustment_total = _sum(adjustment.amount for adjustment in plan_adjustments)
        original_amount = original_version.planned_amount if original_version else ZERO
        current_amount = current_version.planned_amount if current_version else ZERO
        status, status_label, risk_level = _track_status(
            current_version=current_version,
            actual_trigger_date=actual_trigger_date,
            due_date=effective_due_date,
            receivable_total=receivable_total,
            receipt_total=receipt_total,
            today=today,
        )
        reason_parts = [version.change_reason for version in versions[1:] if version.change_reason]
        reason_parts.extend(adjustment.reason for adjustment in plan_adjustments if adjustment.reason)

        tracks.append(
            {
                'plan': plan,
                'plan_url': url_for(plan),
                'contract_line': plan.contract_line,
                'contract_line_url': url_for(plan.contract_line),
                'billing_rule': plan.billing_rule,
                'billing_rule_url': url_for(plan.billing_rule),
                'versions': versions,
                'original_version': original_version,
                'original_version_url': url_for(original_version) if original_version else '',
                'current_version': current_version,
                'current_version_url': url_for(current_version) if current_version else '',
                'original_schedule_label': _schedule_label(original_version),
                'current_schedule_label': _schedule_label(current_version),
                'original_amount': original_amount,
                'current_amount': current_amount,
                'actual_trigger': actual_trigger,
                'actual_trigger_url': url_for(actual_trigger) if actual_trigger else '',
                'actual_trigger_date': actual_trigger_date,
                'actual_receivable_date': actual_receivable_date,
                'actual_due_date': actual_due_date,
                'calculated_due_date': calculated_due_date,
                'effective_due_date': effective_due_date,
                'receivable_total': receivable_total,
                'invoiced_total': invoiced_total,
                'receipt_total': receipt_total,
                'confirmed_adjustment_total': confirmed_adjustment_total,
                'amount_variance': receivable_total - current_amount if current_version else ZERO,
                'adjustments': plan_adjustments,
                'variance_reasons': reason_parts,
                'events': events,
                'status': status,
                'status_label': status_label,
                'risk_level': risk_level,
            }
        )

    tracks.sort(
        key=lambda track: (
            track['current_version'].planned_date
            if track['current_version'] and track['current_version'].planned_date
            else track['effective_due_date'] or date.max,
            track['plan'].plan_code,
        )
    )
    return {
        'tracks': tracks,
        'has_plans': bool(tracks),
        'ambiguous_unassigned_events': ambiguous_unassigned_events,
        'ambiguous_unassigned_event_count': len(ambiguous_unassigned_events),
        'totals': {
            'original_amount': _sum(track['original_amount'] for track in tracks),
            'current_amount': _sum(track['current_amount'] for track in tracks),
            'receivable_total': _sum(track['receivable_total'] for track in tracks),
            'adjustment_total': _sum(track['confirmed_adjustment_total'] for track in tracks),
            'pending_trigger_count': sum(1 for track in tracks if track['status'] == 'pending_trigger'),
            'variance_count': sum(1 for track in tracks if track['amount_variance'] != ZERO),
        },
    }
