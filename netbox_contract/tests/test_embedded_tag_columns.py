import ast
from pathlib import Path


TABLES_PATH = Path(__file__).resolve().parents[1] / 'tables.py'


def _class_node(tree, name):
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def _assigned_value(class_node, name):
    return next(
        ast.literal_eval(node.value)
        for node in class_node.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    )


def test_invoice_table_exposes_tags_before_actions():
    tree = ast.parse(TABLES_PATH.read_text(encoding='utf-8'))
    table = _class_node(tree, 'InvoiceListTable')
    meta = next(
        node
        for node in table.body
        if isinstance(node, ast.ClassDef) and node.name == 'Meta'
    )

    fields = _assigned_value(meta, 'fields')
    default_columns = _assigned_value(meta, 'default_columns')

    assert 'tags' in fields
    assert fields.index('tags') < fields.index('actions')
    assert 'tags' in default_columns

def test_contract_detail_forces_payment_tags_visible_after_user_configuration():
    views_path = TABLES_PATH.with_name('views.py')
    source = views_path.read_text(encoding='utf-8')

    configure = "_configure_detail_table(invoices_table, request, 'invoices_page')"
    show_tags = "invoices_table.columns.show('tags')"

    assert configure in source
    assert show_tags in source
    assert source.index(configure) < source.index(show_tags)

def test_contract_detail_prefetches_payment_tags_for_filter_buttons():
    views_path = TABLES_PATH.with_name('views.py')
    source = views_path.read_text(encoding='utf-8')

    assert "instance.invoices.exclude(template=True).prefetch_related('tags')" in source
