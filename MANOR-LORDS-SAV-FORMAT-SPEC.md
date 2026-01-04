# Manor Lords Save File Format Specification

## Technical Reference for UE5.5 GVAS Format

**Version:** 1.0
**Game:** Manor Lords (Version 0.8.050)
**Engine:** Unreal Engine 5.5.4
**Author:** agentical

---

## Table of Contents

1. [Overview](#1-overview)
2. [Compression Layer](#2-compression-layer)
3. [GVAS Header](#3-gvas-header)
4. [Property System](#4-property-system)
5. [Primitive Types](#5-primitive-types)
6. [Property Types](#6-property-types)
7. [Array Properties](#7-array-properties)
8. [Map Properties](#8-map-properties)
9. [Struct Properties](#9-struct-properties)
10. [Enum Properties](#10-enum-properties)
11. [Complete Property Reference](#11-complete-property-reference)
12. [Implementation Notes](#12-implementation-notes)

---

## 1. Overview

Manor Lords save files (`.sav`) use the Unreal Engine 5.5 Generic Variable Save (GVAS) format with Oodle compression.

### File Structure (High Level)

```
┌─────────────────────────────────────┐
│  Oodle Compression Header (16 bytes)│
├─────────────────────────────────────┤
│  Compressed Chunks (variable)       │
│  - Each chunk: 4-byte size + data   │
├─────────────────────────────────────┤
│  ──── After Decompression ────      │
├─────────────────────────────────────┤
│  GVAS Header (~1711 bytes)          │
├─────────────────────────────────────┤
│  Property List (recursive)          │
│  - Terminated by "None" string      │
└─────────────────────────────────────┘
```

### Byte Order

All multi-byte values are **little-endian**.

---

## 2. Compression Layer

The save file uses **Oodle Kraken** compression. The raw `.sav` file must be decompressed before parsing.

### Compression Header (16 bytes)

| Offset | Size | Type   | Description                    |
|--------|------|--------|--------------------------------|
| 0x00   | 4    | uint32 | Magic: `0x9E2A83C1`            |
| 0x04   | 4    | uint32 | Block size (typically 131072)  |
| 0x08   | 8    | uint64 | Uncompressed total size        |

### Chunk Format

After the header, data is stored in compressed chunks:

```
For each chunk:
┌────────────────────────────────────┐
│ Compressed Size (4 bytes, uint32)  │
├────────────────────────────────────┤
│ Compressed Data (variable)         │
└────────────────────────────────────┘
```

- If compressed_size == block_size, the chunk is stored uncompressed
- Otherwise, decompress using Oodle Kraken (compression level 4)
- Continue until sum of decompressed chunks equals uncompressed_total_size

### Oodle Decompression

Oodle is a proprietary compression library. Options for decompression:
- Use `oo2core_9_win64.dll` from the game files (Windows)
- Use ooz (open-source Oodle decompressor): https://github.com/powzix/ooz
- Python: Use ctypes to call the DLL

```python
# Example Python Oodle call signature
OodleLZ_Decompress(
    compressed_buffer,      # const void*
    compressed_size,        # size_t
    decompressed_buffer,    # void*
    decompressed_size,      # size_t
    0, 0, 0, 0, 0, 0, 0, 0  # Additional params (all 0)
) -> int  # Returns bytes decompressed
```

---

## 3. GVAS Header

After decompression, the file begins with the GVAS header.

### Header Structure

| Offset | Size | Type     | Description                              |
|--------|------|----------|------------------------------------------|
| 0x00   | 4    | char[4]  | Magic: "GVAS"                            |
| 0x04   | 4    | uint32   | Save game version                        |
| 0x08   | 4    | uint32   | Package version (UE4)                    |
| 0x0C   | 4    | uint32   | Package version (UE5)                    |
| 0x10   | 2    | uint16   | Engine major version                     |
| 0x12   | 2    | uint16   | Engine minor version                     |
| 0x14   | 2    | uint16   | Engine patch version                     |
| 0x16   | 4    | uint32   | Engine build number                      |
| 0x1A   | var  | FString  | Engine version string                    |
| var    | 4    | uint32   | Custom version count                     |
| var    | var  | CustomVersion[] | Array of custom versions          |
| var    | var  | FString  | Save game class type                     |

### CustomVersion Structure (per entry)

| Size | Type   | Description          |
|------|--------|----------------------|
| 16   | GUID   | Version GUID         |
| 4    | int32  | Version number       |

### FString Format

Strings in GVAS use a length-prefixed format:

```
┌─────────────────────────────────────┐
│ Length (4 bytes, int32)             │
├─────────────────────────────────────┤
│ String data (Length bytes)          │
│ - Includes null terminator          │
└─────────────────────────────────────┘
```

**Special cases:**
- Length = 0: Empty string (no data bytes)
- Length > 0: UTF-8 encoded string
- Length < 0: UTF-16LE encoded string, actual length = |Length| * 2 bytes

---

## 4. Property System

After the header, the save consists of a flat list of properties. Each property has a name, type, and value.

### Property Parsing Loop

```
while True:
    name = read_string()
    if name == "" or name == "None":
        break  # End of property list

    type = read_string()
    value = parse_property_value(type, name)
    store(name, value)
```

### Base Property Format

All properties start with:

```
┌─────────────────────────────────────┐
│ Property Name (FString)             │
├─────────────────────────────────────┤
│ Property Type (FString)             │
├─────────────────────────────────────┤
│ Type-specific metadata + value      │
└─────────────────────────────────────┘
```

---

## 5. Primitive Types

### Integer Types

| Type    | Size | Description              |
|---------|------|--------------------------|
| int8    | 1    | Signed 8-bit             |
| uint8   | 1    | Unsigned 8-bit           |
| int32   | 4    | Signed 32-bit            |
| uint32  | 4    | Unsigned 32-bit          |
| int64   | 8    | Signed 64-bit            |
| uint64  | 8    | Unsigned 64-bit          |

### Floating Point Types

| Type    | Size | Description              |
|---------|------|--------------------------|
| float32 | 4    | IEEE 754 single          |
| float64 | 8    | IEEE 754 double          |

### GUID

16 bytes, typically displayed as hex string.

---

## 6. Property Types

### 6.1 BoolProperty

```
┌─────────────────────────────────────┐
│ Size: uint32 (always 0)             │
├─────────────────────────────────────┤
│ Index: uint32 (always 0)            │
├─────────────────────────────────────┤
│ Value: uint8 (0=false, 1=true)      │
└─────────────────────────────────────┘
```

**Note:** BoolProperty has NO padding byte after the index. The value byte is where padding would normally be.

### 6.2 IntProperty / UInt32Property

```
┌─────────────────────────────────────┐
│ Size: uint32 (always 0)             │
├─────────────────────────────────────┤
│ Index: uint32 (always 0)            │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Value: int32 / uint32               │
└─────────────────────────────────────┘
```

### 6.3 Int64Property / UInt64Property

```
┌─────────────────────────────────────┐
│ Size: uint32 (always 0)             │
├─────────────────────────────────────┤
│ Index: uint32 (always 0)            │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Value: int64 / uint64               │
└─────────────────────────────────────┘
```

### 6.4 FloatProperty

```
┌─────────────────────────────────────┐
│ Size: uint32 (always 0)             │
├─────────────────────────────────────┤
│ Index: uint32 (always 0)            │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Value: float32                      │
└─────────────────────────────────────┘
```

### 6.5 DoubleProperty

```
┌─────────────────────────────────────┐
│ Size: uint32 (always 0)             │
├─────────────────────────────────────┤
│ Index: uint32 (always 0)            │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Value: float64                      │
└─────────────────────────────────────┘
```

### 6.6 StrProperty / NameProperty / TextProperty

```
┌─────────────────────────────────────┐
│ Size: uint32 (always 0)             │
├─────────────────────────────────────┤
│ Index: uint32 (always 0)            │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Value: FString                      │
└─────────────────────────────────────┘
```

### 6.7 ByteProperty

```
┌─────────────────────────────────────┐
│ Flag: uint32                        │
├─────────────────────────────────────┤
│ Enum Name: FString (or "None")      │
├─────────────────────────────────────┤
│ Size: uint32                        │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Value: uint8 or FString (if enum)   │
└─────────────────────────────────────┘
```

If enum_name is "None", value is uint8. Otherwise, value is FString (enum value name).

### 6.8 ObjectProperty / SoftObjectProperty

```
┌─────────────────────────────────────┐
│ Size: uint32 (always 0)             │
├─────────────────────────────────────┤
│ Index: uint32 (always 0)            │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Object Path: FString                │
└─────────────────────────────────────┘
```

For SoftObjectProperty, there may be an additional sub-path string.

---

## 7. Array Properties

### 7.1 Simple Array (Non-Struct Inner Type)

```
┌─────────────────────────────────────┐
│ Flag: uint32 (typically 1)          │
├─────────────────────────────────────┤
│ Inner Type: FString                 │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Count: uint32                       │
├─────────────────────────────────────┤
│ Elements[Count] (type-dependent)    │
└─────────────────────────────────────┘
```

Element formats by inner type:
- IntProperty: int32
- UInt32Property: uint32
- FloatProperty: float32
- DoubleProperty: float64
- BoolProperty: uint8
- ByteProperty: uint8
- StrProperty/NameProperty: FString
- EnumProperty: FString (enum value name)

### 7.2 Struct Array

When inner type is "StructProperty":

```
┌─────────────────────────────────────┐
│ Flag1: uint32 (typically 1)         │
├─────────────────────────────────────┤
│ Inner Type: FString ("StructProp...│
├─────────────────────────────────────┤
│ Flag2: uint32 (typically 1)         │
├─────────────────────────────────────┤
│ Struct Type Name: FString           │
├─────────────────────────────────────┤
│ Flag3: uint32 (typically 1)         │
├─────────────────────────────────────┤
│ Module Path: FString                │
├─────────────────────────────────────┤
│ Unknown: uint32 (typically 0)       │
├─────────────────────────────────────┤
│ Array Size: uint32 (total bytes)    │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Count: uint32                       │
├─────────────────────────────────────┤
│ Struct Elements[Count]              │
└─────────────────────────────────────┘
```

**Primitive Struct Types** (fixed size, no nested properties):

| Struct Type   | Size (bytes) | Format                                |
|---------------|--------------|---------------------------------------|
| Vector        | 24           | 3 × float64 (x, y, z)                 |
| Vector2D      | 16           | 2 × float64 (x, y)                    |
| Rotator       | 24           | 3 × float64 (pitch, yaw, roll)        |
| Quat          | 32           | 4 × float64 (x, y, z, w)              |
| LinearColor   | 16           | 4 × float32 (r, g, b, a)              |
| Color         | 4            | 4 × uint8 (b, g, r, a) - BGRA order   |
| DateTime      | 8            | uint64 (ticks)                        |
| Timespan      | 8            | int64 (ticks)                         |
| IntPoint      | 8            | 2 × int32 (x, y)                      |
| IntVector     | 12           | 3 × int32 (x, y, z)                   |
| Guid          | 16           | Raw GUID bytes                        |

**Complex Struct Types** (have nested properties):

For structs not in the primitive list (e.g., `Transform`, `SavedUnit`, `SavedBuilding`), each element is parsed as a property list terminated by "None".

### 7.3 Enum Array

When inner type is "EnumProperty":

```
┌─────────────────────────────────────┐
│ Flag1: uint32                       │
├─────────────────────────────────────┤
│ Inner Type: FString ("EnumProp...") │
├─────────────────────────────────────┤
│ Flag2: uint32                       │
├─────────────────────────────────────┤
│ Enum Type Name: FString             │
├─────────────────────────────────────┤
│ Flag3: uint32                       │
├─────────────────────────────────────┤
│ Module Path: FString                │
├─────────────────────────────────────┤
│ Unknown: 4 bytes                    │
├─────────────────────────────────────┤
│ Underlying Type: FString            │
├─────────────────────────────────────┤
│ Unknown: 4 bytes                    │
├─────────────────────────────────────┤
│ Size: uint32                        │
├─────────────────────────────────────┤
│ Padding: 1 byte                     │
├─────────────────────────────────────┤
│ Count: uint32                       │
├─────────────────────────────────────┤
│ Elements: FString[Count]            │
└─────────────────────────────────────┘
```

---

## 8. Map Properties

Maps store key-value pairs. The format varies based on key and value types.

### 8.1 Map with Simple Key Type

```
┌─────────────────────────────────────┐
│ Flag1: uint32                       │
├─────────────────────────────────────┤
│ Key Type: FString                   │
├─────────────────────────────────────┤
│ Flag2: uint32                       │
├─────────────────────────────────────┤
│ Value Type: FString                 │
├─────────────────────────────────────┤
│ Unknown: uint32                     │
├─────────────────────────────────────┤
│ Size: uint32                        │
├─────────────────────────────────────┤
│ Padding: 1 byte                     │
├─────────────────────────────────────┤
│ Removal Count: uint32 (usually 0)   │
├─────────────────────────────────────┤
│ Entry Count: uint32                 │
├─────────────────────────────────────┤
│ Entries[Count]: Key-Value pairs     │
└─────────────────────────────────────┘
```

### 8.2 Map with StructProperty Key

```
┌─────────────────────────────────────┐
│ Flag1: uint32                       │
├─────────────────────────────────────┤
│ Key Type: "StructProperty"          │
├─────────────────────────────────────┤
│ Key Flag: uint32                    │
├─────────────────────────────────────┤
│ Key Struct Type: FString            │
├─────────────────────────────────────┤
│ Key Module Flag: uint32             │
├─────────────────────────────────────┤
│ Key Module Path: FString            │
├─────────────────────────────────────┤
│ Unknown: 4 bytes                    │ ← Skip 4 bytes
├─────────────────────────────────────┤
│ Value Type: FString                 │
├─────────────────────────────────────┤
│ (If value is StructProperty...)    │
│ Value Flag: uint32                  │
│ Value Struct Type: FString          │
│ Value Module Flag: uint32           │
│ Value Module Path: FString          │
│ Unknown: 4 bytes                    │ ← Skip 4 bytes (no extra unknown)
├─────────────────────────────────────┤
│ Size: uint32                        │
├─────────────────────────────────────┤
│ Padding: 1 byte                     │
├─────────────────────────────────────┤
│ Removal Count: uint32               │
├─────────────────────────────────────┤
│ Entry Count: uint32                 │
├─────────────────────────────────────┤
│ Entries[Count]                      │
└─────────────────────────────────────┘
```

**IMPORTANT:** When both key AND value are StructProperty, skip only 4 bytes before size (no extra unknown field).

### 8.3 Map with EnumProperty Key

```
┌─────────────────────────────────────┐
│ Flag1: uint32                       │
├─────────────────────────────────────┤
│ Key Type: "EnumProperty"            │
├─────────────────────────────────────┤
│ Flag2: uint32                       │
├─────────────────────────────────────┤
│ Enum Type Name: FString             │
├─────────────────────────────────────┤
│ Enum Module Flag: uint32            │
├─────────────────────────────────────┤
│ Enum Module Path: FString           │
├─────────────────────────────────────┤
│ Unknown: 4 bytes                    │
├─────────────────────────────────────┤
│ Enum Inner Type: FString            │ ← e.g., "ByteProperty"
├─────────────────────────────────────┤
│ Unknown: 4 bytes                    │
├─────────────────────────────────────┤
│ Value Type: FString                 │ ← e.g., "StructProperty"
├─────────────────────────────────────┤
│ (If value is StructProperty...)    │
│ Value metadata as above...          │
├─────────────────────────────────────┤
│ Size, Padding, Counts, Entries...   │
└─────────────────────────────────────┘
```

**CRITICAL:** The order is: enum_inner_type THEN value_type (not value_type then inner_type).

### 8.4 Map Entry Parsing

For each entry:

**Key parsing by key type:**
- StructProperty: Parse as property list (terminated by "None")
- EnumProperty: Read FString (enum value name like "ESlot::Body")
- IntProperty: Read int32
- StrProperty: Read FString

**Value parsing by value type:**
- StructProperty (primitive): Read fixed bytes based on struct type
- StructProperty (complex): Parse as property list
- Other types: Parse according to their format

---

## 9. Struct Properties

### 9.1 Standalone StructProperty

```
┌─────────────────────────────────────┐
│ Flag1: uint32 (typically 1)         │
├─────────────────────────────────────┤
│ Struct Type Name: FString           │
├─────────────────────────────────────┤
│ Flag2: uint32 (typically 1)         │
├─────────────────────────────────────┤
│ Module Path: FString                │
├─────────────────────────────────────┤
│ Unknown: uint32 (typically 0)       │
├─────────────────────────────────────┤
│ Value Size: uint32                  │
├─────────────────────────────────────┤
│ Padding: 1 byte (0x00)              │
├─────────────────────────────────────┤
│ Struct Data (format varies)         │
└─────────────────────────────────────┘
```

### 9.2 Primitive Struct Data

For primitive struct types, read raw bytes:

```python
if struct_type == "Vector":
    return {"x": read_f64(), "y": read_f64(), "z": read_f64()}
elif struct_type == "Quat":
    return {"x": read_f64(), "y": read_f64(), "z": read_f64(), "w": read_f64()}
elif struct_type == "Color":
    return {"b": read_u8(), "g": read_u8(), "r": read_u8(), "a": read_u8()}
# ... etc
```

### 9.3 Complex Struct Data (e.g., Transform)

Complex structs contain nested properties:

```
┌─────────────────────────────────────┐
│ Property 1: name, type, value       │
├─────────────────────────────────────┤
│ Property 2: name, type, value       │
├─────────────────────────────────────┤
│ ...                                 │
├─────────────────────────────────────┤
│ "None" string (terminator)          │
└─────────────────────────────────────┘
```

**Example: Transform struct typically contains:**
- Rotation (StructProperty → Quat)
- Translation (StructProperty → Vector)
- Scale3D (StructProperty → Vector)

---

## 10. Enum Properties

### Standalone EnumProperty

```
┌─────────────────────────────────────┐
│ Flag1: uint32                       │
├─────────────────────────────────────┤
│ Enum Type Name: FString             │
├─────────────────────────────────────┤
│ Flag2: uint32                       │
├─────────────────────────────────────┤
│ Module Path: FString                │
├─────────────────────────────────────┤
│ Unknown: 4 bytes                    │
├─────────────────────────────────────┤
│ Inner Type: FString                 │ ← e.g., "ByteProperty"
├─────────────────────────────────────┤
│ Unknown: 4 bytes                    │
├─────────────────────────────────────┤
│ Size: uint32                        │
├─────────────────────────────────────┤
│ Padding: 1 byte                     │
├─────────────────────────────────────┤
│ Value: FString                      │ ← e.g., "ENodeType::Iron"
└─────────────────────────────────────┘
```

---

## 11. Complete Property Reference

### Property Type Summary Table

| Property Type       | Has Padding | Value Format                          |
|---------------------|-------------|---------------------------------------|
| BoolProperty        | NO          | uint8 after 8-byte skip               |
| IntProperty         | YES (1)     | int32                                 |
| UInt32Property      | YES (1)     | uint32                                |
| Int64Property       | YES (1)     | int64                                 |
| UInt64Property      | YES (1)     | uint64                                |
| FloatProperty       | YES (1)     | float32                               |
| DoubleProperty      | YES (1)     | float64                               |
| StrProperty         | YES (1)     | FString                               |
| NameProperty        | YES (1)     | FString                               |
| TextProperty        | YES (1)     | FString                               |
| ByteProperty        | YES (1)     | uint8 or FString (enum)               |
| ObjectProperty      | YES (1)     | FString (path)                        |
| SoftObjectProperty  | YES (1)     | FString + optional sub-path           |
| EnumProperty        | YES (1)     | Complex metadata + FString value      |
| StructProperty      | YES (1)     | Complex metadata + struct data        |
| ArrayProperty       | YES (1)     | Complex metadata + elements           |
| MapProperty         | YES (1)     | Complex metadata + entries            |
| SetProperty         | YES (1)     | Similar to ArrayProperty              |

---

## 12. Implementation Notes

### 12.1 Common Pitfalls

1. **BoolProperty has no padding byte** - The value byte occupies where padding would be

2. **MapProperty<EnumProperty, *> field order** - The enum's inner type comes BEFORE the value type:
   ```
   WRONG: [enum_meta] [value_type] [skip4] [inner_type]
   RIGHT: [enum_meta] [skip4] [inner_type] [skip4] [value_type]
   ```

3. **MapProperty<StructProperty, StructProperty>** - When both key and value are structs, there's no extra unknown field between value metadata and size

4. **Large arrays** - Some arrays (like fertilityGridQuantized) have millions of elements. Implement size limits or skip functionality

5. **String encoding** - Negative length means UTF-16LE, positive means UTF-8

6. **Recursion depth** - Complex saves can have deeply nested structures. Implement depth limits

### 12.2 Parsing Algorithm (Pseudocode)

```python
def parse_save(filename):
    data = decompress_oodle(read_file(filename))

    header = parse_header(data)
    properties = {}

    while True:
        name = read_string()
        if name == "" or name == "None":
            break

        prop_type = read_string()
        value = parse_property_value(prop_type)
        properties[name] = value

    return {"header": header, "properties": properties}

def parse_property_value(prop_type):
    if prop_type == "BoolProperty":
        skip(8)  # size + index
        return read_u8() != 0

    elif prop_type == "IntProperty":
        skip(8)  # size + index
        skip(1)  # padding
        return read_i32()

    elif prop_type == "StructProperty":
        return parse_struct_property()

    elif prop_type == "ArrayProperty":
        return parse_array_property()

    elif prop_type == "MapProperty":
        return parse_map_property()

    # ... etc
```

### 12.3 Known Struct Types in Manor Lords

| Struct Type              | Category  | Notes                                |
|--------------------------|-----------|--------------------------------------|
| SavedRegion              | Complex   | Region data with nested properties   |
| SavedLord                | Complex   | Lord/player data                     |
| SavedBuilding            | Complex   | Building with inventory, workers     |
| SavedUnit                | Complex   | Villager/soldier with 69 properties  |
| SavedResourceNode        | Complex   | Resource node with resources         |
| SavedResource            | Complex   | Individual resource item             |
| SavedSquad               | Complex   | Military squad                       |
| SavedGood                | Complex   | Trade/inventory item                 |
| SavedWorkerFamily        | Complex   | Family unit                          |
| ProductionTimeEntry      | Complex   | Production scheduling                |
| Vein                     | Complex   | Water/resource vein                  |
| Transform                | Complex   | Position/rotation/scale              |
| Vector                   | Primitive | 3D position (24 bytes)               |
| Quat                     | Primitive | Quaternion rotation (32 bytes)       |
| Color                    | Primitive | BGRA color (4 bytes)                 |
| DateTime                 | Primitive | Timestamp (8 bytes)                  |

### 12.4 Known Enum Types

| Enum Type            | Example Values                                        |
|----------------------|-------------------------------------------------------|
| ESettlementType      | ESettlementType::None, ESettlementType::Village       |
| ENodeType            | ENodeType::Iron, ENodeType::Stone, ENodeType::Fish    |
| EEquipmentSlot       | EEquipmentSlot::Body, EEquipmentSlot::Weapon          |
| EGoodType            | Various resource/good types                           |

### 12.5 File Validation

After parsing, verify:
- Header magic is "GVAS"
- Engine version matches expected (5.5.x)
- Save class is "/Script/ManorLords.MLSaveGame"
- Total bytes parsed ≈ file size (allow small delta for trailing bytes)

---

## Appendix A: Example Hex Patterns

### BoolProperty (false)
```
09 00 00 00        # name length: 9
62 52 69 63 68 4E 6F 64 65 00  # "bRichNode\0"
0D 00 00 00        # type length: 13
42 6F 6F 6C 50 72 6F 70 65 72 74 79 00  # "BoolProperty\0"
00 00 00 00        # size: 0
00 00 00 00        # index: 0
00                 # value: false (NO PADDING)
```

### IntProperty
```
04 00 00 00        # name length: 4
64 61 79 00        # "day\0"
0C 00 00 00        # type length: 12
49 6E 74 50 72 6F 70 65 72 74 79 00  # "IntProperty\0"
00 00 00 00        # size: 0
04 00 00 00        # size of value (4)
00                 # padding
3D 00 00 00        # value: 61
```

### Vector (primitive struct)
```
18 00 00 00        # 24 bytes
XX XX XX XX XX XX XX XX  # x (float64)
XX XX XX XX XX XX XX XX  # y (float64)
XX XX XX XX XX XX XX XX  # z (float64)
```

---

## Appendix B: Reference Implementation

A complete Python reference implementation is available at:
`ml-sav-parser.py`

Key functions:
- `parse_header()` - GVAS header parsing
- `parse_property()` - Main property dispatcher
- `parse_struct_property()` - Struct handling
- `parse_array_property()` - Array handling
- `parse_map_property()` - Map handling

---

*End of Specification*
