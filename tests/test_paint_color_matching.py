import unittest
from unittest.mock import patch

from src.favorite_color import CustomFavoriteColor, FavoriteColorLibrary
from src.paint_catalog import PaintCatalog, PaintColor, load_citadel_catalog
from src.paint_color_matching import LabColor, ciede2000, find_closest_paints


class PaintColorMatchingTests(unittest.TestCase):
    def test_ciede2000_matches_published_reference_pair(self):
        first = LabColor(50.0, 2.6772, -79.7751)
        second = LabColor(50.0, 0.0, -82.7485)

        self.assertAlmostEqual(ciede2000(first, second), 2.0425, places=4)

    def test_returns_three_catalog_paints_in_ascending_delta_e_order(self):
        paints = (
            PaintColor("far", "Far", 240, 220, 20),
            PaintColor("exact", "Exact", 40, 80, 120),
            PaintColor("nearer", "Nearer", 42, 82, 122),
            PaintColor("near", "Near", 50, 90, 130),
        )

        matches = find_closest_paints("#285078", PaintCatalog(paints))

        self.assertEqual(
            [match.paint.id for match in matches],
            ["exact", "nearer", "near"],
        )
        self.assertEqual(
            [match.delta_e for match in matches],
            sorted(match.delta_e for match in matches),
        )

    def test_custom_favorites_are_not_matching_candidates(self):
        catalog = PaintCatalog((PaintColor("citadel", "Citadel", 12, 34, 57),))
        custom = CustomFavoriteColor("custom", "Exact Custom", "#0C2238")
        library = FavoriteColorLibrary(catalog, (custom,))

        matches = find_closest_paints(custom.color, library.catalog)

        self.assertEqual([match.paint.id for match in matches], ["citadel"])

    def test_default_match_evaluates_every_bundled_citadel_paint(self):
        catalog = load_citadel_catalog()

        with patch(
            "src.paint_color_matching.ciede2000",
            wraps=ciede2000,
        ) as delta_e:
            matches = find_closest_paints("#395C71", catalog)

        self.assertEqual(len(matches), 3)
        self.assertEqual(delta_e.call_count, len(catalog.paints))


if __name__ == "__main__":
    unittest.main()
