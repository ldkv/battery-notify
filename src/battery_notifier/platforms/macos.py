from collections.abc import Callable

from PyObjCTools import AppHelper

from battery_notifier.platforms.base import Platform


class MacOSPlatform(Platform):
    def run_on_main_thread(self, function: Callable[[], None]):
        # AppKit crashes the app when the status item is changed from another thread
        AppHelper.callAfter(function)
