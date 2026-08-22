import unittest

from src.favorite_color import (
    CitadelFavoriteColor,
    CustomFavoriteColor,
    FavoriteColor,
    FavoriteColorType,
)


class FavoriteColorTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
