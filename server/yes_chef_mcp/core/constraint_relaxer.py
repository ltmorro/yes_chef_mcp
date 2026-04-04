"""Constraint relaxation cascade for the optimizer.

When the MILP solver returns infeasible, soft constraints are dropped
in priority order until a solution is found. The solver never surfaces
an infeasible result — it degrades gracefully.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RelaxationState:
    """Tracks which constraints have been relaxed."""

    relaxations: list[str] = field(default_factory=list)
    allow_consecutive_repeats: bool = False
    macro_tolerance_pct: float = 10.0
    enforce_prep_time: bool = True
    enforce_tag_preferences: bool = True
    serving_min: float = 0.5
    serving_max: float = 3.0
    enforce_category_requirements: bool = True
    use_heuristic: bool = False


# Relaxation cascade — each step loosens one constraint
RELAXATION_CASCADE: list[tuple[str, str]] = [
    ("allow_consecutive_repeats", "dropped_variety_penalty"),
    ("widen_macro_tolerance", "widened_macros_to_25pct"),
    ("drop_prep_time", "dropped_prep_time"),
    ("drop_tag_preferences", "dropped_tag_preferences"),
    ("widen_serving_bounds", "widened_serving_bounds"),
    ("drop_category_requirements", "dropped_category_requirements"),
    ("use_heuristic_fallback", "fell_back_to_heuristic"),
]


def apply_relaxation(state: RelaxationState, step: str) -> RelaxationState:
    """Apply one relaxation step to the state.

    Returns a new state with the relaxation applied.
    """
    # Create a modified copy
    new_state = RelaxationState(
        relaxations=list(state.relaxations),
        allow_consecutive_repeats=state.allow_consecutive_repeats,
        macro_tolerance_pct=state.macro_tolerance_pct,
        enforce_prep_time=state.enforce_prep_time,
        enforce_tag_preferences=state.enforce_tag_preferences,
        serving_min=state.serving_min,
        serving_max=state.serving_max,
        enforce_category_requirements=state.enforce_category_requirements,
        use_heuristic=state.use_heuristic,
    )

    match step:
        case "allow_consecutive_repeats":
            new_state.allow_consecutive_repeats = True
        case "widen_macro_tolerance":
            new_state.macro_tolerance_pct = 25.0
        case "drop_prep_time":
            new_state.enforce_prep_time = False
        case "drop_tag_preferences":
            new_state.enforce_tag_preferences = False
        case "widen_serving_bounds":
            new_state.serving_min = 0.25
            new_state.serving_max = 4.0
        case "drop_category_requirements":
            new_state.enforce_category_requirements = False
        case "use_heuristic_fallback":
            new_state.use_heuristic = True

    # Find the label for this step
    for cascade_step, label in RELAXATION_CASCADE:
        if cascade_step == step:
            new_state.relaxations.append(label)
            break

    return new_state


def iterate_relaxations(
    initial_state: RelaxationState | None = None,
) -> list[RelaxationState]:
    """Generate all relaxation states in cascade order.

    Returns a list of progressively relaxed states, starting from the
    initial state (or defaults). Each state builds on the previous one.
    """
    state = initial_state or RelaxationState()
    states = [state]

    for step, _ in RELAXATION_CASCADE:
        state = apply_relaxation(state, step)
        states.append(state)

    return states
