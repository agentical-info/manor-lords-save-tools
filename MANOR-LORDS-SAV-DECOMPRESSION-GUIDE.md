# Manor Lords Save File Decompression Guide

**Author:** agentical

This guide explains how to decompress Manor Lords `.sav` files into the raw binary format that can be parsed by `ml-sav-parser.py`.

## Overview

Manor Lords save files use **Oodle Kraken compression**, a proprietary compression algorithm developed by RAD Game Tools (now owned by Epic Games). The `.sav` file contains a small header followed by compressed data.

## Save File Structure

```
Offset  Size    Description
------  ----    -----------
0x00    4       Magic: "GVAS" (0x53415647)
0x04    4       Save Game Version
0x08    4       Package File Version
0x0C    4       Engine Version Major
0x10    4       Engine Version Minor
0x14    4       Engine Version Patch
0x18    4       Engine Version Build
0x1C    ?       Engine Version String (length-prefixed)
...     ...     Custom Version Format, Save Game Class Name
...     4       Compressed flag (1 = compressed)
...     4       Uncompressed size
...     4       Compressed size
...     ?       Compressed data (Oodle Kraken)
```

The exact offset of the compressed data varies based on string lengths in the header. Look for the compressed/uncompressed size fields to locate it.

## Decompression Methods

### Method 1: Using Python with Oodle DLL (Recommended)

This method uses the Oodle decompression library directly.

#### Prerequisites

1. **Oodle DLL**: Extract `oo2core_9_win64.dll` (or similar version) from another UE4/UE5 game that includes Oodle. Common locations in games that have it:
   - `<Game Install>/Engine/Binaries/Win64/`
   - `<Game Install>/Binaries/Win64/`

2. **Python 3.x** with ctypes (included in standard library)

#### Decompression Script

```python
"""
Manor Lords Save File Decompressor
Extracts Oodle-compressed save data to raw binary format.
"""

import ctypes
import struct
from pathlib import Path

def decompress_save(sav_path: str, output_path: str, oodle_dll_path: str) -> bool:
    """
    Decompress a Manor Lords .sav file.

    Args:
        sav_path: Path to the compressed .sav file
        output_path: Path for the decompressed .bin output
        oodle_dll_path: Path to oo2core_9_win64.dll

    Returns:
        True if successful, False otherwise
    """
    # Load Oodle DLL
    try:
        oodle = ctypes.WinDLL(oodle_dll_path)
    except OSError as e:
        print(f"Failed to load Oodle DLL: {e}")
        return False

    # Set up the decompression function
    # OodleLZ_Decompress(src, src_len, dst, dst_len, ...)
    decompress = oodle.OodleLZ_Decompress
    decompress.restype = ctypes.c_int64
    decompress.argtypes = [
        ctypes.c_void_p,  # src
        ctypes.c_int64,   # src_len
        ctypes.c_void_p,  # dst
        ctypes.c_int64,   # dst_len
        ctypes.c_int,     # fuzz_safe
        ctypes.c_int,     # check_crc
        ctypes.c_int,     # verbosity
        ctypes.c_void_p,  # dst_base
        ctypes.c_int64,   # e
        ctypes.c_void_p,  # cb
        ctypes.c_void_p,  # cb_ctx
        ctypes.c_void_p,  # scratch
        ctypes.c_int64,   # scratch_size
        ctypes.c_int,     # threadPhase
    ]

    with open(sav_path, 'rb') as f:
        data = f.read()

    # Verify GVAS magic
    if data[:4] != b'GVAS':
        print("Error: Not a valid GVAS save file")
        return False

    # Parse header to find compressed data
    # This is a simplified parser - adjust offsets as needed
    pos = 4  # Skip magic

    # Skip version fields (16 bytes)
    pos += 16

    # Read engine version string
    str_len = struct.unpack_from('<i', data, pos)[0]
    pos += 4 + str_len

    # Skip custom version format
    custom_version_count = struct.unpack_from('<i', data, pos)[0]
    pos += 4
    for _ in range(custom_version_count):
        pos += 20  # GUID (16) + version (4)

    # Read save game class name
    str_len = struct.unpack_from('<i', data, pos)[0]
    pos += 4 + str_len

    # Read compression info
    compressed_flag = struct.unpack_from('<i', data, pos)[0]
    pos += 4

    if compressed_flag != 1:
        print("Save file is not compressed")
        # Just copy the remaining data
        with open(output_path, 'wb') as f:
            f.write(data[pos:])
        return True

    uncompressed_size = struct.unpack_from('<i', data, pos)[0]
    pos += 4
    compressed_size = struct.unpack_from('<i', data, pos)[0]
    pos += 4

    print(f"Compressed size: {compressed_size:,} bytes")
    print(f"Uncompressed size: {uncompressed_size:,} bytes")

    compressed_data = data[pos:pos + compressed_size]

    # Allocate output buffer
    output_buffer = (ctypes.c_uint8 * uncompressed_size)()
    src_buffer = (ctypes.c_uint8 * len(compressed_data)).from_buffer_copy(compressed_data)

    # Decompress
    result = decompress(
        ctypes.byref(src_buffer),
        len(compressed_data),
        ctypes.byref(output_buffer),
        uncompressed_size,
        0, 0, 0,  # fuzz_safe, check_crc, verbosity
        None, 0,  # dst_base, e
        None, None,  # cb, cb_ctx
        None, 0,  # scratch, scratch_size
        0  # threadPhase
    )

    if result != uncompressed_size:
        print(f"Decompression failed: got {result}, expected {uncompressed_size}")
        return False

    # Write output
    with open(output_path, 'wb') as f:
        f.write(bytes(output_buffer))

    print(f"Successfully decompressed to: {output_path}")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Decompress Manor Lords save files")
    parser.add_argument("input", help="Input .sav file path")
    parser.add_argument("output", help="Output .bin file path")
    parser.add_argument("--oodle", default="oo2core_9_win64.dll",
                        help="Path to Oodle DLL (default: oo2core_9_win64.dll)")

    args = parser.parse_args()

    success = decompress_save(args.input, args.output, args.oodle)
    exit(0 if success else 1)
```

#### Usage

```bash
python ml-decompress-sav.py "path/to/save.sav" "output.bin" --oodle "path/to/oo2core_9_win64.dll"
```

### Method 2: Using uesave CLI Tool

The [uesave](https://github.com/trumank/uesave-rs) Rust tool can handle Oodle-compressed GVAS files if compiled with Oodle support.

```bash
# Note: Requires uesave built with Oodle support
uesave to-json -i save.sav -o save.json
```

However, uesave may not fully support all UE5.5 property types used by Manor Lords.

### Method 3: Manual Extraction with Hex Editor

For advanced users who want to understand the format:

1. Open the `.sav` file in a hex editor (HxD, 010 Editor, etc.)
2. Verify the `GVAS` magic at offset 0x00
3. Navigate through the header (see structure above)
4. Locate the compressed size and uncompressed size fields
5. Extract the compressed data block
6. Use an Oodle decompression tool to decompress

## Save File Locations

Manor Lords saves are typically located at:

```
%LOCALAPPDATA%\ManorLords\Saved\SaveGames\
```

Or for Steam:
```
C:\Users\<Username>\AppData\Local\ManorLords\Saved\SaveGames\
```

## Troubleshooting

### "Failed to load Oodle DLL"
- Ensure the DLL path is correct
- Use the 64-bit version (`oo2core_9_win64.dll`)
- The DLL version should match what Manor Lords uses (version 9)

### "Decompression failed"
- Verify the save file isn't corrupted
- Check that compressed/uncompressed sizes were read correctly
- Ensure you're using the correct Oodle DLL version

### "Not a valid GVAS save file"
- The file may be a different format or corrupted
- Verify the first 4 bytes are `GVAS` (0x47 0x56 0x41 0x53)

## Next Steps

After decompression, use the parser:

```bash
python ml-sav-parser.py input.bin --output save_data.json
```

See `MANOR-LORDS-SAV-FORMAT-SPEC.md` for the complete format specification.

## License

MIT License - See LICENSE file for details.
