import threading
import unittest
from concurrent.futures import Future

import test_support  # noqa: F401 - installs the user-data path redirect
from src.preview_controller import PreviewController


class FakeScheduler:
    def __init__(self):
        self.callbacks = {}
        self.delays = {}
        self.cancelled = []
        self.next_id = 1

    def after(self, delay, callback):
        callback_id = self.next_id
        self.next_id += 1
        self.callbacks[callback_id] = callback
        self.delays[callback_id] = delay
        return callback_id

    def cancel(self, callback_id):
        self.cancelled.append(callback_id)
        self.callbacks.pop(callback_id, None)

    def run_next(self):
        callback_id = min(self.callbacks)
        callback = self.callbacks.pop(callback_id)
        callback()
        return callback_id


class ControlledExecutor:
    def __init__(self):
        self.submissions = []
        self.shutdown_calls = 0

    def submit(self, function, argument):
        future = Future()
        self.submissions.append((future, function, argument))
        return future

    def complete(self, index=0):
        future, function, argument = self.submissions[index]
        future.set_result(function(argument))

    def fail(self, error, index=0):
        self.submissions[index][0].set_exception(error)

    def shutdown(self, *args, **kwargs):
        self.shutdown_calls += 1


class FakeWorkbench:
    def __init__(self):
        self.snapshot_number = 0

    def render_snapshot(self):
        self.snapshot_number += 1
        return self.snapshot_number


class PreviewControllerTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = FakeScheduler()
        self.executor = ControlledExecutor()
        self.results = []
        self.errors = []
        self.controller = PreviewController(
            workbench=FakeWorkbench(),
            executor=self.executor,
            schedule_after=self.scheduler.after,
            cancel_scheduled=self.scheduler.cancel,
            on_preview_ready=self.results.append,
            on_preview_error=self.errors.append,
            debounce_ms=120,
            render=lambda snapshot: (
                f"workspace-{snapshot}",
                f"team-{snapshot}",
            ),
        )

    def start_request(self, immediate=True):
        if immediate:
            self.controller.request_preview_immediately()
        else:
            self.controller.request_preview()
        self.scheduler.run_next()

    def finish_request(self, submission=0):
        self.executor.complete(submission)
        self.scheduler.run_next()

    def test_one_request_submits_and_delivers_one_preview(self):
        self.start_request()
        self.finish_request()

        self.assertEqual(len(self.executor.submissions), 1)
        self.assertEqual(self.results[0].workspace, "workspace-1")
        self.assertEqual(self.results[0].team_colour, "team-1")

    def test_repeated_debounced_requests_replace_pending_callback(self):
        first = self.controller.request_preview()
        first_callback = min(self.scheduler.callbacks)
        second = self.controller.request_preview()

        self.assertGreater(second, first)
        self.assertIn(first_callback, self.scheduler.cancelled)
        self.assertEqual(len(self.scheduler.callbacks), 1)
        callback_id = min(self.scheduler.callbacks)
        self.assertEqual(self.scheduler.delays[callback_id], 120)
        self.scheduler.run_next()
        self.assertEqual(len(self.executor.submissions), 1)

    def test_immediate_request_replaces_pending_debounce(self):
        self.controller.request_preview()
        pending = min(self.scheduler.callbacks)
        self.controller.request_preview_immediately()

        self.assertIn(pending, self.scheduler.cancelled)
        callback_id = min(self.scheduler.callbacks)
        self.assertEqual(self.scheduler.delays[callback_id], 0)

    def test_pending_preview_can_be_cancelled(self):
        self.controller.request_preview()
        self.controller.cancel_pending_preview()

        self.assertFalse(self.scheduler.callbacks)
        self.assertIsNone(self.controller.pending_request_callback)

    def test_stale_running_result_is_rejected_and_latest_is_delivered(self):
        self.start_request()
        old_future = self.executor.submissions[0][0]
        old_future.set_running_or_notify_cancel()
        self.start_request()
        self.executor.complete(0)
        self.scheduler.run_next()
        self.assertEqual(self.results, [])

        self.executor.complete(1)
        while self.scheduler.callbacks and not self.results:
            self.scheduler.run_next()
        self.assertEqual([result.workspace for result in self.results], ["workspace-2"])

    def test_worker_error_is_reported_and_a_later_request_recovers(self):
        self.start_request()
        error = RuntimeError("render failed")
        self.executor.fail(error)
        self.scheduler.run_next()
        self.assertEqual(self.errors, [error])

        self.start_request()
        self.finish_request(1)
        self.assertEqual(self.results[0].workspace, "workspace-2")

    def test_worker_completion_does_not_invoke_ui_callback(self):
        callback_threads = []
        self.controller.on_preview_ready = (
            lambda result: callback_threads.append(threading.get_ident())
        )
        self.start_request()
        worker = threading.Thread(target=self.executor.complete)
        worker.start()
        worker.join()

        self.assertEqual(callback_threads, [])
        main_thread = threading.get_ident()
        self.scheduler.run_next()
        self.assertEqual(callback_threads, [main_thread])

    def test_invalidate_rejects_a_result_without_scheduling_new_work(self):
        self.start_request()
        future = self.executor.submissions[0][0]
        future.set_running_or_notify_cancel()
        self.controller.invalidate()
        self.executor.complete()
        self.scheduler.run_next()

        self.assertEqual(self.results, [])
        self.assertEqual(len(self.executor.submissions), 1)

    def test_shutdown_cancels_pending_callbacks_and_future_delivery(self):
        self.start_request()
        future = self.executor.submissions[0][0]
        future.set_running_or_notify_cancel()
        self.controller.shutdown()
        self.executor.complete()

        self.assertFalse(self.scheduler.callbacks)
        self.assertEqual(self.results, [])
        self.assertIsNone(self.controller.request_preview())

    def test_shutdown_does_not_take_ownership_of_executor(self):
        self.controller.shutdown()
        self.assertEqual(self.executor.shutdown_calls, 0)

    def test_shutdown_is_idempotent(self):
        self.controller.request_preview()
        self.controller.shutdown()
        self.controller.shutdown()
        self.assertFalse(self.scheduler.callbacks)


if __name__ == "__main__":
    unittest.main()
