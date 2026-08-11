import unittest
from collections import Counter

from src.paint_catalog import PaintColor, load_citadel_catalog
from src.paint_color_analysis import (
    ColorGroup,
    VISUAL_GROUP_ORDER,
    analyze_perceptual_color,
    classify_paint_color,
    get_paints_for_group,
    sort_paints_visually,
)


def paint(identifier, red, green, blue):
    return PaintColor(identifier, identifier, red, green, blue)


REPRESENTATIVE_PAINTS = {
    ColorGroup.RED: paint("red", 255, 0, 0),
    ColorGroup.ORANGE: paint("orange", 255, 128, 0),
    ColorGroup.YELLOW: paint("yellow", 255, 255, 0),
    ColorGroup.GREEN: paint("green", 0, 255, 0),
    ColorGroup.TEAL_CYAN: paint("cyan", 0, 255, 255),
    ColorGroup.BLUE: paint("blue", 0, 0, 255),
    ColorGroup.PURPLE: paint("purple", 128, 0, 255),
    ColorGroup.PINK: paint("pink", 255, 0, 128),
    ColorGroup.BROWN: paint("brown", 120, 70, 30),
}


class PaintColorClassificationTests(unittest.TestCase):
    def test_representative_chromatic_colors_cover_each_group(self):
        for expected_group, sample in REPRESENTATIVE_PAINTS.items():
            with self.subTest(group=expected_group.value):
                self.assertIs(classify_paint_color(sample), expected_group)

    def test_black_white_and_grey_are_neutrals(self):
        neutral_samples = (
            paint("black", 0, 0, 0),
            paint("white", 255, 255, 255),
            paint("grey", 128, 128, 128),
        )

        for sample in neutral_samples:
            with self.subTest(color=sample.id):
                self.assertIs(classify_paint_color(sample), ColorGroup.NEUTRAL)

    def test_low_saturation_colors_are_consistently_neutral(self):
        low_saturation_samples = (
            paint("warm-near-grey", 120, 115, 110),
            paint("cool-near-grey", 110, 115, 120),
            paint("light-near-grey", 230, 225, 225),
        )

        for sample in low_saturation_samples:
            with self.subTest(color=sample.id):
                self.assertIs(classify_paint_color(sample), ColorGroup.NEUTRAL)

    def test_brown_heuristic_separates_dark_orange_hues(self):
        brown = REPRESENTATIVE_PAINTS[ColorGroup.BROWN]
        bright_orange = REPRESENTATIVE_PAINTS[ColorGroup.ORANGE]

        self.assertIs(classify_paint_color(brown), ColorGroup.BROWN)
        self.assertIs(classify_paint_color(bright_orange), ColorGroup.ORANGE)

    def test_classification_uses_rgb_instead_of_paint_name(self):
        misleading_name = PaintColor("not-blue", "Definitely Blue", 255, 0, 0)

        self.assertIs(classify_paint_color(misleading_name), ColorGroup.RED)


class PaintColorSortingTests(unittest.TestCase):
    def setUp(self):
        self.paints = tuple(reversed(tuple(REPRESENTATIVE_PAINTS.values()))) + (
            paint("black", 0, 0, 0),
            paint("white", 255, 255, 255),
            paint("grey", 128, 128, 128),
            paint("second-red", 180, 20, 20),
        )

    def test_sorting_is_deterministic_for_different_input_orders(self):
        expected = sort_paints_visually(self.paints)

        self.assertEqual(sort_paints_visually(self.paints), expected)
        self.assertEqual(sort_paints_visually(reversed(self.paints)), expected)

    def test_sorting_contains_exactly_the_input_paints(self):
        sorted_paints = sort_paints_visually(self.paints)

        self.assertEqual(len(sorted_paints), len(self.paints))
        self.assertEqual(Counter(sorted_paints), Counter(self.paints))

    def test_sorting_retains_every_real_catalog_paint_exactly_once(self):
        catalog_paints = load_citadel_catalog().paints

        sorted_paints = sort_paints_visually(catalog_paints)

        self.assertEqual(len(sorted_paints), len(catalog_paints))
        self.assertEqual(Counter(sorted_paints), Counter(catalog_paints))

    def test_all_colors_follow_a_broad_perceptual_hue_progression(self):
        spectrum_groups = (
            ColorGroup.RED,
            ColorGroup.ORANGE,
            ColorGroup.YELLOW,
            ColorGroup.GREEN,
            ColorGroup.TEAL_CYAN,
            ColorGroup.BLUE,
            ColorGroup.PURPLE,
            ColorGroup.PINK,
        )
        samples = tuple(REPRESENTATIVE_PAINTS[group] for group in spectrum_groups)

        sorted_paints = sort_paints_visually(reversed(samples))

        self.assertEqual(
            [classify_paint_color(sample) for sample in sorted_paints],
            list(spectrum_groups),
        )

    def test_neutrals_are_ordered_primarily_by_perceptual_lightness(self):
        neutrals = (
            paint("white", 255, 255, 255),
            paint("dark-grey", 48, 48, 48),
            paint("light-grey", 190, 190, 190),
            paint("black", 0, 0, 0),
        )

        sorted_paints = sort_paints_visually(neutrals)
        lightnesses = [
            analyze_perceptual_color(sample).lightness for sample in sorted_paints
        ]

        self.assertEqual(lightnesses, sorted(lightnesses))
        self.assertEqual(
            [sample.id for sample in sorted_paints],
            ["black", "dark-grey", "light-grey", "white"],
        )

    def test_sorting_does_not_modify_paint_records_or_rgb_values(self):
        before = tuple(
            (sample.id, sample.name, sample.r, sample.g, sample.b)
            for sample in self.paints
        )

        sort_paints_visually(self.paints)

        self.assertEqual(
            tuple(
                (sample.id, sample.name, sample.r, sample.g, sample.b)
                for sample in self.paints
            ),
            before,
        )

    def test_grouping_loses_and_duplicates_no_paints(self):
        grouped_paints = tuple(
            sample
            for color_group in ColorGroup
            for sample in get_paints_for_group(self.paints, color_group)
        )

        self.assertEqual(len(grouped_paints), len(self.paints))
        self.assertEqual(Counter(grouped_paints), Counter(self.paints))


if __name__ == "__main__":
    unittest.main()
