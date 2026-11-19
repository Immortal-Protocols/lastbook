"""Publisher trust labels: UK government bodies rank like the US ones, and the US ranking is unchanged."""
import unittest

import server

GOVERNMENT = ('Government guidance', 1.4)


class TrustTests(unittest.TestCase):
    def label(self, publisher, collection=''):
        return server.trust({'publisher': publisher, 'collection': collection})

    def test_uk_government_bodies(self):
        for publisher in ('NHS England', 'NHS', 'UKHSA', 'UK Health Security Agency', 'Met Office', 'Environment Agency', 'SEPA',
                          'Food Standards Agency', 'Cabinet Office', 'Home Office', 'Natural Resources Wales', 'Scottish Government',
                          'Welsh Government', 'UK Government', 'GOV.UK', 'gov.uk', 'Ordnance Survey', 'Forestry England'):
            with self.subTest(publisher=publisher):
                self.assertEqual(self.label(publisher), GOVERNMENT)
        self.assertEqual(self.label('Be Ready', 'UK Government'), GOVERNMENT)
        self.assertEqual(self.label('Cabinet Office', 'Ready Scotland'), GOVERNMENT)

    def test_words_that_merely_contain_the_letters_do_not_match(self):
        for publisher in ('UNHSA Holdings', 'Nashville Hobby Club', 'Penhsa Press', 'Sepal Press'):
            with self.subTest(publisher=publisher):
                self.assertEqual(self.label(publisher), ('Reference', 1.0))

    def test_us_ranking_unchanged(self):
        for publisher in ('FEMA', 'CDC', 'USDA', 'NOAA', 'National Park Service', 'Cal OES'):
            with self.subTest(publisher=publisher):
                self.assertEqual(self.label(publisher), GOVERNMENT)
        self.assertEqual(self.label('American Red Cross')[0], 'International health & humanitarian guidance')
        self.assertEqual(self.label('British Red Cross')[0], 'International health & humanitarian guidance')
        self.assertEqual(self.label('St John Ambulance')[0], 'International health & humanitarian guidance')
        self.assertEqual(self.label('Utah State University Extension')[0], 'University / extension service')


if __name__ == '__main__':
    unittest.main()
