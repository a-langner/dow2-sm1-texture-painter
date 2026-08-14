import unittest
from collections import Counter

from src.paint_catalog import PaintColor, load_citadel_catalog
from src.paint_color_analysis import (
    ColorGroup,
    PaletteSortMode,
    VISUAL_GROUP_ORDER,
    analyze_perceptual_color,
    classify_paint_color,
    get_paints_for_group,
    sort_palette_paints,
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

    def test_chromatic_boundaries_match_visual_examples(self):
        boundary_pairs = (
            (
                (ColorGroup.RED, paint("warm-red", 150, 12, 9)),
                (ColorGroup.ORANGE, paint("red-orange", 237, 56, 20)),
            ),
            (
                (ColorGroup.ORANGE, paint("orange", 241, 108, 35)),
                (ColorGroup.YELLOW, paint("gold-yellow", 251, 184, 28)),
            ),
            (
                (ColorGroup.YELLOW, paint("yellow", 255, 242, 0)),
                (ColorGroup.GREEN, paint("olive-green", 135, 141, 82)),
            ),
            (
                (ColorGroup.GREEN, paint("blue-green", 6, 155, 125)),
                (ColorGroup.TEAL_CYAN, paint("green-cyan", 16, 132, 115)),
            ),
            (
                (ColorGroup.TEAL_CYAN, paint("cyan", 0, 112, 138)),
                (ColorGroup.BLUE, paint("cyan-blue", 6, 69, 93)),
            ),
            (
                (ColorGroup.BLUE, paint("violet-blue", 44, 45, 139)),
                (ColorGroup.PURPLE, paint("blue-purple", 65, 42, 122)),
            ),
            (
                (ColorGroup.PURPLE, paint("red-purple", 143, 101, 146)),
                (ColorGroup.PINK, paint("purple-pink", 122, 63, 110)),
            ),
            (
                (ColorGroup.PINK, paint("magenta-pink", 222, 0, 123)),
                (ColorGroup.RED, paint("cool-red", 144, 38, 61)),
            ),
        )

        for lower_sample, upper_sample in boundary_pairs:
            for expected_group, sample in (lower_sample, upper_sample):
                with self.subTest(color=sample.id):
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

    def test_near_black_and_charcoal_are_neutral(self):
        for sample in (
            paint("warm-near-black", 23, 19, 20),
            paint("charcoal", 35, 35, 35),
        ):
            with self.subTest(color=sample.id):
                self.assertIs(classify_paint_color(sample), ColorGroup.NEUTRAL)

    def test_dark_chromatic_colors_remain_chromatic(self):
        dark_colors = {
            ColorGroup.RED: paint("dark-red", 80, 0, 0),
            ColorGroup.BLUE: paint("dark-blue", 0, 16, 80),
            ColorGroup.GREEN: paint("dark-green", 0, 60, 20),
            ColorGroup.PURPLE: paint("dark-purple", 45, 14, 66),
        }

        for expected_group, sample in dark_colors.items():
            with self.subTest(color=sample.id):
                self.assertIs(classify_paint_color(sample), expected_group)

    def test_lightness_aware_limit_recognizes_subtly_tinted_light_grey(self):
        light_grey = paint("subtly-tinted-light-grey", 196, 221, 213)

        self.assertIs(classify_paint_color(light_grey), ColorGroup.NEUTRAL)

    def test_known_near_black_catalog_paints_are_neutral(self):
        paints_by_name = {
            sample.name: sample for sample in load_citadel_catalog().paints
        }

        for name in ("Corvus Black", "Mordant Earth"):
            with self.subTest(name=name):
                self.assertIs(
                    classify_paint_color(paints_by_name[name]),
                    ColorGroup.NEUTRAL,
                )

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

    def test_brown_rule_covers_earth_tone_hue_range(self):
        brown_samples = (
            paint("dark-brown", 55, 30, 18),
            paint("reddish-brown", 70, 47, 48),
            paint("orange-brown", 120, 70, 30),
            paint("yellow-brown", 145, 120, 55),
        )

        for sample in brown_samples:
            with self.subTest(color=sample.id):
                self.assertIs(classify_paint_color(sample), ColorGroup.BROWN)

    def test_brown_rule_does_not_capture_vivid_chromatic_colors(self):
        chromatic_samples = {
            ColorGroup.RED: paint("vivid-red", 255, 0, 0),
            ColorGroup.ORANGE: paint("vivid-orange", 255, 128, 0),
            ColorGroup.YELLOW: paint("true-yellow", 255, 255, 0),
        }

        for expected_group, sample in chromatic_samples.items():
            with self.subTest(color=sample.id):
                self.assertIs(classify_paint_color(sample), expected_group)

    def test_brown_rule_excludes_pale_creams_and_green_olives(self):
        non_brown_samples = (
            paint("beige", 220, 205, 165),
            paint("cream", 245, 235, 200),
            paint("olive", 90, 105, 30),
        )

        for sample in non_brown_samples:
            with self.subTest(color=sample.id):
                self.assertIsNot(classify_paint_color(sample), ColorGroup.BROWN)

    def test_light_earth_tone_remains_brown_without_capturing_pale_cream(self):
        light_earth = paint("light-earth", 179, 158, 128)
        pale_cream = paint("pale-cream", 245, 235, 200)

        self.assertIs(classify_paint_color(light_earth), ColorGroup.BROWN)
        self.assertIsNot(classify_paint_color(pale_cream), ColorGroup.BROWN)

    def test_muted_olive_crosses_into_green_before_saturated_yellow(self):
        muted_olive = paint("muted-olive", 182, 183, 136)
        saturated_yellow = paint("saturated-yellow", 255, 242, 0)

        self.assertIs(classify_paint_color(muted_olive), ColorGroup.GREEN)
        self.assertIs(classify_paint_color(saturated_yellow), ColorGroup.YELLOW)

    def test_perceptual_special_cases_precede_hue_sectors(self):
        near_black_red = paint("near-black-red", 23, 19, 20)
        earthy_orange = paint("earthy-orange", 120, 70, 30)
        vivid_orange = paint("vivid-orange", 255, 128, 0)

        self.assertIs(classify_paint_color(near_black_red), ColorGroup.NEUTRAL)
        self.assertIs(classify_paint_color(earthy_orange), ColorGroup.BROWN)
        self.assertIs(classify_paint_color(vivid_orange), ColorGroup.ORANGE)

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

    def test_color_palette_mode_preserves_existing_visual_sort_exactly(self):
        self.assertEqual(
            sort_palette_paints(self.paints, PaletteSortMode.COLOR),
            sort_paints_visually(self.paints),
        )

    def test_alphabetical_palette_mode_is_case_insensitive_and_deterministic(self):
        paints = (
            PaintColor("zulu", "zulu", 0, 0, 0),
            PaintColor("bravo-lower", "bravo", 0, 0, 0),
            PaintColor("alpha", "Alpha", 0, 0, 0),
            PaintColor("bravo-upper", "Bravo", 0, 0, 0),
        )

        self.assertEqual(
            tuple(
                paint.id
                for paint in sort_palette_paints(
                    paints, PaletteSortMode.ALPHABETICAL
                )
            ),
            ("alpha", "bravo-upper", "bravo-lower", "zulu"),
        )

    def test_palette_sort_display_names_resolve_to_internal_modes(self):
        self.assertIs(
            PaletteSortMode.from_display_name("Color"), PaletteSortMode.COLOR
        )
        self.assertIs(
            PaletteSortMode.from_display_name("Alphabetical"),
            PaletteSortMode.ALPHABETICAL,
        )
        with self.assertRaises(ValueError):
            PaletteSortMode.from_display_name("Brightness")

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

    def test_filtered_chromatic_group_avoids_large_lightness_resets(self):
        reds = (
            paint("light-red", 255, 170, 170),
            paint("dark-red", 55, 0, 0),
            paint("medium-red", 160, 20, 20),
        )

        sorted_paints = sort_paints_visually(reds)

        self.assertEqual(
            [sample.id for sample in sorted_paints],
            ["dark-red", "medium-red", "light-red"],
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


class CitadelCatalogClassificationSanityTests(unittest.TestCase):
    def setUp(self):
        self.paints = load_citadel_catalog().paints

    def test_every_catalog_paint_belongs_to_exactly_one_filtered_group(self):
        grouped = {
            color_group: get_paints_for_group(self.paints, color_group)
            for color_group in ColorGroup
        }
        memberships = {
            sample: sum(
                sample in grouped[color_group] for color_group in ColorGroup
            )
            for sample in self.paints
        }
        grouped_paints = tuple(
            sample
            for color_group in ColorGroup
            for sample in grouped[color_group]
        )

        self.assertTrue(all(count == 1 for count in memberships.values()))
        self.assertEqual(len(grouped_paints), len(self.paints))
        self.assertEqual(Counter(grouped_paints), Counter(self.paints))

    def test_real_catalog_classification_and_sorting_are_deterministic(self):
        expected_groups = tuple(classify_paint_color(sample) for sample in self.paints)
        repeated_groups = tuple(classify_paint_color(sample) for sample in self.paints)

        self.assertEqual(repeated_groups, expected_groups)
        self.assertEqual(
            sort_paints_visually(self.paints),
            sort_paints_visually(reversed(self.paints)),
        )

    def test_catalog_rgb_values_remain_unchanged_after_analysis(self):
        before = tuple((sample.r, sample.g, sample.b) for sample in self.paints)

        for sample in self.paints:
            classify_paint_color(sample)
        for color_group in ColorGroup:
            sort_paints_visually(get_paints_for_group(self.paints, color_group))
        sort_paints_visually(self.paints)

        self.assertEqual(
            tuple((sample.r, sample.g, sample.b) for sample in self.paints),
            before,
        )

    def test_very_low_chroma_catalog_paints_do_not_leak_into_chromatic_groups(self):
        very_low_chroma = tuple(
            sample
            for sample in self.paints
            if analyze_perceptual_color(sample).chroma <= 0.01
        )

        self.assertGreater(len(very_low_chroma), 0)
        self.assertTrue(
            all(
                classify_paint_color(sample) is ColorGroup.NEUTRAL
                for sample in very_low_chroma
            )
        )

    def test_clearly_chromatic_dark_catalog_paints_remain_non_neutral(self):
        chromatic_dark_paints = tuple(
            sample
            for sample in self.paints
            if analyze_perceptual_color(sample).lightness <= 0.35
            and analyze_perceptual_color(sample).chroma >= 0.08
        )

        self.assertGreater(len(chromatic_dark_paints), 0)
        self.assertTrue(
            all(
                classify_paint_color(sample) is not ColorGroup.NEUTRAL
                for sample in chromatic_dark_paints
            )
        )

    def test_curated_catalog_classification_regressions(self):
        paints_by_name = {sample.name: sample for sample in self.paints}
        expected_groups = {
            "Corvus Black": ColorGroup.NEUTRAL,
            "Mordant Earth": ColorGroup.NEUTRAL,
            "Mournfang Brown": ColorGroup.BROWN,
            "Camo Green": ColorGroup.GREEN,
        }

        for name, expected_group in expected_groups.items():
            with self.subTest(name=name):
                self.assertIs(
                    classify_paint_color(paints_by_name[name]),
                    expected_group,
                )


if __name__ == "__main__":
    unittest.main()
