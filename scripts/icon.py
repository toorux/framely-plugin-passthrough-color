"""Render the Framely-style tint mark for the repository and plugin package."""
import math
import pathlib
import struct
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SIZE = 256
SAMPLES = 4
BACKGROUND = (44, 48, 54)
FOREGROUND = (220, 226, 232)


def pixel(x, y):
    # Rounded tile and the same circle, axes and arc used by src/ui.tsx.
    corner_x, corner_y = max(abs(x - 128) - 88, 0), max(abs(y - 128) - 88, 0)
    if math.hypot(corner_x, corner_y) > 24:
        return (0, 0, 0, 0)
    dx, dy = x - 128, y - 128
    circle = abs(math.hypot(dx, dy) - 81) <= 7.2
    axes = (abs(dx) <= 7.2 and abs(dy) <= 81) or (abs(dy) <= 7.2 and abs(dx) <= 81)
    # Radius 135, endpoints at (128, 47) and (128, 209).
    arc = dx >= 0 and abs(dy) <= 81 and abs(math.hypot(dx + 108, dy) - 135) <= 7.2
    return (*FOREGROUND, 255) if circle or axes or arc else (*BACKGROUND, 255)


rows = []
for y in range(SIZE):
    row = bytearray()
    for x in range(SIZE):
        samples = [pixel(x + (sx + .5) / SAMPLES, y + (sy + .5) / SAMPLES)
                   for sy in range(SAMPLES) for sx in range(SAMPLES)]
        alpha = sum(p[3] for p in samples)
        rgb = [round(sum(p[c] * p[3] for p in samples) / alpha) if alpha else 0 for c in range(3)]
        row.extend([*rgb, round(alpha / len(samples))])
    rows.append(b'\0' + row)


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


image = (b'\x89PNG\r\n\x1a\n' +
         chunk(b'IHDR', struct.pack('>IIBBBBB', SIZE, SIZE, 8, 6, 0, 0, 0)) +
         chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + chunk(b'IEND', b''))
output = ROOT / 'payload/icon.png'
output.parent.mkdir(exist_ok=True)
(ROOT / 'icon.png').write_bytes(image)
output.write_bytes(image)
