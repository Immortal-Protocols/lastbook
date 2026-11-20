#!/usr/bin/env python3
"""Synthetic document-search regression for #154 (no installed pack required).

Run: python3 -B -m unittest app.tests.test_document_search_emergency -v

This is a *baseline* for the document retrieval gap, not a claim that the
current ranking is fixed. The synthetic pages deliberately distinguish first
aid from unrelated water/fire how-to content. Keep the cases when changing
server.find or assistant._fts and remeasure on the Medium pack.
"""
import sqlite3
import unittest

import server


CASES = (
    ("treat water in the lungs after drowning",
     "drowning resuscitation airway breathing first aid",
     "water treatment disinfect chlorine drinking water"),
    ("light a fire to keep him warm with hypothermia",
     "hypothermia cold exposure first aid warming",
     "fire tinder kindling firecraft campfire"),
    ("carbon monoxide from making a fire in the tent",
     "carbon monoxide poisoning first aid ventilation",
     "fire starting kindling tinder tent camping"),
)

# Queries that must keep their ordinary how-to matches.
CONTROLS = (
    ("how do i treat water", "water treatment disinfect chlorine"),
    ("how do i light a fire", "fire tinder kindling firecraft"),
)


def matches(db, query):
    """Use the same FTS5 MATCH expression builder as the app."""
    _, groups = server.query_groups(query)
    expression = server.fts_expr(groups)
    return [row[0] for row in db.execute(
        "SELECT title FROM pages WHERE pages MATCH ? ORDER BY rank",
        (expression,))]


class DocumentSearchEmergencyBaseline(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE VIRTUAL TABLE pages USING fts5(title, body)")
        for i, (_, urgent, ordinary) in enumerate(CASES):
            self.db.execute("INSERT INTO pages VALUES (?, ?)", ("urgent" + str(i), urgent))
            self.db.execute("INSERT INTO pages VALUES (?, ?)", ("ordinary" + str(i), ordinary))
        for i, (_, ordinary) in enumerate(CONTROLS):
            self.db.execute("INSERT INTO pages VALUES (?, ?)", ("control" + str(i), ordinary))

    def tearDown(self):
        self.db.close()

    def test_urgent_pages_exist_and_are_searchable(self):
        for i, (_, urgent, _) in enumerate(CASES):
            with self.subTest(i=i):
                # A source exists for the key medical concept independently of
                # the unrelated how-to words in the question.
                medical_term = ("drowning", "hypothermia", "monoxide")[i]
                titles = [r[0] for r in self.db.execute(
                    "SELECT title FROM pages WHERE pages MATCH ?", (medical_term,))]
                self.assertIn("urgent" + str(i), titles)

    def test_records_current_strict_and_query_for_review(self):
        for query, _, _ in CASES:
            with self.subTest(query=query):
                _, groups = server.query_groups(query)
                self.assertGreater(len(groups), 1)
                self.assertIn(" AND ", server.fts_expr(groups))
                # A strict conjunction can exclude a medically relevant page;
                # this test documents the mechanism, not an acceptable outcome.

    def test_controls_keep_meaningful_query_terms(self):
        for query, _ in CONTROLS:
            with self.subTest(query=query):
                _, groups = server.query_groups(query)
                self.assertTrue(groups)
                self.assertTrue(server.fts_expr(groups))


if __name__ == "__main__":
    unittest.main()
