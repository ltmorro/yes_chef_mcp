# Cookbook

This cookbook provides practical examples of how to use the `yes_chef_mcp.core` APIs to achieve common meal planning goals.

---

### Recipe 1: Create and Populate a Meal Plan Manually

**The Goal:** Initialize a new 7-day meal plan for your family and manually schedule a specific recipe for Monday's breakfast.

**The Prerequisites:** 
* An existing `family_id`
* The `recipe_id` of the recipe you want to add

```python
from datetime import date
from yes_chef_mcp.core.planner import create_meal_plan, add_meal_slot
from yes_chef_mcp.core.models import MealType

async def setup_weekly_plan():
    # 1. Create the plan scaffold
    plan = await create_meal_plan(
        family_id="my-family-123",
        name="Spring Week 1",
        start_date=date(2026, 4, 6),
        days=7
    )
    print(f"Created plan: {plan.id}")

    # 2. Add a recipe to Day 0 (Monday) Breakfast
    # This assumes we want 2 total servings, split evenly among family members
    slot = await add_meal_slot(
        plan_id=plan.id,
        day_offset=0,
        meal_type=MealType.BREAKFAST,
        recipe_id="oatmeal-001",
        servings=2.0
    )
    print(f"Scheduled {slot.recipe_id} for Day {slot.day_offset}")

    return plan
```

---

### Recipe 2: Optimize a Single Meal for Specific Members

**The Goal:** Ask the optimizer engine to find the best dinner combination that hits the active macro targets for two specific family members.

**The Prerequisites:** 
* The database must be populated with recipes and nutrition data.
* The members must have active `MacroTarget` records in the database.

```python
from yes_chef_mcp.core.optimizer import optimize_meal
from yes_chef_mcp.core.models import MealType

async def find_optimal_dinner():
    # Ask the solver for the best dinner combination (max 3 components)
    # It will return the top 1 alternative
    results = await optimize_meal(
        member_ids=["user-1", "user-2"],
        meal_type=MealType.DINNER,
        max_components=3,
        num_alternatives=1
    )

    if not results:
        print("No feasible combinations found.")
        return

    best_option = results[0]
    print(f"Best Option Objective Score: {best_option.objective_score:.2f}")
    
    # List the components and their suggested servings
    for comp in best_option.recipes:
        print(f"- Recipe ID: {comp.recipe_id}")
        print(f"  Total Servings: {comp.servings}")
        
        # Show per-member serving breakdowns
        for mid, member_recipes in best_option.member_servings.items():
            srv = member_recipes.get(comp.recipe_id, 0)
            print(f"    Member {mid} eats: {srv} servings")
```

---

### Recipe 3: Suggest a Side Dish to Hit Macros

**The Goal:** You already know you want to eat a specific main course, but you need a side dish that perfectly fills the remaining macro gap for your daily target.

**The Prerequisites:**
* The `recipe_id` of your main course.
* Your `member_id` with an active macro target.

```python
from yes_chef_mcp.core.meal_composer import suggest_complements
from yes_chef_mcp.core.models import RecipeCategory

async def find_perfect_side():
    main_course_id = "grilled-chicken-001"
    my_member_id = "user-1"
    
    # We are eating 1 serving of the main course
    suggestions = await suggest_complements(
        existing_recipe_ids=[main_course_id],
        existing_servings=[1.0],
        member_id=my_member_id,
        complement_category=RecipeCategory.SIDE,
        max_results=3
    )
    
    print("Top Side Dish Suggestions:")
    for i, rec in enumerate(suggestions, 1):
        print(f"{i}. {rec.recipe_name}")
        print(f"   Gap Fill: Adds {rec.projected_totals.protein_g}g Protein")
        print(f"   Remaining Deviation: {rec.projected_deviation.calories} cal")
```

---

### Recipe 4: Generate a Smart Grocery List

**The Goal:** After building a meal plan, generate a consolidated shopping list that merges similar ingredients and excludes basic pantry staples like salt and oil.

**The Prerequisites:**
* An existing `plan_id` that has recipes assigned to its slots.

```python
from yes_chef_mcp.core.grocery import generate_grocery_list

async def get_shopping_list(plan_id: str):
    # Generate the list, automatically scaling ingredient quantities 
    # based on the serving sizes in the plan slots.
    grocery_list = await generate_grocery_list(
        plan_id=plan_id,
        merge_similar=True,
        exclude_pantry=True
    )
    
    # Group the output by aisle/category
    current_category = None
    for item in grocery_list.items:
        if item.category != current_category:
            print(f"\n--- {item.category.upper()} ---")
            current_category = item.category
            
        unit_str = f" {item.unit}" if item.unit else ""
        print(f"[ ] {item.quantity}{unit_str} {item.name}")
```
