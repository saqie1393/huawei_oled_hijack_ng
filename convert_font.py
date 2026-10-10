#!/usr/bin/env python3
"""
Convert 1-bit SMALL_FONT to 4-bit anti-aliased version.
Yeh script oled_font.h ko read karti hai, SMALL_FONT array nikaliti hai,
aur 4-bit anti-aliased version generate karti hai.
"""

import re
import sys

def parse_font_from_header(filepath):
    """oled_font.h se SMALL_FONT array aur widths parse karein"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # SMALL_FONT array dhoondein
    match = re.search(r'SMALL_FONT\[\]\[28\]\s*=\s*\{(.*?)\n\};', content, re.DOTALL)
    if not match:
        print("ERROR: SMALL_FONT not found in oled_font.h", file=sys.stderr)
        sys.exit(1)
    
    font_body = match.group(1)
    
    # Har character ka data nikaalein
    chars = []
    for char_match in re.finditer(r'\{([^}]+)\}', font_body):
        values = [int(x.strip(), 16) if x.strip().startswith('0x') 
                  else int(x.strip()) 
                  for x in char_match.group(1).split(',') if x.strip()]
        if values:
            chars.append(values)
    
    # Widths dhoondein
    widths_match = re.search(r'SMALL_FONT_WIDTHS\[\]\s*=\s*\{(.*?)\};', content, re.DOTALL)
    widths = []
    if widths_match:
        widths = [int(x.strip(), 16) if x.strip().startswith('0x') 
                  else int(x.strip()) 
                  for x in widths_match.group(1).split(',') if x.strip()]
    
    return chars, widths


def bit_to_4bit_value(bit_val):
    """1-bit (0/1) ko 4-bit (0/15) mein convert karein"""
    return 15 if bit_val else 0


def blur_character(char_data, width, height=14):
    """
    1-bit character ko 4-bit anti-aliased mein convert karein.
    Blur algorithm: har pixel ke aas paas ke pixels ka average lein.
    """
    # Pehle 1-bit ko 2D array mein convert karein
    pixels = [[0] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            byte_idx = y * 2 + (x // 8)  # 2 bytes per row
            if byte_idx < len(char_data):
                bit_idx = 7 - (x % 8)
                if char_data[byte_idx] & (0x1 << bit_idx):
                    pixels[y][x] = 1
    
    # Ab blur karein (3x3 kernel)
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
            # Average ko 4-bit (0-15) mein convert karein
            if count > 0:
                avg = total / count
                blurred[y][x] = int(avg * 15)
    
    # Original 1-bit pixels ko preserve karein (sharp edges)
    for y in range(height):
        for x in range(width):
            if pixels[y][x]:
                blurred[y][x] = 15
    
    return blurred


def pack_4bit_to_bytes(pixels, width, height=14):
    """4-bit pixels ko bytes mein pack karein (2 pixels per byte)"""
    packed = []
    for y in range(height):
        x = 0
        while x < width:
            # Upper nibble
            high = pixels[y][x] if x < width else 0
            # Lower nibble
            low = pixels[y][x + 1] if x + 1 < width else 0
            packed.append((high << 4) | low)
            x += 2
    return packed


def generate_4bit_font(chars, widths):
    """Poora 4-bit font array generate karein"""
    output = []
    output.append("// 4-bit anti-aliased font (auto-generated)")
    output.append("static uint8_t SMALL_FONT_4BPP[][28] = {")
    
    for i, char_data in enumerate(chars):
        width = widths[i] if i < len(widths) else 14
        if width == 0:
            width = 14
        
        # Blur karein
        blurred = blur_character(char_data, width)
        packed = pack_4bit_to_bytes(blurred, width)
        
        # Hex values format karein
        hex_vals = ','.join(f'0x{b:02x}' for b in packed)
        output.append(f"    /*0x{i:04x}*/ {{{hex_vals}}},")
    
    output.append("};")
    output.append("")
    output.append("static const uint8_t SMALL_FONT_4BPP_BYTES_PER_CHAR = 28;")
    output.append("")
    
    return '\n'.join(output)


def main():
    header_file = 'oled_font.h'
    
    print(f"Reading {header_file}...", file=sys.stderr)
    chars, widths = parse_font_from_header(header_file)
    print(f"Found {len(chars)} characters", file=sys.stderr)
    
    print("Generating 4-bit font...", file=sys.stderr)
    output = generate_4bit_font(chars, widths)
    
    # Output ko file mein likhein
    with open('oled_font_4bpp.h', 'w') as f:
        f.write(output)
    
    print("Generated oled_font_4bpp.h", file=sys.stderr)


if __name__ == '__main__':
    main()
