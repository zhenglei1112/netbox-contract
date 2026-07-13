# Native Detail Pagination Fix Design

## Goal

Replace the `django_tables2` native pagination rendered by nested tables on contract and invoice detail pages with NetBox-style pagination controls, following commit `67fbab227dbbf4353596879f792ec21d3ce7d6dc` from `zhenglei1112/netbox-otnfaults`.

## Scope

The change covers every nested table rendered directly by these two detail views:

- `ContractView`: invoice template lines, assignments, child contracts, and invoices.
- `InvoiceView`: invoice lines and contracts.

Top-level NetBox object list views and the revenue-contract work currently present in the working tree are outside this change.

## Design

Each nested table receives a stable, independent query-string prefix. The view reads a shared `per_page` value and a table-specific page value, validates both, then explicitly calls the table pagination API. Invalid values fall back to page 1 and 25 rows per page. Supported page sizes are 25, 50, 100, 250, and 500; unsupported sizes also fall back to 25.

The templates wrap each rendered table in a table-specific container. CSS hides only the native `django_tables2` pagination within those containers. A NetBox-style card footer then renders previous/next controls, a compact page-number window, the current result range and total, and the page-size selector.

Links preserve the current page of the other nested tables and the selected page size. Changing page size resets table pages to page 1 to prevent an out-of-range page after the size change.

## Query Parameters

- Shared: `per_page`.
- Contract detail: `invoice_lines_page`, `assignments_page`, `children_page`, `invoices_page`.
- Invoice detail: `invoice_lines_page`, `contracts_page`.

## Error Handling

Non-integer, zero, negative, or out-of-range page parameters resolve safely through the paginator or fall back to page 1. Non-integer or unsupported `per_page` values fall back to 25. Empty or absent tables do not render a pagination footer.

## Testing

Regression tests will verify:

- each table is explicitly and independently paginated;
- default, supported, and invalid page-size handling;
- template containers suppress the native paginator;
- each custom paginator uses its own page parameter and preserves sibling state;
- page-size choices and result-count output are present;
- existing view tests still pass.

Implementation will follow red-green-refactor: add a focused failing regression test, confirm the expected failure, implement the smallest fix, then run focused and broader test suites.
