# Code Reference

This document outlines the core public APIs and functions within the `yes_chef_mcp.core` module, grouped by domain.

## Domain: Meal Planning (`core.planner`)

* **`create_meal_plan`**
  * *Description*: Creates a new empty meal plan scaffold for a family.
  * *Inputs*: `family_id` (str), `name` (str), `start_date` (date), `days` (int, default=7).
  * *Returns*: `MealPlan` object.

* **`add_meal_slot`**
  * *Description*: Assigns a recipe to a specific day and meal type within a plan.
  * *Inputs*: `plan_id` (str), `day_offset` (int), `meal_type` (MealType), `recipe_id` (str), `servings` (float, default=1.0), `member_servings` (dict[str, float] | None).
  * *Returns*: `MealSlot` object.

* **`get_meal_slots`**
  * *Description*: Retrieves all assigned meal slots for a plan, optionally filtered by a specific day offset.
  * *Inputs*: `plan_id` (str), `day_offset` (int | None).
  * *Returns*: `list[MealSlot]`.

## Domain: Recipe Management (`core.recipe_store`)

* **`upsert_recipe`**
  * *Description*: Inserts or updates a recipe and its structured ingredients in the database.
  * *Inputs*: `recipe` (Recipe dataclass).
  * *Returns*: `None`.

* **`list_recipes`**
  * *Description*: Retrieves recipes based on optional filters like category or tags.
  * *Inputs*: `family_id` (str | None), `category` (RecipeCategory | None), `tags` (list[str] | None), `limit` (int, default=50), `offset` (int, default=0).
  * *Returns*: `list[Recipe]`.

* **`get_nutrition`**
  * *Description*: Fetches the stored macronutrient and micronutrient data for a specific recipe.
  * *Inputs*: `recipe_id` (str).
  * *Returns*: `Nutrition | None`.

## Domain: Search (`core.search`)

* **`hybrid_search`**
  * *Description*: Performs a Reciprocal Rank Fusion (RRF) search combining FTS5 keyword matching (boosted for exact terms) and `sqlite-vec` semantic vector similarity.
  * *Inputs*: `query` (str), `embedding` (list[float] | None), `category` (RecipeCategory | None), `tags` (list[str] | None), `max_results` (int), `min_confidence` (float).
  * *Returns*: `RecipeSearchPage` object containing a list of `RecipeSearchHit`.

* **`macro_distance_search`**
  * *Description*: Finds recipes closest to specific target macros using a weighted Euclidean distance calculation.
  * *Inputs*: `target_calories` (float | None), `target_protein_g` (float | None), `target_carbs_g` (float | None), `target_fat_g` (float | None), `category` (RecipeCategory | None), `max_results` (int), `tolerance_pct` (float).
  * *Returns*: `RecipeSearchPage` object.

## Domain: Macro Optimization (`core.optimizer`)

* **`optimize_meal`**
  * *Description*: Finds the optimal combination of recipes and per-member serving sizes for a single meal to minimize deviation from active macro targets.
  * *Inputs*: `member_ids` (list[str]), `meal_type` (MealType), `candidate_recipe_ids` (list[str] | None), `max_components` (int), `num_alternatives` (int).
  * *Returns*: `list[OptimizedMeal]` ranked by their objective score.

* **`optimize_plan`**
  * *Description*: Autonomously fills empty slots in an entire meal plan, balancing macros and preventing excessive recipe repetition across the week.
  * *Inputs*: `plan_id` (str), `member_ids` (list[str]), `meal_types` (list[MealType] | None), `max_components_per_meal` (int).
  * *Returns*: `OptimizedPlan` containing the full schedule, daily summaries, and solver metadata.

## Domain: Meal Composition (`core.meal_composer`)

* **`compose_meal`**
  * *Description*: Ad-hoc composition of a meal from multiple recipe components, computing aggregate nutrition and comparing it against a member's macro targets.
  * *Inputs*: `components` (list[MealComponent]), `member_id` (str | None), `target_name` (str | None).
  * *Returns*: `MealComposition` object including totals and macro gap suggestions.

* **`suggest_complements`**
  * *Description*: Suggests additional recipes (e.g., sides) that best fill the macro gap between an existing partial meal and a member's target.
  * *Inputs*: `existing_recipe_ids` (list[str]), `existing_servings` (list[float]), `member_id` (str), `complement_category` (RecipeCategory).
  * *Returns*: `list[ComplementSuggestion]`.

## Domain: Grocery Generation (`core.grocery`)

* **`generate_grocery_list`**
  * *Description*: Consolidates all ingredients from a meal plan into a single list, scaling quantities by serving sizes, guessing store aisles, and optionally excluding common pantry staples.
  * *Inputs*: `plan_id` (str), `merge_similar` (bool, default=True), `exclude_pantry` (bool, default=True).
  * *Returns*: `GroceryList` object containing a list of `GroceryItem`.
