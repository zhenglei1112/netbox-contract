from extras.scripts import Script

from netbox_contract.models import Contract

name = 'Contract Name Management'


class update_contract_names_with_contractnumber(Script):
    class Meta:
        name = 'Update contract names with ContractNumber'
        description = 'Check if contract names contain ContractNumber custom field, and append if not'
        commit_default = False

    def run(self, data, commit):
        username = self.request.user.username
        self.log_info(f'Running as user {username}')

        output = []

        # Get all contracts
        contracts = Contract.objects.all()
        contract_count = contracts.count()
        
        self.log_info(f'Found {contract_count} contracts to check')

        updated_count = 0
        skipped_count = 0
        error_count = 0

        # Process each contract
        for contract in contracts:
            try:
                # Check if contract has ContractNumber custom field
                if not contract.custom_field_data or 'ContractNumber' not in contract.custom_field_data:
                    self.log_info(f'Contract {contract.name} (ID: {contract.id}) does not have ContractNumber custom field - skipping')
                    skipped_count += 1
                    continue

                contract_number = contract.custom_field_data['ContractNumber']
                
                # Skip if ContractNumber is empty or None
                if not contract_number:
                    self.log_info(f'Contract {contract.name} (ID: {contract.id}) has empty ContractNumber - skipping')
                    skipped_count += 1
                    continue

                # Check if contract name already contains the contract number
                if str(contract_number) in contract.name:
                    self.log_info(f'Contract {contract.name} (ID: {contract.id}) already contains ContractNumber {contract_number} - skipping')
                    skipped_count += 1
                    continue

                # Update contract name by appending ContractNumber with hyphen
                new_name = f"{contract.name}-{contract_number}"
                
                # Log the change
                self.log_info(f'Updating contract {contract.name} (ID: {contract.id}) to {new_name}')
                
                # Update the contract name
                if commit:
                    contract.name = new_name
                    contract.save()
                    self.log_success(f'Successfully updated contract {contract.id} name to {new_name}')
                else:
                    self.log_info(f'[DRY RUN] Would update contract {contract.id} name from "{contract.name}" to "{new_name}"')

                updated_count += 1
                output.append(f'Contract {contract.id}: "{contract.name}" -> "{new_name}"')

            except Exception as e:
                self.log_error(f'Error processing contract {contract.id}: {str(e)}')
                error_count += 1
                output.append(f'ERROR: Contract {contract.id}: {str(e)}')

        # Summary
        summary = f"""
Summary:
- Total contracts processed: {contract_count}
- Contracts updated: {updated_count}
- Contracts skipped: {skipped_count}
- Errors encountered: {error_count}
"""
        self.log_info(summary)
        output.append(summary)

        if not commit:
            output.append("\nNOTE: This was a dry run. No changes were actually made.")
            output.append("To apply changes, enable the commit option when running the script.")

        return '\n'.join(output)
