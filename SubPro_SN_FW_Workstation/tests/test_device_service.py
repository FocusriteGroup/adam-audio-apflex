"""Tests for app/services/device_service.py."""


class _FakeOcaDevice:
    def __init__(self, payload):
        self._payload = payload

    def discover(self, timeout=2):
        return self._payload


def test_discover_returns_device_name_and_updates_service():
    from app.services.device_service import DeviceService

    service = DeviceService('SubPro')
    service._discover_via_workstation_cli = lambda timeout: None
    service._device = _FakeOcaDevice({
        'devices': [{'name': 'SubPro-EF0000', 'ip': '169.254.43.61', 'port': '50001'}],
        'raw': 'Discovered device: SubPro-EF0000 (tcp::169.254.43.61:50001)',
    })

    ok, value, err = service.discover()

    assert ok is True
    assert err is None
    assert value == 'SubPro-EF0000'
    assert service.device_name == 'SubPro-EF0000'


def test_discover_prefers_adam_workstation_cli_result():
    from app.services.device_service import DeviceService

    service = DeviceService('SubPro')
    service._discover_via_workstation_cli = lambda timeout: 'SubPro-CLI0001'

    ok, value, err = service.discover(timeout=10)

    assert ok is True
    assert err is None
    assert value == 'SubPro-CLI0001'
    assert service.device_name == 'SubPro-CLI0001'


def test_discover_fails_when_no_devices_are_returned():
    from app.services.device_service import DeviceService

    service = DeviceService('SubPro')
    service._discover_via_workstation_cli = lambda timeout: None
    service._device = _FakeOcaDevice({'devices': [], 'raw': ''})

    ok, value, err = service.discover()

    assert ok is False
    assert value is None
    assert err == 'No device discovered.'


def test_discover_with_retries_succeeds_after_initial_miss(monkeypatch):
    from app.services.device_service import DeviceService

    service = DeviceService('SubPro')
    results = [
        (False, None, 'No device discovered.'),
        (True, 'SubPro-EF0000', None),
    ]

    def fake_discover(timeout=2):
        return results.pop(0)

    monkeypatch.setattr(service, 'discover', fake_discover)

    ok, value, err = service.discover_with_retries(
        attempts=3, timeout=2, retry_delay_s=0.0)

    assert ok is True
    assert value == 'SubPro-EF0000'
    assert err is None


def test_discover_with_retries_returns_last_error(monkeypatch):
    from app.services.device_service import DeviceService

    service = DeviceService('SubPro')

    def fake_discover(timeout=2):
        return False, None, 'No device discovered.'

    monkeypatch.setattr(service, 'discover', fake_discover)

    ok, value, err = service.discover_with_retries(
        attempts=3, timeout=2, retry_delay_s=0.0)

    assert ok is False
    assert value is None
    assert err == 'No device discovered.'
