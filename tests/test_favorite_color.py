import unittest

from src.favorite_color import (
    CitadelFavoriteColor,
    CustomFavoriteColor,
    FavoriteColor,
    FavoriteColorType,
    resolve_exact_citadel_favorite,
)
from src.paint_catalog import PaintCatalog, PaintColor


class FavoriteColorTests(unittest.TestCase):
    def setUp(self):
        self.first_duplicate = PaintColor("first", "First", 10, 20, 30)
        self.second_duplicate = PaintColor("second", "Second", 10, 20, 30)
        self.catalog = PaintCatalog(
            paints=(
                self.first_duplicate,
                self.second_duplicate,
                PaintColor("unique", "Unique", 40, 50, 60),
            )
        )

    def test_citadel_favorite_stores_only_stable_catalog_identity(self):
        favorite: FavoriteColor = CitadelFavoriteColor("  mephiston-red  ")

        self.assertEqual(favorite.citadel_id, "mephiston-red")
        self.assertIs(favorite.type, FavoriteColorType.CITADEL)
        self.assertEqual(vars(favorite), {"citadel_id": "mephiston-red"})

    def test_custom_favorite_normalizes_name_identity_and_authoritative_hex(self):
        favorite: FavoriteColor = CustomFavoriteColor(
            id="  custom-1  ",
            name="  My Armor Blue  ",
            color="  395c71  ",
        )

        self.assertEqual(favorite.id, "custom-1")
        self.assertEqual(favorite.name, "My Armor Blue")
        self.assertEqual(favorite.color, "#395C71")
        self.assertIs(favorite.type, FavoriteColorType.CUSTOM)

    def test_blank_custom_name_falls_back_to_normalized_hex(self):
        favorite = CustomFavoriteColor("custom-1", "  ", "#abcdef")

        self.assertEqual(favorite.name, "#ABCDEF")

    def test_custom_factory_generates_distinct_stable_identities(self):
        first = CustomFavoriteColor.create("First", "#112233")
        second = CustomFavoriteColor.create("Second", "#112233")

        self.assertTrue(first.id)
        self.assertNotEqual(first.id, second.id)

    def test_favorite_identities_reject_empty_values(self):
        with self.assertRaises(ValueError):
            CitadelFavoriteColor(" ")
        with self.assertRaises(ValueError):
            CustomFavoriteColor(" ", "Name", "#112233")

    def test_custom_color_rejects_non_rgb_hex_without_hsv_or_hsl_storage(self):
        with self.assertRaises(ValueError):
            CustomFavoriteColor("custom-1", "Name", "#1234")

    def test_explicit_exact_identity_wins_for_duplicate_rgb(self):
        favorite = resolve_exact_citadel_favorite(
            self.catalog,
            "#0A141E",
            explicit_citadel_id="second",
        )

        self.assertEqual(favorite, CitadelFavoriteColor("second"))

    def test_manual_exact_rgb_uses_existing_canonical_catalog_identity(self):
        favorite = resolve_exact_citadel_favorite(self.catalog, "0a141e")

        self.assertEqual(favorite, CitadelFavoriteColor("first"))

    def test_stale_explicit_identity_falls_back_to_current_exact_rgb(self):
        favorite = resolve_exact_citadel_favorite(
            self.catalog,
            "#28323C",
            explicit_citadel_id="second",
        )

        self.assertEqual(favorite, CitadelFavoriteColor("unique"))

    def test_unmatched_exact_rgb_resolves_as_custom(self):
        favorite = resolve_exact_citadel_favorite(self.catalog, "#010203")

        self.assertIsNone(favorite)


if __name__ == "__main__":
    unittest.main()
