# Architecture Context (C4 Level 1)

This diagram illustrates the high-level system context of the `yes-chef-mcp` application. It shows the primary users, the core system, and external dependencies.

````mermaid
graph TD
    User((Home Chef))
    Claude[Claude Desktop / Goose / AI Client]
    WebBrowser[Web Browser]
    
    subgraph YesChefSystem [Yes Chef MCP Server]
        App[FastAPI / FastMCP Application]
        DB[(SQLite / sqlite-vec)]
    end
    
    Mealie[Mealie API]
    AnyList[AnyList API]
    NutritionAPI[Nutrition Data Providers]
    
    User -->|Uses natural language to plan meals| Claude
    User -->|Interacts with UI components| WebBrowser
    
    Claude -->|Executes Tools via MCP HTTP| App
    WebBrowser -->|Fetches Static Assets & REST API| App
    
    App -->|Reads/Writes Recipes, Plans, Embeddings| DB
    
    App -->|Imports Recipes| Mealie
    App -->|Exports Grocery Lists| AnyList
    App -->|Fetches Macro Data| NutritionAPI
````

## Actors and Systems

* **Home Chef (User):** The primary user of the system who wants to plan meals, optimize their macronutrient intake, and generate grocery lists.
* **Claude / AI Client:** An LLM-powered client that connects to the system via the Model Context Protocol (MCP). It acts as the intelligent agent translating the user's natural language requests into specific tool calls (e.g., `optimize_plan`, `search_recipes_by_macros`).
* **Web Browser:** The interface used to render the interactive "MCP Apps" views (React components served by FastAPI) directly to the user. This allows for rich interactions like adjusting macro sliders or checking off grocery items.
* **Yes Chef MCP Server:** The core backend system. It combines a FastAPI web server for REST/Static asset delivery with a FastMCP server for tool exposure. It contains the core optimization logic, search algorithms, and data access layers.
* **SQLite (Database):** The local, embedded database. It stores structured relational data (recipes, plans, targets), full-text search indexes (`recipes_fts`), and vector embeddings (`vec_recipes`) via the `sqlite-vec` extension.
* **External Integrations:**
  * **Mealie API:** A potential source for importing existing recipe catalogs.
  * **AnyList API:** A potential target for syncing generated grocery lists.
  * **Nutrition Data Providers:** External services used by the data ingestion pipeline to enrich imported recipes with accurate macronutrient breakdowns.
