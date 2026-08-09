"""Preview scheduling and background-render orchestration."""

from concurrent.futures import Executor, Future
from dataclasses import dataclass
import logging
from typing import Callable

from PIL import Image

from src.render_settings import RenderSettings
from src.texture_renderer import TextureRenderer
from src.texture_set import TextureSet

LOGGER = logging.getLogger(__name__)
PREVIEW_POLL_INTERVAL_MS = 20

ScheduledCallbackId = str
AfterCallback = Callable[[], None]
ScheduleAfter = Callable[[int, AfterCallback], ScheduledCallbackId]
CancelScheduled = Callable[[ScheduledCallbackId], None]
PreviewRequestFactory = Callable[[], "PreviewRequest"]
PreviewReadyCallback = Callable[["PreviewResult"], None]
PreviewErrorCallback = Callable[[BaseException], None]


@dataclass(frozen=True)
class PreviewResult:
    request_id: int
    workspace: Image.Image
    team_colour: Image.Image | None


@dataclass(frozen=True)
class PreviewRequest:
    textures: TextureSet
    settings: RenderSettings


@dataclass(frozen=True)
class PreviewRenderResult:
    """Pillow-only worker output that is safe to deliver to the Tk thread."""

    workspace: Image.Image
    team_colour: Image.Image | None


PreviewRender = Callable[
    [TextureRenderer, PreviewRequest],
    PreviewRenderResult,
]


def render_preview(
    renderer: TextureRenderer,
    request: PreviewRequest,
) -> PreviewRenderResult:
    """Render one immutable source/settings request in a worker thread."""
    return PreviewRenderResult(
        workspace=renderer.render(request.textures, request.settings),
        team_colour=renderer.render_team_colour(
            request.textures,
            request.settings,
        ),
    )


class PreviewController:
    """Coordinate previews using an externally owned executor.

    The injected executor remains owned by the composition root. ``shutdown``
    cancels this controller's pending futures but does not shut the executor
    down.
    """

    def __init__(
        self,
        *,
        renderer: TextureRenderer,
        snapshot_provider: PreviewRequestFactory,
        executor: Executor,
        schedule_after: ScheduleAfter,
        cancel_scheduled: CancelScheduled,
        on_preview_ready: PreviewReadyCallback,
        on_preview_error: PreviewErrorCallback,
        debounce_ms: int,
        render: PreviewRender = render_preview,
        poll_interval_ms: int = PREVIEW_POLL_INTERVAL_MS,
    ) -> None:
        self.renderer: TextureRenderer = renderer
        self.snapshot_provider: PreviewRequestFactory = snapshot_provider
        self.executor: Executor = executor
        self.schedule_after: ScheduleAfter = schedule_after
        self.cancel_scheduled: CancelScheduled = cancel_scheduled
        self.on_preview_ready: PreviewReadyCallback = on_preview_ready
        self.on_preview_error: PreviewErrorCallback = on_preview_error
        self.debounce_ms: int = debounce_ms
        self.render: PreviewRender = render
        self.poll_interval_ms: int = poll_interval_ms
        self.request_id: int = 0
        self.pending_request_callback: ScheduledCallbackId | None = None
        self.scheduled_callbacks: set[ScheduledCallbackId] = set()
        self.futures: set[Future[PreviewRenderResult]] = set()
        self.is_shutdown: bool = False

    def request_preview(self) -> int | None:
        return self._request(self.debounce_ms)

    def request_preview_immediately(self) -> int | None:
        return self._request(0)

    def _request(self, delay_ms: int) -> int | None:
        if self.is_shutdown:
            return None
        self.request_id += 1
        request_id = self.request_id
        self.cancel_pending_preview()
        self.pending_request_callback = self._schedule(
            delay_ms,
            lambda: self._start_request(request_id),
        )
        return request_id

    def cancel_pending_preview(self) -> None:
        callback_id = self.pending_request_callback
        if callback_id is None:
            return
        try:
            self.cancel_scheduled(callback_id)
        except Exception:
            # Tk raises when an already-fired callback is cancelled. Its ID is
            # stale either way, so cancellation remains complete.
            LOGGER.debug(
                "Scheduled preview callback had already fired: %s",
                callback_id,
                exc_info=True,
            )
        self.scheduled_callbacks.discard(callback_id)
        self.pending_request_callback = None

    def invalidate(self) -> None:
        """Make pending/running results stale without scheduling new work."""
        if self.is_shutdown:
            return
        self.request_id += 1
        self.cancel_pending_preview()
        self._cancel_not_running_futures()

    def _start_request(self, request_id: int) -> None:
        self.pending_request_callback = None
        if self.is_shutdown or request_id != self.request_id:
            return
        self._cancel_not_running_futures()
        request = self.snapshot_provider()
        future = self.executor.submit(self.render, self.renderer, request)
        self.futures.add(future)
        self._schedule(
            self.poll_interval_ms,
            lambda: self._poll_result(request_id, future),
        )

    def _poll_result(
        self,
        request_id: int,
        future: Future[PreviewRenderResult],
    ) -> None:
        if self.is_shutdown:
            return
        if not future.done():
            self._schedule(
                self.poll_interval_ms,
                lambda: self._poll_result(request_id, future),
            )
            return
        self.futures.discard(future)
        if future.cancelled() or request_id != self.request_id:
            return
        try:
            render_result = future.result()
        except Exception as exc:
            LOGGER.exception("Preview render failed")
            self.on_preview_error(exc)
            return
        self.on_preview_ready(
            PreviewResult(
                request_id,
                render_result.workspace,
                render_result.team_colour,
            )
        )

    def _schedule(
        self,
        delay_ms: int,
        callback: AfterCallback,
    ) -> ScheduledCallbackId:
        callback_id: ScheduledCallbackId | None = None

        def deliver() -> None:
            if callback_id is not None:
                self.scheduled_callbacks.discard(callback_id)
            callback()

        callback_id = self.schedule_after(delay_ms, deliver)
        self.scheduled_callbacks.add(callback_id)
        return callback_id

    def _cancel_not_running_futures(self) -> None:
        for future in tuple(self.futures):
            if not future.running():
                future.cancel()
                self.futures.discard(future)

    def shutdown(self) -> None:
        if self.is_shutdown:
            return
        self.is_shutdown = True
        self.request_id += 1
        for callback_id in tuple(self.scheduled_callbacks):
            try:
                self.cancel_scheduled(callback_id)
            except Exception:
                LOGGER.debug(
                    "Scheduled preview callback had already fired: %s",
                    callback_id,
                    exc_info=True,
                )
        self.scheduled_callbacks.clear()
        self.pending_request_callback = None
        for future in tuple(self.futures):
            future.cancel()
        self.futures.clear()
