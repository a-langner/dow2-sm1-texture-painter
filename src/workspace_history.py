"""Lightweight, session-only history for editable workspace state."""

from copy import deepcopy
from dataclasses import dataclass

from src.color_processing_settings import ColorProcessingSettings
from src.color_slot_state import ColorSlotStates
from src.processing_mode import ProcessingMode
from src.render_settings import RenderSettings
from src.team_color_mask_variant import TeamColorMaskVariant

UNDO_HISTORY_LIMIT = 50


@dataclass(frozen=True)
class EditableWorkspaceState:
    """Immutable pixel-affecting state without textures or transient UI state."""

    color_slot_states: ColorSlotStates
    global_processing: ColorProcessingSettings
    processing_mode: ProcessingMode
    per_color_processing_initialized: bool
    selected_channels: tuple[int, ...]
    apply_alpha: bool
    apply_dirt: bool
    apply_spec: bool
    team_color_mask_variant: TeamColorMaskVariant | None

    @classmethod
    def from_render_settings(
        cls,
        settings: RenderSettings,
        team_color_mask_variant: TeamColorMaskVariant | None,
    ) -> "EditableWorkspaceState":
        """Capture render state while deliberately excluding active-slot focus."""
        return cls(
            color_slot_states=settings.color_slot_states,
            global_processing=settings.global_processing,
            processing_mode=settings.processing_mode,
            per_color_processing_initialized=(
                settings.per_color_processing_initialized
            ),
            selected_channels=settings.tem_selected,
            apply_alpha=settings.apply_alpha,
            apply_dirt=settings.apply_dirt,
            apply_spec=settings.apply_spec,
            team_color_mask_variant=team_color_mask_variant,
        )


class WorkspaceHistory:
    """Bounded Undo/Redo stacks containing independent state snapshots."""

    def __init__(self, limit: int = UNDO_HISTORY_LIMIT) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer.")
        if limit <= 0:
            raise ValueError("limit must be positive.")
        self._limit = limit
        self._undo_stack: list[EditableWorkspaceState] = []
        self._redo_stack: list[EditableWorkspaceState] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)

    def clear(self) -> None:
        """Discard all history at a workspace boundary."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    def record_edit(
        self,
        previous: EditableWorkspaceState,
        current: EditableWorkspaceState,
    ) -> bool:
        """Record one effective edit and invalidate its former Redo branch."""
        if previous == current:
            return False
        self._undo_stack.append(deepcopy(previous))
        if len(self._undo_stack) > self._limit:
            del self._undo_stack[: len(self._undo_stack) - self._limit]
        self._redo_stack.clear()
        return True

    def undo(
        self, current: EditableWorkspaceState
    ) -> EditableWorkspaceState | None:
        """Return the previous state and retain the state being left for Redo."""
        if not self._undo_stack:
            return None
        previous = self._undo_stack.pop()
        self._redo_stack.append(deepcopy(current))
        return deepcopy(previous)

    def redo(
        self, current: EditableWorkspaceState
    ) -> EditableWorkspaceState | None:
        """Return the next state and retain the state being left for Undo."""
        if not self._redo_stack:
            return None
        next_state = self._redo_stack.pop()
        self._undo_stack.append(deepcopy(current))
        if len(self._undo_stack) > self._limit:
            del self._undo_stack[: len(self._undo_stack) - self._limit]
        return deepcopy(next_state)
