import unittest

from src.color_picker_visual import (
    clamp_coordinate,
    hsl_field_position,
    hsl_from_field_position,
    hsl_to_rgb_hex,
    hsv_field_position,
    hsv_from_field_position,
    hsv_to_rgb_hex,
    hue_from_slider_position,
    hue_slider_position,
)


class ColorPickerVisualTests(unittest.TestCase):
    def test_field_edges_map_saturation_and_value(self):
        self.assertEqual(hsv_from_field_position(0, 0, 101, 101, 0.5), (0.5, 0.0, 1.0))
        self.assertEqual(hsv_from_field_position(100, 100, 101, 101, 0.5), (0.5, 1.0, 0.0))

    def test_field_mapping_round_trips(self):
        x, y = hsv_field_position(0.25, 0.75, 101, 201)
        self.assertEqual((x, y), (25.0, 50.0))
        self.assertEqual(hsv_from_field_position(x, y, 101, 201, 0.4), (0.4, 0.25, 0.75))

    def test_hue_slider_endpoints_and_round_trip(self):
        self.assertEqual(hue_from_slider_position(0, 101), 0.0)
        self.assertEqual(hue_from_slider_position(100, 101), 1.0)
        self.assertEqual(hue_slider_position(0.5, 101), 50.0)

    def test_coordinates_are_clamped(self):
        self.assertEqual(clamp_coordinate(-20, 100), 0.0)
        self.assertEqual(clamp_coordinate(120, 100), 99.0)
        self.assertEqual(hsv_from_field_position(-1, 500, 101, 101, 0.0), (0.0, 0.0, 0.0))

    def test_representative_hsv_values_produce_expected_rgb(self):
        self.assertEqual(hsv_to_rgb_hex(0.0, 1.0, 1.0), "#ff0000")
        self.assertEqual(hsv_to_rgb_hex(1 / 3, 1.0, 1.0), "#00ff00")
        self.assertEqual(hsv_to_rgb_hex(2 / 3, 1.0, 1.0), "#0000ff")
        self.assertEqual(hsv_to_rgb_hex(0.2, 0.0, 0.5), "#808080")

    def test_hsl_field_mapping_and_round_trip(self):
        self.assertEqual(
            hsl_from_field_position(0, 0, 101, 101, 0.5),
            (0.5, 0.0, 1.0),
        )
        x, y = hsl_field_position(0.25, 0.75, 101, 201)
        self.assertEqual((x, y), (25.0, 50.0))
        self.assertEqual(
            hsl_from_field_position(x, y, 101, 201, 0.4),
            (0.4, 0.25, 0.75),
        )

    def test_representative_hsl_values_produce_expected_rgb(self):
        self.assertEqual(hsl_to_rgb_hex(0.0, 1.0, 0.5), "#ff0000")
        self.assertEqual(hsl_to_rgb_hex(1 / 3, 1.0, 0.5), "#00ff00")
        self.assertEqual(hsl_to_rgb_hex(2 / 3, 1.0, 0.5), "#0000ff")
        self.assertEqual(hsl_to_rgb_hex(0.2, 0.0, 0.5), "#808080")


if __name__ == "__main__":
    unittest.main()
