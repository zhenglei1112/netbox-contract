import unittest
from pathlib import Path


TABLES_PATH = Path(__file__).resolve().parents[1] / "tables.py"


class InvoiceFaultFilterButtonTestCase(unittest.TestCase):
    def test_filter_button_precedes_seal_reason_button(self):
        source = TABLES_PATH.read_text(encoding="utf-8-sig")

        filter_button = source.index('title="\u7b5b\u9009\u5bf9\u5e94\u6545\u969c"')
        seal_reason_button = source.index("invoice_generate_seal_reason")

        self.assertLess(filter_button, seal_reason_button)
        self.assertIn('class="mdi mdi-filter-outline"', source)
        self.assertIn('btn btn-sm btn-outline-primary position-relative', source)

    def test_filter_button_uses_lightweight_fragment_endpoint(self):
        source = TABLES_PATH.read_text(encoding="utf-8-sig")

        self.assertIn(
            "{% if contract_faults_url and record.period_start and record.period_end %}",
            source,
        )
        self.assertIn('hx-get="{{ contract_faults_url }}?', source)
        self.assertIn(
            "fault_occurrence_time_after={{ record.period_start|date:'Y-m-d' }}",
            source,
        )
        self.assertIn(
            "fault_occurrence_time_before={{ record.period_end|date:'Y-m-d' }}",
            source,
        )
        self.assertIn("{% for tag in record.tags.all %}", source)
        self.assertIn("&amp;fault_tag={{ tag.pk }}", source)
        self.assertIn('hx-target="#contract_otn_faults"', source)
        self.assertNotIn('hx-select="#contract_otn_faults"', source)
        self.assertIn('hx-swap="outerHTML"', source)
        self.assertIn('hx-push-url="false"', source)
        self.assertIn(
            'hx-indicator="find .invoice-fault-filter-indicator"', source
        )
        self.assertIn('hx-disabled-elt="this"', source)
        self.assertIn('spinner-border spinner-border-sm htmx-indicator', source)
        self.assertIn('aria-label="\u6b63\u5728\u7b5b\u9009\u5bf9\u5e94\u6545\u969c"', source)
        self.assertNotIn('href="?fault_occurrence_time_after=', source)

    def test_contract_detail_provides_lightweight_fault_fragment_url(self):
        template_path = (
            TABLES_PATH.parent
            / "templates"
            / "netbox_contract"
            / "contract.html"
        )
        template = template_path.read_text(encoding="utf-8-sig")

        url_tag = (
            "{% url 'plugins:netbox_otnfaults:contract_faults_fragment' "
            "contract_id=object.pk as contract_faults_url %}"
        )
        payment_table = "{% render_table invoices_table 'inc/table.html' %}"

        self.assertIn(url_tag, template)
        self.assertLess(template.index(url_tag), template.index(payment_table))


if __name__ == "__main__":
    unittest.main()
