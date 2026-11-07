"""
The shared validators in ``wherewhen._validators``.

Each validator has one job, raises ``TypeError`` for a wrong type and
``ValueError`` for a bad value (the rule agreed on #5), and names the caller.
"""
import math

import pytest

from wherewhen._validators import (
    _validate_integer,
    _validate_latitude,
    _validate_longitude,
    _validate_mgrs_precision,
    _validate_number,
)


class TestValidateNumber:

    @pytest.mark.parametrize("value", [0, -3, 2.5, 1e300, math.inf, math.nan])
    def test_accepts_ints_and_floats(self, value):
        # Type only: ranges (and NaN / inf) are each caller's business.
        assert _validate_number(value, "caller") is None

    @pytest.mark.parametrize("value", [True, False, "1", None, [1], 1j])
    def test_rejects_bools_and_non_numbers(self, value):
        with pytest.raises(TypeError, match=r"\[caller\] Weight must be a number, got "):
            _validate_number(value, "caller", "Weight")


class TestValidateInteger:

    def test_accepts_an_int(self):
        assert _validate_integer(3, "caller") is None

    @pytest.mark.parametrize("value", [True, 3.0, "3", None])
    def test_rejects_bools_floats_and_others(self, value):
        with pytest.raises(TypeError, match=r"\[caller\] Precision must be an integer, got "):
            _validate_integer(value, "caller", "Precision")


@pytest.mark.parametrize("validator, name", [
    (_validate_latitude, "Latitude"),
    (_validate_longitude, "Longitude"),
])
class TestCoordinateValidators:

    def test_wrong_type_is_type_error(self, validator, name):
        with pytest.raises(TypeError, match=rf"\[caller\] {name} must be a number, got str"):
            validator("10", "caller")

    def test_bool_is_rejected(self, validator, name):
        with pytest.raises(TypeError, match=rf"{name} must be a number, got bool"):
            validator(True, "caller")

    @pytest.mark.parametrize("value", [500.0, -500, math.nan])
    def test_out_of_range_is_value_error(self, validator, name, value):
        with pytest.raises(ValueError, match=rf"\[caller\] {name} must be in"):
            validator(value, "caller")


def test_mgrs_precision_rejects_a_bool():
    with pytest.raises(TypeError, match=r"MGRS precision must be an integer, got bool"):
        _validate_mgrs_precision(True, "caller")
