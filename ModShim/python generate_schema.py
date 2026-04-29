import re
import os

def generate_ctypes_schema(header_path: str, output_path: str):
    # Mapping C++ types to Python ctypes
    TYPE_MAP = {
        "uint8_t": "ctypes.c_uint8",
        "uint16_t": "ctypes.c_uint16",
        "uint32_t": "ctypes.c_uint32",
        "float": "ctypes.c_float",
        "bool": "ctypes.c_bool",
        "char": "ctypes.c_char",
        "int": "ctypes.c_int"
    }

    with open(header_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    output = ["import ctypes\n\n"]
    in_struct = False
    
    # Regex definitions
    re_const = re.compile(r'constexpr\s+(?:int|uint\d+_t)\s+(\w+)\s*=\s*(\d+);')
    re_struct = re.compile(r'struct\s+(\w+)\s*\{')
    re_end = re.compile(r'\}\s*;')
    re_field = re.compile(r'^([a-zA-Z0-9_:]+)\s+([a-zA-Z0-9_]+)(?:\[([a-zA-Z0-9_]+)\])?\s*;(.*)')

    for line in lines:
        sline = line.strip()
        
        # 1. Match Constants (constexpr)
        m_const = re_const.match(sline)
        if m_const:
            output.append(f"{m_const.group(1)} = {m_const.group(2)}\n")
            continue

        # 2. Match Struct Start
        m_struct = re_struct.match(sline)
        if m_struct:
            in_struct = True
            output.append(f"\nclass {m_struct.group(1)}(ctypes.Structure):\n")
            output.append("    _pack_ = 1\n")
            output.append("    _layout_ = 'ms'\n")
            output.append("    _fields_ =[\n")
            continue

        # 3. Match Struct End
        if in_struct and re_end.match(sline):
            in_struct = False
            output.append("    ]\n")
            continue

        # 4. Parse inside Struct
        if in_struct:
            # Preserve full-line comments
            if sline.startswith("//"):
                output.append(f"        # {sline[2:].strip()}\n")
            # Preserve blank lines
            elif not sline:
                output.append("\n")
            # Parse field definitions
            else:
                m_field = re_field.match(sline)
                if m_field:
                    ctype_base = m_field.group(1)
                    name = m_field.group(2)
                    arr_size = m_field.group(3)
                    comment = m_field.group(4).strip()
                    
                    # Convert C type to Python type (or keep as struct name)
                    py_type = TYPE_MAP.get(ctype_base, ctype_base)
                    
                    # Handle arrays (e.g. [MAX_ENTITIES] or [64])
                    if arr_size:
                        py_type = f"{py_type} * {arr_size}"
                        
                    # Handle inline comments
                    py_comment = ""
                    if comment.startswith("//"):
                        py_comment = f" # {comment[2:].strip()}"
                        
                    output.append(f"        (\"{name}\", {py_type}),{py_comment}\n")

    # Write the output file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(output))
    print(f"Successfully generated {output_path} from {header_path}")

if __name__ == "__main__":
    # Point this to your actual file locations
    SOURCE_H = "src/IPCSerialization.h"
    DEST_PY = "../env/ipc_schema.py"
    
    if os.path.exists(SOURCE_H):
        generate_ctypes_schema(SOURCE_H, DEST_PY)
    else:
        print(f"Error: {SOURCE_H} not found.")
