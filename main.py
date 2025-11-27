"""Entry point for the binary adder visualization."""

from __future__ import annotations
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional, Tuple

from .binary_adder import AdditionResult, GateState, simulate_addition
from .simulation import SimulationTimeline, TimelineEvent
from .types import NUMERIC_TYPES, NumericType, get_numeric_type


HIGHLIGHT_COLOR = "#ffd166"
DEFAULT_GATE_COLOR = "#f8f9fa"
WIRE_COLOR = "#8d99ae"
ACTIVE_WIRE_COLOR = "#ff9f1c"
BACKGROUND_COLOR = "#f4ede2"
SUPPLY_COLOR = "#8ecae6"
GROUND_COLOR = "#adb5bd"
ACTIVE_SUPPLY_COLOR = "#ffb703"
ACTIVE_GROUND_COLOR = "#219ebc"
WIRE_WIDTH = 3
WIRE_ACTIVE_WIDTH = 5
TERMINAL_RADIUS = 4


@dataclass
class GateVisual:
    gate: GateState
    item_ids: Tuple[int, ...]


class AdderVisualizer:
    """Tkinter-based visualizer that animates ripple-carry addition."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Binary Adder Visualizer")
        self.root.configure(bg=BACKGROUND_COLOR)

        self.type_var = tk.StringVar(value="int32_t")
        self.left_var = tk.StringVar(value="13")
        self.right_var = tk.StringVar(value="5")
        self.speed_var = tk.DoubleVar(value=250.0)  # milliseconds per tick

        self.timeline: Optional[SimulationTimeline] = None
        self.addition: Optional[AdditionResult] = None
        self.event_index = 0
        self.after_id: Optional[str] = None
        self.current_gate_key: Optional[Tuple[int, str]] = None

        self.gate_visuals: Dict[Tuple[int, str], GateVisual] = {}
        self.sum_labels: Dict[int, int] = {}
        self.carry_labels: Dict[int, int] = {}
        self.wire_segments: Dict[Tuple[int, str], Tuple[int, ...]] = {}
        self.wire_styles: Dict[int, Dict[str, Any]] = {}
        self.supply_y: float = 0.0
        self.ground_y: float = 0.0
        self.level_gap: float = 0.0
        self.column_width: float = 0.0

        self._build_controls()
        self._build_canvas()
        self._build_status_panel()

    # ------------------------------------------------------------------ UI setup
    def _build_controls(self) -> None:
        controls_frame = ttk.Frame(self.root, padding=12)
        controls_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(controls_frame, text="Тип:").grid(row=0, column=0, padx=4)
        type_names = sorted(NUMERIC_TYPES.keys())
        type_combo = ttk.Combobox(
            controls_frame,
            values=type_names,
            textvariable=self.type_var,
            state="readonly",
            width=12,
        )
        type_combo.grid(row=0, column=1, padx=4)

        ttk.Label(controls_frame, text="A:").grid(row=0, column=2, padx=4)
        ttk.Entry(controls_frame, textvariable=self.left_var, width=12).grid(
            row=0, column=3, padx=4
        )

        ttk.Label(controls_frame, text="B:").grid(row=0, column=4, padx=4)
        ttk.Entry(controls_frame, textvariable=self.right_var, width=12).grid(
            row=0, column=5, padx=4
        )

        ttk.Button(controls_frame, text="Старт", command=self.start_animation).grid(
            row=0, column=6, padx=6
        )
        ttk.Button(controls_frame, text="Сброс", command=self.reset).grid(
            row=0, column=7, padx=6
        )

        ttk.Label(controls_frame, text="Скорость (мс/шаг):").grid(
            row=1, column=0, padx=4, pady=(8, 0)
        )
        speed_scale = ttk.Scale(
            controls_frame,
            from_=50,
            to=1000,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
        )
        speed_scale.grid(row=1, column=1, columnspan=3, sticky="ew", padx=4, pady=(8, 0))

        controls_frame.columnconfigure(1, weight=1)
        controls_frame.columnconfigure(2, weight=0)

    def _build_canvas(self) -> None:
        canvas_frame = ttk.Frame(self.root, padding=6)
        canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(
            canvas_frame, bg=BACKGROUND_COLOR, height=760, highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _build_status_panel(self) -> None:
        status_frame = ttk.Frame(self.root, padding=12)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_var = tk.StringVar(value="Введите числа и нажмите «Старт».")
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor="w")

        self.binary_a_var = tk.StringVar(value="")
        self.binary_b_var = tk.StringVar(value="")
        self.binary_sum_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self.binary_a_var).pack(anchor="w")
        ttk.Label(status_frame, textvariable=self.binary_b_var).pack(anchor="w")
        ttk.Label(status_frame, textvariable=self.binary_sum_var).pack(anchor="w")

    # ------------------------------------------------------------------ canvas helpers
    def _line(self, *coords: float, **kwargs) -> int:
        options = {
            "fill": WIRE_COLOR,
            "width": WIRE_WIDTH,
            "capstyle": tk.ROUND,
            "joinstyle": tk.ROUND,
        }
        options.update(kwargs)
        return self.canvas.create_line(*coords, **options)

    def _terminal(
        self,
        x: float,
        y: float,
        *,
        radius: int = TERMINAL_RADIUS,
        fill: str = BACKGROUND_COLOR,
        outline: str = WIRE_COLOR,
    ) -> int:
        return self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline=outline,
            fill=fill,
            width=2,
        )

    # ------------------------------------------------------------------ control actions
    def reset(self) -> None:
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.timeline = None
        self.addition = None
        self.event_index = 0
        self.current_gate_key = None
        self.gate_visuals.clear()
        self.sum_labels.clear()
        self.carry_labels.clear()
        self.wire_segments.clear()
        self.wire_styles.clear()
        self.supply_y = 0.0
        self.ground_y = 0.0
        self.level_gap = 0.0
        self.column_width = 0.0
        self.canvas.delete("all")
        self.status_var.set("Введите числа и нажмите «Старт».")
        self.binary_a_var.set("")
        self.binary_b_var.set("")
        self.binary_sum_var.set("")

    def start_animation(self) -> None:
        try:
            lhs = int(self.left_var.get(), 0)
            rhs = int(self.right_var.get(), 0)
        except ValueError:
            messagebox.showerror(
                "Ошибка ввода", "Неверный формат чисел. Используйте целые значения."
            )
            return

        try:
            numeric_type = get_numeric_type(self.type_var.get())
        except KeyError as exc:
            messagebox.showerror("Неизвестный тип", str(exc))
            return

        try:
            addition = simulate_addition(lhs, rhs, numeric_type)
        except OverflowError as exc:
            messagebox.showerror("Ошибка", str(exc))
            return

        self.reset()
        self.addition = addition
        self.timeline = SimulationTimeline(addition)

        self.status_var.set(
            f"{lhs} + {rhs} ({numeric_type.name}) → {addition.result} | Переполнение: "
            f"{'да' if addition.overflow else 'нет'}"
        )

        self._update_binary_labels(addition, numeric_type)
        self._build_circuit(addition)

        if len(self.timeline) == 0:
            self._finalize_visuals()
            return

        self.event_index = 0
        self._schedule_next()

    # ------------------------------------------------------------------ visualization helpers
    def _schedule_next(self) -> None:
        delay = max(10, int(self.speed_var.get()))
        self.after_id = self.root.after(delay, self._animate_next_event)

    def _animate_next_event(self) -> None:
        if not self.timeline:
            return

        if self.event_index >= len(self.timeline):
            self._finalize_visuals()
            self.after_id = None
            return

        event = self.timeline[self.event_index]
        self._highlight_event(event)
        self.event_index += 1
        self._schedule_next()

    def _highlight_event(self, event: TimelineEvent) -> None:
        self._clear_active_highlight()
        self._reset_wire_colors()
        key = (event.bit_index, event.gate_state.name)

        if key in self.gate_visuals:
            gate_visual = self.gate_visuals[key]
            for item_id in gate_visual.item_ids:
                self.canvas.itemconfig(item_id, fill=HIGHLIGHT_COLOR)
            self.current_gate_key = key

        gate = event.gate_state
        if gate.gate_type == "OR" and event.step:
            self._activate_wire(event.bit_index, "wire_carry_out")
            self._update_sum_label(event.step.bit_index, event.step.sum_bit)
            self._update_carry_label(event.step.bit_index + 1, event.step.carry_out)
        elif gate.gate_type == "XOR" and gate.name.startswith("A"):
            self._activate_wire(event.bit_index, "wire_A_input")
            self._activate_wire(event.bit_index, "wire_B_input")
        elif gate.gate_type == "OUTPUT":
            self._activate_wire(event.bit_index, "wire_carry_out")
            self._update_carry_label(
                event.bit_index + 1,
                gate.output,
            )
        self._highlight_current_flow(event)

    def _clear_active_highlight(self) -> None:
        if not self.current_gate_key:
            return
        gate_visual = self.gate_visuals.get(self.current_gate_key)
        if not gate_visual:
            return
        for item_id in gate_visual.item_ids:
            self.canvas.itemconfig(item_id, fill=DEFAULT_GATE_COLOR)
        self.current_gate_key = None

    def _activate_wire(self, bit_index: int, wire: str) -> None:
        segments = self.wire_segments.get((bit_index, wire))
        if not segments:
            return
        for item_id in segments:
            style = self.wire_styles.get(item_id)
            if not style:
                continue
            item_type = style["type"]
            if bit_index == -1 and wire == "supply":
                active_color = ACTIVE_SUPPLY_COLOR
            elif bit_index == -1 and wire == "ground":
                active_color = ACTIVE_GROUND_COLOR
            else:
                active_color = ACTIVE_WIRE_COLOR
            if item_type == "line":
                self.canvas.itemconfig(item_id, fill=active_color, width=WIRE_ACTIVE_WIDTH)
            elif item_type == "oval":
                self.canvas.itemconfig(
                    item_id,
                    outline=active_color,
                    width=float(style.get("width", 2)),
                    fill=active_color if style.get("fill_enabled") else style.get("fill"),
                )
            elif item_type == "rectangle":
                self.canvas.itemconfig(
                    item_id,
                    outline=active_color,
                    width=float(style.get("width", 2)),
                    fill=style.get("fill"),
                )

    def _reset_wire_colors(self) -> None:
        for (bit_idx, name), segments in self.wire_segments.items():
            for item_id in segments:
                style = self.wire_styles.get(item_id)
                if not style:
                    continue
                item_type = style["type"]
                if bit_idx == -1 and name == "supply":
                    base_color = SUPPLY_COLOR
                elif bit_idx == -1 and name == "ground":
                    base_color = GROUND_COLOR
                else:
                    base_color = style.get("fill", WIRE_COLOR)
                if item_type == "line":
                    self.canvas.itemconfig(
                        item_id,
                        fill=base_color,
                        width=float(style.get("width", WIRE_WIDTH)),
                    )
                elif item_type == "oval":
                    self.canvas.itemconfig(
                        item_id,
                        outline=style.get("outline", base_color),
                        width=float(style.get("width", 2)),
                        fill=style.get("fill"),
                    )
                elif item_type == "rectangle":
                    self.canvas.itemconfig(
                        item_id,
                        outline=style.get("outline", base_color),
                        width=float(style.get("width", 2)),
                        fill=style.get("fill"),
                    )

    def _register_wire(self, bit_index: int, name: str, *item_ids: int) -> None:
        if not item_ids:
            return
        self.wire_segments[(bit_index, name)] = tuple(item_ids)
        for item_id in item_ids:
            item_type = self.canvas.type(item_id)
            if item_type == "line":
                width_str = self.canvas.itemcget(item_id, "width")
                self.wire_styles[item_id] = {
                    "type": "line",
                    "fill": self.canvas.itemcget(item_id, "fill"),
                    "width": float(width_str) if width_str else WIRE_WIDTH,
                }
            elif item_type == "oval":
                width_str = self.canvas.itemcget(item_id, "width")
                self.wire_styles[item_id] = {
                    "type": "oval",
                    "outline": self.canvas.itemcget(item_id, "outline"),
                    "fill": self.canvas.itemcget(item_id, "fill"),
                    "width": float(width_str) if width_str else 2.0,
                    "fill_enabled": self.canvas.itemcget(item_id, "fill") not in ("", " "),
                }
            elif item_type == "rectangle":
                width_str = self.canvas.itemcget(item_id, "width")
                self.wire_styles[item_id] = {
                    "type": "rectangle",
                    "outline": self.canvas.itemcget(item_id, "outline"),
                    "fill": self.canvas.itemcget(item_id, "fill"),
                    "width": float(width_str) if width_str else 1.0,
                }

    def _highlight_current_flow(self, event: TimelineEvent) -> None:
        gate = event.gate_state
        bit_index = event.bit_index

        def highlight_if(signal_name: str, value: int) -> None:
            if value:
                self._activate_wire(bit_index, signal_name)

        if gate.gate_type == "XOR":
            if gate.name.startswith("A"):
                highlight_if("wire_A_input", gate.inputs.get("A", 0))
                highlight_if("wire_B_input", gate.inputs.get("B", 0))
                if gate.output:
                    self._activate_wire(-1, "supply")
                    self._activate_wire(bit_index, "wire_xor_signal")
            else:
                highlight_if("wire_carry_in", gate.inputs.get("CarryIn", 0))
                highlight_if("wire_xor_signal", gate.inputs.get("XOR", 0))
                if gate.output:
                    self._activate_wire(-1, "supply")
                    self._activate_wire(bit_index, "wire_sum_output")
        elif gate.gate_type == "AND":
            if "GEN" in gate.name:
                highlight_if("wire_A_input", gate.inputs.get("A", 0))
                highlight_if("wire_B_input", gate.inputs.get("B", 0))
                if gate.output:
                    self._activate_wire(-1, "supply")
                    self._activate_wire(bit_index, "wire_carry_gen")
            else:
                highlight_if("wire_carry_in", gate.inputs.get("CarryIn", 0))
                highlight_if("wire_xor_signal", gate.inputs.get("A_xor_B", gate.inputs.get("A⊕B", 0)))
                if gate.output:
                    self._activate_wire(bit_index, "wire_carry_prop")
        elif gate.gate_type == "OR":
            highlight_if("wire_carry_gen", gate.inputs.get("Gen", 0))
            highlight_if("wire_carry_prop", gate.inputs.get("Prop", 0))
            if gate.output:
                self._activate_wire(bit_index, "wire_carry_out")
        elif gate.gate_type == "OUTPUT":
            if gate.output:
                self._activate_wire(-1, "supply")
                self._activate_wire(bit_index, "wire_carry_out")
            else:
                self._activate_wire(-1, "ground")

    def _update_sum_label(self, bit_index: int, value: int) -> None:
        item_id = self.sum_labels.get(bit_index)
        if item_id:
            self.canvas.itemconfig(item_id, text=str(value))

    def _update_carry_label(self, bit_index: int, value: int) -> None:
        item_id = self.carry_labels.get(bit_index)
        if item_id:
            self.canvas.itemconfig(item_id, text=str(value))

    def _finalize_visuals(self) -> None:
        if not self.addition:
            return
        for bit_idx, step in enumerate(self.addition.steps):
            self._update_sum_label(bit_idx, step.sum_bit)
        self._update_carry_label(len(self.addition.steps), self.addition.final_carry)

    # ------------------------------------------------------------------ drawing
    def _build_circuit(self, addition: AdditionResult) -> None:
        self.canvas.delete("all")
        self.gate_visuals.clear()
        self.sum_labels.clear()
        self.carry_labels.clear()
        self.wire_segments.clear()

        bit_count = max(1, len(addition.steps))
        self.column_width = 210
        self.level_gap = 120
        margin_x = 180
        top_y = 160

        self.supply_y = top_y - 90
        self.ground_y = top_y + self.level_gap * 4 + 140

        line_left = margin_x - self.column_width / 2 - 60
        line_right = (
            margin_x + (bit_count - 1) * self.column_width + self.column_width / 2 + 60
        )

        self.final_carry_x = line_left - 20

        supply_line = self._line(
            line_left,
            self.supply_y,
            line_right,
            self.supply_y,
            fill=SUPPLY_COLOR,
            width=6,
        )
        ground_line = self._line(
            line_left,
            self.ground_y,
            line_right,
            self.ground_y,
            fill=GROUND_COLOR,
            width=6,
        )
        self._register_wire(-1, "supply", supply_line)
        self._register_wire(-1, "ground", ground_line)

        self.canvas.create_text(
            line_left - 40, self.supply_y, text="VDD (+)", font=("Helvetica", 11, "bold"), anchor="e"
        )
        self.canvas.create_text(
            line_left - 40, self.ground_y, text="GND (-)", font=("Helvetica", 11, "bold"), anchor="e"
        )

        gate_height = 56
        carry_out_center_y = top_y + self.level_gap * 4
        carry_channel_y = carry_out_center_y + gate_height // 2 + 24
        sum_label_y = carry_channel_y + 60
        carry_label_y = sum_label_y + 50

        for logical_index in range(bit_count):
            display_index = bit_count - 1 - logical_index
            x_center = margin_x + display_index * self.column_width
            self._draw_bit_column(
                addition,
                logical_index,
                x_center,
                top_y=top_y,
                sum_label_y=sum_label_y,
                carry_label_y=carry_label_y,
                gate_height=gate_height,
                carry_channel_y=carry_channel_y,
            )

        carry_label = self.canvas.create_text(
            self.final_carry_x,
            carry_label_y,
            text="0",
            font=("Courier", 18, "bold"),
            fill="#1d3557",
        )
        self.carry_labels[len(addition.steps)] = carry_label
        self.canvas.create_text(
            self.final_carry_x,
            carry_label_y + 26,
            text="Cout",
            font=("Helvetica", 11),
        )

        self.canvas.create_text(
            (line_left + line_right) / 2,
            self.supply_y - 110,
            text="MSB ← направление переноса → LSB",
            font=("Helvetica", 11, "italic"),
        )

        legend_text = (
            "Легенда:\n"
            " • оранжевая подсветка — активный сигнал/ток\n"
            " • верхняя голубая шина — питание (VDD), при срабатывании жёлтая\n"
            " • нижняя серая шина — земля (GND), при активации синяя\n"
            " • блоки XOR/AND/OR — логические элементы полно-сумматора\n"
            " • пары транзисторов управляют переносом (заряд/разряд)"
        )
        self.canvas.create_text(
            line_right + 120,
            top_y - 60,
            text=legend_text,
            anchor="nw",
            font=("Helvetica", 10),
            justify=tk.LEFT,
        )

    def _draw_bit_column(
        self,
        addition: AdditionResult,
        bit_index: int,
        x_center: int,
        *,
        top_y: int,
        sum_label_y: int,
        carry_label_y: int,
        gate_height: int,
        carry_channel_y: int,
    ) -> None:
        """Render a single bit slice and register canvas item references."""
        step = addition.steps[bit_index] if addition.steps else None
        lhs_bit = step.gate_states[0].inputs.get("A", 0) if step else 0
        rhs_bit = step.gate_states[0].inputs.get("B", 0) if step else 0
        carry_in = step.carry_in if step else 0

        gate_width = 110
        column_left = x_center - self.column_width / 2 + 18
        column_right = x_center + self.column_width / 2 - 18
        lane_a = column_left + 14
        lane_b = column_left + 70
        carry_lane_x = column_right - 12
        gen_center = x_center - 46
        prop_center = x_center + 46

        xor_y = top_y
        sum_y = top_y + self.level_gap
        carry_gen_y = top_y + 2 * self.level_gap
        carry_prop_y = top_y + 3 * self.level_gap
        carry_out_y = top_y + 4 * self.level_gap

        xor_left = x_center - gate_width // 2
        xor_right = x_center + gate_width // 2
        input_top = self.supply_y - 24

        background = self.canvas.create_rectangle(
            column_left,
            self.supply_y - 60,
            column_right,
            self.ground_y + 30,
            fill="#f8efe3",
            outline="#e0d6c5",
            width=1,
        )
        self.canvas.tag_lower(background)

        self.canvas.create_text(
            x_center,
            top_y - 68,
            text=f"Разряд {bit_index}",
            font=("Helvetica", 12, "bold"),
        )
        self.canvas.create_text(
            lane_a,
            self.supply_y - 48,
            text=f"A{bit_index}",
            font=("Helvetica", 11, "bold"),
        )
        self.canvas.create_text(
            lane_a,
            self.supply_y - 28,
            text=str(lhs_bit),
            font=("Courier", 16, "bold"),
        )
        self.canvas.create_text(
            lane_b,
            self.supply_y - 48,
            text=f"B{bit_index}",
            font=("Helvetica", 11, "bold"),
        )
        self.canvas.create_text(
            lane_b,
            self.supply_y - 28,
            text=str(rhs_bit),
            font=("Courier", 16, "bold"),
        )

        a_segments = [
            self._terminal(lane_a, input_top),
            self._line(lane_a, input_top, lane_a, xor_y),
            self._terminal(lane_a, xor_y),
            self._line(lane_a, xor_y, xor_left, xor_y),
            self._line(lane_a, xor_y, lane_a, carry_gen_y),
            self._terminal(lane_a, carry_gen_y),
            self._line(lane_a, carry_gen_y, gen_center - 20, carry_gen_y),
            self._terminal(gen_center - 20, carry_gen_y),
        ]
        b_segments = [
            self._terminal(lane_b, input_top),
            self._line(lane_b, input_top, lane_b, xor_y),
            self._terminal(lane_b, xor_y),
            self._line(lane_b, xor_y, xor_right, xor_y),
            self._line(lane_b, xor_y, lane_b, carry_gen_y),
            self._terminal(lane_b, carry_gen_y),
            self._line(lane_b, carry_gen_y, gen_center + 20, carry_gen_y),
            self._terminal(gen_center + 20, carry_gen_y),
        ]
        self._register_wire(bit_index, "wire_A_input", *a_segments)
        self._register_wire(bit_index, "wire_B_input", *b_segments)

        carry_segments = [
            self._terminal(carry_lane_x, carry_channel_y, fill=BACKGROUND_COLOR),
            self._line(carry_lane_x, carry_channel_y, carry_lane_x, sum_y),
            self._terminal(carry_lane_x, sum_y, fill=BACKGROUND_COLOR),
            self._line(carry_lane_x, sum_y, xor_right, sum_y),
            self._terminal(xor_right, sum_y, fill=BACKGROUND_COLOR),
            self._line(carry_lane_x, sum_y, carry_lane_x, carry_prop_y),
            self._terminal(carry_lane_x, carry_prop_y, fill=BACKGROUND_COLOR),
            self._line(carry_lane_x, carry_prop_y, prop_center - 20, carry_prop_y),
            self._terminal(prop_center - 20, carry_prop_y, fill=BACKGROUND_COLOR),
        ]
        self.canvas.create_text(
            carry_lane_x + 24,
            sum_y - 12,
            text=f"Cin{bit_index} = {carry_in}",
            font=("Helvetica", 10),
            anchor="w",
        )
        self._register_wire(bit_index, "wire_carry_in", *carry_segments)

        xor_rect = self._draw_gate(
            x_center,
            xor_y,
            gate_width,
            gate_height,
            "XOR\n(без переноса)",
        )
        self.gate_visuals[(bit_index, f"A{bit_index}_XOR_B{bit_index}")] = GateVisual(
            gate=GateState(
                name=f"A{bit_index}_XOR_B{bit_index}",
                gate_type="XOR",
                inputs={},
                output=0,
            ),
            item_ids=(xor_rect,),
        )

        sum_rect = self._draw_gate(
            x_center, sum_y, gate_width, gate_height, "XOR\n(+ перенос)"
        )
        self.gate_visuals[(bit_index, f"SUM{bit_index}")] = GateVisual(
            gate=GateState(
                name=f"SUM{bit_index}",
                gate_type="XOR",
                inputs={},
                output=0,
            ),
            item_ids=(sum_rect,),
        )

        xor_segments = [
            self._line(x_center, xor_y + gate_height // 2, x_center, sum_y - gate_height // 2),
            self._terminal(x_center, sum_y - gate_height // 2),
            self._line(x_center, sum_y - gate_height // 2, prop_center - 20, sum_y - gate_height // 2),
            self._line(prop_center - 20, sum_y - gate_height // 2, prop_center - 20, carry_prop_y),
            self._terminal(prop_center - 20, carry_prop_y),
        ]
        self._register_wire(bit_index, "wire_xor_signal", *xor_segments)

        carry_gen_items, gen_top, gen_bottom = self._draw_transistor_pair(
            gen_center, carry_gen_y, label="Gᵢ = A · B"
        )
        self.gate_visuals[(bit_index, f"CARRY_GEN{bit_index}")] = GateVisual(
            gate=GateState(
                name=f"CARRY_GEN{bit_index}",
                gate_type="AND",
                inputs={},
                output=0,
            ),
            item_ids=carry_gen_items,
        )
        gen_supply = self._line(gen_center, gen_top, gen_center, self.supply_y)
        gen_ground = self._line(gen_center, gen_bottom, gen_center, self.ground_y, dash=(4, 4))
        gen_to_or = self._line(gen_center, carry_gen_y + gate_height // 2, gen_center, carry_out_y)
        gen_into_or = self._line(gen_center, carry_out_y, x_center - gate_width // 2, carry_out_y)
        self._register_wire(
            bit_index,
            "wire_carry_gen",
            gen_supply,
            gen_to_or,
            gen_into_or,
        )

        carry_prop_items, prop_top, prop_bottom = self._draw_transistor_pair(
            prop_center, carry_prop_y, label="Pᵢ = A ⊕ B"
        )
        self.gate_visuals[(bit_index, f"CARRY_PROP{bit_index}")] = GateVisual(
            gate=GateState(
                name=f"CARRY_PROP{bit_index}",
                gate_type="AND",
                inputs={},
                output=0,
            ),
            item_ids=carry_prop_items,
        )
        prop_supply = self._line(prop_center, prop_top, prop_center, self.supply_y, dash=(4, 4))
        prop_ground = self._line(prop_center, prop_bottom, prop_center, self.ground_y, dash=(4, 4))
        prop_to_lane = self._line(prop_center, carry_prop_y + gate_height // 2, carry_lane_x, carry_prop_y + gate_height // 2)
        prop_drop = self._line(carry_lane_x, carry_prop_y + gate_height // 2, carry_lane_x, carry_out_y)
        self._register_wire(
            bit_index,
            "wire_carry_prop",
            prop_to_lane,
            prop_drop,
        )

        carry_out_rect = self._draw_gate(
            x_center, carry_out_y, gate_width + 24, gate_height, "OR\n(итоговый перенос)"
        )
        self.gate_visuals[(bit_index, f"CARRY_OUT{bit_index}")] = GateVisual(
            gate=GateState(
                name=f"CARRY_OUT{bit_index}",
                gate_type="OR",
                inputs={},
                output=0,
            ),
            item_ids=(carry_out_rect,),
        )

        carry_out_segments = [
            self._line(x_center + gate_width // 2, carry_out_y, carry_lane_x, carry_out_y),
            self._line(carry_lane_x, carry_out_y, carry_lane_x, carry_channel_y),
            self._terminal(carry_lane_x, carry_out_y, fill=BACKGROUND_COLOR),
            self._terminal(carry_lane_x, carry_channel_y, fill=BACKGROUND_COLOR),
        ]
        if bit_index + 1 < len(addition.steps):
            next_lane_x = carry_lane_x - self.column_width
            carry_out_segments.append(
                self._line(
                    carry_lane_x,
                    carry_channel_y,
                    next_lane_x,
                    carry_channel_y,
                    arrow=tk.LAST,
                    arrowshape=(10, 12, 6),
                )
            )
            carry_out_segments.append(
                self._terminal(next_lane_x, carry_channel_y, fill=BACKGROUND_COLOR)
            )
        else:
            carry_out_segments.append(
                self._line(carry_lane_x, carry_channel_y, self.final_carry_x, carry_channel_y)
            )
            carry_out_segments.append(
                self._terminal(self.final_carry_x, carry_channel_y, fill=BACKGROUND_COLOR)
            )
            carry_out_segments.append(
                self._line(self.final_carry_x, carry_channel_y, self.final_carry_x, carry_label_y - 22)
            )
            carry_out_segments.append(
                self._terminal(self.final_carry_x, carry_label_y - 22, fill=BACKGROUND_COLOR)
            )
        self._register_wire(bit_index, "wire_carry_out", *carry_out_segments)

        sum_vertical = self._line(
            x_center,
            sum_y + gate_height // 2,
            x_center,
            sum_label_y - 28,
        )
        sum_indicator_circle = self.canvas.create_oval(
            x_center - 12,
            sum_label_y - 32,
            x_center + 12,
            sum_label_y - 8,
            outline=WIRE_COLOR,
            fill=DEFAULT_GATE_COLOR,
            width=2,
        )
        self._register_wire(bit_index, "wire_sum_output", sum_vertical, sum_indicator_circle)

        sum_label = self.canvas.create_text(
            x_center,
            sum_label_y,
            text="?",
            font=("Courier", 20, "bold"),
            fill="#1d3557",
        )
        self.sum_labels[bit_index] = sum_label
        self.canvas.create_text(
            x_center,
            sum_label_y + 26,
            text=f"S{bit_index}",
            font=("Helvetica", 11),
        )

        carry_label_item = self.canvas.create_text(
            x_center,
            carry_label_y,
            text="0",
            font=("Courier", 16, "bold"),
            fill="#457b9d",
        )
        self.carry_labels[bit_index + 1] = carry_label_item
        self.canvas.create_text(
            x_center,
            carry_label_y + 24,
            text=f"C{bit_index + 1}",
            font=("Helvetica", 10),
        )
    def _draw_gate(self, x: int, y: int, width: int, height: int, label: str) -> int:
        rect = self.canvas.create_rectangle(
            x - width // 2,
            y - height // 2,
            x + width // 2,
            y + height // 2,
            fill=DEFAULT_GATE_COLOR,
            outline="#444",
            width=2,
        )
        self.canvas.create_text(x, y, text=label, font=("Helvetica", 10, "bold"))
        return rect

    def _draw_transistor_pair(
        self, x: int, y: int, label: str
    ) -> Tuple[Tuple[int, ...], float, float]:
        radius = 16
        spacing = 44
        circle1 = self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline="#444",
            fill=DEFAULT_GATE_COLOR,
            width=2,
        )
        circle2 = self.canvas.create_oval(
            x - radius,
            y - radius + spacing,
            x + radius,
            y + radius + spacing,
            outline="#444",
            fill=DEFAULT_GATE_COLOR,
            width=2,
        )
        link = self._line(
            x,
            y + radius,
            x,
            y + spacing - radius,
            width=2,
        )
        text = self.canvas.create_text(
            x,
            y + spacing + 24,
            text=label,
            font=("Helvetica", 9),
        )
        return (circle1, circle2, link, text), y - radius, y + spacing + radius

    # ------------------------------------------------------------------ metadata labels
    def _update_binary_labels(self, addition: AdditionResult, numeric_type: NumericType) -> None:
        bit_width = (
            numeric_type.bits if numeric_type.bits is not None else len(addition.result_bits)
        )

        def format_bits(value: int) -> str:
            if numeric_type.bits is None:
                width = max(bit_width, value.bit_length() or 1)
            else:
                width = bit_width
            if value < 0 and numeric_type.bits is None:
                return "-" + format_bits(-value)
            encoded = value & ((1 << width) - 1)
            return format(encoded, f"0{width}b")

        self.binary_a_var.set(f"A = {format_bits(addition.lhs)}₂")
        self.binary_b_var.set(f"B = {format_bits(addition.rhs)}₂")
        sum_bits = "".join(str(bit) for bit in reversed(addition.result_bits))
        self.binary_sum_var.set(
            f"Σ = {sum_bits}₂  ({addition.result})  Переполнение: {'да' if addition.overflow else 'нет'}"
        )


def main() -> None:
    root = tk.Tk()
    app = AdderVisualizer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
