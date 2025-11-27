"""Helpers for turning addition results into time-ordered events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Sequence

from .binary_adder import AdditionResult, AdderStep, GateState


@dataclass(frozen=True)
class TimelineEvent:
    """Single event in the visualization timeline."""

    tick: int
    bit_index: int
    gate_state: GateState
    step: Optional[AdderStep]

    @property
    def label(self) -> str:
        return f"bit {self.bit_index}: {self.gate_state.gate_type}"


class SimulationTimeline(Sequence[TimelineEvent]):
    """Convenience wrapper for iterating over gate events."""

    def __init__(self, addition: AdditionResult):
        events: List[TimelineEvent] = []
        tick = 0
        for step in addition.steps:
            for gate_state in step.gate_states:
                events.append(
                    TimelineEvent(
                        tick=tick,
                        bit_index=step.bit_index,
                        gate_state=gate_state,
                        step=step,
                    )
                )
                tick += 1
        # Add a final tick to display the result wire stabilising.
        if addition.final_carry:
            msb_index = addition.steps[-1].bit_index if addition.steps else 0
            events.append(
                TimelineEvent(
                    tick=tick,
                    bit_index=msb_index,
                    gate_state=GateState(
                        name="FINAL_CARRY",
                        gate_type="OUTPUT",
                        inputs={"CarryOut": addition.final_carry},
                        output=addition.final_carry,
                    ),
                    step=addition.steps[-1] if addition.steps else None,  # type: ignore[arg-type]
                )
            )
        self._events = events

    def __len__(self) -> int:
        return len(self._events)

    def __getitem__(self, index: int) -> TimelineEvent:
        return self._events[index]

    def __iter__(self) -> Iterator[TimelineEvent]:
        return iter(self._events)

    def ticks(self) -> Iterable[int]:
        return (event.tick for event in self._events)
