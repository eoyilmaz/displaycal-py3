"""Tests for the VideoLUT verify/re-load logic that mitigates issue #694.

The shared detection/recovery helpers live on ``worker.Worker`` and are used
both by the in-session calibration flow (worker.install_profile) and by the
profile loader's macOS watch.
"""

from unittest import mock

from DisplayCAL import config
from DisplayCAL.profile_loader import ProfileLoader
from DisplayCAL.worker import Worker, reload_black_videoluts


class FakeMultiDisplayWorker:
    """A stand-in for Worker exposing just the ``displays`` list."""

    def __init__(self, ndisplays):
        self.displays = [f"Display {i + 1}" for i in range(ndisplays)]


def _profile_loader_stub():
    """A ProfileLoader instance without the heavy wx/thread __init__ side effects."""
    pl = ProfileLoader.__new__(ProfileLoader)
    pl._shutdown = False
    return pl


class FakeExec:
    """Records dispwin args and feeds canned 'Verify:' output to a Worker."""

    def __init__(self, errors=None, output=None):
        self._errors = errors or []
        self._output = output or []
        self.calls = []

    def __call__(self, worker, cmd, args, **kwargs):
        self.calls.append((cmd, args, kwargs))
        worker.errors = list(self._errors)
        worker.output = list(self._output)
        return True


def _worker_with_output(errors=None, output=None):
    """A Worker whose exec_cmd is replaced by a FakeExec."""
    worker = Worker.__new__(Worker)
    worker.errors = []
    worker.output = []
    fake = FakeExec(errors=errors, output=output)
    worker.exec_cmd = lambda cmd, args, **kw: fake(worker, cmd, args, **kw)
    worker._fake = fake
    return worker


def test_discrepancy_parsed_from_not_loaded():
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' is NOT loaded (discrepancy 8.6%)"]
    )
    assert worker.get_calibration_load_discrepancy("dispwin", 0, "/tmp/p.icc") == 8.6


def test_discrepancy_parsed_from_is_loaded():
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' IS loaded (discrepancy 0.3%)"]
    )
    assert worker.get_calibration_load_discrepancy("dispwin", 0, "/tmp/p.icc") == 0.3


def test_discrepancy_none_without_videolut_access():
    worker = _worker_with_output(errors=["We don't have access to the VideoLUT"])
    assert worker.get_calibration_load_discrepancy("dispwin", 0, "/tmp/p.icc") is None


def test_discrepancy_none_when_unparseable():
    worker = _worker_with_output(output=["some unrelated message"])
    assert worker.get_calibration_load_discrepancy("dispwin", 0, "/tmp/p.icc") is None


def test_verify_uses_verify_only_args():
    """Verification must use -V (read-only) and not load (-L would change the LUT)."""
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' IS loaded (discrepancy 0.1%)"]
    )
    worker.get_calibration_load_discrepancy("dispwin", 1, "/tmp/p.icc")
    _cmd, args, _kw = worker._fake.calls[0]
    assert "-V" in args and "-d2" in args and "/tmp/p.icc" in args
    assert "-L" not in args


def test_clobbered_true_for_black_screen():
    config.initcfg()
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' is NOT loaded (discrepancy 98.4%)"]
    )
    assert worker.calibration_is_clobbered("dispwin", 0, "/tmp/p.icc") is True


def test_clobbered_false_for_quantization_noise():
    """A small discrepancy (quantization) must NOT be treated as clobbered.

    dispwin would report this as 'is NOT loaded' (its tolerance is ~0.4%), but
    re-loading on such noise would needlessly re-trigger the macOS bug.
    """
    config.initcfg()
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' is NOT loaded (discrepancy 3.0%)"]
    )
    assert worker.calibration_is_clobbered("dispwin", 0, "/tmp/p.icc") is False


def test_clobbered_false_when_undetermined():
    config.initcfg()
    worker = _worker_with_output(errors=["We don't have access to the VideoLUT"])
    assert worker.calibration_is_clobbered("dispwin", 0, "/tmp/p.icc") is False


def test_clobbered_threshold_is_configurable():
    config.initcfg()
    config.setcfg("profile_loader.clobbered_discrepancy_threshold", 5)
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' is NOT loaded (discrepancy 8.6%)"]
    )
    try:
        assert worker.calibration_is_clobbered("dispwin", 0, "/tmp/p.icc") is True
    finally:
        config.setcfg("profile_loader.clobbered_discrepancy_threshold", 25)


def test_reload_black_videoluts_noop_off_macos():
    """The recovery is macOS-only; elsewhere it does nothing."""
    with mock.patch("DisplayCAL.worker.sys.platform", "win32"):
        assert reload_black_videoluts("dispwin") == []


def test_reload_black_videoluts_reloads_only_black_displays():
    """Only displays whose VideoLUT max is below threshold get re-loaded."""
    runs = []
    # display 0 is fine (1.0), display 1 is black (0.0); after one reload all fine.
    maxima_seq = iter([[1.0, 0.0], [1.0, 1.0]])
    with mock.patch("DisplayCAL.worker.sys.platform", "darwin"):
        reloaded = reload_black_videoluts(
            "dispwin",
            retries=4,
            _maxima_fn=lambda: next(maxima_seq),
            _reload=runs.append,
            _sleep=lambda s: None,
        )
    assert reloaded == [1]
    assert runs == [[1]]


def test_reload_black_videoluts_retries_until_sticks():
    """If a re-load gets clobbered again, it retries until it sticks."""
    runs = []
    # black, black again after first reload, then clean.
    maxima_seq = iter([[0.0], [0.0], [1.0]])
    with mock.patch("DisplayCAL.worker.sys.platform", "darwin"):
        reloaded = reload_black_videoluts(
            "dispwin",
            retries=5,
            _maxima_fn=lambda: next(maxima_seq),
            _reload=runs.append,
            _sleep=lambda s: None,
        )
    assert reloaded == [0]
    assert runs == [[0], [0]]


def test_reload_black_videoluts_noop_when_all_fine():
    """No re-load when every display has a healthy VideoLUT."""
    runs = []
    with mock.patch("DisplayCAL.worker.sys.platform", "darwin"):
        reloaded = reload_black_videoluts(
            "dispwin",
            _maxima_fn=lambda: [1.0, 0.98],
            _reload=runs.append,
            _sleep=lambda s: None,
        )
    assert reloaded == []
    assert runs == []


def test_reload_black_videoluts_ignores_unreadable_displays():
    """A display that couldn't be read (None) is left alone."""
    runs = []
    with mock.patch("DisplayCAL.worker.sys.platform", "darwin"):
        reloaded = reload_black_videoluts(
            "dispwin",
            _maxima_fn=lambda: [None, 1.0],
            _reload=runs.append,
            _sleep=lambda s: None,
        )
    assert reloaded == []
    assert runs == []


def test_reload_black_videoluts_reloads_all_black_displays_in_one_call():
    """All black displays are re-loaded together, not one process per display.

    Reloading one display per dispwin process exit blacks out the other one on
    macOS, making both flicker (issue #991).
    """
    runs = []
    maxima_seq = iter([[0.0, 0.0], [1.0, 1.0]])
    with mock.patch("DisplayCAL.worker.sys.platform", "darwin"):
        reloaded = reload_black_videoluts(
            "dispwin",
            _maxima_fn=lambda: next(maxima_seq),
            _reload=runs.append,
            _sleep=lambda s: None,
        )
    assert reloaded == [0, 1]
    assert runs == [[0, 1]]


def test_reload_black_videoluts_doesnt_run_dispwin():
    """The default re-load never runs a dispwin process."""
    maxima_seq = iter([[1.0, 0.0], [1.0, 1.0]])
    with (
        mock.patch("DisplayCAL.worker.sys.platform", "darwin"),
        mock.patch(
            "DisplayCAL.worker.reload_macos_calibration", return_value=[1]
        ) as reload_mock,
        mock.patch("DisplayCAL.worker.sp.call") as call_mock,
    ):
        reloaded = reload_black_videoluts(
            "dispwin",
            _maxima_fn=lambda: next(maxima_seq),
            _sleep=lambda s: None,
        )
    assert reloaded == [1]
    reload_mock.assert_called_once_with([1], log=None)
    call_mock.assert_not_called()


def _maxima_from_clobbered(ndisplays, clobbered):
    """Build a get_macos_videolut_maxima()-shaped list from a clobbered set."""
    return [0.0 if i in clobbered else 1.0 for i in range(ndisplays)]


def test_clobbered_displays_skips_virtual_displays():
    """Virtual displays are skipped even if their VideoLUT reads as black."""
    worker = FakeMultiDisplayWorker(ndisplays=3)
    pl = _profile_loader_stub()
    with (
        mock.patch(
            "DisplayCAL.profile_loader.config.is_virtual_display",
            side_effect=lambda i: i == 2,
        ),
        mock.patch(
            "DisplayCAL.worker.get_macos_videolut_maxima",
            return_value=_maxima_from_clobbered(3, {0, 2}),
        ),
    ):
        assert pl._clobbered_displays(worker, "dispwin") == [0]


def test_reload_clobbered_displays_batches_simultaneous_clobbers_in_one_pass():
    """Two displays black at once are both reloaded within a single call."""
    worker = FakeMultiDisplayWorker(ndisplays=2)
    clobbered = {0, 1}
    pl = _profile_loader_stub()
    calls = []

    def fake_reload(indices, log=None):
        calls.append(list(indices))
        for i in indices:
            clobbered.discard(i)
        return list(indices)

    with (
        mock.patch(
            "DisplayCAL.profile_loader.config.is_virtual_display",
            return_value=False,
        ),
        mock.patch(
            "DisplayCAL.worker.get_macos_videolut_maxima",
            side_effect=lambda: _maxima_from_clobbered(2, clobbered),
        ),
        mock.patch(
            "DisplayCAL.worker.reload_macos_calibration", side_effect=fake_reload
        ),
        mock.patch("DisplayCAL.profile_loader.time.sleep"),
    ):
        converged = pl._reload_clobbered_displays(
            worker, "dispwin", max_passes=5, settle=0
        )
    assert calls == [[0, 1]]
    assert converged is True


def test_reload_clobbered_displays_converges_after_a_reload_not_sticking():
    """A display whose reload doesn't stick right away is retried until it converges.

    Reloading all clobbered displays from one process (rather than one
    dispwin subprocess per display) avoids the deterministic multi-display
    ping-pong that issue #824 was originally about, but the pass loop
    remains as a safety net for a display simply not sticking on the first
    try (e.g. disturbed again before the next scan).
    """
    worker = FakeMultiDisplayWorker(ndisplays=2)
    clobbered = {0}
    pl = _profile_loader_stub()
    calls = []
    passes_done = 0

    def fake_reload(indices, log=None):
        nonlocal passes_done
        calls.append(list(indices))
        for i in indices:
            clobbered.discard(i)
        if passes_done < 2:
            clobbered.add(0)
        return list(indices)

    def fake_sleep(_seconds):
        nonlocal passes_done
        passes_done += 1

    with (
        mock.patch(
            "DisplayCAL.profile_loader.config.is_virtual_display",
            return_value=False,
        ),
        mock.patch(
            "DisplayCAL.worker.get_macos_videolut_maxima",
            side_effect=lambda: _maxima_from_clobbered(2, clobbered),
        ),
        mock.patch(
            "DisplayCAL.worker.reload_macos_calibration", side_effect=fake_reload
        ),
        mock.patch("DisplayCAL.profile_loader.time.sleep", side_effect=fake_sleep),
    ):
        converged = pl._reload_clobbered_displays(
            worker, "dispwin", max_passes=10, settle=0
        )
    assert not clobbered
    assert calls == [[0], [0], [0]]
    assert converged is True


def test_reload_clobbered_displays_stops_after_max_passes_without_hanging():
    """A display that never sticks must be bounded, not retried forever."""
    worker = FakeMultiDisplayWorker(ndisplays=2)
    clobbered = {0}
    pl = _profile_loader_stub()
    calls = []

    def fake_reload(indices, log=None):
        calls.append(list(indices))
        # Reload "succeeds" but the display is immediately clobbered again.
        return list(indices)

    with (
        mock.patch(
            "DisplayCAL.profile_loader.config.is_virtual_display",
            return_value=False,
        ),
        mock.patch(
            "DisplayCAL.worker.get_macos_videolut_maxima",
            side_effect=lambda: _maxima_from_clobbered(2, clobbered),
        ),
        mock.patch(
            "DisplayCAL.worker.reload_macos_calibration", side_effect=fake_reload
        ),
        mock.patch("DisplayCAL.profile_loader.time.sleep"),
    ):
        converged = pl._reload_clobbered_displays(
            worker, "dispwin", max_passes=4, settle=0
        )
    assert len(calls) == 4
    assert clobbered
    assert converged is False


def test_reload_clobbered_displays_stops_on_shutdown():
    """The shutdown flag must break out of the reload loop promptly."""
    worker = FakeMultiDisplayWorker(ndisplays=1)
    clobbered = {0}
    pl = _profile_loader_stub()
    calls = []

    def fake_reload(indices, log=None):
        calls.append(list(indices))
        pl._shutdown = True
        # Still "clobbered" - a real shutdown just stops trying.
        return []

    with (
        mock.patch(
            "DisplayCAL.profile_loader.config.is_virtual_display",
            return_value=False,
        ),
        mock.patch(
            "DisplayCAL.worker.get_macos_videolut_maxima",
            side_effect=lambda: _maxima_from_clobbered(1, clobbered),
        ),
        mock.patch(
            "DisplayCAL.worker.reload_macos_calibration", side_effect=fake_reload
        ),
        mock.patch("DisplayCAL.profile_loader.time.sleep"),
    ):
        converged = pl._reload_clobbered_displays(
            worker, "dispwin", max_passes=10, settle=0
        )
    assert calls == [[0]]
    assert converged is True


def test_macos_watch_backs_off_after_repeated_non_convergence():
    """Non-converging displays trigger a notification and a backoff pause.

    Some multi-display Macs never converge (issue #824): reloading display A
    deterministically clobbers display B and vice-versa, confirmed by hand.
    Retrying forever would just keep flickering the screens, so after a few
    consecutive non-converging ticks the watch must stop touching the
    displays for a while and notify the user once, instead of hammering
    dispwin indefinitely.
    """
    config.initcfg()
    config.setcfg("profile_loader.macos_reapply_watch_interval", 1)
    config.setcfg("profile_loader.macos_reapply_watch_unstable_threshold", 2)
    config.setcfg("profile_loader.macos_reapply_watch_backoff_seconds", 9999)

    pl = _profile_loader_stub()
    pl._reload_clobbered_displays = mock.Mock(return_value=False)
    pl._notify_macos_watch_unstable = mock.Mock()

    tick_count = {"n": 0}

    def fake_is_displaycal_running():
        tick_count["n"] += 1
        if tick_count["n"] >= 5:
            pl._shutdown = True
        return False

    pl._is_displaycal_running = fake_is_displaycal_running

    try:
        with (
            mock.patch("DisplayCAL.profile_loader.time.sleep"),
            mock.patch("DisplayCAL.worker.get_argyll_util", return_value="dispwin"),
            mock.patch("DisplayCAL.worker.Worker") as mock_worker_cls,
        ):
            mock_worker_cls.return_value.enumerate_displays_and_ports = mock.Mock()
            pl._macos_watch()
        # Only the first two ticks actually attempt a reload (that's what
        # trips the unstable threshold); the rest are skipped by the backoff.
        assert pl._reload_clobbered_displays.call_count == 2
        assert pl._notify_macos_watch_unstable.call_count == 1
    finally:
        config.setcfg("profile_loader.macos_reapply_watch_interval", 5)
        config.setcfg("profile_loader.macos_reapply_watch_unstable_threshold", 3)
        config.setcfg("profile_loader.macos_reapply_watch_backoff_seconds", 300)
