import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_contract', '0053_revenuereceivableplan_revenuereceivableplanversion_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='revenuereceivableline',
            name='receivable_plan',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='receivable_lines',
                to='netbox_contract.revenuereceivableplan',
            ),
        ),
    ]