import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import test_support  # noqa: F401 - installs the user-data path redirect
from src.frame_main import ArmyPainter


class FakeFrame:
    def pack(self, **options):
        self.pack_options = options


class FakePatternPanel(FakeFrame):
    pass


class ArmyPainterCompositionTests(unittest.TestCase):
    def test_constructor_runs_explicit_stages_in_order(self):
        order = []
        stage_names = (
            "_initialize_application_state",
            "_configure_main_window",
            "_initialize_services_and_controllers",
            "_create_application_widgets",
            "_initialize_view_state",
        )
        patches = [
            patch.object(
                ArmyPainter,
                name,
                side_effect=lambda *args, stage=name: order.append(stage),
            )
            for name in stage_names
        ]

        with patch("src.frame_main.tk.Tk.__init__"):
            for stage_patch in patches:
                stage_patch.start()
            try:
                ArmyPainter(application_log_path="application.log")
            finally:
                for stage_patch in reversed(patches):
                    stage_patch.stop()

        self.assertEqual(order, list(stage_names))

    @patch("src.frame_main.BatchProcessingService")
    @patch("src.frame_main.PreviewController")
    @patch("src.frame_main.TextureLoadingService")
    @patch("src.frame_main.FileSelectionService")
    @patch("src.frame_main.SettingsHandler")
    @patch("src.frame_main.ImageWorkbench")
    @patch("src.frame_main.ThreadPoolExecutor")
    @patch.object(ArmyPainter, "_create_pattern_controller")
    def test_services_and_controllers_receive_explicit_dependencies(
        self,
        create_pattern_controller,
        executor_type,
        workbench_type,
        settings_type,
        file_selection_type,
        texture_loading_type,
        preview_controller_type,
        batch_service_type,
    ):
        preview_executor = Mock(name="preview_executor")
        batch_executor = Mock(name="batch_executor")
        executor_type.side_effect = (preview_executor, batch_executor)
        painter = SimpleNamespace(
            dialogs=Mock(name="dialogs"),
            texture_naming_profile=Mock(name="profile"),
            after=Mock(name="after"),
            after_cancel=Mock(name="after_cancel"),
            apply_preview_result=Mock(name="apply_preview_result"),
            show_preview_error=Mock(name="show_preview_error"),
        )

        ArmyPainter._initialize_services_and_controllers(painter)

        executor_type.assert_has_calls([call(max_workers=1), call(max_workers=1)])
        self.assertEqual(executor_type.call_count, 2)
        file_selection_type.assert_called_once_with(
            settings_type.return_value, painter.dialogs
        )
        create_pattern_controller.assert_called_once_with(painter)
        texture_loading_type.assert_called_once_with(
            workbench_type.return_value, painter.texture_naming_profile
        )
        preview_controller_type.assert_called_once_with(
            workbench=workbench_type.return_value,
            executor=preview_executor,
            schedule_after=painter.after,
            cancel_scheduled=painter.after_cancel,
            on_preview_ready=painter.apply_preview_result,
            on_preview_error=painter.show_preview_error,
            debounce_ms=120,
        )
        batch_service_type.assert_called_once_with()
        self.assertIs(painter.batch_executor, batch_executor)

    @patch("src.frame_main.FramePatternList", return_value=FakePatternPanel())
    @patch("src.frame_main.tk.Frame", side_effect=(FakeFrame(), FakeFrame()))
    def test_widgets_receive_callbacks_and_activate_after_assignment(
        self, frame_type, pattern_panel_type
    ):
        channel_list = SimpleNamespace(lb=SimpleNamespace(bind=Mock()))
        callback_names = (
            "save_pattern",
            "update_selected_pattern",
            "rename_selected_pattern",
            "delete_pattern",
            "on_pattern_select",
            "update_pattern_action_states",
        )
        painter = SimpleNamespace(
            define_frame_workspace_tool=Mock(),
            define_frame_workspace=Mock(),
            define_menu=Mock(),
            activate_pattern_panel_callbacks=Mock(),
            frame_channel_select=channel_list,
            select_channel=Mock(),
            **{name: Mock(name=name) for name in callback_names},
        )

        ArmyPainter._create_application_widgets(painter)

        options = pattern_panel_type.call_args.kwargs
        self.assertIs(options["on_save_new"], painter.save_pattern)
        self.assertIs(options["on_update"], painter.update_selected_pattern)
        self.assertIs(options["on_rename"], painter.rename_selected_pattern)
        self.assertIs(options["on_delete"], painter.delete_pattern)
        self.assertIs(options["on_selection_changed"], painter.on_pattern_select)
        self.assertIs(options["on_state_changed"], painter.update_pattern_action_states)
        self.assertIs(painter.frame_army_pattern, pattern_panel_type.return_value)
        painter.define_menu.assert_called_once_with()
        painter.activate_pattern_panel_callbacks.assert_called_once_with()

    def test_initial_view_state_runs_only_after_preview_controller_exists(self):
        painter = SimpleNamespace(
            preview_controller=object(),
            after_idle=Mock(),
            show_user_pattern_load_warning=Mock(),
        )

        def reset_workspace():
            self.assertIsNotNone(painter.preview_controller)

        painter.reset_workspace = Mock(side_effect=reset_workspace)
        ArmyPainter._initialize_view_state(painter)

        painter.reset_workspace.assert_called_once_with()
        painter.after_idle.assert_called_once_with(
            painter.show_user_pattern_load_warning
        )

    def test_shutdown_order_and_executor_ownership_are_unambiguous(self):
        order = []
        painter = SimpleNamespace(
            preview_controller=Mock(
                shutdown=Mock(side_effect=lambda: order.append("controller"))
            ),
            preview_executor=Mock(
                shutdown=Mock(side_effect=lambda **kwargs: order.append("preview"))
            ),
            batch_executor=Mock(
                shutdown=Mock(side_effect=lambda **kwargs: order.append("batch"))
            ),
        )

        ArmyPainter._shutdown_owned_background_workers(painter)

        self.assertEqual(order, ["controller", "preview", "batch"])
        painter.preview_executor.shutdown.assert_called_once_with(
            wait=False, cancel_futures=True
        )
        painter.batch_executor.shutdown.assert_called_once_with(
            wait=False, cancel_futures=True
        )

    def test_controllers_and_services_do_not_import_army_painter(self):
        import src.batch_processing_service as batch_service
        import src.pattern_controller as pattern_controller
        import src.preview_controller as preview_controller
        import src.texture_loading_service as texture_service

        for module in (
            batch_service,
            pattern_controller,
            preview_controller,
            texture_service,
        ):
            with self.subTest(module=module.__name__):
                self.assertNotIn("ArmyPainter", inspect.getsource(module))


if __name__ == "__main__":
    unittest.main()
