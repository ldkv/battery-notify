"""Describe the settings dialog from the `Settings` fields, independently of the GUI toolkit."""

import typing
from dataclasses import dataclass, fields
from enum import Enum

from battery_notifier.core.settings import Settings


class FieldKind(Enum):
    NUMBER = "number"
    CHECKLIST = "checklist"


@dataclass(frozen=True)
class FormField:
    name: str
    label: str
    kind: FieldKind
    help_text: str = ""
    min: int | None = None
    max: int | None = None


def form_fields() -> list[FormField]:
    hints = typing.get_type_hints(Settings)
    form = []
    for setting_field in fields(Settings):
        field_type = hints[setting_field.name]
        if field_type is int:
            kind = FieldKind.NUMBER
        elif typing.get_origin(field_type) is frozenset:
            kind = FieldKind.CHECKLIST
        else:
            raise TypeError(f"No form widget for {setting_field.name}: {field_type}")
        metadata = setting_field.metadata
        form.append(
            FormField(
                name=setting_field.name,
                label=metadata["label"],
                kind=kind,
                help_text=metadata.get("help", ""),
                min=metadata.get("min"),
                max=metadata.get("max"),
            )
        )
    return form
