from battery_notifier.battery import BatteryThreshold


def test_battery_threshold_order():
    thresholds = BatteryThreshold.ascending_order()
    for i in range(len(thresholds) - 1):
        assert thresholds[i].value < thresholds[i + 1].value
