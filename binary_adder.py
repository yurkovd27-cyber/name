"""Binary addition logic and simulation details."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from .types import NumericType


@dataclass(frozen=True)
class GateState:
    """Represents the state of a logic gate during a single tick."""

    name: str
    gate_type: str
    inputs: Dict[str, int]
    output: int


@dataclass(frozen=True)
class AdderStep:
    """Single step of the ripple-carry adder."""

    bit_index: int
    carry_in: int
    gate_states: Sequence[GateState]
    sum_bit: int
    carry_out: int


@dataclass(frozen=True)
class AdditionResult:
    """Outcome of an addition including visualization metadata."""

    numeric_type: NumericType
    lhs: int
    rhs: int
    result: int
    overflow: bool
    steps: Sequence[AdderStep]
    result_bits: Sequence[int]
    final_carry: int


def _int_to_bits(value: int, *, bits: int, signed: bool) -> List[int]:
    """Convert an integer into LSB-first bits with two's complement semantics."""
    if bits <= 0:
        return [0]

    if signed and value < 0:
        value = (1 << bits) + value

    mask = (1 << bits) - 1
    value &= mask
    return [(value >> i) & 1 for i in range(bits)]


def _bits_to_int(bits: Sequence[int], *, signed: bool) -> int:
    """Convert LSB-first bits back into an integer with two's complement semantics."""
    value = 0
    for idx, bit in enumerate(bits):
        if bit:
            value |= 1 << idx

    if signed and bits and bits[-1] == 1:
        # Negative number: subtract 2**n to interpret as signed.
        value -= 1 << len(bits)
    return value


def simulate_addition(
    lhs: int, rhs: int, numeric_type: NumericType
) -> AdditionResult:
    """Simulate a ripple-carry adder and collect visualization steps."""
    if numeric_type.bits is not None:
        min_val, max_val = numeric_type.range()
        if not (min_val <= lhs <= max_val):
            raise OverflowError(
                f"Left operand {lhs} does not fit into {numeric_type.name}."
            )
        if not (min_val <= rhs <= max_val):
            raise OverflowError(
                f"Right operand {rhs} does not fit into {numeric_type.name}."
            )

    if numeric_type.bits is None:
        dynamic_bits = numeric_type.bit_length_for_values([lhs, rhs, lhs + rhs])
        bit_width = max(dynamic_bits, 1)
        lhs_norm = lhs
        rhs_norm = rhs
    else:
        bit_width = numeric_type.bits
        lhs_norm = numeric_type.normalize(lhs)
        rhs_norm = numeric_type.normalize(rhs)

    lhs_bits = _int_to_bits(lhs_norm, bits=bit_width, signed=numeric_type.signed)
    rhs_bits = _int_to_bits(rhs_norm, bits=bit_width, signed=numeric_type.signed)

    carry = 0
    steps: List[AdderStep] = []
    sum_bits: List[int] = []

    for idx in range(bit_width):
        a_bit = lhs_bits[idx] if idx < len(lhs_bits) else 0
        b_bit = rhs_bits[idx] if idx < len(rhs_bits) else 0
        xor_ab = a_bit ^ b_bit
        sum_bit = xor_ab ^ carry
        and_ab = a_bit & b_bit
        and_xor_carry = xor_ab & carry
        carry_out = and_ab | and_xor_carry

        gates = [
            GateState(
                name=f"A{idx}_XOR_B{idx}",
                gate_type="XOR",
                inputs={"A": a_bit, "B": b_bit},
                output=xor_ab,
            ),
            GateState(
                name=f"SUM{idx}",
                gate_type="XOR",
                inputs={"XOR": xor_ab, "CarryIn": carry},
                output=sum_bit,
            ),
            GateState(
                name=f"CARRY_GEN{idx}",
                gate_type="AND",
                inputs={"A": a_bit, "B": b_bit},
                output=and_ab,
            ),
            GateState(
                name=f"CARRY_PROP{idx}",
                gate_type="AND",
                inputs={"A_xor_B": xor_ab, "CarryIn": carry},
                output=and_xor_carry,
            ),
            GateState(
                name=f"CARRY_OUT{idx}",
                gate_type="OR",
                inputs={"Gen": and_ab, "Prop": and_xor_carry},
                output=carry_out,
            ),
        ]

        steps.append(
            AdderStep(
                bit_index=idx,
                carry_in=carry,
                gate_states=gates,
                sum_bit=sum_bit,
                carry_out=carry_out,
            )
        )

        sum_bits.append(sum_bit)
        carry = carry_out

    final_carry = carry

    # Determine final integer result and overflow.
    raw_sum = lhs + rhs

    if numeric_type.bits is None:
        result_value = raw_sum
        overflow = False
        if final_carry:
            sum_bits.append(final_carry)
    else:
        normalized_sum = numeric_type.normalize(raw_sum)
        encoded = normalized_sum & ((1 << bit_width) - 1)
        sum_bits = _int_to_bits(encoded, bits=bit_width, signed=False)
        result_value = normalized_sum

        range_min, range_max = numeric_type.range()
        range_overflow = not (range_min <= raw_sum <= range_max)

        carry_overflow = bool(final_carry) if not numeric_type.signed else False
        signed_overflow = (
            bool(steps[-1].carry_in ^ steps[-1].carry_out)
            if numeric_type.signed and steps
            else False
        )

        overflow = range_overflow or carry_overflow or signed_overflow

    return AdditionResult(
        numeric_type=numeric_type,
        lhs=lhs,
        rhs=rhs,
        result=result_value,
        overflow=overflow,
        steps=steps,
        result_bits=sum_bits,
        final_carry=final_carry,
    )
