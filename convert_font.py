#!/usr/bin/env python3
"""
Convert 1-bit SMALL_FONT to 4-bit anti-aliased version.
Correctly packs 2 pixels per byte (4 bits each), row-aligned.
"""

import re
import sys

# Constants
MAX_WIDTH = 14
HEIGHT = 14
BYTES_PER_ROW = MAX_WIDTH // 2   # 7 bytes per row
BYTES_PER_CHAR = BYTES_PER_ROW * HEIGHT   # 98 bytes per char


def parse_font_from_header(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    match = re.search(r'SMALL_FONT\[\]\[28\]\s*=\s*\{(.*?)\n\};', content, re.DOTALL)
    if not match:
        print("ERROR: SMALL_FONT not found", file=sys.stderr)
        sys.exit(1)

    font_body = match.group(1)

    chars = []
    for char_match in re.finditer(r'\{([^}]+)\}', font_body):
        values = []
        for x in char_match.group(1).split(','):
            x = x.strip()
            if not x:
                continue
            if x.startswith('0x'):
                values.append(int(x, 16))
            else:
                values.append(int(x))
        if values:
            chars.append(values)

    widths_match = re.search(r'SMALL_FONT_WIDTHS\[\]\s*=\s*\{(.*?)\};', content, re.DOTALL)
    widths = []
    if widths_match:
        for x in widths_match.group(1).split(','):
            x = x.strip()
            if not x:
                continue
            if x.startswith('0x'):
                widths.append(int(x, 16))
            else:
                widths.append(int(x))

    return chars, widths


def to_2d_pixels(char_data, width, height=HEIGHT):
    """1-bit data ko 2D pixel array mein convert karein."""
    pixels = [[0] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            byte_idx = y * 2 + (x // 8)
            if byte_idx < len(char_data):
                bit_idx = 7 - (x % 8)
                if char_data[byte_idx] & (1 << bit_idx):
                    pixels[y][x] = 1
    return pixels


def blur_to_4bit(pixels, width, height=HEIGHT):
    """1-bit pixels ko 4-bit anti-aliased mein convert karein (3x3 box blur)."""
    blurred = [[0] * width for _ in range(height)]

    for y in range(height):
        for x in range(width):
            total = 0
            count = 0
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        total += pixels[ny][nx]
                        count += 1
            if count > 0:
                avg = total / count
                blurred[y][x] = int(round(avg * 15))

    # Original 1-bit pixels ko sharp rakhein
    for y in range(height):
        for x in range(width):
            if pixels[y][x]:
                blurred[y][x] = 15

    return blurred


def pack_4bit_row(row_pixels):
    """Ek row ke 4-bit pixels ko bytes mein pack karein (MAX_WIDTH tak pad)."""
    padded = list(row_pixels)
    while len(padded) < MAX_WIDTH:
        padded.append(0)
    padded = padded[:MAX_WIDTH]

    packed = []
    for x in range(0, MAX_WIDTH, 2):
        high = padded[x] & 0x0F
        low = padded[x + 1] & 0x0F if x + 1 < MAX_WIDTH else 0
        packed.append((high << 4) | low)
    return packed


def pack_4bit(blurred, width, height=HEIGHT):
    """Poora character pack karein — har row ko MAX_WIDTH tak pad karke."""
    packed = []
    for y in range(height):
        row = blurred[y] if y < len(blurred) else []
        packed.extend(pack_4bit_row(row))
    return packed


def main():
    print("Reading oled_font.h...", file=sys.stderr)
    chars, widths = parse_font_from_header('oled_font.h')
    print(f"Found {len(chars)} characters", file=sys.stderr)
    print(f"Bytes per char: {BYTES_PER_CHAR}", file=sys.stderr)

    output = []
    output.append("// 4-bit anti-aliased font (auto-generated)")
    output.append(f"// {BYTES_PER_CHAR} bytes per char ({MAX_WIDTH}x{HEIGHT}, 4bpp)")
    output.append(f"static uint8_t SMALL_FONT_4BPP[][{BYTES_PER_CHAR}] = {{")

    for i, char_data in enumerate(chars):
        width = widths[i] if i < len(widths) else MAX_WIDTH
        if width == 0 or width > MAX_WIDTH:
            width = MAX_WIDTH

        pixels = to_2d_pixels(char_data, width)
        blurred = blur_to_4bit(pixels, width)
        packed = pack_4bit(blurred, width)

        # Safety: ensure exactly BYTES_PER_CHAR
        while len(packed) < BYTES_PER_CHAR:
            packed.append(0)
        packed = packed[:BYTES_PER_CHAR]

        hex_vals = ','.join(f'0x{b:02x}' for b in packed)
        output.append(f"    /*0x{i:04x}*/ {{{hex_vals}}},")

    output.append("};")
    output.append("")
    output.append(f"static const uint8_t SMALL_FONT_4BPP_BYTES_PER_CHAR = {BYTES_PER_CHAR};")
    output.append("")

    with open('oled_font_4bpp.h', 'w') as f:
        f.write('\n'.join(output))

    print(f"Generated oled_font_4bpp.h", file=sys.stderr)
    print(f"Size: {len(output)} lines", file=sys.stderr)


if __name__ == '__main__':
    main()
