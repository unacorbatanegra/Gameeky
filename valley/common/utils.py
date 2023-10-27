import os

from gi.repository import GLib


def get_time_milliseconds() -> int:
    return int(GLib.get_monotonic_time() / 1000)


def get_data_path(*paths) -> str:
    return os.path.join(os.environ.get("DATA_DIR", ""), *paths)


def clamp(maximum, minimum, value):
    return min(max(minimum, value), maximum)


def division(dividend, divisor):
    return dividend / divisor if divisor > 0 else 0


def element(array, index):
    return array[index] if len(array) > 0 else None
