import pytest
from unittest.mock import patch
from queue import Empty

import DisplayCAL.mscms as mscms_module
from DisplayCAL.mscms import WCSManagerProxy, WCSManagerShutdownError

#Tests including mocks and multiprocess do not work under Windows due to spawn != fork, so this is why some tests are ugly

def _mock_wcs_worker_process(request_queue, response_queue, log_queue):
    """Замена реальному _wcs_worker_process для тестов."""
    while True:
        try:
            request = request_queue.get(timeout=1.0)
        except Empty:
            continue

        if request is None:
            break

        request_id = request["id"]
        method_name = request["method"]
        args = request.get("args", ())
        kwargs = request.get("kwargs", {})

        response = {
            "type": "resp_success",
            "id": request_id,
            "result": {"method": method_name, "args": args, "kwargs": kwargs},
        }
        response_queue.put(response)


def _oserror_wcs_worker_process(request_queue, response_queue, log_queue):
    while True:
        try:
            request = request_queue.get(timeout=1.0)
        except Empty:
            continue
        if request is None:
            break

        request_id = request["id"]
        method_name = request["method"]

        if method_name == "SetCalibrationManagementState":
            error = OSError(5, "Access is denied")
            response = {
                "type": "resp_error",
                "id": request_id,
                "error": {
                    "type": "OSError",
                    "message": str(error),
                    "errno": error.errno,
                },
            }
        else:
            response = {
                "type": "resp_success",
                "id": request_id,
                "result": {"method": method_name},
            }

        response_queue.put(response)


@pytest.fixture
def wcs_manager():
    original_worker = mscms_module._wcs_worker_process
    mscms_module._wcs_worker_process = _mock_wcs_worker_process

    manager = None
    try:
        manager = mscms_module.WCSManager()
        yield manager
    finally:
        if manager:
            manager.shutdown()

        mscms_module._wcs_worker_process = original_worker


def test_manager_initialization(wcs_manager):
    assert wcs_manager._worker_process.is_alive()


def test_successful_method_call(wcs_manager):
    result = wcs_manager.get_calibration_management_state()
    assert result["method"] == "GetCalibrationManagementState"
    assert result["args"] == ()
    assert result["kwargs"] == {}


def test_method_call_with_args(wcs_manager):
    scope = "user"
    device_key = r"\\?\DISPLAY#..."
    result = wcs_manager.get_default_color_profile(scope, device_key)
    assert result["method"] == "GetDefaultColorProfile"
    assert scope in result["args"]
    assert device_key in result["args"]


def test_call_after_shutdown_raises_error():
    import DisplayCAL.mscms as mscms_module

    original_worker = mscms_module._wcs_worker_process
    mscms_module._wcs_worker_process = _mock_wcs_worker_process

    manager = None
    try:
        manager = mscms_module.WCSManager()

        manager.shutdown()

        with pytest.raises(
            WCSManagerShutdownError, match="WCSManager is set to shut down"
        ):
            manager.get_calibration_management_state()

    finally:
        mscms_module._wcs_worker_process = original_worker
        if manager and not manager._shutdown_event.is_set():
            manager.shutdown()


def test_exception_transparency_oserror():
    original_worker = mscms_module._wcs_worker_process
    mscms_module._wcs_worker_process = _oserror_wcs_worker_process

    manager = None
    try:
        manager = mscms_module.WCSManager()

        with pytest.raises(OSError) as exc_info:
            manager.set_calibration_management_state(True)

        assert exc_info.value.errno == 5
        assert "Access is denied" in str(exc_info.value)

    finally:
        if manager:
            manager.shutdown()
        mscms_module._wcs_worker_process = original_worker


@pytest.fixture
def clean_wcs_proxy():
    """Очищает синглтон перед и после теста."""
    WCSManagerProxy._instance = None
    yield
    WCSManagerProxy._instance = None


def test_wcs_proxy_lazy_init(clean_wcs_proxy):
    proxy = WCSManagerProxy()

    assert WCSManagerProxy._instance is None

    with patch("DisplayCAL.mscms.WCSManager") as MockManager:
        mock_instance = MockManager.return_value
        mock_instance.get_calibration_management_state.return_value = True

        assert WCSManagerProxy._instance is None
        result = proxy.get_calibration_management_state()
        assert WCSManagerProxy._instance is not None

        MockManager.assert_called_once()
        mock_instance.get_calibration_management_state.assert_called_once()
        assert result is True


def test_wcs_proxy_singleton(clean_wcs_proxy):
    proxy = WCSManagerProxy()
    proxy2 = WCSManagerProxy()

    with patch("DisplayCAL.mscms.WCSManager") as MockManager:
        mock_instance = MockManager.return_value
        mock_instance.get_calibration_management_state.return_value = True

        proxy.get_calibration_management_state()

        assert proxy._instance == proxy2._instance
