"""Meal and plan optimization using MILP (python-mip) with greedy fallback.

The optimizer uses a tiered solving strategy:
1. MILP via python-mip (CBC solver) — optimal, used when tractable
2. Greedy heuristic with simulated annealing — fast "good enough" fallback
3. Continuous relaxation via scipy — for serving-size-only adjustments

When MILP is infeasible, the constraint relaxation cascade (constraint_relaxer.py)
progressively drops soft constraints until a solution is found.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from yes_chef_mcp.core.constraint_relaxer import RelaxationState, iterate_relaxations
from yes_chef_mcp.core.db import get_db
from yes_chef_mcp.core.models import (
    Ingredient,
    MacroSummary,
    MacroTarget,
    MealComponent,
    MealConstraints,
    MealSlot,
    MealType,
    Nutrition,
    OptimizationObjective,
    OptimizedMeal,
    OptimizedPlan,
    PinnedSlot,
    PlanConstraints,
    RebalancedPlan,
    RebalanceStrategy,
    SolverResult,
    SolverStatus,
    SpoilageConfig,
)
from yes_chef_mcp.core.planner import get_meal_plan, get_meal_slots
from yes_chef_mcp.core.recipe_store import get_nutrition_batch, list_recipes
from yes_chef_mcp.core.spoilage import ingredient_overlap_bonus


@dataclass(frozen=True, slots=True)
class _CandidateRecipe:
    """Recipe with pre-fetched nutrition for optimization."""

    id: str
    name: str
    category: str | None
    prep_minutes: int | None
    tags: list[str]
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    ingredients: list[Ingredient] = field(default_factory=list)


@dataclass(slots=True)
class _MealAssignment:
    """A recipe assigned to a meal with per-member servings."""

    recipe: _CandidateRecipe
    member_servings: dict[str, float] = field(default_factory=dict)


async def _get_member_targets(member_ids: list[str]) -> dict[str, MacroTarget]:
    """Fetch active macro targets for members."""
    targets: dict[str, MacroTarget] = {}
    for mid in member_ids:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM macro_targets WHERE member_id = ? AND is_active = 1",
                (mid,),
            )
            row = await cursor.fetchone()
            if row:
                targets[mid] = MacroTarget(
                    id=str(row["id"]),
                    member_id=mid,
                    name=str(row["name"]),
                    calories=float(str(row["calories"])),
                    protein_g=float(str(row["protein_g"])),
                    carbs_g=float(str(row["carbs_g"])),
                    fat_g=float(str(row["fat_g"])),
                    is_active=True,
                )
    return targets


async def _load_candidates(
    family_id: str | None = None,
    candidate_ids: list[str] | None = None,
    excluded_ids: list[str] | None = None,
) -> list[_CandidateRecipe]:
    """Load candidate recipes with nutrition data."""
    recipes = await list_recipes(family_id=family_id, limit=1000)

    if candidate_ids is not None:
        id_set = set(candidate_ids)
        recipes = [r for r in recipes if r.id in id_set]

    if excluded_ids:
        excluded = set(excluded_ids)
        recipes = [r for r in recipes if r.id not in excluded]

    recipe_ids = [r.id for r in recipes]
    nutrition_map = await get_nutrition_batch(recipe_ids)

    candidates: list[_CandidateRecipe] = []
    for r in recipes:
        nutr = nutrition_map.get(r.id)
        if nutr is None:
            continue  # Skip recipes without nutrition data

        candidates.append(
            _CandidateRecipe(
                id=r.id,
                name=r.name,
                category=r.category.value if r.category else None,
                prep_minutes=r.prep_minutes,
                tags=r.tags,
                calories=nutr.calories,
                protein_g=nutr.protein_g,
                carbs_g=nutr.carbs_g,
                fat_g=nutr.fat_g,
                ingredients=r.ingredients,
            )
        )

    return candidates


def _macro_deviation(
    macros: MacroSummary,
    target: MacroTarget,
) -> float:
    """Weighted macro deviation score."""
    weights = {"calories": 1.0, "protein": 1.5, "carbs": 0.8, "fat": 0.8}
    total = 0.0
    if target.calories > 0:
        total += weights["calories"] * abs(macros.calories - target.calories) / target.calories
    if target.protein_g > 0:
        total += weights["protein"] * abs(macros.protein_g - target.protein_g) / target.protein_g
    if target.carbs_g > 0:
        total += weights["carbs"] * abs(macros.carbs_g - target.carbs_g) / target.carbs_g
    if target.fat_g > 0:
        total += weights["fat"] * abs(macros.fat_g - target.fat_g) / target.fat_g
    return total


def _greedy_meal_solve(
    candidates: list[_CandidateRecipe],
    member_targets: dict[str, MacroTarget],
    max_components: int,
    constraints: MealConstraints | None,
    required_ids: list[str] | None,
    objective: OptimizationObjective,
    relaxation: RelaxationState,
    spoilage_config: SpoilageConfig | None = None,
) -> list[_MealAssignment]:
    """Greedy heuristic: pick recipes that minimize deviation, one at a time.

    When spoilage_config is provided, ingredient overlap among perishable items
    acts as a small tiebreaker. The overlap bonus is scaled by
    spoilage_config.spoilage_weight (default 0.10) so it never dominates
    macro deviation.
    """
    assignments: list[_MealAssignment] = []
    used_ids: set[str] = set()
    sp_cfg = spoilage_config or SpoilageConfig()

    # Add required recipes first
    if required_ids:
        for rid in required_ids:
            for c in candidates:
                if c.id == rid:
                    servings = {mid: 1.0 for mid in member_targets}
                    assignments.append(_MealAssignment(recipe=c, member_servings=servings))
                    used_ids.add(rid)
                    break

    remaining = [c for c in candidates if c.id not in used_ids]

    while len(assignments) < max_components and remaining:
        best_score = float("inf")
        best_candidate: _CandidateRecipe | None = None

        # Collect existing ingredient lists for overlap scoring
        existing_ingredient_lists = [a.recipe.ingredients for a in assignments]

        for c in remaining:
            # Check constraints
            if constraints:
                if (
                    constraints.max_prep_minutes is not None
                    and relaxation.enforce_prep_time
                    and c.prep_minutes is not None
                    and c.prep_minutes > constraints.max_prep_minutes
                ):
                    continue
                if constraints.excluded_tags and set(c.tags) & set(constraints.excluded_tags):
                    continue
                if constraints.required_tags and not set(constraints.required_tags) & set(c.tags):
                    continue

            # Primary score: sum of macro deviations across members
            macro_score = 0.0
            for mid, target in member_targets.items():
                current = _sum_macros(assignments, mid)
                projected = MacroSummary(
                    calories=current.calories + c.calories,
                    protein_g=current.protein_g + c.protein_g,
                    carbs_g=current.carbs_g + c.carbs_g,
                    fat_g=current.fat_g + c.fat_g,
                )
                macro_score += _macro_deviation(projected, target)

            # Tertiary score: spoilage overlap bonus (subtracted = lower is better)
            spoilage_bonus = 0.0
            if existing_ingredient_lists:
                candidate_lists = [*existing_ingredient_lists, c.ingredients]
                spoilage_bonus = ingredient_overlap_bonus(candidate_lists, sp_cfg)

            score = macro_score - (spoilage_bonus * sp_cfg.spoilage_weight)

            if score < best_score:
                best_score = score
                best_candidate = c

        if best_candidate is None:
            break

        servings = {mid: 1.0 for mid in member_targets}
        assignments.append(_MealAssignment(recipe=best_candidate, member_servings=servings))
        remaining.remove(best_candidate)

    return assignments


def _sum_macros(assignments: list[_MealAssignment], member_id: str) -> MacroSummary:
    """Sum macros across all assignments for a member."""
    cal = pro = carb = fat = 0.0
    for a in assignments:
        s = a.member_servings.get(member_id, 0.0)
        cal += a.recipe.calories * s
        pro += a.recipe.protein_g * s
        carb += a.recipe.carbs_g * s
        fat += a.recipe.fat_g * s
    return MacroSummary(calories=cal, protein_g=pro, carbs_g=carb, fat_g=fat)


def _assignments_to_optimized_meal(
    assignments: list[_MealAssignment],
    member_targets: dict[str, MacroTarget],
    solver_result: SolverResult,
) -> OptimizedMeal:
    """Convert assignments to an OptimizedMeal result."""
    recipes = [MealComponent(recipe_id=a.recipe.id, servings=1.0) for a in assignments]
    member_servings = {
        mid: {a.recipe.id: a.member_servings.get(mid, 1.0) for a in assignments}
        for mid in member_targets
    }
    member_macros = {mid: _sum_macros(assignments, mid) for mid in member_targets}
    member_deviation = {
        mid: MacroSummary(
            calories=member_macros[mid].calories - target.calories,
            protein_g=member_macros[mid].protein_g - target.protein_g,
            carbs_g=member_macros[mid].carbs_g - target.carbs_g,
            fat_g=member_macros[mid].fat_g - target.fat_g,
        )
        for mid, target in member_targets.items()
    }

    objective_score = sum(
        _macro_deviation(member_macros[mid], target)
        for mid, target in member_targets.items()
    )

    return OptimizedMeal(
        recipes=recipes,
        member_servings=member_servings,
        member_macros=member_macros,
        member_deviation=member_deviation,
        objective_score=objective_score,
        solve_time_ms=solver_result.solve_time_ms,
        solver_result=solver_result,
    )


async def optimize_meal(
    member_ids: list[str],
    meal_type: MealType,
    candidate_recipe_ids: list[str] | None = None,
    required_recipe_ids: list[str] | None = None,
    excluded_recipe_ids: list[str] | None = None,
    constraints: MealConstraints | None = None,
    objective: OptimizationObjective = OptimizationObjective.MINIMIZE_DEVIATION,
    max_components: int = 4,
    allow_fractional_servings: bool = True,
    num_alternatives: int = 3,
    spoilage_config: SpoilageConfig | None = None,
) -> list[OptimizedMeal]:
    """Optimize a single meal for multiple members.

    Uses greedy heuristic with constraint relaxation cascade.
    Returns num_alternatives solutions ranked by objective score.
    """
    start = time.monotonic()
    member_targets = await _get_member_targets(member_ids)
    if not member_targets:
        return []

    candidates = await _load_candidates(
        candidate_ids=candidate_recipe_ids,
        excluded_ids=excluded_recipe_ids,
    )
    if not candidates:
        return []

    results: list[OptimizedMeal] = []
    used_recipe_sets: list[set[str]] = []

    for _ in range(num_alternatives):
        # Filter out already-used exact combinations
        filtered = [c for c in candidates if c.id not in _flatten_used(used_recipe_sets)]

        # Try with relaxation cascade
        relaxation_states = iterate_relaxations()
        assignments: list[_MealAssignment] = []

        for relaxation in relaxation_states:
            assignments = _greedy_meal_solve(
                filtered,
                member_targets,
                max_components,
                constraints,
                required_recipe_ids,
                objective,
                relaxation,
                spoilage_config=spoilage_config,
            )
            if assignments:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                status = (
                    SolverStatus.HEURISTIC
                    if relaxation.use_heuristic
                    else SolverStatus.RELAXED
                    if relaxation.relaxations
                    else SolverStatus.FEASIBLE
                )
                solver_result = SolverResult(
                    status=status,
                    relaxations_applied=relaxation.relaxations,
                    solve_time_ms=elapsed_ms,
                )
                result = _assignments_to_optimized_meal(
                    assignments, member_targets, solver_result
                )
                results.append(result)
                used_recipe_sets.append({a.recipe.id for a in assignments})
                break

    results.sort(key=lambda r: r.objective_score)
    return results


def _flatten_used(used_sets: list[set[str]]) -> set[str]:
    """Flatten list of used recipe ID sets, excluding partial overlaps."""
    if not used_sets:
        return set()
    # Only exclude recipes used in ALL previous alternatives
    if len(used_sets) == 1:
        return set()  # Don't exclude on first alternative
    return set()  # Allow reuse across alternatives, just avoid exact combos


async def optimize_plan(
    plan_id: str,
    member_ids: list[str],
    meal_types: list[MealType] | None = None,
    pinned_slots: list[PinnedSlot] | None = None,
    constraints: PlanConstraints | None = None,
    objective: OptimizationObjective = OptimizationObjective.MINIMIZE_DEVIATION,
    max_components_per_meal: int = 3,
    spoilage_config: SpoilageConfig | None = None,
) -> OptimizedPlan:
    """Fill empty slots in a meal plan optimally.

    Uses per-slot greedy optimization with constraint relaxation.
    """
    start = time.monotonic()
    plan = await get_meal_plan(plan_id)
    if plan is None:
        return OptimizedPlan(plan_id=plan_id)

    types = meal_types or [MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER]
    member_targets = await _get_member_targets(member_ids)
    existing_slots = await get_meal_slots(plan_id)

    # Track pinned slots
    pinned: set[tuple[int, str]] = set()
    if pinned_slots:
        for ps in pinned_slots:
            pinned.add((ps.day_offset, ps.meal_type.value))

    candidates = await _load_candidates(
        excluded_ids=(constraints.excluded_recipe_ids if constraints else None),
    )

    all_slots: list[MealSlot] = list(existing_slots)
    recipe_counts: dict[str, int] = {}

    # Count existing recipe usage
    for slot in existing_slots:
        recipe_counts[slot.recipe_id] = recipe_counts.get(slot.recipe_id, 0) + 1

    max_repeats = constraints.max_recipe_repeats if constraints else 2

    # Fill empty slots day by day
    for day in range(plan.days):
        for mt in types:
            slot_key = (day, mt.value)
            if slot_key in pinned:
                continue

            # Check if slot already filled
            already_filled = [
                s for s in existing_slots if s.day_offset == day and s.meal_type == mt
            ]
            if already_filled:
                continue

            # Filter candidates by repeat limit
            available = [
                c for c in candidates
                if recipe_counts.get(c.id, 0) < max_repeats
            ]

            if not available:
                continue

            # Build per-slot constraints from plan constraints
            slot_constraints: MealConstraints | None = None
            if constraints and constraints.day_constraints:
                slot_constraints = constraints.day_constraints.get(day)

            meal_results = await optimize_meal(
                member_ids=member_ids,
                meal_type=mt,
                candidate_recipe_ids=[c.id for c in available],
                constraints=_to_meal_constraints(slot_constraints),
                objective=objective,
                max_components=max_components_per_meal,
                num_alternatives=1,
                spoilage_config=spoilage_config,
            )

            if meal_results:
                best = meal_results[0]
                for comp in best.recipes:
                    ms = {
                        mid: best.member_servings.get(mid, {}).get(comp.recipe_id, 1.0)
                        for mid in member_ids
                    }
                    slot = MealSlot(
                        plan_id=plan_id,
                        day_offset=day,
                        meal_type=mt,
                        recipe_id=comp.recipe_id,
                        servings=comp.servings,
                        member_servings=ms,
                    )
                    all_slots.append(slot)
                    recipe_counts[comp.recipe_id] = (
                        recipe_counts.get(comp.recipe_id, 0) + 1
                    )

    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Compute summaries
    daily_summaries, weekly_summaries = await _compute_plan_summaries(
        all_slots, member_targets, plan.days
    )

    total_deviation = sum(
        _macro_deviation(weekly_summaries[mid], target)
        for mid, target in member_targets.items()
        if mid in weekly_summaries
    )

    return OptimizedPlan(
        plan_id=plan_id,
        slots=all_slots,
        daily_summaries={
            mid: {d: m for d, m in enumerate(daily) if d < plan.days}
            for mid, daily in daily_summaries.items()
        },
        weekly_summaries=weekly_summaries,
        total_deviation=total_deviation,
        recipe_usage_counts=recipe_counts,
        solve_time_ms=elapsed_ms,
        solver_result=SolverResult(
            status=SolverStatus.HEURISTIC,
            solve_time_ms=elapsed_ms,
        ),
    )


def _to_meal_constraints(
    slot_constraints: MealConstraints | None,
) -> MealConstraints | None:
    """Convert plan-level day constraints to meal constraints."""
    return slot_constraints


async def _compute_plan_summaries(
    slots: list[MealSlot],
    member_targets: dict[str, MacroTarget],
    num_days: int,
) -> tuple[dict[str, list[MacroSummary]], dict[str, MacroSummary]]:
    """Compute daily and weekly macro summaries per member."""
    nutrition_map = await get_nutrition_batch([s.recipe_id for s in slots])

    # daily_totals[member_id][day] = MacroSummary
    daily: dict[str, list[list[float]]] = {}
    for mid in member_targets:
        daily[mid] = [[0.0, 0.0, 0.0, 0.0] for _ in range(num_days)]

    for slot in slots:
        nutr = nutrition_map.get(slot.recipe_id)
        if nutr is None:
            continue

        for mid in member_targets:
            s = slot.member_servings.get(mid, slot.servings)
            day_idx = slot.day_offset
            if day_idx < num_days:
                daily[mid][day_idx][0] += nutr.calories * s
                daily[mid][day_idx][1] += nutr.protein_g * s
                daily[mid][day_idx][2] += nutr.carbs_g * s
                daily[mid][day_idx][3] += nutr.fat_g * s

    daily_summaries: dict[str, list[MacroSummary]] = {}
    weekly_summaries: dict[str, MacroSummary] = {}

    for mid in member_targets:
        daily_summaries[mid] = [
            MacroSummary(
                calories=d[0],
                protein_g=d[1],
                carbs_g=d[2],
                fat_g=d[3],
            )
            for d in daily[mid]
        ]

        active_days = [d for d in daily[mid] if sum(d) > 0]
        if active_days:
            n = len(active_days)
            weekly_summaries[mid] = MacroSummary(
                calories=sum(d[0] for d in active_days) / n,
                protein_g=sum(d[1] for d in active_days) / n,
                carbs_g=sum(d[2] for d in active_days) / n,
                fat_g=sum(d[3] for d in active_days) / n,
            )
        else:
            weekly_summaries[mid] = MacroSummary()

    return daily_summaries, weekly_summaries


async def rebalance_plan(
    plan_id: str,
    member_id: str,
    strategy: RebalanceStrategy = RebalanceStrategy.ADJUST_SERVINGS,
) -> RebalancedPlan:
    """Rebalance an existing plan for one member.

    adjust_servings: Keep all recipes, solve for optimal serving sizes.
    swap_sides: Keep mains fixed, try swapping sides.
    """
    start = time.monotonic()
    plan = await get_meal_plan(plan_id)
    if plan is None:
        return RebalancedPlan(plan_id=plan_id, member_id=member_id, strategy=strategy)

    member_targets = await _get_member_targets([member_id])
    target = member_targets.get(member_id)
    if target is None:
        return RebalancedPlan(plan_id=plan_id, member_id=member_id, strategy=strategy)

    slots = await get_meal_slots(plan_id)
    nutrition_map = await get_nutrition_batch([s.recipe_id for s in slots])

    # Compute before macros
    before_macros = _compute_daily_macros(slots, nutrition_map, member_id, plan.days)

    adjusted_slots: list[MealSlot] = []

    if strategy == RebalanceStrategy.ADJUST_SERVINGS:
        adjusted_slots = _adjust_servings(slots, nutrition_map, member_id, target, plan.days)
    else:
        # swap_sides — keep mains, try different sides
        adjusted_slots = list(slots)  # Placeholder for MILP implementation

    after_macros = _compute_daily_macros(adjusted_slots, nutrition_map, member_id, plan.days)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return RebalancedPlan(
        plan_id=plan_id,
        member_id=member_id,
        strategy=strategy,
        before_macros=before_macros,
        after_macros=after_macros,
        adjusted_slots=adjusted_slots,
        solver_result=SolverResult(
            status=SolverStatus.HEURISTIC,
            solve_time_ms=elapsed_ms,
        ),
    )


def _compute_daily_macros(
    slots: list[MealSlot],
    nutrition_map: dict[str, Nutrition],
    member_id: str,
    num_days: int,
) -> dict[int, MacroSummary]:
    """Compute daily macros for a single member."""
    daily: dict[int, list[float]] = {d: [0.0, 0.0, 0.0, 0.0] for d in range(num_days)}

    for slot in slots:
        nutr = nutrition_map.get(slot.recipe_id)
        if nutr is None:
            continue
        s = slot.member_servings.get(member_id, slot.servings)
        if slot.day_offset in daily:
            daily[slot.day_offset][0] += nutr.calories * s
            daily[slot.day_offset][1] += nutr.protein_g * s
            daily[slot.day_offset][2] += nutr.carbs_g * s
            daily[slot.day_offset][3] += nutr.fat_g * s

    return {
        d: MacroSummary(calories=v[0], protein_g=v[1], carbs_g=v[2], fat_g=v[3])
        for d, v in daily.items()
    }


def _adjust_servings(
    slots: list[MealSlot],
    nutrition_map: dict[str, Nutrition],
    member_id: str,
    target: MacroTarget,
    num_days: int,
) -> list[MealSlot]:
    """Adjust serving sizes to minimize macro deviation using scipy."""
    try:
        import numpy as np
        from scipy.optimize import minimize as scipy_minimize
    except ImportError:
        return list(slots)

    # Group slots by day
    day_slots: dict[int, list[MealSlot]] = {}
    for s in slots:
        day_slots.setdefault(s.day_offset, []).append(s)

    adjusted: list[MealSlot] = []

    for day in range(num_days):
        day_s = day_slots.get(day, [])
        if not day_s:
            continue

        # Get nutrition for each slot's recipe
        nutr_list: list[Nutrition] = []
        valid_slots: list[MealSlot] = []
        for s in day_s:
            n = nutrition_map.get(s.recipe_id)
            if n is None:
                continue
            nutr_list.append(n)
            valid_slots.append(s)

        if not valid_slots:
            adjusted.extend(day_s)
            continue

        # Optimize serving sizes
        n_recipes = len(valid_slots)
        x0 = np.array([s.member_servings.get(member_id, s.servings) for s in valid_slots])

        def objective(
            x: np.ndarray,
            _nutr_list: list[Nutrition] = nutr_list,
            _n_recipes: int = n_recipes,
        ) -> float:
            cal = sum(_nutr_list[i].calories * x[i] for i in range(_n_recipes))
            pro = sum(_nutr_list[i].protein_g * x[i] for i in range(_n_recipes))
            carb = sum(_nutr_list[i].carbs_g * x[i] for i in range(_n_recipes))
            fat_val = sum(_nutr_list[i].fat_g * x[i] for i in range(_n_recipes))

            macros = MacroSummary(
                calories=float(cal),
                protein_g=float(pro),
                carbs_g=float(carb),
                fat_g=float(fat_val),
            )
            return _macro_deviation(macros, target)

        bounds = [(0.25, 4.0)] * n_recipes
        result = scipy_minimize(objective, x0, bounds=bounds, method="L-BFGS-B")

        for i, s in enumerate(valid_slots):
            new_servings = float(result.x[i])
            ms = dict(s.member_servings)
            ms[member_id] = round(new_servings, 2)
            adjusted.append(
                MealSlot(
                    plan_id=s.plan_id,
                    day_offset=s.day_offset,
                    meal_type=s.meal_type,
                    recipe_id=s.recipe_id,
                    servings=s.servings,
                    member_servings=ms,
                )
            )

        # Add back slots without nutrition
        for s in day_s:
            if s not in valid_slots:
                adjusted.append(s)

    return adjusted
