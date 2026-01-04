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
python ml-sav-parser.py <input.bin> [-o output.json] [-m output.md] [--quiet]
```

Example:
```bash
python ml-sav-parser.py saveGame_1.bin -o save.json -m save.md
```

Options:
- `-o, --output` - JSON output path (default: `<input>_parsed.json`)
- `-m, --markdown` - Markdown output path (default: `<input>_parsed.md`)
- `--json-only` - Only output JSON
- `--quiet` - Suppress progress output

## Save File Location

Manor Lords saves are typically at:
```
%LOCALAPPDATA%\ManorLords\Saved\SaveGames\
```

## Documentation

- [MANOR-LORDS-SAV-FORMAT-SPEC.md](MANOR-LORDS-SAV-FORMAT-SPEC.md) - Complete binary format specification
- [MANOR-LORDS-SAV-DECOMPRESSION-GUIDE.md](MANOR-LORDS-SAV-DECOMPRESSION-GUIDE.md) - Decompression details

## License

MIT
