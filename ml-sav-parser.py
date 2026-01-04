#!/usr/bin/env python3
"""
Manor Lords Save File Parser

A complete parser for Manor Lords save files (.sav) that have been decompressed
from their Oodle-compressed format. Outputs structured data as JSON and/or Markdown.

This parser handles the Unreal Engine 5.5 GVAS (Generic Variable Save) format used
by Manor Lords, including all property types: structs, arrays, maps, enums, and
primitive types.

Usage:
    python ml-sav-parser.py <input_file> [options]

Examples:
    # Parse and output both JSON and Markdown (default)
    python ml-sav-parser.py save_decompressed.bin

    # Output only JSON
    python ml-sav-parser.py save_decompressed.bin --json-only

    # Specify custom output paths
    python ml-sav-parser.py save.bin -o output.json -m output.md

    # Quiet mode (minimal output)
    python ml-sav-parser.py save.bin --quiet

Note:
    This parser expects DECOMPRESSED save data. Manor Lords .sav files are
    Oodle-compressed and must be decompressed first. See the format specification
    document for decompression details.

Author: agentical
License: MIT
Repository: https://github.com/agentical-info/manor-lords-save-tools
"""

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


# =============================================================================
# PARSER CLASS
# =============================================================================

class ManorLordsSaveParser:
    """
    Parser for decompressed Manor Lords save files (UE5.5 GVAS format).

    This class handles the binary parsing of Unreal Engine 5.5 serialized
    save game data, including the GVAS header and all property types.

    Attributes:
        data (bytes): The raw binary data to parse.
        pos (int): Current read position in the data.
        errors (list): List of non-fatal errors encountered during parsing.
        depth (int): Current recursion depth for nested structures.
        max_depth (int): Maximum allowed recursion depth.
        quiet (bool): If True, suppress progress output.

    Example:
        >>> data = Path('save_decompressed.bin').read_bytes()
        >>> parser = ManorLordsSaveParser(data)
        >>> result = parser.parse()
        >>> print(f"Parsed {result['stats']['percent']:.1f}% of file")
    """

    # Primitive struct types and their fixed byte sizes
    # These structs contain raw data without nested properties
    PRIMITIVE_STRUCTS = {
        'Vector': 24,       # 3 x float64 (x, y, z)
        'Vector2D': 16,     # 2 x float64 (x, y)
        'Rotator': 24,      # 3 x float64 (pitch, yaw, roll)
        'Quat': 32,         # 4 x float64 (x, y, z, w)
        'LinearColor': 16,  # 4 x float32 (r, g, b, a)
        'Color': 4,         # 4 x uint8 (b, g, r, a) - BGRA order
        'DateTime': 8,      # 1 x uint64 (ticks)
        'Timespan': 8,      # 1 x int64 (ticks)
        'IntPoint': 8,      # 2 x int32 (x, y)
        'IntVector': 12,    # 3 x int32 (x, y, z)
        'Guid': 16,         # 16 bytes raw GUID
    }

    def __init__(self, data: bytes, quiet: bool = False):
        """
        Initialize the parser with binary data.

        Args:
            data: The decompressed save file contents as bytes.
            quiet: If True, suppress progress messages during parsing.
        """
        self.data = data
        self.pos = 0
        self.errors: List[str] = []
        self.depth = 0
        self.max_depth = 50
        self.quiet = quiet

    # =========================================================================
    # PRIMITIVE READ OPERATIONS
    # =========================================================================

    def read(self, n: int) -> bytes:
        """
        Read n bytes from the current position.

        Args:
            n: Number of bytes to read.

        Returns:
            The bytes read.

        Raises:
            EOFError: If there aren't enough bytes remaining.
        """
        if self.pos + n > len(self.data):
            raise EOFError(f"EOF at 0x{self.pos:X}, need {n} bytes")
        result = self.data[self.pos:self.pos + n]
        self.pos += n
        return result

    def peek(self, n: int = 4) -> bytes:
        """Peek at the next n bytes without advancing position."""
        return self.data[self.pos:self.pos + n]

    def skip(self, n: int) -> None:
        """Skip n bytes (advance position without reading)."""
        self.pos += n

    def remaining(self) -> int:
        """Return number of bytes remaining to be read."""
        return len(self.data) - self.pos

    # Integer types (little-endian)
    def u8(self) -> int:
        """Read unsigned 8-bit integer."""
        return struct.unpack('<B', self.read(1))[0]

    def i32(self) -> int:
        """Read signed 32-bit integer."""
        return struct.unpack('<i', self.read(4))[0]

    def u32(self) -> int:
        """Read unsigned 32-bit integer."""
        return struct.unpack('<I', self.read(4))[0]

    def i64(self) -> int:
        """Read signed 64-bit integer."""
        return struct.unpack('<q', self.read(8))[0]

    def u64(self) -> int:
        """Read unsigned 64-bit integer."""
        return struct.unpack('<Q', self.read(8))[0]

    # Floating point types (little-endian)
    def f32(self) -> float:
        """Read 32-bit float (IEEE 754 single precision)."""
        return struct.unpack('<f', self.read(4))[0]

    def f64(self) -> float:
        """Read 64-bit float (IEEE 754 double precision)."""
        return struct.unpack('<d', self.read(8))[0]

    def guid(self) -> str:
        """Read 16-byte GUID and return as hex string."""
        return self.read(16).hex()

    def string(self) -> str:
        """
        Read a length-prefixed string (FString format).

        Format:
            - Length (int32): If positive, UTF-8. If negative, UTF-16LE.
            - String data: Includes null terminator.

        Returns:
            The decoded string (without null terminator).
        """
        length = self.i32()
        if length == 0:
            return ""
        if length < 0:
            # UTF-16LE encoding (negative length indicates wide chars)
            length = -length
            return self.read(length * 2).decode('utf-16-le', errors='replace').rstrip('\x00')
        # UTF-8 encoding
        return self.read(length).decode('utf-8', errors='replace').rstrip('\x00')

    # =========================================================================
    # GVAS HEADER PARSING
    # =========================================================================

    def parse_header(self) -> Dict[str, Any]:
        """
        Parse the GVAS file header.

        The header contains engine version info, custom format versions,
        and the save game class type.

        Returns:
            Dictionary containing header fields.

        Raises:
            ValueError: If the file doesn't start with 'GVAS' magic.
        """
        magic = self.read(4).decode('ascii')
        if magic != 'GVAS':
            raise ValueError(f"Invalid magic: {magic} (expected 'GVAS')")

        header = {
            'magic': magic,
            'save_version': self.u32(),
            'package_version_ue4': self.u32(),
            'package_version_ue5': self.u32(),
        }

        # Engine version (3 x uint16 + build number)
        header['engine_major'] = struct.unpack('<H', self.read(2))[0]
        header['engine_minor'] = struct.unpack('<H', self.read(2))[0]
        header['engine_patch'] = struct.unpack('<H', self.read(2))[0]
        header['engine_build'] = self.u32()
        header['engine_string'] = self.string()

        # Custom format versions
        custom_format = self.u32()
        custom_count = self.u32()

        header['custom_versions'] = []
        for _ in range(custom_count):
            header['custom_versions'].append({
                'guid': self.guid(),
                'version': self.u32()
            })

        header['save_class'] = self.string()

        # UE5.5: Skip extra null byte after save class if present
        if self.remaining() > 0 and self.peek(1) == b'\x00':
            self.skip(1)

        return header

    # =========================================================================
    # PROPERTY PARSING - MAIN ENTRY POINTS
    # =========================================================================

    def parse_properties(self, debug: bool = False) -> Dict[str, Any]:
        """
        Parse a sequence of properties until 'None' terminator.

        Args:
            debug: If True, print each top-level property name.

        Returns:
            Dictionary mapping property names to their values.
        """
        props = {}
        count = 0
        max_pos = len(self.data) - 4

        while self.remaining() > 4 and self.pos < max_pos:
            start_pos = self.pos
            prop = self.parse_property()
            if prop is None:
                if debug and self.depth == 0 and not self.quiet:
                    print(f"Top-level parse ended at 0x{start_pos:X} after {count} properties")
                break
            if debug and self.depth == 0 and not self.quiet:
                print(f"[{count}] 0x{start_pos:X}: {prop[0]}")
            props[prop[0]] = prop[1]
            count += 1

        return props

    def parse_property(self) -> Optional[Tuple[str, Any]]:
        """
        Parse a single property (name, type, and value).

        Returns:
            Tuple of (property_name, property_value), or None if 'None' terminator
            or end of data is reached.
        """
        if self.depth > self.max_depth:
            return None

        self.depth += 1
        start_pos = self.pos

        try:
            if self.remaining() < 8:
                self.depth -= 1
                return None

            name = self.string()
            if not name or name == "None":
                self.depth -= 1
                return None

            prop_type = self.string()
            if not prop_type:
                self.depth -= 1
                return None

            value = self.parse_value(prop_type, name)

            self.depth -= 1
            return (name, value)

        except Exception as e:
            self.errors.append(f"Error at 0x{start_pos:X}: {e}")
            self.depth -= 1
            return None

    # =========================================================================
    # PROPERTY VALUE PARSING BY TYPE
    # =========================================================================

    def parse_value(self, prop_type: str, name: str = "") -> Any:
        """
        Parse a property value based on its type.

        Args:
            prop_type: The UE property type name (e.g., 'IntProperty', 'StructProperty').
            name: The property name (used for debugging).

        Returns:
            The parsed value (type depends on prop_type).
        """
        # ---------------------------------------------------------------------
        # Boolean - Note: NO padding byte (value is where padding would be)
        # ---------------------------------------------------------------------
        if prop_type == "BoolProperty":
            self.skip(8)  # size(0) + index(0)
            return bool(self.u8())

        # ---------------------------------------------------------------------
        # Integer types
        # ---------------------------------------------------------------------
        elif prop_type == "IntProperty":
            self.skip(8)  # size + index
            self.skip(1)  # padding
            return self.i32()

        elif prop_type == "UInt32Property":
            self.skip(8)
            self.skip(1)
            return self.u32()

        elif prop_type == "Int64Property":
            self.skip(8)
            self.skip(1)
            return self.i64()

        elif prop_type == "UInt64Property":
            self.skip(8)
            self.skip(1)
            return self.u64()

        # ---------------------------------------------------------------------
        # Floating point types
        # ---------------------------------------------------------------------
        elif prop_type == "FloatProperty":
            self.skip(8)
            self.skip(1)
            return self.f32()

        elif prop_type == "DoubleProperty":
            self.skip(8)
            self.skip(1)
            return self.f64()

        # ---------------------------------------------------------------------
        # String types
        # ---------------------------------------------------------------------
        elif prop_type == "StrProperty":
            self.skip(8)
            self.skip(1)
            return self.string()

        elif prop_type == "NameProperty":
            self.skip(8)
            self.skip(1)
            return self.string()

        elif prop_type == "TextProperty":
            self.skip(8)
            self.skip(1)
            flags = self.u32()
            history_type = self.u8()
            if history_type == 255:
                has_culture = self.u32()
                return self.string()
            return f"<Text:{history_type}>"

        # ---------------------------------------------------------------------
        # Byte property (can be raw byte or enum)
        # ---------------------------------------------------------------------
        elif prop_type == "ByteProperty":
            size = self.u32()
            index = self.u32()
            if size == 0:
                self.skip(1)  # padding
                return self.u8()
            else:
                enum_name = self.string()
                self.skip(1)  # padding
                if enum_name == "None":
                    return self.u8()
                return {"enum": enum_name, "value": self.string()}

        # ---------------------------------------------------------------------
        # Enum property
        # ---------------------------------------------------------------------
        elif prop_type == "EnumProperty":
            flag1 = self.u32()
            enum_type = self.string()
            flag2 = self.u32()
            module = self.string()
            self.skip(4)  # unknown
            inner_type = self.string()  # Usually "ByteProperty"
            self.skip(4)  # unknown
            size = self.u32()
            self.skip(1)  # padding
            return {"type": enum_type, "value": self.string()}

        # ---------------------------------------------------------------------
        # Object references
        # ---------------------------------------------------------------------
        elif prop_type == "ObjectProperty":
            self.skip(8)
            self.skip(1)
            return self.string()

        elif prop_type == "SoftObjectProperty":
            self.skip(8)
            self.skip(1)
            return {"path": self.string(), "sub_path": self.string()}

        # ---------------------------------------------------------------------
        # Complex types (delegate to specialized methods)
        # ---------------------------------------------------------------------
        elif prop_type == "StructProperty":
            return self.parse_struct_property()

        elif prop_type == "ArrayProperty":
            return self.parse_array_property()

        elif prop_type == "MapProperty":
            return self.parse_map_property()

        elif prop_type == "SetProperty":
            return self.parse_set_property()

        # ---------------------------------------------------------------------
        # Unknown type
        # ---------------------------------------------------------------------
        else:
            self.errors.append(f"Unknown type '{prop_type}' at 0x{self.pos:X}")
            return f"<{prop_type}>"

    # =========================================================================
    # STRUCT PROPERTY PARSING
    # =========================================================================

    def parse_struct_property(self) -> Dict[str, Any]:
        """
        Parse a StructProperty.

        Format: [flag][struct_type][flag][module][unknown][size][padding][value]

        Returns:
            Dictionary containing struct data.
        """
        flag1 = self.u32()
        struct_type = self.string()
        flag2 = self.u32()
        module_path = self.string()
        unknown = self.u32()
        value_size = self.u32()
        self.skip(1)  # padding

        return self.parse_struct_value(struct_type, value_size)

    def parse_struct_value(self, struct_type: str, size: int) -> Any:
        """
        Parse struct content based on its type.

        Args:
            struct_type: The struct type name (e.g., 'Vector', 'Transform').
            size: Declared size of the struct data in bytes.

        Returns:
            Parsed struct data (format depends on struct_type).
        """
        # Primitive struct types - fixed binary format
        if struct_type == "DateTime":
            return {"_type": "DateTime", "ticks": self.u64()}

        elif struct_type == "Timespan":
            return {"_type": "Timespan", "ticks": self.i64()}

        elif struct_type == "Guid":
            return {"_type": "Guid", "value": self.guid()}

        elif struct_type == "Vector":
            return {"_type": "Vector", "x": self.f64(), "y": self.f64(), "z": self.f64()}

        elif struct_type == "Vector2D":
            return {"_type": "Vector2D", "x": self.f64(), "y": self.f64()}

        elif struct_type == "Rotator":
            return {"_type": "Rotator", "pitch": self.f64(), "yaw": self.f64(), "roll": self.f64()}

        elif struct_type == "Quat":
            return {"_type": "Quat", "x": self.f64(), "y": self.f64(), "z": self.f64(), "w": self.f64()}

        elif struct_type == "LinearColor":
            return {"_type": "LinearColor", "r": self.f32(), "g": self.f32(), "b": self.f32(), "a": self.f32()}

        elif struct_type == "Color":
            return {"_type": "Color", "b": self.u8(), "g": self.u8(), "r": self.u8(), "a": self.u8()}

        elif struct_type == "IntPoint":
            return {"_type": "IntPoint", "x": self.i32(), "y": self.i32()}

        elif struct_type == "IntVector":
            return {"_type": "IntVector", "x": self.i32(), "y": self.i32(), "z": self.i32()}

        elif struct_type == "Box":
            return {
                "_type": "Box",
                "min": {"x": self.f64(), "y": self.f64(), "z": self.f64()},
                "max": {"x": self.f64(), "y": self.f64(), "z": self.f64()},
                "valid": self.u8()
            }

        # Complex struct - parse as nested properties
        else:
            result = {"_type": struct_type}
            start_pos = self.pos
            while self.pos <= start_pos + size:
                prop = self.parse_property()
                if prop is None:
                    break
                result[prop[0]] = prop[1]
            return result

    # =========================================================================
    # ARRAY PROPERTY PARSING
    # =========================================================================

    def parse_array_property(self) -> List[Any]:
        """
        Parse an ArrayProperty.

        Format varies based on inner type:
        - StructProperty: Has additional metadata for struct type.
        - EnumProperty: Has enum type metadata.
        - Simple types: Just count and raw values.

        Returns:
            List of parsed array elements.
        """
        flag1 = self.u32()
        inner_type = self.string()

        if inner_type == "StructProperty":
            return self.parse_struct_array()

        elif inner_type == "EnumProperty":
            # Enum array: [flag][enum_type][flag][module][unknown][inner_type][unknown][size][padding][count][values]
            self.skip(4)  # flag2
            enum_type = self.string()
            self.skip(4)  # flag3
            module = self.string()
            self.skip(4)  # unknown
            inner2 = self.string()  # ByteProperty
            self.skip(4)  # unknown
            size = self.u32()
            self.skip(1)  # padding
            count = self.u32()

            return [self.string() for _ in range(count)]

        else:
            # Simple array: [unknown][size][padding][count][values]
            self.skip(4)  # unknown
            self.skip(4)  # size
            self.skip(1)  # padding
            count = self.u32()

            return [self.parse_array_element(inner_type) for _ in range(count)]

    def parse_struct_array(self) -> List[Dict[str, Any]]:
        """
        Parse an array of structs.

        Returns:
            List of struct dictionaries.
        """
        flag2 = self.u32()
        struct_type = self.string()
        flag3 = self.u32()
        module_path = self.string()
        unknown = self.u32()
        array_size = self.u32()
        self.skip(1)  # padding
        count = self.u32()

        array_start = self.pos
        array_end = array_start + array_size - 4 - 1  # size includes count(4) and padding(1)

        if count > 0 and not self.quiet:
            print(f"  Struct array: {struct_type} x{count}, size={array_size}, "
                  f"range 0x{array_start:X}-0x{array_end:X}")

        items = []

        if struct_type in self.PRIMITIVE_STRUCTS:
            # Primitive struct - parse as raw fixed-size data
            for _ in range(count):
                items.append(self.parse_struct_value(struct_type, self.PRIMITIVE_STRUCTS[struct_type]))
        else:
            # Complex struct - parse as nested properties
            for i in range(count):
                item = {"_struct_type": struct_type}
                while True:
                    prop = self.parse_property()
                    if prop is None:
                        break
                    item[prop[0]] = prop[1]
                items.append(item)

        return items

    def parse_array_element(self, inner_type: str) -> Any:
        """
        Parse a single array element based on its type.

        Args:
            inner_type: The UE type name for array elements.

        Returns:
            The parsed element value.
        """
        if inner_type == "IntProperty":
            return self.i32()
        elif inner_type == "UInt32Property":
            return self.u32()
        elif inner_type == "Int64Property":
            return self.i64()
        elif inner_type == "UInt64Property":
            return self.u64()
        elif inner_type == "FloatProperty":
            return self.f32()
        elif inner_type == "DoubleProperty":
            return self.f64()
        elif inner_type == "BoolProperty":
            return bool(self.u8())
        elif inner_type == "ByteProperty":
            return self.u8()
        elif inner_type in ("StrProperty", "NameProperty"):
            return self.string()
        elif inner_type == "EnumProperty":
            return self.string()
        elif inner_type == "ObjectProperty":
            return self.string()
        else:
            return f"<{inner_type}>"

    # =========================================================================
    # MAP PROPERTY PARSING
    # =========================================================================

    def parse_map_property(self) -> Dict[str, Any]:
        """
        Parse a MapProperty (key-value dictionary).

        Format varies based on key and value types. Special handling for:
        - StructProperty keys/values
        - EnumProperty keys

        Returns:
            Dictionary of parsed key-value pairs.
        """
        flag1 = self.u32()
        key_type = self.string()

        key_struct_type = None
        key_enum_type = None

        # Parse key type metadata
        if key_type == "StructProperty":
            key_flag = self.u32()
            key_struct_type = self.string()
            key_mod_flag = self.u32()
            key_module = self.string()
            self.skip(4)  # unknown padding
            value_type = self.string()

        elif key_type == "EnumProperty":
            # IMPORTANT: enum_inner_type comes BEFORE value_type
            flag2 = self.u32()
            key_enum_type = self.string()
            key_mod_flag = self.u32()
            key_module = self.string()
            self.skip(4)  # unknown
            enum_inner_type = self.string()  # e.g., "ByteProperty"
            self.skip(4)  # unknown
            value_type = self.string()

        else:
            # Simple key type
            flag2 = self.u32()
            value_type = self.string()

        # Parse value type metadata if struct
        value_struct_type = None
        if value_type == "StructProperty":
            val_flag = self.u32()
            value_struct_type = self.string()
            val_mod_flag = self.u32()
            val_module = self.string()

            # When both key and value are StructProperty, different padding
            if key_type == "StructProperty":
                self.skip(4)
                size = self.u32()
            else:
                unknown = self.u32()
                size = self.u32()
        else:
            unknown = self.u32()
            size = self.u32()

        self.skip(1)  # padding
        removal = self.u32()  # number of removed entries (usually 0)
        count = self.u32()

        result = {}
        for _ in range(count):
            # Parse key
            if key_type == "StructProperty":
                key = {"_struct_type": key_struct_type}
                while True:
                    prop = self.parse_property()
                    if prop is None:
                        break
                    key[prop[0]] = prop[1]
            elif key_type == "EnumProperty":
                key = self.string()
            else:
                key = self.parse_array_element(key_type)

            # Parse value
            if value_type == "StructProperty":
                if value_struct_type in self.PRIMITIVE_STRUCTS:
                    val = self.parse_struct_value(value_struct_type, 0)
                else:
                    val = {"_struct_type": value_struct_type}
                    while True:
                        prop = self.parse_property()
                        if prop is None:
                            break
                        val[prop[0]] = prop[1]
            else:
                val = self.parse_array_element(value_type)

            result[str(key)] = val

        return result

    # =========================================================================
    # SET PROPERTY PARSING
    # =========================================================================

    def parse_set_property(self) -> List[Any]:
        """
        Parse a SetProperty (unique values collection).

        Format: [flag][inner_type][unknown][size][padding][removal][count][items]

        Returns:
            List of unique values.
        """
        flag1 = self.u32()
        inner_type = self.string()
        unknown = self.u32()
        size = self.u32()
        self.skip(1)  # padding
        removal = self.u32()
        count = self.u32()

        return [self.parse_array_element(inner_type) for _ in range(count)]

    # =========================================================================
    # MAIN PARSE METHOD
    # =========================================================================

    def parse(self) -> Dict[str, Any]:
        """
        Parse the entire save file.

        Returns:
            Dictionary containing:
            - header: GVAS header data
            - properties: All parsed properties
            - errors: List of non-fatal errors
            - stats: Parsing statistics (file_size, parsed, percent, etc.)
        """
        result = {}

        try:
            result['header'] = self.parse_header()
            if not self.quiet:
                print(f"Header parsed, pos = 0x{self.pos:X}")
                print(f"Starting property parsing...")
            result['properties'] = self.parse_properties(debug=True)
            if not self.quiet:
                print(f"Property parsing complete at 0x{self.pos:X}")
        except Exception as e:
            self.errors.append(f"Fatal: {e}")
            import traceback
            traceback.print_exc()
        except KeyboardInterrupt:
            if not self.quiet:
                print(f"\nInterrupted at pos 0x{self.pos:X}")
            result['properties'] = {}

        result['errors'] = self.errors
        result['stats'] = {
            'file_size': len(self.data),
            'parsed': self.pos,
            'remaining': self.remaining(),
            'percent': 100.0 * self.pos / len(self.data) if len(self.data) > 0 else 0
        }

        return result


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def count_items(obj: Any, depth: int = 0) -> int:
    """Recursively count all data items in the parsed result."""
    if depth > 20:
        return 1
    if isinstance(obj, dict):
        return sum(count_items(v, depth + 1) for v in obj.values())
    elif isinstance(obj, list):
        return sum(count_items(v, depth + 1) for v in obj)
    return 1


def to_markdown(result: Dict[str, Any], output_path: Path) -> None:
    """
    Convert parsed result to Markdown format.

    Args:
        result: The parsed save data from ManorLordsSaveParser.parse().
        output_path: Path to write the Markdown file.
    """
    lines = ["# Manor Lords Save - Complete Parse\n"]

    # Header section
    if 'header' in result:
        h = result['header']
        lines.append("## Header\n")
        lines.append(f"- **Magic:** {h.get('magic')}")
        lines.append(f"- **Engine:** {h.get('engine_major')}.{h.get('engine_minor')}.{h.get('engine_patch')}")
        lines.append(f"- **Engine String:** {h.get('engine_string')}")
        lines.append(f"- **Save Class:** {h.get('save_class')}")
        lines.append(f"- **Custom Versions:** {len(h.get('custom_versions', []))}")
        lines.append("")

    # Statistics section
    if 'stats' in result:
        s = result['stats']
        lines.append("## Parse Statistics\n")
        lines.append(f"- **File Size:** {s['file_size']:,} bytes")
        lines.append(f"- **Parsed:** {s['parsed']:,} bytes ({s['percent']:.1f}%)")
        lines.append(f"- **Remaining:** {s['remaining']:,} bytes")
        lines.append(f"- **Errors:** {len(result.get('errors', []))}")

        if 'properties' in result:
            item_count = count_items(result['properties'])
            lines.append(f"- **Data Items:** {item_count:,}")
        lines.append("")

    # Properties section
    if 'properties' in result:
        lines.append("## Properties\n")
        _write_props_md(lines, result['properties'], 0)

    # Errors section
    if result.get('errors'):
        lines.append("\n## Errors\n")
        for e in result['errors']:
            lines.append(f"- {e}")

    output_path.write_text("\n".join(lines), encoding='utf-8')


def _write_props_md(lines: List[str], props: Dict[str, Any], depth: int, max_depth: int = 20) -> None:
    """Recursively write properties as Markdown (internal helper)."""
    if depth > max_depth:
        lines.append("  " * depth + "*[max depth reached]*")
        return

    indent = "  " * depth

    for name, value in props.items():
        if name.startswith('_'):
            continue

        if isinstance(value, dict):
            struct_type = value.get('_type', '')
            if struct_type:
                simple = {k: v for k, v in value.items()
                          if not isinstance(v, (dict, list)) and not k.startswith('_')}
                if simple:
                    formatted = ", ".join(f"{k}={v}" for k, v in simple.items())
                    lines.append(f"{indent}- **{name}** ({struct_type}): {formatted}")
                else:
                    lines.append(f"{indent}- **{name}** ({struct_type}):")
                    _write_props_md(lines, value, depth + 1, max_depth)
            else:
                lines.append(f"{indent}- **{name}**:")
                _write_props_md(lines, value, depth + 1, max_depth)

        elif isinstance(value, list):
            lines.append(f"{indent}- **{name}** [{len(value)} items]:")
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    elem_type = item.get('_array_elem', item.get('_type', ''))
                    lines.append(f"{indent}  - [{i}] ({elem_type}):")
                    _write_props_md(lines, item, depth + 2, max_depth)
                else:
                    lines.append(f"{indent}  - [{i}]: {item}")

        else:
            lines.append(f"{indent}- **{name}**: {value}")


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Parse Manor Lords save files (decompressed GVAS format)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s save_decompressed.bin
  %(prog)s save.bin -o output.json -m output.md
  %(prog)s save.bin --json-only --quiet
        """
    )

    parser.add_argument(
        'input_file',
        type=Path,
        help='Path to decompressed save file (.bin)'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=None,
        help='JSON output path (default: <input_name>.json)'
    )

    parser.add_argument(
        '-m', '--markdown',
        type=Path,
        default=None,
        help='Markdown output path (default: <input_name>.md)'
    )

    parser.add_argument(
        '--json-only',
        action='store_true',
        help='Only output JSON, skip Markdown'
    )

    parser.add_argument(
        '--markdown-only',
        action='store_true',
        help='Only output Markdown, skip JSON'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    # Validate input file
    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    # Determine output paths
    base_name = args.input_file.stem
    output_dir = args.input_file.parent

    json_out = args.output or (output_dir / f"{base_name}.json")
    md_out = args.markdown or (output_dir / f"{base_name}.md")

    # Read and parse
    if not args.quiet:
        print(f"Parsing {args.input_file}...")
        print(f"Size: {args.input_file.stat().st_size:,} bytes")
        print()

    data = args.input_file.read_bytes()
    save_parser = ManorLordsSaveParser(data, quiet=args.quiet)
    result = save_parser.parse()

    # Write JSON output
    if not args.markdown_only:
        with open(json_out, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)
        if not args.quiet:
            print(f"JSON: {json_out}")

    # Write Markdown output
    if not args.json_only:
        to_markdown(result, md_out)
        if not args.quiet:
            print(f"Markdown: {md_out}")

    # Print summary
    if not args.quiet:
        print()
        print("=" * 60)
        s = result.get('stats', {})
        print(f"Parsed: {s.get('parsed', 0):,} / {s.get('file_size', 0):,} bytes "
              f"({s.get('percent', 0):.1f}%)")
        print(f"Properties: {len(result.get('properties', {}))}")
        print(f"Errors: {len(result.get('errors', []))}")

        if result.get('errors'):
            print()
            print("First 10 errors:")
            for e in result['errors'][:10]:
                print(f"  - {e}")


if __name__ == "__main__":
    # Configure stdout for Unicode on Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    main()
