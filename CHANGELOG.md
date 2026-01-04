# Changelog

All notable changes to this project will be documented in this file.

## [1.4.0] - 2025-01-04

### Added
- `--terse` mode (default): Excludes large data properties for smaller output
- `--verbose` mode: Includes all data (fertilityGrid*, savedRoads, waterVeins)
- `--show-waterveins` option: Include waterVeins in terse mode
- KNOWN-ISSUES.md documenting InterpCurve parsing limitations

### Changed
- Default output now excludes:
  - `fertilityGridQuantized` (1M Color structs)
  - `fertilityGridLimitsQuantized` (1M Color structs)
  - `savedRoads` (InterpCurve spline data)
  - `waterVeins` (vein polygon vectors)
- JSON output reduced from ~240MB to ~4MB for typical saves

### Fixed
- Struct array parsing now uses declared size boundaries instead of "None" terminator
- Parser recovers correctly when encountering InterpCurve data in savedRoads
- 100% parse rate on all tested saves (was failing on maps with road data)

## [1.0.0] - 2025-01-03

### Added
- Initial release
- `ml-sav-parser.py`: Parse decompressed Manor Lords saves to JSON/Markdown
- `ml-decompress-sav.py`: Decompress Oodle-compressed .sav files
- Format specification document
- Decompression guide
