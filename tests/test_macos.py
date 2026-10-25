import sys
import threading

import pytest

if sys.platform != "darwin":
    pytest.skip("PyObjC is only installed on macOS", allow_module_level=True)

from PyObjCTools import AppHelper  # noqa: E402

from battery_notifier.platforms import current_platform  # noqa: E402


def test_run_on_main_thread_from_another_thread():
    ran_on: list[threading.Thread] = []

    def record():
        ran_on.append(threading.current_thread())
        AppHelper.stopEventLoop()

    threading.Thread(target=current_platform().run_on_main_thread, args=[record]).start()
    AppHelper.callLater(5, AppHelper.stopEventLoop)  # don't hang if `record` never runs
    AppHelper.runConsoleEventLoop()
    assert ran_on == [threading.main_thread()]
