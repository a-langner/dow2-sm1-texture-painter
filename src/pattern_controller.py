"""Pattern workflow orchestration independent of Tk widgets."""

from dataclasses import dataclass
import logging

import src.color_pattern_handler as pattern_store
from src.color_pattern_handler import (
    InvalidPatternError,
    get_pattern_colors,
    normalize_pattern_name,
    pattern_colors_equal,
)
from src.pattern_exchange import (
    BuiltinPatternImportConflictError,
    UserPatternImportConflictError,
    analyze_pattern_collection_import,
    export_pattern,
    export_user_pattern_collection,
    import_analyzed_pattern_collection,
    import_pattern,
    read_pattern_collection_file,
    read_pattern_file,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PatternOperationResult:
    """Describe GUI state changes resulting from a Pattern operation."""

    selected_name: str | None = None
    colors_to_apply: tuple[str, ...] | None = None
    list_changed: bool = False
    persisted: bool = False
    changed: bool = False
    selected_data_changed: bool = False


@dataclass(frozen=True)
class PatternImportPreparation:
    imported_pattern: object
    source: object


@dataclass(frozen=True)
class CollectionImportPreparation:
    collection: object
    analysis: object
    source: object


class PatternController:
    """Coordinate Pattern persistence and exchange without accessing widgets."""

    def __init__(
        self,
        *,
        file_selection=None,
        store=pattern_store,
        get_colors=get_pattern_colors,
        read_single=read_pattern_file,
        persist_single_import=import_pattern,
        export_single=export_pattern,
        read_collection=read_pattern_collection_file,
        analyze_collection=analyze_pattern_collection_import,
        persist_collection=import_analyzed_pattern_collection,
        export_collection=export_user_pattern_collection,
    ):
        self.file_selection = file_selection
        self.store = store
        self.get_colors = get_colors
        self.read_single = read_single
        self.persist_single_import = persist_single_import
        self.export_single = export_single
        self.read_collection = read_collection
        self.analyze_collection = analyze_collection
        self.persist_collection = persist_collection
        self.export_collection = export_collection

    def save_new_pattern(self, name, current_colors):
        normalized_name = normalize_pattern_name(name)
        self.store.save(name=normalized_name, colors=current_colors)
        return PatternOperationResult(
            selected_name=normalized_name,
            list_changed=True,
            persisted=True,
            changed=True,
        )

    def update_pattern(self, pattern_name, current_colors):
        stored_colors = self.get_colors(pattern_name)
        if pattern_colors_equal(current_colors, stored_colors):
            return PatternOperationResult(selected_name=pattern_name)
        self.store.update_user_pattern(pattern_name, current_colors)
        return PatternOperationResult(
            selected_name=pattern_name,
            persisted=True,
            changed=True,
        )

    def pattern_is_modified(self, pattern_name, current_colors):
        return not pattern_colors_equal(current_colors, self.get_colors(pattern_name))

    def rename_pattern(self, old_name, new_name):
        normalized_name = normalize_pattern_name(new_name)
        if normalized_name == old_name:
            return PatternOperationResult(selected_name=old_name)
        renamed_name = self.store.rename_user_pattern(old_name, normalized_name)
        return PatternOperationResult(
            selected_name=renamed_name,
            list_changed=True,
            persisted=True,
            changed=True,
        )

    def duplicate_pattern(self, source_name, new_name):
        stored_colors = self.get_colors(source_name)
        normalized_name = normalize_pattern_name(new_name)
        self.store.save(normalized_name, stored_colors)
        return PatternOperationResult(
            selected_name=normalized_name,
            colors_to_apply=tuple(stored_colors),
            list_changed=True,
            persisted=True,
            changed=True,
        )

    def delete_pattern(self, name, fallback_name=None):
        self.store.delete(name)
        return PatternOperationResult(
            selected_name=fallback_name,
            list_changed=True,
            persisted=True,
            changed=True,
        )

    def reset_pattern(self, name):
        return PatternOperationResult(
            selected_name=name,
            colors_to_apply=tuple(self.get_colors(name)),
            changed=True,
        )

    def prepare_single_import(self, source):
        imported = self.read_single(source)
        self._remember_import(source)
        return PatternImportPreparation(imported, source)

    def import_single(
        self,
        preparation,
        *,
        selected_name,
        choose_conflict,
        request_rename,
        report_invalid_name,
    ):
        overwritten = False

        def persist(pattern, target_name=None, overwrite=False):
            nonlocal overwritten
            persisted_name = self.persist_single_import(
                pattern, target_name=target_name, overwrite=overwrite
            )
            overwritten = overwrite
            return persisted_name

        imported_name = resolve_pattern_import_conflicts(
            preparation.imported_pattern,
            persist,
            choose_conflict,
            request_rename,
            report_invalid_name,
        )
        if imported_name is None:
            return PatternOperationResult(selected_name=selected_name)
        restored_name, apply_colors = single_import_selection_policy(
            selected_name, imported_name, overwritten
        )
        colors = (
            _ordered_imported_colors(preparation.imported_pattern)
            if apply_colors
            else None
        )
        return PatternOperationResult(
            selected_name=restored_name,
            colors_to_apply=colors,
            list_changed=True,
            persisted=True,
            changed=True,
        )

    def export_selected(self, name, destination):
        self.export_single(name, destination)
        self._remember_export(destination)

    def prepare_collection_import(self, source):
        collection = self.read_collection(source)
        self._remember_import(source)
        return CollectionImportPreparation(
            collection,
            self.analyze_collection(collection),
            source,
        )

    def import_collection(
        self, preparation, *, selected_name, overwrite_user_conflicts
    ):
        result = self.persist_collection(
            preparation.analysis,
            overwrite_user_conflicts=overwrite_user_conflicts,
        )
        selected_overwritten = collection_selection_was_overwritten(
            selected_name,
            preparation.analysis,
            overwrite_user_conflicts,
        )
        colors = None
        if selected_overwritten:
            colors = next(
                _ordered_imported_colors(pattern)
                for pattern in preparation.analysis.user_conflicts
                if pattern.name == selected_name
            )
        operation = PatternOperationResult(
            selected_name=selected_name,
            colors_to_apply=colors,
            list_changed=True,
            persisted=bool(result.imported_count or result.overwritten_count),
            changed=bool(result.imported_count or result.overwritten_count),
            selected_data_changed=selected_overwritten,
        )
        return operation, result

    def export_user_collection(self, collection_name, destination):
        self.export_collection(collection_name, destination)
        self._remember_export(destination)

    def _remember_import(self, source):
        if self.file_selection is not None:
            try:
                self.file_selection.remember_successful_pattern_import(source)
            except OSError:
                LOGGER.exception(
                    "Could not remember Pattern import directory for %s", source
                )

    def _remember_export(self, destination):
        if self.file_selection is not None:
            try:
                self.file_selection.remember_successful_pattern_export(destination)
            except OSError:
                LOGGER.exception(
                    "Could not remember Pattern export directory for %s",
                    destination,
                )


def collection_selection_was_overwritten(
    selected_pattern_name, analysis, overwrite_user_conflicts
):
    if selected_pattern_name is None or not overwrite_user_conflicts:
        return False
    return any(
        pattern.name == selected_pattern_name for pattern in analysis.user_conflicts
    )


def _ordered_imported_colors(pattern):
    try:
        return tuple(pattern.colors[key] for key in pattern_store.color_key)
    except KeyError:
        return None


def single_import_selection_policy(
    selected_pattern_name, imported_pattern_name, overwritten
):
    if overwritten:
        selected_was_overwritten = (
            selected_pattern_name is not None
            and selected_pattern_name == imported_pattern_name
        )
        return selected_pattern_name, selected_was_overwritten
    return imported_pattern_name, True


def resolve_pattern_import_conflicts(
    imported_pattern,
    persist,
    choose_conflict,
    request_rename,
    report_invalid_name,
):
    """Resolve import conflicts iteratively without coupling policy to Tk."""
    target_name = None
    overwrite = False
    while True:
        try:
            return persist(
                imported_pattern,
                target_name=target_name,
                overwrite=overwrite,
            )
        except BuiltinPatternImportConflictError:
            conflict_type = "builtin"
        except UserPatternImportConflictError:
            conflict_type = "user"

        effective_name = target_name or imported_pattern.name
        decision = choose_conflict(conflict_type, effective_name)
        if decision == "cancel":
            return None
        if decision == "overwrite" and conflict_type == "user":
            overwrite = True
            continue
        if decision != "rename":
            return None

        while True:
            replacement_name = request_rename(effective_name)
            if replacement_name is None:
                return None
            try:
                target_name = normalize_pattern_name(replacement_name)
            except InvalidPatternError as exc:
                report_invalid_name(str(exc))
                continue
            overwrite = False
            break
