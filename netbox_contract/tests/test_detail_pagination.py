import ast
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
VIEWS_PATH = PACKAGE_ROOT / "views.py"
TEMPLATE_ROOT = PACKAGE_ROOT / "templates" / "netbox_contract"


class DetailPaginationTestCase(unittest.TestCase):
    def test_detail_views_validate_pagination_parameters(self):
        source = VIEWS_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("DETAIL_PAGE_SIZES = (25, 50, 100, 250, 500)", source)
        self.assertIn("def _detail_per_page(params):", source)
        self.assertIn("def _detail_page(params, key):", source)

    def test_detail_pagination_falls_back_to_last_page_when_page_is_too_large(self):
        source = VIEWS_PATH.read_text(encoding="utf-8-sig")
        module = ast.parse(source)
        helper = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_paginate_detail_table"
        )

        class FakeEmptyPage(Exception):
            pass

        class FakeTable:
            paginator = type("Paginator", (), {"num_pages": 3})()

            def __init__(self):
                self.calls = []

            def paginate(self, *, page, per_page):
                self.calls.append((page, per_page))
                if len(self.calls) == 1:
                    raise FakeEmptyPage

        namespace = {"EmptyPage": FakeEmptyPage}
        exec(
            compile(
                ast.Module(body=[helper], type_ignores=[]),
                str(VIEWS_PATH),
                "exec",
            ),
            namespace,
        )
        table = FakeTable()

        namespace["_paginate_detail_table"](table, 999, 25)

        self.assertEqual(table.calls, [(999, 25), (3, 25)])

    def test_detail_views_paginate_tables_independently(self):
        source = VIEWS_PATH.read_text(encoding="utf-8-sig")

        self.assertIn("from django_tables2 import RequestConfig", source)
        self.assertNotIn("configure(request, paginate=False)", source)
        self.assertEqual(
            source.count("RequestConfig(request, paginate=False).configure("),
            6,
        )
        for page_key in (
            "invoice_lines_page",
            "assignments_page",
            "children_page",
            "invoices_page",
            "contracts_page",
        ):
            self.assertIn(f"_detail_page(request.GET, '{page_key}')", source)
        self.assertIn("'detail_per_page': per_page", source)
        self.assertIn("'detail_page_sizes': DETAIL_PAGE_SIZES", source)

    def test_shared_footer_contains_netbox_pagination_controls(self):
        template = (
            TEMPLATE_ROOT / "inc" / "detail_table_pagination.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("table.page.has_previous", template)
        self.assertIn("table.page.start_index", template)
        self.assertIn("table.paginator.count", template)
        self.assertIn("detail_page_sizes", template)
        self.assertIn("page_param", template)

    def test_per_page_change_resets_all_independent_page_numbers(self):
        template = (
            TEMPLATE_ROOT / "inc" / "detail_table_pagination.html"
        ).read_text(encoding="utf-8-sig")

        for page_key in (
            "invoice_lines_page",
            "assignments_page",
            "children_page",
            "invoices_page",
            "contracts_page",
        ):
            self.assertIn(f"'{page_key}'", template)
        self.assertIn("url.searchParams.delete(key)", template)

    def test_detail_templates_replace_native_pagination(self):
        contract = (TEMPLATE_ROOT / "contract.html").read_text(encoding="utf-8-sig")
        invoice = (TEMPLATE_ROOT / "invoice.html").read_text(encoding="utf-8-sig")

        self.assertIn(".detail-table-container ul.pagination", contract)
        self.assertIn(".detail-table-container ul.pagination", invoice)
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
