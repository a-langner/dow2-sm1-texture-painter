"""Preview scheduling and background-render orchestration."""

from dataclasses import dataclass
import logging

LOGGER = logging.getLogger(__name__)
PREVIEW_POLL_INTERVAL_MS = 20


@dataclass(frozen=True)
class PreviewResult:
    request_id: int
    workspace: object
    team_colour: object


def render_preview(snapshot):
    """Render one immutable workbench snapshot in a worker thread."""
    return snapshot.refresh_workspace(), snapshot.refresh_team_colour_img()


class PreviewController:
    """Coordinate previews using an externally owned executor.

    The injected executor remains owned by the composition root. ``shutdown``
    cancels this controller's pending futures but does not shut the executor
    down.
    """

    def __init__(
        self,
        *,
        workbench,
        executor,
        schedule_after,
        cancel_scheduled,
        on_preview_ready,
        on_preview_error,
        debounce_ms,
        render=render_preview,
        poll_interval_ms=PREVIEW_POLL_INTERVAL_MS,
    ):
        self.workbench = workbench
        self.executor = executor
        self.schedule_after = schedule_after
        self.cancel_scheduled = cancel_scheduled
        self.on_preview_ready = on_preview_ready
        self.on_preview_error = on_preview_error
        self.debounce_ms = debounce_ms
        self.render = render
        self.poll_interval_ms = poll_interval_ms
        self.request_id = 0
        self.pending_request_callback = None
        self.scheduled_callbacks = set()
        self.futures = set()
        self.is_shutdown = False

    def request_preview(self):
        return self._request(self.debounce_ms)

    def request_preview_immediately(self):
        return self._request(0)

    def _request(self, delay_ms):
        if self.is_shutdown:
            return None
        self.request_id += 1
        request_id = self.request_id
        self.cancel_pending_preview()
        self.pending_request_callback = self._schedule(
            delay_ms, self._start_request, request_id
        )
        return request_id

    def cancel_pending_preview(self):
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

    def invalidate(self):
        """Make pending/running results stale without scheduling another render."""
        if self.is_shutdown:
            return
        self.request_id += 1
        self.cancel_pending_preview()
        self._cancel_not_running_futures()

    def _start_request(self, request_id):
        self.pending_request_callback = None
        if self.is_shutdown or request_id != self.request_id:
            return
        self._cancel_not_running_futures()
        snapshot = self.workbench.render_snapshot()
        future = self.executor.submit(self.render, snapshot)
        self.futures.add(future)
        self._schedule(
            self.poll_interval_ms,
            self._poll_result,
            request_id,
            future,
        )

    def _poll_result(self, request_id, future):
        if self.is_shutdown:
            return
        if not future.done():
            self._schedule(
                self.poll_interval_ms,
                self._poll_result,
                request_id,
                future,
            )
            return
        self.futures.discard(future)
        if future.cancelled() or request_id != self.request_id:
            return
        try:
            workspace, team_colour = future.result()
        except Exception as exc:
            LOGGER.exception("Preview render failed")
            self.on_preview_error(exc)
            return
        self.on_preview_ready(
            PreviewResult(request_id, workspace, team_colour)
        )

    def _schedule(self, delay_ms, callback, *args):
        callback_id_holder = {}

        def deliver():
            callback_id = callback_id_holder.get("id")
            if callback_id is not None:
                self.scheduled_callbacks.discard(callback_id)
            callback(*args)

        callback_id = self.schedule_after(delay_ms, deliver)
        callback_id_holder["id"] = callback_id
        self.scheduled_callbacks.add(callback_id)
        return callback_id

    def _cancel_not_running_futures(self):
        for future in tuple(self.futures):
            if not future.running():
                future.cancel()
                self.futures.discard(future)

    def shutdown(self):
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
