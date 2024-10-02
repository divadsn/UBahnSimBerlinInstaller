from typing import Any


def fullname(o: Any) -> str:
    module = o.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return o.__class__.__name__
    return module + '.' + o.__class__.__name__


def format_speed(speed: float) -> str:
    """Convert speed to the best possible unit (B/s, KB/s, MB/s, etc.)."""
    units = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s']
    unit = units[0]
    for u in units:
        if speed < 1024:
            unit = u
            break
        speed /= 1024
    return f"{speed:.2f} {unit}"


def readable_size(size: int) -> str:
    units = ('KB', 'MB', 'GB', 'TB')
    size_list = [f'{int(size):,} B'] + [f'{int(size) / 1024 ** (i + 1):,.1f} {u}' for i, u in enumerate(units)]
    return [size for size in size_list if not size.startswith('0.')][-1]
