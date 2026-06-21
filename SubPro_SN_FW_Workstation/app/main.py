"""
Sub-Pro SN/FW Workstation — application entry point.

Responsibilities
────────────────
• Open / create the SQLite database.
• Initialise the DeviceService.
• Build the ScreenManager with all screens.
• Route to first-run password setup or the main workflow screen.
• Expose navigate_to() so screens and the NavBar can trigger transitions
  (with optional password-gate for protected screens).
"""
import logging
from pathlib import Path

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import NoTransition, ScreenManager

from app.db.database import Database
from app.services.device_service import DeviceService
from app.screens.first_run_screen import FirstRunScreen
from app.screens.history_screen import HistoryScreen
from app.screens.settings_screen import SettingsScreen
from app.screens.unlock_screen import UnlockScreen
from app.screens.workflow_screen import WorkflowScreen

_PROJECT_ROOT = Path(__file__).parent.parent
_DB_PATH      = _PROJECT_ROOT / 'Data' / 'subpro_workstation.db'


class SubProApp(App):
    title = 'Sub-Pro SN/FW Workstation'

    def build(self):
        Window.clearcolor = (0.12, 0.12, 0.12, 1)
        Window.size       = (1280, 760)

        # Core services
        self.db             = Database(_DB_PATH)
        self.device_service = DeviceService(
            self.db.get_config('device_name', 'SubPro'))
        ok, discovered_name, _ = self.device_service.discover(timeout=2)
        if ok and discovered_name:
            self.db.set_config('device_name', discovered_name)

        # Screen manager
        self.sm = ScreenManager(transition=NoTransition())

        self.sm.add_widget(FirstRunScreen(self.db,             name='first_run'))
        self.sm.add_widget(WorkflowScreen(self.db, self.device_service, name='workflow'))
        self.sm.add_widget(SettingsScreen(self.db, self.device_service, name='settings'))
        self.sm.add_widget(UnlockScreen(  self.db, self.device_service, name='unlock'))
        self.sm.add_widget(HistoryScreen( self.db,             name='history'))

        self.sm.current = 'first_run' if not self.db.has_password() else 'workflow'
        return self.sm

    # ── Navigation API ────────────────────────────────────────────────────────

    def navigate_to(self, screen_name: str, require_password: bool = False):
        """
        Switch to *screen_name*.

        If *require_password* is True a PasswordPopup is shown first; the
        transition only happens on a correct password entry.
        """
        if require_password:
            from app.components.password_popup import PasswordPopup
            PasswordPopup(
                db=self.db,
                on_success=lambda: setattr(self.sm, 'current', screen_name),
            ).open()
        else:
            self.sm.current = screen_name
