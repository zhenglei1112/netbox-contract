import ast
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
VIEWS_PATH = PACKAGE_ROOT / "views.py"
TEMPLATE_ROOT = PACKAGE_ROOT / "templates" / "netbox_contract"


class DetailPaginationTestCase(unittest.TestCase):
    def test_detail_views_validate_pagination_parameters(self):
        source = VIEWS_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("from utilities.paginator import get_paginate_count", source)
        self.assertNotIn("def _detail_per_page(params):", source)
        self.assertNotIn("def _detail_page(params, key):", source)

    def test_detail_table_configuration_uses_namespaced_page_parameter(self):
        source = VIEWS_PATH.read_text(encoding="utf-8-sig")
        module = ast.parse(source)
        helper = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_configure_detail_table"
        )

        class FakeTable:
            def __init__(self):
                self.prefix = None
                self.configured_with = None

            def configure(self, request):
                self.configured_with = request

        namespace = {}
        exec(
            compile(
                ast.Module(body=[helper], type_ignores=[]),
                str(VIEWS_PATH),
                "exec",
            ),
            namespace,
        )
        table = FakeTable()
        request = object()

        namespace["_configure_detail_table"](table, request, "invoice_lines_page")

        self.assertEqual(table.prefix, "invoice_lines_")
        self.assertIs(table.configured_with, request)

    def test_detail_views_paginate_tables_independently(self):
        source = VIEWS_PATH.read_text(encoding="utf-8-sig")

        self.assertNotIn("from django_tables2 import RequestConfig", source)
        self.assertIn("table.prefix = page_param.removesuffix('page')", source)
        self.assertIn("table.configure(request)", source)
        self.assertEqual(source.count("_configure_detail_table("), 7)
        for page_key in (
            "invoice_lines_page",
            "assignments_page",
            "children_page",
            "invoices_page",
            "contracts_page",
        ):
            self.assertIn(f"request, '{page_key}')", source)
        self.assertEqual(source.count("per_page = get_paginate_count(request)"), 2)

    def test_shared_footer_contains_netbox_pagination_controls(self):
        template = (
            TEMPLATE_ROOT / "inc" / "detail_table_pagination.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("table.page.has_previous", template)
        self.assertIn("table.page.start_index", template)
        self.assertIn("table.page.paginator.count", template)
        self.assertIn("table.page.smart_pages", template)
        self.assertIn('class="pagination mb-0"', template)
        self.assertIn('class="btn btn-sm btn-outline-secondary dropdown-toggle"', template)
        self.assertIn("table.page.paginator.get_page_lengths", template)
        self.assertNotIn("pagination-sm", template)
        self.assertIn("page_param", template)

    def test_per_page_change_resets_all_independent_page_numbers(self):
        source = VIEWS_PATH.read_text(encoding="utf-8-sig")
        template = (TEMPLATE_ROOT / "inc" / "detail_table_pagination.html").read_text(
            encoding="utf-8-sig"
        )

        for page_key in (
            "invoice_lines_page",
            "assignments_page",
            "children_page",
            "invoices_page",
            "contracts_page",
        ):
            self.assertIn(f"'{page_key}'", source)
        self.assertIn("detail_per_page_query", template)
        self.assertNotIn("onchange=", template)

    def test_detail_templates_replace_native_pagination(self):
        contract = (TEMPLATE_ROOT / "contract.html").read_text(encoding="utf-8-sig")
        invoice = (TEMPLATE_ROOT / "invoice.html").read_text(encoding="utf-8-sig")

        self.assertNotIn(".detail-table-container ul.pagination", contract)
        self.assertNotIn(".detail-table-container ul.pagination", invoice)
        self.assertEqual(contract.count("'inc/table.html'"), 4)
        self.assertEqual(invoice.count("'inc/table.html'"), 2)
        for page_key in (
            "invoice_lines_page",
            "assignments_page",
            "children_page",
            "invoices_page",
        ):
            self.assertIn(f'page_param="{page_key}"', contract)
        for page_key in ("invoice_lines_page", "contracts_page"):
            self.assertIn(f'page_param="{page_key}"', invoice)


if __name__ == "__main__":
    unittest.main()
