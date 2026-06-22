"""Tests for the product-serial scan discovery flow."""

from pathlib import Path


class _Label:
    def __init__(self):
        self.text = ''


class _Db:
    def __init__(self):
        self.config_calls = []

    def is_golden_sample(self, sn):
        return False

    def create_unit(self, sn, variant):
        return 42

    def set_config(self, key, value):
        self.config_calls.append((key, value))


class _DeviceService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def discover(self, timeout=2):
        self.calls.append(timeout)
        return self.result

    def discover_with_retries(self, attempts=3, timeout=2, retry_delay_s=0.5):
        self.calls.append((attempts, timeout, retry_delay_s))
        return self.result


def test_product_scan_triggers_discovery_before_processing():
    from app.screens.workflow_screen import WorkflowScreen

    screen = WorkflowScreen.__new__(WorkflowScreen)
    screen.db = _Db()
    screen.device_service = _DeviceService((True, 'SubPro-EF0000', None))
    screen._session = {'parts_scanned': {}}
    screen._variant_lbl = _Label()
    screen._status_lbl = _Label()
    screen._go_processing = lambda: setattr(screen, '_processing_called', True)
    screen._go_fail = lambda reason: setattr(screen, '_fail_reason', reason)
    screen._rebuild_parts_list = lambda variant=None: None
    screen._set_status = lambda msg: setattr(screen, '_status_msg', msg)

    screen._handle_product_scan('CI6400001')

    assert screen.device_service.calls == [(2, 10, 0.5)]
    assert ('device_name', 'SubPro-EF0000') in screen.db.config_calls
    assert getattr(screen, '_processing_called', False) is True
    assert not hasattr(screen, '_fail_reason')
    assert screen._status_msg == 'Discovering device...'


def test_product_scan_fails_when_discovery_returns_nothing():
    from app.screens.workflow_screen import WorkflowScreen

    screen = WorkflowScreen.__new__(WorkflowScreen)
    screen.db = _Db()
    screen.device_service = _DeviceService((False, None, 'No device discovered.'))
    screen._session = {'parts_scanned': {}}
    screen._variant_lbl = _Label()
    screen._status_lbl = _Label()
    screen._go_processing = lambda: setattr(screen, '_processing_called', True)
    screen._go_fail = lambda reason: setattr(screen, '_fail_reason', reason)
    screen._rebuild_parts_list = lambda variant=None: None
    screen._set_status = lambda msg: setattr(screen, '_status_msg', msg)

    screen._handle_product_scan('CI6400001')

    assert screen.device_service.calls == [(2, 10, 0.5)]
    assert getattr(screen, '_processing_called', False) is False
    assert screen._fail_reason == 'Could not discover device.\nNo device discovered.'


def test_part_scan_completion_shows_done_then_auto_advances_to_next_unit_scan():
    import app.screens.workflow_screen as workflow_screen

    WorkflowScreen = workflow_screen.WorkflowScreen

    class _Db:
        def __init__(self):
            self.completed = []

        def get_parts_config(self):
            return [
                {
                    'name': 'DSP Board',
                    'required': True,
                    'prefix_a8s': 'BH',
                    'prefix_a10s': 'BI',
                }
            ]

        def get_latest_unit_for_part_sn(self, sn):
            return None

        def add_part_scan(self, unit_id, part_name, sn, previous_unit_id=None):
            return None

        def complete_unit(self, unit_id, status):
            self.completed.append((unit_id, status))

    screen = WorkflowScreen.__new__(WorkflowScreen)
    screen.db = _Db()
    screen._session = {
        'unit_id': 42,
        'variant': 'A8S',
        'product_sn': 'CI6400001',
        'parts_scanned': {},
    }
    screen._status_lbl = _Label()
    screen._instr_lbl = _Label()
    screen._step_lbl = _Label()
    screen._result_lbl = _Label()
    screen._variant_lbl = _Label()
    screen._action_btn = type('B', (), {
        'text': '',
        'opacity': 1,
        'disabled': False,
        'background_color': None,
    })()
    screen._rebuild_parts_list = lambda variant=None: None
    screen._show_scan_input = lambda: None
    screen._hide_scan_input = lambda: None
    screen._hide_cancel = lambda: None
    screen._set_nav_session = lambda active: setattr(screen, '_nav_active', active)
    screen._advance_to_next_unit_scan = lambda sn='': setattr(screen, '_advanced_from_sn', sn)

    scheduled = {}
    original_schedule_once = workflow_screen.Clock.schedule_once
    workflow_screen.Clock.schedule_once = (
        lambda callback, delay: scheduled.update({'callback': callback, 'delay': delay})
    )

    try:
        screen._handle_part_scan('BH0100001')
    finally:
        workflow_screen.Clock.schedule_once = original_schedule_once

    assert screen._state == workflow_screen._DONE
    assert screen._result_lbl.text == 'PASS'
    assert 'Next scan starts in' in screen._status_lbl.text
    assert screen.db.completed == [(42, 'PASS')]
    assert scheduled['delay'] == workflow_screen._NEXT_UNIT_ADVANCE_DELAY_S
    assert not hasattr(screen, '_advanced_from_sn')

    scheduled['callback'](None)
    assert screen._advanced_from_sn == 'CI6400001'


def test_run_backend_fails_on_firmware_mismatch_without_bin_path():
    from app.screens.workflow_screen import WorkflowScreen

    class _Db:
        def get_config(self, key, default=''):
            return 'fw-pp-rc7' if key == 'target_fw_version' else default

    class _DeviceService:
        def get_firmware_version(self):
            return True, 'fw-pp-rc6', None

    screen = WorkflowScreen.__new__(WorkflowScreen)
    screen.db = _Db()
    screen.device_service = _DeviceService()
    screen._session = {'product_sn': 'CI6400001', 'unit_id': 42}
    screen._set_status = lambda msg: setattr(screen, '_status_msg', msg)
    screen._go_fail = lambda reason: setattr(screen, '_fail_reason', reason)

    screen._run_backend()

    assert getattr(screen, '_fail_reason', None) == (
        'Firmware mismatch: found fw-pp-rc6, expected fw-pp-rc7.\n'
        'This unit must be removed from the production flow and flashed separately.'
    )


def test_resolve_firmware_bin_path_uses_repo_root_for_relative_paths():
    from app.screens.workflow_screen import _REPO_ROOT, resolve_firmware_bin_path

    path = resolve_firmware_bin_path('SubsProFirmware/fw-pp-rc7.bin')

    assert path == _REPO_ROOT / 'SubsProFirmware/fw-pp-rc7.bin'
    assert 'SubPro_SN_FW_Workstation' not in str(path.parent)


def test_wait_for_firmware_ready_retries_until_target_matches():
    from app.screens.workflow_screen import wait_for_firmware_ready

    responses = iter([
        (False, None, 'device rebooting'),
        (True, 'fw-pp-rc6', None),
        (True, 'fw-pp-rc7', None),
    ])

    now = {'t': 0.0}

    def now_fn():
        return now['t']

    def sleep_fn(seconds):
        now['t'] += seconds

    ok, fw_after, err = wait_for_firmware_ready(
        read_version=lambda: next(responses),
        target_fw='fw-pp-rc7',
        max_wait_s=30.0,
        retry_interval_s=2.0,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
    )

    assert ok is True
    assert fw_after == 'fw-pp-rc7'
    assert err is None


def test_wait_for_firmware_ready_times_out_with_last_error():
    from app.screens.workflow_screen import wait_for_firmware_ready

    now = {'t': 0.0}

    def now_fn():
        return now['t']

    def sleep_fn(seconds):
        now['t'] += seconds

    ok, fw_after, err = wait_for_firmware_ready(
        read_version=lambda: (False, None, 'still rebooting'),
        target_fw='fw-pp-rc7',
        max_wait_s=3.0,
        retry_interval_s=1.0,
        now_fn=now_fn,
        sleep_fn=sleep_fn,
    )

    assert ok is False
    assert fw_after is None
    assert err == 'still rebooting'


def test_is_transient_flash_disconnect_detects_keepalive_error():
    from app.screens.workflow_screen import is_transient_flash_disconnect

    err = 'Command failed (exit code 110): FirmwareUpdateError: KeepAliveFailed'
    assert is_transient_flash_disconnect(err) is True


def test_is_transient_flash_disconnect_ignores_non_transient_errors():
    from app.screens.workflow_screen import is_transient_flash_disconnect

    err = 'Command failed (exit code 2): Firmware image not found'
    assert is_transient_flash_disconnect(err) is False


def test_is_device_not_found_error_detects_cli_message():
    from app.screens.workflow_screen import is_device_not_found_error

    err = 'Command failed (exit code 100): IoError: Device not found: SubPro-EF0000'
    assert is_device_not_found_error(err) is True


def test_get_firmware_version_with_rediscovery_recovers_after_stale_target():
    from app.screens.workflow_screen import get_firmware_version_with_rediscovery

    class _Svc:
        def __init__(self):
            self.read_calls = 0
            self.discover_calls = 0

        def get_firmware_version(self):
            self.read_calls += 1
            if self.read_calls == 1:
                return False, None, 'Command failed (exit code 100): IoError: Device not found: SubPro-EF0000'
            return True, 'fw-pp-rc7', None

        def discover(self, timeout=2):
            self.discover_calls += 1
            return True, 'SubPro-EF0011', None

    svc = _Svc()
    persisted = []
    ok, version, err = get_firmware_version_with_rediscovery(
        device_service=svc,
        on_rediscovered=lambda name: persisted.append(name),
        max_rediscover_attempts=2,
    )

    assert ok is True
    assert version == 'fw-pp-rc7'
    assert err is None
    assert svc.discover_calls == 1
    assert persisted == ['SubPro-EF0011']


def test_get_firmware_version_with_rediscovery_fails_if_discovery_fails():
    from app.screens.workflow_screen import get_firmware_version_with_rediscovery

    class _Svc:
        def get_firmware_version(self):
            return False, None, 'Command failed (exit code 100): IoError: Device not found: SubPro-EF0000'

        def discover(self, timeout=2):
            return False, None, 'No device discovered.'

    ok, version, err = get_firmware_version_with_rediscovery(
        device_service=_Svc(),
        max_rediscover_attempts=1,
    )

    assert ok is False
    assert version is None
    assert 'rediscovery failed' in err
