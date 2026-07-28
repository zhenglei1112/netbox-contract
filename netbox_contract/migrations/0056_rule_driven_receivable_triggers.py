import django.db.models.deletion
from django.db import migrations, models


def link_legacy_trigger_rules(apps, schema_editor):
    RevenueTriggerRecord = apps.get_model('netbox_contract', 'RevenueTriggerRecord')
    for record in RevenueTriggerRecord.objects.select_related('plan').iterator():
        if record.plan_id and record.plan.billing_rule_id:
            record.billing_rule_id = record.plan.billing_rule_id
            record.save(update_fields=['billing_rule'])


def backfill_receivable_line_dates(apps, schema_editor):
    RevenueReceivableLine = apps.get_model('netbox_contract', 'RevenueReceivableLine')
    for line in RevenueReceivableLine.objects.select_related('bill').iterator():
        line.receivable_date = line.bill.receivable_date
        line.due_date = line.bill.due_date
        line.save(update_fields=['receivable_date', 'due_date'])


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_contract', '0055_revenueorder_contractline_revenue_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='revenuebillingrule',
            name='trigger_offset_days',
            field=models.PositiveIntegerField(
                default=0,
                help_text='阶段或一次性规则在业务事件确认后，延后多少天形成应收。',
            ),
        ),
        migrations.AlterField(
            model_name='revenuetriggerrecord',
            name='plan',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='trigger_records',
                to='netbox_contract.revenuereceivableplan',
            ),
        ),
        migrations.AddField(
            model_name='revenuetriggerrecord',
            name='billing_rule',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='trigger_records',
                to='netbox_contract.revenuebillingrule',
            ),
        ),
        migrations.AddField(
            model_name='revenuereceivableline',
            name='receivable_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='revenuereceivableline',
            name='due_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(link_legacy_trigger_rules, migrations.RunPython.noop),
        migrations.RunPython(backfill_receivable_line_dates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='revenuetriggerrecord',
            constraint=models.CheckConstraint(
                condition=models.Q(plan__isnull=False) | models.Q(billing_rule__isnull=False),
                name='revenue_trigger_requires_target',
            ),
        ),
    ]
