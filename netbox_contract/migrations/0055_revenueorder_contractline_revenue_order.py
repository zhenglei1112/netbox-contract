import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


def backfill_revenue_orders(apps, schema_editor):
    RevenueContractLine = apps.get_model('netbox_contract', 'RevenueContractLine')
    RevenueOrder = apps.get_model('netbox_contract', 'RevenueOrder')
    grouped = {}
    for line in RevenueContractLine.objects.exclude(order_id='').iterator():
        order_code = (line.order_id or '').strip()
        if not order_code:
            continue
        key = (line.contract_id, line.project_id, order_code)
        group = grouped.setdefault(
            key,
            {
                'line_ids': [],
                'amount': 0,
                'start_date': None,
                'end_date': None,
                'has_open_end': False,
                'statuses': set(),
            },
        )
        group['line_ids'].append(line.pk)
        group['amount'] += line.unit_price * line.quantity
        group['start_date'] = min(
            value for value in (group['start_date'], line.valid_from) if value is not None
        )
        if line.valid_to is None:
            group['has_open_end'] = True
        else:
            group['end_date'] = max(
                value for value in (group['end_date'], line.valid_to) if value is not None
            )
        group['statuses'].add(line.status)

    for (contract_id, project_id, order_code), group in grouped.items():
        if 'active' in group['statuses']:
            status = 'executing'
        elif 'suspended' in group['statuses']:
            status = 'suspended'
        elif group['statuses'] == {'terminated'}:
            status = 'cancelled'
        else:
            status = 'draft'
        order = RevenueOrder.objects.create(
            order_code=order_code,
            contract_id=contract_id,
            project_id=project_id,
            name=f'历史订单 {order_code}',
            amount=group['amount'],
            start_date=group['start_date'],
            end_date=None if group['has_open_end'] else group['end_date'],
            status=status,
            source_system='LEGACY_LEDGER',
            external_id=order_code,
        )
        RevenueContractLine.objects.filter(pk__in=group['line_ids']).update(revenue_order=order)


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_contract', '0054_revenuereceivableline_receivable_plan'),
    ]

    operations = [
        migrations.CreateModel(
            name='RevenueOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('order_code', models.CharField(max_length=100)),
                ('name', models.CharField(blank=True, max_length=200)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(default='draft', max_length=50)),
                ('source_system', models.CharField(default='REVENUE_SYS', max_length=50)),
                ('external_id', models.CharField(blank=True, max_length=100)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='netbox_contract.revenuecontract')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='revenue_orders', to='netbox_contract.revenueproject')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': '收入订单/开工单',
                'verbose_name_plural': '收入订单/开工单',
                'ordering': ('contract', 'project', 'order_code'),
                'constraints': [models.UniqueConstraint(fields=('contract', 'project', 'order_code'), name='unique_revenue_order_contract_project_code')],
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.AddField(
            model_name='revenuecontractline',
            name='revenue_order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='contract_lines', to='netbox_contract.revenueorder'),
        ),
        migrations.RunPython(backfill_revenue_orders, migrations.RunPython.noop),
    ]