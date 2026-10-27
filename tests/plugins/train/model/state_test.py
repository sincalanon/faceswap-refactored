#!/usr/bin/env python3
""" Pytest unit tests for the legacy config migration in
:class:`plugins.train.model._base.state.State` """
import copy
import typing as T

import pytest

from plugins.train.model._base.state import State


def _state(config: dict[str, T.Any], mixed_precision: list[str] | None = None) -> State:
    """ Build a bare :class:`State` holding only the attributes the legacy updater touches """
    state = State.__new__(State)
    state._config = copy.deepcopy(config)  # pylint:disable=protected-access
    state._mixed_precision_layers = list(mixed_precision or [])  # pylint:disable=protected-access
    return state


_CASES: list[tuple[str, dict[str, T.Any], list[str], dict[str, T.Any], list[str], bool]] = [
    ("nothing_to_do",
     {"loss_function": "ssim", "learn_mask": True, "mask_type": "extended"}, ["a_b"],
     {"loss_function": "ssim", "learn_mask": True, "mask_type": "extended"}, ["a_b"], False),
    ("dssim_true", {"dssim_loss": True}, [], {"loss_function": "ssim"}, [], True),
    ("dssim_false", {"dssim_loss": False}, [], {"loss_function": "mae"}, [], True),
    ("learn_mask_added_none", {"mask_type": None}, [],
     {"mask_type": None, "learn_mask": False}, [], True),
    ("learn_mask_added_facehull", {"mask_type": "facehull"}, [],
     {"mask_type": "components", "learn_mask": True}, [], True),
    ("mask_type_replaced_only", {"mask_type": "dfl_full", "learn_mask": False}, [],
     {"mask_type": "components", "learn_mask": False}, [], True),
    ("l2_reg_term", {"l2_reg_term": 50}, [],
     {"loss_function_2": "mse", "loss_weight_2": 50}, [], True),
    ("clipnorm", {"clipnorm": True}, [], {"gradient_clipping": "norm"}, [], True),
    ("autoclip", {"autoclip": True}, [], {"clipping": "autoclip"}, [], True),
    ("clip_layer_names", {}, ["clip.layer.1", "other"], {}, ["clip_layer_1", "other"], True),
    ("everything",
     {"dssim_loss": True, "mask_type": "facehull", "l2_reg_term": 10, "clipnorm": 1,
      "autoclip": False, "keep": 1},
     ["x.y"],
     {"loss_function": "ssim", "mask_type": "components", "learn_mask": True,
      "loss_function_2": "mse", "loss_weight_2": 10, "gradient_clipping": "norm",
      "clipping": "autoclip", "keep": 1},
     ["x_y"], True),
]


@pytest.mark.parametrize("config, layers, expected, expected_layers, updated",
                         [c[1:] for c in _CASES], ids=[c[0] for c in _CASES])
def test_update_legacy_config(config: dict[str, T.Any],
                              layers: list[str],
                              expected: dict[str, T.Any],
                              expected_layers: list[str],
                              updated: bool) -> None:
    """ Legacy state config items are migrated to their current equivalents """
    state = _state(config, layers)
    assert state._update_legacy_config() is updated  # pylint:disable=protected-access
    assert state._config == expected  # pylint:disable=protected-access
    assert state._mixed_precision_layers == expected_layers  # pylint:disable=protected-access
