from battery_notifier.ui.form import FieldKind, FormField, form_fields


def test_form_is_generated_from_settings():
    form = {form_field.name: form_field for form_field in form_fields()}

    assert list(form) == ["check_interval_minutes", "low_threshold", "critical_threshold", "disabled_devices"]
    assert form["check_interval_minutes"] == FormField(
        "check_interval_minutes", "Check interval (minutes)", FieldKind.NUMBER, min=1, max=120
    )
    assert form["low_threshold"].help_text == "Notify when a device drops to this level"
    assert form["disabled_devices"].kind is FieldKind.CHECKLIST
