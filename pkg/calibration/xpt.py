"""Minimal SAS Transport (XPT v5) reader.

NHANES publishes only in XPT. Reading it needs either pandas (a very large runtime
dependency for a library that advertises `pydantic` + `numpy`) or about a hundred
lines of well-documented binary parsing. This is the hundred lines.

Calibration is an offline step, like `pkg/spec/codegen.py` — nothing here is imported
on the generation path.

Format reference: SAS Technical Support document TS-140.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

RECORD = 80
NAMESTR_SIZE = 140

_LIBRARY_HEADER = b"HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!"
_MEMBER_HEADER = b"HEADER RECORD*******MEMBER  HEADER RECORD!!!!!!!"
_NAMESTR_HEADER = b"HEADER RECORD*******NAMESTR HEADER RECORD!!!!!!!"
_OBS_HEADER = b"HEADER RECORD*******OBS     HEADER RECORD!!!!!!!"


@dataclass(frozen=True)
class Variable:
    name: str
    label: str
    is_numeric: bool
    length: int
    position: int


def ibm_to_double(raw: bytes) -> float | None:
    """Convert IBM hexadecimal floating point to IEEE double.

    IBM format is sign(1) + base-16 exponent(7, excess-64) + mantissa(56), so the
    mantissa is a fraction and the exponent steps by powers of 16, not 2. Reading it
    as an IEEE double gives silently wrong numbers rather than an error.
    """
    if len(raw) < 8:
        raw = raw.ljust(8, b"\x00")
    if raw == b"\x00" * 8 or raw[0:1] in (b".", b" "):
        return None

    value = int.from_bytes(raw, "big")
    sign = -1.0 if value >> 63 else 1.0
    exponent = (value >> 56) & 0x7F
    mantissa = value & 0x00FFFFFFFFFFFFFF
    if mantissa == 0:
        return 0.0
    # Missing values are encoded as a leading '.' or letter with a zero mantissa.
    return sign * mantissa * 16.0 ** (exponent - 64 - 14)


def _parse_namestrs(block: bytes, count: int) -> list[Variable]:
    variables = []
    for index in range(count):
        chunk = block[index * NAMESTR_SIZE : (index + 1) * NAMESTR_SIZE]
        if len(chunk) < NAMESTR_SIZE:
            break
        # NAMESTR field offsets, per TS-140. Getting these wrong does not raise —
        # it yields plausible-looking variables with 1-byte lengths and garbage
        # labels, and every value read afterwards is silently misaligned.
        #   0..2   ntype  (1 = numeric, 2 = character)
        #   4..6   nlng   (field width in bytes)
        #   8..16  nname
        #   16..56 nlabel
        #   84..88 npos   (byte offset of the field within a row)
        var_type = struct.unpack(">h", chunk[0:2])[0]
        length = struct.unpack(">h", chunk[4:6])[0]
        name = chunk[8:16].decode("ascii", "replace").strip()
        label = chunk[16:56].decode("ascii", "replace").strip()
        offset = struct.unpack(">i", chunk[84:88])[0]
        variables.append(
            Variable(
                name=name,
                label=label,
                is_numeric=var_type == 1,
                length=length,
                position=offset,
            )
        )
    return variables


def read_xpt(path) -> tuple[list[Variable], list[dict]]:
    """Read one XPT member into (variables, rows)."""
    data = Path(path).read_bytes()
    if not data.startswith(_LIBRARY_HEADER):
        raise ValueError(f"{path} is not a SAS Transport file")

    cursor = data.find(_NAMESTR_HEADER)
    if cursor < 0:
        raise ValueError(f"{path} has no NAMESTR header")
    header = data[cursor : cursor + RECORD]
    variable_count = int(header[54:58])
    cursor += RECORD

    namestr_bytes = variable_count * NAMESTR_SIZE
    variables = _parse_namestrs(data[cursor : cursor + namestr_bytes], variable_count)

    obs = data.find(_OBS_HEADER, cursor)
    if obs < 0:
        raise ValueError(f"{path} has no OBS header")
    cursor = obs + RECORD

    row_size = sum(v.length for v in variables)
    if row_size == 0:
        return variables, []

    rows = []
    payload = data[cursor:]
    for start in range(0, len(payload) - row_size + 1, row_size):
        record = payload[start : start + row_size]
        # Trailing records are ASCII-space padding, not data.
        if record.strip(b" \x00") == b"":
            continue
        row = {}
        for variable in variables:
            field = record[variable.position : variable.position + variable.length]
            if variable.is_numeric:
                row[variable.name] = ibm_to_double(field)
            else:
                row[variable.name] = field.decode("ascii", "replace").strip()
        rows.append(row)
    return variables, rows


def column(rows: list[dict], name: str) -> list[float]:
    """Non-missing numeric values for one variable."""
    return [
        row[name]
        for row in rows
        if row.get(name) is not None and isinstance(row.get(name), float)
    ]
