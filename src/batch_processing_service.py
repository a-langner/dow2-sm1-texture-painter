"""Non-GUI batch recoloring and filesystem orchestration."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
import logging
import os
from pathlib import Path
from queue import Queue
import tempfile
from threading import Event
from typing import Callable, Literal

from PIL import Image

from src.dow1_converter import (
    convert_tem_texture,
    get_tem_filenames,
    team_color_output_path,
)
from src.image_process import (
    TextureValidationError,
    load_diffuse_texture,
    load_optional_texture,
    load_team_colour_texture,
)
from src.render_settings import RenderSettings
from src.texture_renderer import TextureRenderer
from src.texture_set import TextureSet
from src.texture_loading_service import find_companion_texture
from src.texture_naming import (
    DEFAULT_TEXTURE_NAMING,
    TextureKind,
    TextureNamingProfile,
    is_texture_kind,
)

LOGGER = logging.getLogger(__name__)

CancellationCheck = Callable[[], bool]
ProgressCallback = Callable[["BatchProgress"], None]
BatchQueueEvent = (
    tuple[Literal["total"], int]
    | tuple[Literal["progress"], int, int]
)
LegacyBatchResult = tuple[list[str], list[str], bool]


class BatchItemStatus(Enum):
    PROCESSED = "processed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class BatchProcessingRequest:
    source_directory: Path
    destination_directory: Path
    source_formats: tuple[str, ...]
    destination_format: str
    settings: RenderSettings
    naming_profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING
    overwrite_existing: bool = False


@dataclass(frozen=True)
class BatchItemResult:
    source: Path
    destination: Path | None
    status: BatchItemStatus
    warnings: tuple[str, ...] = ()
    error_message: str | None = None


@dataclass(frozen=True)
class BatchProgress:
    completed: int
    total: int
    current_path: Path | None


@dataclass(frozen=True)
class BatchProcessingResult:
    processed_count: int
    skipped_count: int
    failed_count: int
    cancelled: bool
    items: tuple[BatchItemResult, ...]

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(
            f"{item.source.name}: {item.error_message}"
            for item in self.items
            if item.status is BatchItemStatus.FAILED
        )

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(
            f"{item.source.name}: {warning}"
            for item in self.items
            for warning in item.warnings
        )


def is_batch_diffuse(
    path: Path,
    source_formats: Sequence[str],
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> bool:
    """Return whether a non-recursive batch entry is a supported diffuse."""
    normalized_formats = {value.casefold().lstrip(".") for value in source_formats}
    return path.suffix[1:].casefold() in normalized_formats and is_texture_kind(
        path, TextureKind.DIFFUSE, profile
    )


def discover_batch_diffuses(
    source_directory: Path,
    source_formats: Sequence[str],
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> tuple[Path, ...]:
    """Discover deterministic, non-recursive diffuse inputs."""
    return tuple(
        sorted(
            (
                path
                for path in source_directory.iterdir()
                if path.is_file() and is_batch_diffuse(path, source_formats, profile)
            ),
            key=lambda path: (path.name.casefold(), path.name),
        )
    )


def load_batch_texture_set(
    diffuse_path: Path,
    profile: TextureNamingProfile = DEFAULT_TEXTURE_NAMING,
) -> tuple[TextureSet, tuple[str, ...]]:
    """Load one isolated texture set for batch rendering."""
    diffuse = load_diffuse_texture(diffuse_path)
    team_color_mask_path = find_companion_texture(
        diffuse_path, TextureKind.TEAM_COLOR, profile
    )
    if team_color_mask_path is None:
        raise TextureValidationError(
            f'No team-colour mask was found for "{diffuse_path.name}".'
        )
    team_color = load_team_colour_texture(team_color_mask_path, diffuse.size)

    warnings: list[str] = []
    optional_images: dict[TextureKind, Image.Image | None] = {}
    for texture_kind, label in (
        (TextureKind.DIRT, "Dirt"),
        (TextureKind.SPECULAR, "Specular"),
    ):
        optional_path = find_companion_texture(diffuse_path, texture_kind, profile)
        if optional_path is None:
            optional_images[texture_kind] = None
            continue
        try:
            optional_images[texture_kind] = load_optional_texture(
                optional_path,
                label,
                diffuse.size,
            )
        except TextureValidationError as exc:
            warnings.append(f"{label}: {exc}")
            optional_images[texture_kind] = None

    return (
        TextureSet(
            diffuse=diffuse,
            team_color=team_color,
            dirt=optional_images[TextureKind.DIRT],
            specular=optional_images[TextureKind.SPECULAR],
        ),
        tuple(warnings),
    )


def save_processed_image(image: Image.Image, filepath: Path) -> None:
    """Atomically save a processed image without exposing a partial output."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f".{filepath.stem}.",
        suffix=filepath.suffix,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        if filepath.suffix.casefold() in (".jpg", ".jpeg"):
            image.convert("RGB").save(temporary_path)
        else:
            image.save(temporary_path)
        os.replace(temporary_path, filepath)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            LOGGER.warning(
                "Could not remove temporary batch output %s",
                temporary_path,
                exc_info=True,
            )


def batch_convert_worker(
    source: Path,
    destination: Path,
    dest_format: str,
    src_format: Sequence[str],
    profile: TextureNamingProfile,
    cancel: Event,
    events: Queue[BatchQueueEvent],
) -> LegacyBatchResult:
    """Convert legacy team-colour batches without touching Tk widgets."""
    errors: list[str] = []
    try:
        files_dict = get_tem_filenames(source, src_format)
    except Exception as exc:
        return [str(exc)], [], cancel.is_set()

    events.put(("total", len(files_dict)))
    for current, (name, textures) in enumerate(files_dict.items(), start=1):
        if cancel.is_set():
            break
        try:
            result = convert_tem_texture(textures, source)
            output_path = team_color_output_path(
                name, destination, dest_format, profile
            )
            if output_path is None:
                raise ValueError(f"Cannot create a team-color filename from '{name}'.")
            save_processed_image(result, output_path)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
        events.put(("progress", current, len(files_dict)))
    return errors, [], cancel.is_set()


class BatchProcessingService:
    """Process isolated batch items and report worker-thread-safe progress."""

    def __init__(self, renderer: TextureRenderer | None = None) -> None:
        self.renderer: TextureRenderer = renderer or TextureRenderer()

    def discover_inputs(
        self,
        request: BatchProcessingRequest,
    ) -> tuple[Path, ...]:
        return discover_batch_diffuses(
            request.source_directory,
            request.source_formats,
            request.naming_profile,
        )

    def process(
        self,
        request: BatchProcessingRequest,
        cancellation_requested: CancellationCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> BatchProcessingResult:
        """Process a request; progress callbacks may run on a worker thread."""
        cancelled = cancellation_requested or (lambda: False)
        files = self.discover_inputs(request)
        items: list[BatchItemResult] = []
        total = len(files)
        if progress_callback is not None:
            progress_callback(BatchProgress(0, total, None))

        for diffuse_path in files:
            if cancelled():
                break
            destination = request.destination_directory / (
                f"{diffuse_path.stem}.{request.destination_format}"
            )
            if destination.exists() and not request.overwrite_existing:
                item = BatchItemResult(
                    diffuse_path, destination, BatchItemStatus.SKIPPED
                )
            else:
                item = self._process_item(request, diffuse_path, destination)
            items.append(item)
            if progress_callback is not None:
                progress_callback(BatchProgress(len(items), total, diffuse_path))

        return BatchProcessingResult(
            processed_count=sum(
                item.status is BatchItemStatus.PROCESSED for item in items
            ),
            skipped_count=sum(item.status is BatchItemStatus.SKIPPED for item in items),
            failed_count=sum(item.status is BatchItemStatus.FAILED for item in items),
            cancelled=cancelled(),
            items=tuple(items),
        )

    def process_to_queue(
        self,
        request: BatchProcessingRequest,
        cancel: Event,
        events: Queue[BatchQueueEvent],
    ) -> BatchProcessingResult:
        """Adapt structured progress to the GUI's thread-safe event queue."""

        def report(progress: BatchProgress) -> None:
            if progress.current_path is None:
                events.put(("total", progress.total))
            else:
                events.put(("progress", progress.completed, progress.total))

        return self.process(request, cancel.is_set, report)

    def _process_item(
        self,
        request: BatchProcessingRequest,
        diffuse_path: Path,
        destination: Path,
    ) -> BatchItemResult:
        try:
            textures, warnings = load_batch_texture_set(
                diffuse_path,
                request.naming_profile,
            )
            output = self.renderer.render(textures, request.settings)
            save_processed_image(output, destination)
            return BatchItemResult(
                diffuse_path,
                destination,
                BatchItemStatus.PROCESSED,
                warnings,
            )
        except (OSError, TextureValidationError, ValueError) as exc:
            LOGGER.exception("Batch processing failed for %s", diffuse_path)
            return BatchItemResult(
                diffuse_path,
                destination,
                BatchItemStatus.FAILED,
                error_message=str(exc),
            )
