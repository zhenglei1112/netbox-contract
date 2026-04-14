from django.test import SimpleTestCase

from netbox_contract.models import InternalEntityChoices


class InternalEntityChoicesTestCase(SimpleTestCase):
    def test_contains_general_affairs_department_choice(self):
        values = [value for value, _label, *_rest in InternalEntityChoices.CHOICES]

        self.assertIn('general-affairs', values)

