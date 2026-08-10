import json
import tempfile
import unittest
from pathlib import Path

from src.paint_catalog import PaintCatalogError, PaintColor, load_citadel_catalog


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


if __name__ == "__main__":
    unittest.main()
