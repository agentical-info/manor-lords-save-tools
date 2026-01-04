#!/usr/bin/env python3
"""
Manor Lords Save File Decompressor

Decompresses Oodle-compressed Manor Lords .sav files to raw GVAS format
that can be parsed by ml-sav-parser.py.

The entire .sav file is Oodle-compressed. The expected decompressed size
is read from the companion _descr.sav file (which contains an UncompressedSize
property). The decompressed output starts with GVAS magic.

Requirements:
    - Python 3.x
    - oo2core_*_win64.dll (from another UE4/UE5 game that includes Oodle)

Usage:
    python ml-decompress-sav.py input.sav output.bin
    python ml-decompress-sav.py input.sav output.bin --oodle path/to/oo2core_7_win64.dll

Author: agentical
License: MIT
Repository: https://github.com/agentical-info/manor-lords-save-tools
"""

import argparse
import ctypes
import os
import struct
import sys
from pathlib import Path


def find_oodle_dll():
    """
    Search for Oodle DLL in common locations.

    Returns:
        Path to DLL if found, None otherwise.
    """
    search_paths = [
        os.path.dirname(os.path.abspath(__file__)),
        os.getcwd(),
    ]

    dll_names = [
        "oo2core_9_win64.dll",
        "oo2core_8_win64.dll",
        "oo2core_7_win64.dll",
        "oo2core_6_win64.dll",
        "oo2core_5_win64.dll",
        "oo2core_win64.dll",
    ]

    for path in search_paths:
        for name in dll_names:
            full_path = os.path.join(path, name)
            if os.path.exists(full_path):
                return full_path

    return None


def get_uncompressed_size(sav_path: str) -> int:
    """
    Get uncompressed size from companion _descr.sav file.

    Manor Lords saves have a companion descriptor file that contains
    metadata including the UncompressedSize property.

    Args:
        sav_path: Path to the main .sav file

    Returns:
        Uncompressed size in bytes, or None if not found
    """
    descr_path = sav_path.replace('.sav', '_descr.sav')
    if not os.path.exists(descr_path):
        return None

    with open(descr_path, 'rb') as f:
        data = f.read()

    # Search for "UncompressedSize" property in the descriptor
    marker = b'UncompressedSize\x00'
    pos = data.find(marker)
    if pos == -1:
        return None

    # Property format (after name):
    #   4 bytes: type name length
    #   N bytes: type name (e.g., "IntProperty\0")
    #   4 bytes: size (0 for IntProperty)
    #   4 bytes: index (0)
    #   1 byte:  padding
    #   4 bytes: int32 value
    pos += len(marker)  # skip "UncompressedSize\0"

    type_len = struct.unpack('<I', data[pos:pos+4])[0]
    pos += 4 + type_len  # skip type length + type string
    pos += 8  # skip size + index
    pos += 1  # skip padding byte

    if pos + 4 <= len(data):
        return struct.unpack('<I', data[pos:pos+4])[0]

    return None


def decompress_save(input_path: str, output_path: str, dll_path: str = None) -> bool:
    """
    Decompress a Manor Lords .sav file.

    The entire .sav file is passed to Oodle for decompression.
    The decompressed output is raw GVAS data.

    Args:
        input_path: Path to compressed .sav file
        output_path: Path for decompressed output
        dll_path: Optional path to Oodle DLL

    Returns:
        True if successful
    """
    # Find Oodle DLL
    if dll_path is None:
        dll_path = find_oodle_dll()

    if dll_path is None:
        print("Error: Oodle DLL not found.", file=sys.stderr)
        print("Place oo2core_*_win64.dll in script directory or use --oodle", file=sys.stderr)
        return False

    print(f"Using Oodle DLL: {dll_path}")

    # Load Oodle DLL
    try:
        oodle = ctypes.CDLL(dll_path)
    except OSError as e:
        print(f"Error: Failed to load Oodle DLL: {e}", file=sys.stderr)
        return False

    # Set up decompression function
    OodleLZ_Decompress = oodle.OodleLZ_Decompress
    OodleLZ_Decompress.restype = ctypes.c_int64
    OodleLZ_Decompress.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t,  # compressed buf, size
        ctypes.c_void_p, ctypes.c_size_t,  # output buf, size
        ctypes.c_int, ctypes.c_int, ctypes.c_int,  # fuzzSafe, checkCRC, verbosity
        ctypes.c_void_p, ctypes.c_size_t,  # decoder buf base, size
        ctypes.c_void_p, ctypes.c_void_p,  # callbacks
        ctypes.c_void_p, ctypes.c_size_t,  # decoder memory
        ctypes.c_int  # thread phase
    ]

    # Read compressed input file
    with open(input_path, 'rb') as f:
        compressed_data = f.read()

    print(f"Input: {input_path}")
    print(f"Compressed size: {len(compressed_data):,} bytes")

    # Get expected decompressed size from _descr.sav
    expected_size = get_uncompressed_size(input_path)
    if expected_size:
        print(f"Uncompressed size (from _descr.sav): {expected_size:,} bytes")
    else:
        # Fallback: estimate based on typical compression ratio
        expected_size = len(compressed_data) * 6
        print(f"Estimated uncompressed size: {expected_size:,} bytes")

    # Allocate buffers
    output = ctypes.create_string_buffer(expected_size + 4096)
    comp_buf = ctypes.create_string_buffer(compressed_data)

    # Decompress
    print("Decompressing...")
    result = OodleLZ_Decompress(
        comp_buf, len(compressed_data),
        output, expected_size,
        1, 0, 0,  # fuzzSafe=1, checkCRC=0, verbosity=0
        None, 0,
        None, None,
        None, 0,
        0
    )

    if result <= 0:
        print(f"Error: Decompression failed (returned {result})", file=sys.stderr)
        return False

    print(f"Decompressed size: {result:,} bytes")

    # Verify GVAS magic in decompressed output
    if output.raw[:4] != b'GVAS':
        print("WARNING: Decompressed data does not start with GVAS magic!")
    else:
        print("GVAS magic verified OK")

    # Write decompressed output
    with open(output_path, 'wb') as f:
        f.write(output.raw[:result])

    print(f"Output: {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Decompress Manor Lords .sav files (Oodle compression)",
        epilog="""
Examples:
  python ml-decompress-sav.py save.sav save.bin
  python ml-decompress-sav.py save.sav save.bin --oodle path/to/oo2core_7_win64.dll

After decompression, parse with:
  python ml-sav-parser.py save.bin --output save.json
        """
    )

    parser.add_argument("input", help="Input .sav file")
    parser.add_argument("output", help="Output .bin file")
    parser.add_argument("--oodle", help="Path to Oodle DLL")

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    success = decompress_save(args.input, args.output, args.oodle)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
