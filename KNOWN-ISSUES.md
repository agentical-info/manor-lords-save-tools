# Known Issues

## ml-sav-parser.py

### KI-001: InterpCurve ByteProperty enum format not fully parsed
**Status:** Open
**Severity:** Low
**Affected versions:** 1.1.0+
**Affected saves:** Maps with savedRoads property (road spline data)

**Description:**
ByteProperty enums inside InterpCurve structures (InterpCurvePointVector, InterpCurvePointQuat) use an extended format with additional metadata (module path, raw byte value) that the parser doesn't fully handle. This affects saves that include savedRoads with road spline data.

**Affected maps:**
- High Peaks (~27 errors)
- Germanic River (~182 errors)
- Jagged Cliffs (~31 errors)

**Impact:**
- Parse errors reported within savedRoads boundary
- Does NOT affect overall parse (100% of file still parsed)
- Road spline data partially captured, enum values missing
- savedRoads excluded from terse output (v1.3.0+)

**Workaround:**
None needed - parser recovers automatically via boundary enforcement.

**Example error:**
```
Error at 0xA5C: EOF at 0xA88, need 1953384773 bytes
```

---

## ml-decompress-sav.py

*No known issues*

---

## Log

| ID | Date Opened | Date Closed | Description |
|----|-------------|-------------|-------------|
| KI-001 | 2025-01-04 | - | InterpCurve ByteProperty format (multiple maps with savedRoads) |
