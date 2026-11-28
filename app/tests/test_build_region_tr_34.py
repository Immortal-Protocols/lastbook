#!/usr/bin/env python3
"""Offline Istanbul builder regressions: python3 -B -m unittest app.tests.test_build_region_tr_34."""
import unittest

from tools.build_region_tr_34 import parse_ibb_address


class IbbAddressTests(unittest.TestCase):
    def test_neighbourhood_is_not_a_door_suffix(self):
        for neighbourhood in ('FENERYOLU/KADIKÖY', 'FİKİRTEPE/KADIKÖY', 'Fıstıkağacı/ÜSKÜDAR'):
            with self.subTest(neighbourhood=neighbourhood):
                self.assertEqual(
                    parse_ibb_address(f'Bağdat Caddesi No:75 {neighbourhood}'),
                    ('Bağdat Caddesi', '75'),
                )

    def test_actual_door_suffix_is_retained(self):
        for number in ('25 F', '25/F', '25-F', '25 f'):
            with self.subTest(number=number):
                self.assertEqual(
                    parse_ibb_address(f'Çayır Cad. No:{number} YALIKÖY/BEYKOZ'),
                    ('Çayır Cad.', '25F'),
                )
        self.assertEqual(parse_ibb_address('Çayır Cad. No:25 F'), ('Çayır Cad.', '25F'))

    def test_plain_number_is_retained(self):
        self.assertEqual(parse_ibb_address('Bağdat Caddesi No:75'), ('Bağdat Caddesi', '75'))


if __name__ == '__main__':
    unittest.main()
