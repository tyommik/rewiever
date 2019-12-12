import os
import pathlib


INPUT = r'/home/ashibaev/Documents/Toloka_1_edit'
not_delete = set()
with open(r'/home/ashibaev/Documents/toloka_part1_new.txt', 'r') as p_inf:
    for line in p_inf:
        line = line.strip()
        guid = line
        not_delete.add(guid)


for root, dirs, files in os.walk(INPUT):
    for file in files:
        p = pathlib.Path(INPUT) / file
        if p.suffix == '.mp4':
            name = p.stem
            if name not in not_delete:
                p.unlink()