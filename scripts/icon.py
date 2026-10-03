"""Render the UI color-wheel mark for the repository and plugin package."""
import math
import pathlib
import re
import struct
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
style = (ROOT / 'src/style.css').read_text()
wheel = re.search(r'\.color-wheel\{([^}]+)\}', style).group(1)
gradient = re.search(r'conic-gradient\(([^)]+)\)', wheel).group(1)
colors = [tuple(bytes.fromhex(value.strip().lstrip('#'))) for value in gradient.split(',')]
shadow = re.search(r'box-shadow:inset 0 0 0 (\d+)px #([0-9a-f]{6})([0-9a-f]{2})', wheel)
shadow_color = tuple(bytes.fromhex(shadow.group(2)))
shadow_alpha = int(shadow.group(3), 16) / 255
ui_width = int(re.search(r'width:(\d+)px', wheel).group(1))
size = 256
radius = 108
inset = int(shadow.group(1)) / ui_width * radius * 2
center = (size - 1) / 2
rows = []
for y in range(size):
    row = bytearray()
    for x in range(size):
        dx, dy = x - center, y - center
        distance = math.hypot(dx, dy)
        alpha = min(1, max(0, radius + .5 - distance))
        angle = (math.atan2(dx, -dy) / (2 * math.pi)) % 1
        position = angle * (len(colors) - 1)
        index = min(int(position), len(colors) - 2)
        fraction = position - index
        rgb = [a + (b - a) * fraction for a, b in zip(colors[index], colors[index + 1])]
        if distance >= radius - inset:
            rgb = [value * (1 - shadow_alpha) + tint * shadow_alpha for value, tint in zip(rgb, shadow_color)]
        if alpha == 0:
            rgb = [0, 0, 0]
        row.extend([round(value) for value in rgb] + [round(alpha * 255)])
    rows.append(b'\0' + row)


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


output = ROOT / 'payload/icon.png'
output.parent.mkdir(exist_ok=True)
image = (b'\x89PNG\r\n\x1a\n' +
    chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)) +
    chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + chunk(b'IEND', b''))
(ROOT / 'icon.png').write_bytes(image)
output.write_bytes(image)
