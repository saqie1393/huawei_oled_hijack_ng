#!/usr/bin/env python3
"""
Convert 1-bit SMALL_FONT to 4-bit anti-aliased version.
Correctly packs 2 pixels per byte (4 bits each).
"""

import re
import sys

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


def to_2d_pixels(char_data, width, height=14):
    """1-bit data ko 2D pixel array mein convert karein."""
    # SMALL_FONT has 2 bytes per row (28 bytes / 14 rows = 2)
    pixels = [[0] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            byte_idx = y * 2 + (x // 8)
            if byte_idx < len(char_data):
                bit_idx = 7 - (x % 8)
                if char_data[byte_idx] & (1 << bit_idx):
                    pixels[y][x] = 1
    return pixels


def blur_to_4bit(pixels, width, height=14):
    """
    1-bit pixels ko 4-bit anti-aliased mein convert karein.
    3x3 box blur + original pixels ko preserve karein.
    """
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


def pack_4bit(pixels, width, height=14):
    """
    4-bit pixels ko bytes mein pack karein.
    Har byte mein 2 pixels (upper nibble + lower nibble).
    Row-aligned, 2 pixels per byte.
    """
    packed = []
    for y in range(height):
        x = 0
        while x < width:
            high = pixels[y][x] if x < width else 0
            low = pixels[y][x + 1] if x + 1 < width else 0
            packed.append((high << 4) | low)
            x += 2
    return packed


def main():
    print("Reading oled_font.h...", file=sys.stderr)
    chars, widths = parse_font_from_header('oled_font.h')
    print(f"Found {len(chars)} characters", file=sys.stderr)
    
    # Har character ke liye bytes per row calculate karein
    # Width ke hisaab se alag hoga — lekin array size fix karna hoga
    # Max width 14 → 7 bytes per row, 14 rows → 98 bytes per char
    
    MAX_WIDTH = 14
    HEIGHT = 14
    BYTES_PER_CHAR = (MAX_WIDTH // 2) * HEIGHT  # 7 * 14 = 98
    
    print(f"Bytes per char: {BYTES_PER_CHAR}", file=sys.stderr)
    
    output = []
    output.append("// 4-bit anti-aliased font (auto-generated)")
    output.append(f"// {BYTES_PER_CHAR} bytes per char ({MAX_WIDTH}x{HEIGHT}, 4bpp)")
    output.append(f"static uint8_t SMALL_FONT_4BPP[][{BYTES_PER_CHAR}] = {{")
    
    for i, char_data in enumerate(chars):
        width = widths[i] if i < len(widths) else 14
        if width == 0:
            width = 14
        
        pixels = to_2d_pixels(char_data, width)
        blurred = blur_to_4bit(pixels, width)
        packed = pack_4bit(blurred, MAX_WIDTH)  # Max width ke saath pack karein
        
        # Pad to BYTES_PER_CHAR
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
