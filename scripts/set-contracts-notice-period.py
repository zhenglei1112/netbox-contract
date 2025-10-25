from datetime import date, timedelta

from django.db.models import Count
from extras.scripts import ChoiceVar, IntegerVar, ObjectVar, Script, StringVar

from netbox_contract.models import (
    AccountingDimension,
    Contract,
    Invoice,
    InvoiceLine,
    StatusChoices,
)

name = 'Contract Notice Period Management'


class set_all_contracts_notice_period(Script):
    class Meta:
        name = 'Set all contracts notice period to 30 days'
        description = 'Update the notice period for all contracts to 30 days'
        commit_default = False

    def run(self, data, commit):
        username = self.request.user.username
        self.log_info(f'Running as user {username}')

        output = []

        # Get all contracts
        contracts = Contract.objects.all()
        contract_count = contracts.count()
        
        self.log_info(f'Found {contract_count} contracts to update')

        # Update notice period for all contracts
        updated_count = contracts.update(notice_period=30)
        
        self.log_success(f'Successfully updated {updated_count} contracts with notice period set to 30 days')
        output.append(f'Updated {updated_count} contracts with notice period set to 30 days')

        return '\n'.join(output)
