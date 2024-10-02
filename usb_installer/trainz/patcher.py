import re
import shutil

from pathlib import Path

strings_to_replace = [
    "sounds/junction/bump.wav",
    "sounds/junction/wheels_over_points_1.wav",
    "sounds/junction/wheels_over_points_2.wav",
    "sounds/junction/wheels_over_points_3.wav",
    "sounds/junction/wheels_over_points_4.wav",
    "sounds/junction/wheels_over_points_5.wav",
    "sounds/junction/wheels_over_points_6.wav",
    "sounds/slack/slack%d.wav",
]


def replace_strings_with_nops(input_file, output_file, strings):
    with open(input_file, 'rb') as f:
        data = bytearray(f.read())

    for s in strings:
        pattern = re.compile(re.escape(s.encode()))
        matches = pattern.finditer(data)
        for match in matches:
            start = match.start()
            end = match.end()
            data[start:end] = b'\x90' * (end - start)

    with open(output_file, 'wb') as f:
        f.write(data)


def patch_sounds(input_file: Path):
    backup_file = input_file.with_suffix(input_file.suffix + ".bak")

    # Check if backup exists and restore it if necessary
    if backup_file.exists():
        backup_file.replace(input_file)

    # Create a backup of the original file
    shutil.copy(input_file, backup_file)

    # Replace strings with NOPs in the original file
    replace_strings_with_nops(backup_file, input_file, strings_to_replace)
