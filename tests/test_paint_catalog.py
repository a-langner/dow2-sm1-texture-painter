import json
import tempfile
import unittest
from pathlib import Path

from src.paint_catalog import (
    PaintCatalog,
    PaintCatalogError,
    PaintColor,
    load_citadel_catalog,
)


VALID_DOCUMENT = {
    "schemaVersion": 1,
    "brand": "Citadel",
    "paints": [
        {
            "id": "ardcoat",
            "name": "'Ardcoat",
            "rgb": {"r": 249, "g": 249, "b": 249},
        }
    ],
}


class PaintCatalogTests(unittest.TestCase):
    def _write_catalog(self, directory: str, document: object) -> Path:
        path = Path(directory) / "citadel.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_loads_bundled_catalog_as_typed_paints(self):
        catalog = load_citadel_catalog()

        self.assertTrue(catalog.paints)
        self.assertTrue(all(isinstance(paint, PaintColor) for paint in catalog.paints))
        ardcoat = next(paint for paint in catalog.paints if paint.id == "ardcoat")
        self.assertEqual(ardcoat.name, "'Ardcoat")
        self.assertEqual((ardcoat.r, ardcoat.g, ardcoat.b), (249, 249, 249))

    def test_parses_all_required_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_catalog(directory, VALID_DOCUMENT)

            catalog = load_citadel_catalog(path)

        self.assertEqual(
            catalog.paints,
            (PaintColor("ardcoat", "'Ardcoat", 249, 249, 249),),
        )

    def test_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "citadel.json"
            path.write_text("{not-json", encoding="utf-8")

            with self.assertLogs("src.paint_catalog", level="ERROR"):
                with self.assertRaisesRegex(PaintCatalogError, "invalid JSON"):
                    load_citadel_catalog(path)

    def test_rejects_missing_required_field(self):
        document = json.loads(json.dumps(VALID_DOCUMENT))
        del document["paints"][0]["name"]

        with tempfile.TemporaryDirectory() as directory:
            path = self._write_catalog(directory, document)

            with self.assertRaisesRegex(PaintCatalogError, "missing 'name'"):
                load_citadel_catalog(path)

    def test_rejects_invalid_rgb_types(self):
        for invalid_value in (True, 1.5, "1", None):
            with self.subTest(value=invalid_value):
                document = json.loads(json.dumps(VALID_DOCUMENT))
                document["paints"][0]["rgb"]["r"] = invalid_value
                with tempfile.TemporaryDirectory() as directory:
                    path = self._write_catalog(directory, document)

                    with self.assertRaisesRegex(PaintCatalogError, "channel 'r'"):
                        load_citadel_catalog(path)

    def test_rejects_out_of_range_rgb_values(self):
        for invalid_value in (-1, 256):
            with self.subTest(value=invalid_value):
                document = json.loads(json.dumps(VALID_DOCUMENT))
                document["paints"][0]["rgb"]["b"] = invalid_value
                with tempfile.TemporaryDirectory() as directory:
                    path = self._write_catalog(directory, document)

                    with self.assertRaisesRegex(PaintCatalogError, "channel 'b'"):
                        load_citadel_catalog(path)

    def test_reports_missing_catalog_file(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing.json"

            with self.assertRaisesRegex(PaintCatalogError, "Could not read"):
                load_citadel_catalog(missing_path)

    def test_exact_rgb_lookup_returns_existing_catalog_record(self):
        catalog = load_citadel_catalog()
        mephiston_red = next(
            paint for paint in catalog.paints if paint.id == "mephiston-red"
        )

        match = catalog.find_exact_rgb((150, 12, 9))

        self.assertIs(match, mephiston_red)

    def test_rgb_lookup_rejects_one_channel_difference(self):
        catalog = load_citadel_catalog()

        self.assertIsNone(catalog.find_exact_rgb((151, 12, 9)))

    def test_rgb_lookup_rejects_arbitrary_non_catalog_color(self):
        catalog = load_citadel_catalog()

        self.assertIsNone(catalog.find_exact_rgb((1, 2, 3)))

    def test_duplicate_rgb_lookup_uses_first_catalog_record(self):
        first = PaintColor("first", "First", 10, 20, 30)
        second = PaintColor("second", "Second", 10, 20, 30)
        catalog = PaintCatalog((first, second))

        self.assertIs(catalog.find_exact_rgb((10, 20, 30)), first)

    def test_stable_id_lookup_returns_exact_catalog_record(self):
        catalog = load_citadel_catalog()
        paint = catalog.paints[10]

        self.assertIs(catalog.find_by_id(paint.id), paint)
        self.assertIsNone(catalog.find_by_id("missing-paint-id"))

    def test_real_duplicate_rgb_uses_first_catalog_entry(self):
        catalog = load_citadel_catalog()

        match = catalog.find_exact_rgb((0, 0, 0))

        self.assertIsNotNone(match)
        self.assertEqual(match.id, "abaddon-black")

    def test_rgb_lookup_index_reuses_loaded_paint_objects(self):
        catalog = load_citadel_catalog()

        for paint in catalog.paints:
            match = catalog.find_exact_rgb((paint.r, paint.g, paint.b))
            self.assertTrue(
                any(match is catalog_paint for catalog_paint in catalog.paints)
            )


if __name__ == "__main__":
    unittest.main()
