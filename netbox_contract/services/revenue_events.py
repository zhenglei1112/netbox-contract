from datetime import date
from decimal import Decimal


ZERO = Decimal('0')


def _sum(values):
    return sum(values, ZERO)


def _collection_status(*, net_amount, mapped_amount, receipted_amount, overdue_amount):
    if mapped_amount > net_amount or receipted_amount > net_amount:
        return 'error', '金额异常', 'danger'
    if overdue_amount > ZERO:
        return 'overdue', '逾期未收', 'danger'
    if receipted_amount >= net_amount and net_amount > ZERO:
        return 'paid', '已结清', 'success'
    if receipted_amount > ZERO:
        return 'partial_receipt', '部分收款', 'warning'
    if mapped_amount >= net_amount and net_amount > ZERO:
        return 'invoiced', '已开票', 'info'
    if mapped_amount > ZERO:
        return 'partial_invoice', '部分开票', 'warning'
    return 'uninvoiced', '待开票', 'muted'


def build_revenue_event_rows(
    receivable_lines,
    invoice_mappings,
    receipt_allocations,
    *,
    url_for=None,
    today=None,
):
    """Project receivable facts into one row per receivable line."""
    today = today or date.today()
    url_for = url_for or (lambda _obj: '')

    mappings_by_line = {}
    for mapping in invoice_mappings:
        mappings_by_line.setdefault(mapping.receivable_line_id, []).append(mapping)

    allocations_by_line = {}
    allocations_by_mapping = {}
    for allocation in receipt_allocations:
        allocations_by_line.setdefault(allocation.receivable_line_id, []).append(allocation)
        if allocation.invoice_mapping_id:
            allocations_by_mapping.setdefault(allocation.invoice_mapping_id, []).append(allocation)

    rows = []
    for line in receivable_lines:
        bill = line.bill
        receivable_date = getattr(line, 'receivable_date', None) or bill.receivable_date
        due_date = getattr(line, 'due_date', None) or bill.due_date
        line_mappings = mappings_by_line.get(line.pk, [])
        line_allocations = allocations_by_line.get(line.pk, [])
        active_mappings = [mapping for mapping in line_mappings if mapping.status == 'active']
        active_allocations = [allocation for allocation in line_allocations if allocation.status == 'active']
        mapped_amount = _sum(mapping.mapped_amount for mapping in active_mappings)
        receipted_amount = _sum(allocation.allocated_amount for allocation in active_allocations)
        uninvoiced_amount = line.net_amount - mapped_amount
        unreceived_amount = line.net_amount - receipted_amount
        is_confirmed = bill.confirm_status == 'confirmed'
        overdue_amount = (
            max(unreceived_amount, ZERO) if is_confirmed and due_date and due_date < today else ZERO
        )
        collection_status, collection_status_label, risk_level = _collection_status(
            net_amount=line.net_amount,
            mapped_amount=mapped_amount,
            receipted_amount=receipted_amount,
            overdue_amount=overdue_amount,
        )

        rows.append(
            {
                'event_key': f'receivable-line:{line.pk}',
                'event_dom_id': f'receivable-event-{line.pk}',
                'line': line,
                'line_url': url_for(line),
                'bill': bill,
                'bill_url': url_for(bill),
                'contract_line': line.contract_line,
                'contract_line_url': url_for(line.contract_line),
                'billing_rule': line.billing_rule,
                'billing_period': bill.billing_period,
                'receivable_date': receivable_date,
                'due_date': due_date,
                'net_amount': line.net_amount,
                'mapped_amount': mapped_amount,
                'receipted_amount': receipted_amount,
                'uninvoiced_amount': uninvoiced_amount,
                'unreceived_amount': unreceived_amount,
                'overdue_amount': overdue_amount,
                'collection_status': collection_status,
                'collection_status_label': collection_status_label,
                'risk_level': risk_level,
                'has_amount_error': mapped_amount > line.net_amount or receipted_amount > line.net_amount,
                'is_confirmed': is_confirmed,
                'confirm_status': bill.confirm_status,
                'mappings': [
                    {
                        'mapping': mapping,
                        'mapping_url': url_for(mapping),
                        'invoice_line': mapping.invoice_line,
                        'invoice': mapping.invoice_line.invoice,
                        'invoice_url': url_for(mapping.invoice_line.invoice),
                        'mapped_amount': mapping.mapped_amount,
                        'receipt_allocations': allocations_by_mapping.get(mapping.pk, []),
                        'receipt_amount': _sum(
                            allocation.allocated_amount
                            for allocation in allocations_by_mapping.get(mapping.pk, [])
                            if allocation.status == 'active'
                        ),
                    }
                    for mapping in line_mappings
                ],
                'receipt_allocations': line_allocations,
            }
        )

    return rows


def summarize_revenue_events(rows, receivable_bills):
    """Return execution totals from facts and reconciliation against bill caches."""
    confirmed_rows = [row for row in rows if row['is_confirmed']]
    confirmed_bills = [bill for bill in receivable_bills if bill.confirm_status == 'confirmed']

    calculated_receivable_total = _sum(row['net_amount'] for row in confirmed_rows)
    calculated_invoiced_total = _sum(row['mapped_amount'] for row in confirmed_rows)
    calculated_receipt_total = _sum(row['receipted_amount'] for row in confirmed_rows)
    overdue_total = _sum(row['overdue_amount'] for row in confirmed_rows)

    cached_receivable_total = _sum(bill.net_amount for bill in confirmed_bills)
    cached_invoiced_total = _sum(bill.invoiced_amount for bill in confirmed_bills)
    cached_receipt_total = _sum(bill.receipted_amount for bill in confirmed_bills)

    differences = {
        'receivable': cached_receivable_total - calculated_receivable_total,
        'invoiced': cached_invoiced_total - calculated_invoiced_total,
        'receipt': cached_receipt_total - calculated_receipt_total,
    }

    return {
        'receivable_total': calculated_receivable_total,
        'invoiced_total': calculated_invoiced_total,
        'receipt_total': calculated_receipt_total,
        'overdue_total': overdue_total,
        'uninvoiced_total': calculated_receivable_total - calculated_invoiced_total,
        'unreceived_total': calculated_receivable_total - calculated_receipt_total,
        'open_item_count': sum(
            1 for row in confirmed_rows if row['unreceived_amount'] > ZERO or row['uninvoiced_amount'] > ZERO
        ),
        'confirmed_rows': confirmed_rows,
        'confirmed_bills': confirmed_bills,
        'reconciliation': {
            'has_mismatch': any(value != ZERO for value in differences.values()),
            'calculated_receivable_total': calculated_receivable_total,
            'calculated_invoiced_total': calculated_invoiced_total,
            'calculated_receipt_total': calculated_receipt_total,
            'cached_receivable_total': cached_receivable_total,
            'cached_invoiced_total': cached_invoiced_total,
            'cached_receipt_total': cached_receipt_total,
            'differences': differences,
        },
    }
