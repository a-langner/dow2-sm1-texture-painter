import unittest
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.color_pattern_handler import (
    CUSTOM_FAVORITE_IDENTITIES_KEY,
    _stored_pattern,
    color_key,
    get_pattern_color_identities,
    parse_pattern_color_identities,
)
from src.color_processing_settings import DEFAULT_COLOR_PROCESSING_SETTINGS
from src.color_slot_state import ColorSlotState, CustomFavoriteIdentity
from src.favorite_color import (
    CustomFavoriteColor,
    FavoriteColorLibrary,
    FavoritePaletteColor,
)
from src.frame_main import ArmyPainter
from src.paint_catalog import PaintCatalog, PaintColor
from src.pattern_exchange import (
    create_pattern_collection_exchange_document,
    create_pattern_exchange_document,
    validate_imported_pattern,
    validate_imported_pattern_collection,
)
from src.render_settings import DEFAULT_RENDER_SETTINGS
from src.widget import (
    ColorPickerDialog,
    SelectedColor,
    color_slot_presentation,
)
from src.workspace_history import EditableWorkspaceState


IDENTITY = CustomFavoriteIdentity("custom-1", "My Armor Blue")
COLOR = "#395c71"


class CustomFavoriteSlotIdentityTests(unittest.TestCase):
    def test_slot_display_prefers_citadel_then_custom_identity_then_hex(self):
        def measure(text):
            return len(text) * 5

        custom = color_slot_presentation(
            COLOR, PaintCatalog(()), 82, measure, IDENTITY
        )
        ordinary = color_slot_presentation(COLOR, PaintCatalog(()), 82, measure)
        citadel = PaintColor("citadel", "Canonical Blue", 57, 92, 113)
        canonical = color_slot_presentation(
            COLOR, PaintCatalog((citadel,)), 82, measure, IDENTITY
        )

        self.assertEqual(custom.text, "My Armor Blue")
        self.assertEqual(ordinary.text, "#395C71")
        self.assertEqual(canonical.text, "Canonical Blue")

    def test_picker_returns_string_compatible_custom_favorite_identity(self):
        favorite = CustomFavoriteColor("custom-1", "My Armor Blue", COLOR)
        tile = FavoritePaletteColor(
            "custom:custom-1", "My Armor Blue", 57, 92, 113, favorite
        )
        dialog = object.__new__(ColorPickerDialog)
        dialog.selected_paint_id = None
        dialog.current_color = "#000000"
        dialog.current_custom_favorite = None
        dialog.paint_catalog = PaintCatalog(())
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog, (favorite,)
        )
        dialog.palette_grid = Mock()
        dialog._refresh_color_representations = Mock()
        dialog._remember_accepted_color = Mock()
        dialog._save_geometry = Mock()
        dialog.destroy = Mock()

        dialog.select_paint(tile)
        dialog.accept()

        result = dialog.get_accepted_color()
        self.assertIsInstance(result, str)
        self.assertEqual(result, COLOR)
        self.assertEqual(result.custom_favorite, IDENTITY)

    def test_manual_edit_re_resolves_exact_custom_or_clears_stale_identity(self):
        first = CustomFavoriteColor("custom-1", "My Armor Blue", COLOR)
        second = CustomFavoriteColor("custom-2", "Edge Blue", "#395C72")
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog(())
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog, (first, second)
        )
        dialog.current_custom_favorite = IDENTITY
        dialog._refresh_color_representations = Mock()

        dialog.set_current_color("#395C72")
        self.assertEqual(
            dialog.current_custom_favorite,
            CustomFavoriteIdentity("custom-2", "Edge Blue"),
        )

        dialog.set_current_color("#395C73")
        self.assertIsNone(dialog.current_custom_favorite)

    def test_manual_exact_citadel_match_wins_over_custom_identity(self):
        paint = PaintColor("citadel", "Canonical Blue", 57, 92, 113)
        custom = CustomFavoriteColor("custom-1", "My Armor Blue", COLOR)
        dialog = object.__new__(ColorPickerDialog)
        dialog.paint_catalog = PaintCatalog((paint,))
        dialog.favorite_library = FavoriteColorLibrary(
            dialog.paint_catalog, (custom,)
        )
        dialog.current_custom_favorite = IDENTITY
        dialog._refresh_color_representations = Mock()

        dialog.set_current_color(COLOR)

        self.assertIsNone(dialog.current_custom_favorite)

    def test_slot_state_swap_and_workspace_restore_keep_identity(self):
        states = list(DEFAULT_RENDER_SETTINGS.color_slot_states)
        states[0] = ColorSlotState(
            COLOR, DEFAULT_COLOR_PROCESSING_SETTINGS, IDENTITY
        )
        settings = DEFAULT_RENDER_SETTINGS.with_color_slot_states(tuple(states))
        swapped = list(settings.color_slot_states)
        swapped[0], swapped[2] = swapped[2], swapped[0]
        settings = settings.with_color_slot_states(tuple(swapped))

        snapshot = EditableWorkspaceState.from_render_settings(settings, None)
        restored = snapshot.restore_render_settings(DEFAULT_RENDER_SETTINGS)

        self.assertIsNone(restored.color_slot_states[0].custom_favorite)
        self.assertEqual(restored.color_slot_states[2].custom_favorite, IDENTITY)

    def test_copy_and_both_paste_modes_keep_identity(self):
        states = list(DEFAULT_RENDER_SETTINGS.color_slot_states)
        states[0] = ColorSlotState(
            COLOR, DEFAULT_COLOR_PROCESSING_SETTINGS, IDENTITY
        )
        settings = DEFAULT_RENDER_SETTINGS.with_color_slot_states(tuple(states))
        chooser = SimpleNamespace(
            color_boxes=[{"bg": state.color} for state in states],
            _color_identities=[state.custom_favorite for state in states],
            draw_rgb_value=Mock(),
        )
        painter = SimpleNamespace(
            render_settings=settings,
            frame_color_chooser=chooser,
            _color_slot_clipboard_color=None,
            _color_slot_clipboard_identity=None,
            _color_slot_clipboard_state=None,
            update_pattern_action_states=Mock(),
            refresh_workspace=Mock(),
        )

        with patch.object(ArmyPainter, "sync_render_settings"), patch.object(
            ArmyPainter, "capture_editable_workspace_state", return_value=Mock()
        ), patch.object(ArmyPainter, "record_workspace_edit"):
            ArmyPainter.copy_color_slot(painter, 0)
            ArmyPainter.paste_color_slot(painter, 1)
            ArmyPainter.copy_color_slot_with_settings(painter, 0)
            ArmyPainter.paste_color_slot_with_settings(painter, 3)

        self.assertEqual(
            painter.render_settings.color_slot_states[1].custom_favorite,
            IDENTITY,
        )
        self.assertEqual(
            painter.render_settings.color_slot_states[3].custom_favorite,
            IDENTITY,
        )

    def test_pattern_metadata_is_optional_and_round_trips(self):
        colors = [COLOR, "#111111", "#222222", "#333333"]
        identities = (IDENTITY, None, None, None)
        stored = _stored_pattern(colors, None, color_identities=identities)
        legacy = OrderedDict(zip(color_key, colors))

        with patch(
            "src.color_pattern_handler.get_all_patterns",
            return_value={"Named": stored, "Legacy": legacy},
        ):
            self.assertEqual(get_pattern_color_identities("Named"), identities)
            self.assertEqual(
                get_pattern_color_identities("Legacy"),
                (None, None, None, None),
            )

        self.assertIn(CUSTOM_FAVORITE_IDENTITIES_KEY, stored)
        self.assertNotIn(CUSTOM_FAVORITE_IDENTITIES_KEY, legacy)

    def test_single_and_collection_exchange_preserve_identity(self):
        colors = [COLOR, "#111111", "#222222", "#333333"]
        stored = _stored_pattern(
            colors, None, color_identities=(IDENTITY, None, None, None)
        )
        single = create_pattern_exchange_document("Named", stored)
        imported = validate_imported_pattern(single)
        collection = create_pattern_collection_exchange_document(
            "Collection", (("Named", stored),)
        )
        imported_collection = validate_imported_pattern_collection(collection)

        self.assertEqual(
            parse_pattern_color_identities(
                imported[CUSTOM_FAVORITE_IDENTITIES_KEY]
            )[0],
            IDENTITY,
        )
        self.assertEqual(
            imported_collection.patterns[0].color_identities[0], IDENTITY
        )

    def test_manual_color_result_has_no_custom_identity(self):
        result = SelectedColor("#010203")

        self.assertIsNone(result.custom_favorite)


if __name__ == "__main__":
    unittest.main()
