# Manor Lords Save Tools

Python tools for parsing Manor Lords save files (.sav).

## Requirements

- Python 3.x
- `oo2core_*_win64.dll` (Oodle decompression library from another UE4/UE5 game)

## Usage

### 1. Decompress the save file

Manor Lords saves are Oodle-compressed. First decompress:

```bash
python ml-decompress-sav.py <input.sav> <output.bin> [--oodle path/to/oo2core_7_win64.dll]
```

Example:
```bash
python ml-decompress-sav.py saveGame_1.sav saveGame_1.bin
```

The script looks for the Oodle DLL in the current directory. Use `--oodle` to specify a different path.

**Note:** The companion `_descr.sav` file must be in the same directory (e.g., `saveGame_1_descr.sav`).

### 2. Parse the decompressed data

```bash
python ml-sav-parser.py <input.bin> [options]
```

Examples:
```bash
# Default (terse mode - smaller output)
python ml-sav-parser.py saveGame_1.bin

# Include water vein data for map generation
python ml-sav-parser.py saveGame_1.bin --show-waterveins

# Include all data (large output ~240MB)
python ml-sav-parser.py saveGame_1.bin --verbose
```

**Output options:**
- `-o, --output` - JSON output path (default: `<input>.json`)
- `-m, --markdown` - Markdown output path (default: `<input>.md`)
- `--json-only` - Only output JSON
- `--markdown-only, --md-only` - Only output Markdown
- `-q, --quiet` - Suppress progress output

**Verbosity options:**
- `--terse` - Exclude large data (default) - ~4MB output
- `--verbose` - Include all data - ~240MB output
- `--show-waterveins` - Include waterVeins in terse mode

By default, the parser excludes large properties (`fertilityGridQuantized`, `fertilityGridLimitsQuantized`, `savedRoads`, `waterVeins`) to keep output manageable. Use `--verbose` for complete data or `--show-waterveins` for map visualization.

## Save File Location

Manor Lords saves are typically at:
```
%LOCALAPPDATA%\ManorLords\Saved\SaveGames\
```

## Documentation

- [MANOR-LORDS-SAV-FORMAT-SPEC.md](MANOR-LORDS-SAV-FORMAT-SPEC.md) - Complete binary format specification
- [MANOR-LORDS-SAV-DECOMPRESSION-GUIDE.md](MANOR-LORDS-SAV-DECOMPRESSION-GUIDE.md) - Decompression details
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [KNOWN-ISSUES.md](KNOWN-ISSUES.md) - Known limitations

## License

MIT
