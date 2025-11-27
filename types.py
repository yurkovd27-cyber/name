"""Numeric type metadata used by the binary adder simulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class NumericType:
    """Description of a hardware-like integer type."""

    name: str
    bits: Optional[int]
    signed: bool

    def min_value(self) -> int:
        """Return the minimum representable integer."""
        if self.bits is None:
            return -(1 << 63)  # effectively unlimited, but keep helpers happy
        if self.signed:
            return -(1 << (self.bits - 1))
        return 0

    def max_value(self) -> int:
        """Return the maximum representable integer."""
        if self.bits is None:
            return (1 << 63) - 1  # effectively unlimited
        if self.signed:
            return (1 << (self.bits - 1)) - 1
        return (1 << self.bits) - 1

    def requires_clamp(self) -> bool:
        """Indicates whether the values must be clamped to the bit width."""
        return self.bits is not None

    def normalize(self, value: int) -> int:
        """Normalize a value into the range of this type using two's complement rules."""
        if self.bits is None:
            return value

        mask = (1 << self.bits) - 1
        value &= mask

        if self.signed and (value & (1 << (self.bits - 1))):
            # Interpret as negative number in two's complement.
            value -= 1 << self.bits
        return value

    def encode(self, value: int) -> int:
        """Encode a Python int into the two's complement representation for this type."""
        if self.bits is None:
            return value

        min_val, max_val = self.range()
        if not (min_val <= value <= max_val):
            raise OverflowError(
                f"value {value} does not fit into {self.name} (range {min_val}..{max_val})"
            )
        return value & ((1 << self.bits) - 1)

    def range(self) -> tuple[int, int]:
        """Return (min, max) inclusive range."""
        return (self.min_value(), self.max_value())

    def bit_length_for_values(self, values: Iterable[int]) -> int:
        """Return the bit length needed to display all provided values."""
        if self.bits is not None:
            return self.bits
        max_abs = max((abs(v) for v in values), default=0)
        # At least 1 bit for zero.
        needed = max_abs.bit_length() + 1  # extra bit to visualize sign/carry.
        return max(needed, 1)


def _make_types() -> Dict[str, NumericType]:
    types: Dict[str, NumericType] = {}

    def add(name: str, bits: Optional[int], signed: bool, aliases: Iterable[str] = ()):
        numeric_type = NumericType(name, bits, signed)
        types[name] = numeric_type
        for alias in aliases:
            types[alias] = numeric_type

    add("int", None, True, aliases=("python-int",))
    add("int8_t", 8, True, aliases=("int8",))
    add("int16_t", 16, True, aliases=("int16",))
    add("int32_t", 32, True, aliases=("int32",))
    add("int64_t", 64, True, aliases=("int64",))
    add("uint8_t", 8, False, aliases=("uint8",))
    add("uint16_t", 16, False, aliases=("uint16",))
    add("uint32_t", 32, False, aliases=("uint32",))
    add("uint64_t", 64, False, aliases=("uint64",))
    add("size_t", 64, False)
    add("uint", 32, False)
    add("long", 64, True)
    add("unsigned long", 64, False, aliases=("ulong",))

    return types


NUMERIC_TYPES: Dict[str, NumericType] = _make_types()


def get_numeric_type(name: str) -> NumericType:
    """Lookup a type by name, raising a helpful error if it does not exist."""
    normalized = name.strip().lower()
    try:
        return NUMERIC_TYPES[normalized]
    except KeyError as exc:
        available = ", ".join(sorted(NUMERIC_TYPES))
        raise KeyError(f"Unknown numeric type '{name}'. Known types: {available}") from exc
