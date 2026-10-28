#!/usr/bin/env python3
""" Remember the paths a user entered recently (a small JSON file in the user config folder).
"""
from __future__ import annotations

import json
import logging
import os
import typing as T

from .paths import clean_path, user_config_dir

logger = logging.getLogger(__name__)

MAX_ITEMS = 8
FILENAME = "recent_paths.json"


class RecentPaths:
    """ Recently used values, stored per field name (e.g. ``extract.input_path``).

    Parameters
    ----------
    config_dir
        Folder that holds the JSON file. Default: :func:`simple_gui.paths.user_config_dir`
    max_items
        How many entries to keep for each field
    """
    def __init__(self, config_dir: str | None = None, max_items: int = MAX_ITEMS) -> None:
        self._dir = config_dir or user_config_dir()
        self._max = max_items
        self._data: dict[str, T.Any] = self._load()

    @property
    def filename(self) -> str:
        """ str : Full path to the JSON file """
        return os.path.join(self._dir, FILENAME)

    def _load(self) -> dict[str, T.Any]:
        """ Load the stored data. A missing or corrupt file gives an empty store. """
        try:
            with open(self.filename, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self) -> None:
        """ Write the data. Failure to save is logged, never raised: it is only a convenience """
        try:
            os.makedirs(self._dir, exist_ok=True)
            tmp = f"{self.filename}.tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self.filename)
        except OSError as err:
            logger.warning("Could not save recent paths: %s", err)

    def get(self, field: str) -> list[str]:
        """ Most recent first list of values for a field """
        values = self._data.get("paths", {}).get(field, [])
        return [str(val) for val in values] if isinstance(values, list) else []

    def last(self, field: str) -> str:
        """ The most recent value for a field, or ``""`` """
        values = self.get(field)
        return values[0] if values else ""

    def add(self, field: str, value: str | None, save: bool = True) -> None:
        """ Put a value at the front of a field's list (de-duplicated, trimmed to max) """
        value = clean_path(value)
        if not value:
            return
        values = [val for val in self.get(field) if val != value]
        self._data.setdefault("paths", {})[field] = ([value] + values)[:self._max]
        if save:
            self._save()

    def add_many(self, values: T.Mapping[str, str | None]) -> None:
        """ Add several fields at once and save once """
        for field, value in values.items():
            self.add(field, value, save=False)
        self._save()

    @property
    def workdir(self) -> str:
        """ str : The fixed work folder (工作文件夹), or ``""`` """
        return str(self._data.get("workdir", ""))

    @workdir.setter
    def workdir(self, path: str) -> None:
        self._data["workdir"] = clean_path(path)
        self._save()

    @property
    def preset(self) -> str:
        """ str : The last preset the user picked, or ``""`` """
        return str(self._data.get("preset", ""))

    @preset.setter
    def preset(self, name: str) -> None:
        self._data["preset"] = name
        self._save()
