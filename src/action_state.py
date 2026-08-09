"""Pure Pattern action-state policy without GUI dependencies."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternActionContext:
    has_selection: bool
    selected_is_user_pattern: bool
    selected_is_dirty: bool
    has_any_user_patterns: bool


@dataclass(frozen=True)
class PatternActionState:
    save_new_enabled: bool
    update_enabled: bool
    reset_enabled: bool
    rename_enabled: bool
    duplicate_enabled: bool
    delete_enabled: bool
    export_selected_enabled: bool
    export_all_enabled: bool
    modified_indicator_visible: bool


def derive_pattern_action_state(
    context: PatternActionContext,
) -> PatternActionState:
    """Derive every Pattern command state from one immutable context."""
    has_selection = bool(context.has_selection)
    user_selected = bool(has_selection and context.selected_is_user_pattern)
    dirty = bool(has_selection and context.selected_is_dirty)
    return PatternActionState(
        save_new_enabled=True,
        update_enabled=user_selected and dirty,
        reset_enabled=dirty,
        rename_enabled=user_selected,
        duplicate_enabled=has_selection,
        delete_enabled=user_selected,
        export_selected_enabled=has_selection,
        export_all_enabled=bool(context.has_any_user_patterns),
        modified_indicator_visible=dirty,
    )
