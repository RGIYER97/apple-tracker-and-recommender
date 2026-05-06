# Apple Tracker — Claude Code Guide

Personal Streamlit app for tracking and discovering apple varieties. Python + Streamlit, Google Sheets backend, OpenRouter LLM, Tavily web search.

## Module map

| File | Responsibility |
|---|---|
| `app.py` | All UI — 6 tabs, CSS tokens, session state, chart helpers |
| `sheets.py` | Google Sheets read/write (load collection, enrich, append, wishlist) |
| `enrichment.py` | Tavily search → tasting note extraction → applerankings.com scraper |
| `recommendations.py` | LLM prompts and callers: standard recs, AR-smart recs, similar-variety recs |
| `planner.py` | Season data for ~70 varieties + store visit plan logic (no API calls) |

## Design tokens (app.py)

```python
BG_APP     = "#FAF7F2"   # warm off-white
BG_CARD    = "#FFFFFF"
BG_SIDEBAR = "#1A3B2A"   # deep forest green
ACCENT     = "#C0392B"   # red apple
TEXT_MAIN  = "#1A1208"
TEXT_MUTED = "#6B5B4E"
GRID       = "#EDE5DA"
```

Do not introduce new colour values. All charts use `PLOT_LAYOUT` and `apply_axes()`.

## Sheet schema

Primary tab: `apples` (or whatever `APPLE_SHEET_NAME` is set to).

Required columns: `Apple Variety`, `Score` (1–10).
Optional: `Date` (format `Month YYYY`), `From Where`, `Tasting Notes`.
Enrichment columns (written by the app): `Image`, `Prof. Tasting Notes`, `Notes Source`, `AR Score`, `AR Notes`.
Auto-tag columns: `Type`, `Origin`, `Country`.

`sheets.py` detects the header row dynamically via `_find_header()` — do not assume a fixed row number.

## Key patterns

**Session state keys used across tabs:**
- `recommendations` — main AI rec list (also persisted to `recommendations_cache.json`)
- `smart_recs` — AR-smart rec list (persisted to `smart_recommendations_cache.json`)
- `similar_recs` / `similar_to` — "Find Me Something Like" results
- `pinned_names` — set of variety names saved to wishlist
- `add_auto_name`, `add_tags`, `_prefill_source`, `prefill_from_rec` — Add Entry prefill flow

**Enrichment flow** (`enrichment.py`):
1. Tavily searches apple-specific sites (orangepippin.com, pomiferous.com) for tasting notes
2. `_extract_notes()` filters sentences: must pass boilerplate filter AND `_TASTE_PATTERN` (taste vocabulary required per sentence)
3. If the fast path yields nothing, `_llm_extract_notes()` synthesises from raw snippets — taste/flavor/aroma ONLY, no history or growing info
4. `_fetch_applerankings()` scrapes applerankings.com for a numeric score + review snippet

**Recommendation flow** (`recommendations.py`):
- `_STORE_TIERS` — the store priority list injected into every prompt; locations are specific to South Orange NJ and Flatiron Manhattan (★ = within 5 miles)
- `_REC_SCHEMA` — JSON schema all three rec functions share
- Three prompt builders: `_build_prompt` (standard), `_build_ar_smart_prompt` (AR + user correlation), `_build_similar_prompt` (similar variety)
- All return the same JSON array format; `add_images()` enriches with Tavily image URLs after the LLM call

**Planner** (`planner.py`):
- `APPLE_SEASONS` — ~70 varieties with `orchard` months, `market` months, `stores` tier (`all`/`premium`/`specialty`/`orchard-only`), and a short note
- `classify_store(name)` maps a store name to `orchard`, `farmers_market`, `premium`, `supermarket`, or `unknown`
- `plan_visit()` returns `{wishlist_hits, restock, scout}` — pure Python, no API calls
- `UNION_SQUARE_VENDORS` — four named orchard vendors displayed as a callout in the UI (Locust Grove, Fishkill Farms, Samascott, Wilklow)

## Location context

The user is based near **South Orange, NJ** (also near Harrison, NJ). They regularly shop in:
- South Orange / Maplewood / Millburn area (NJ)
- Flatiron District, Manhattan — especially Union Square Greenmarket (14th St & Broadway)

When adding new store references anywhere, use the ★ prefix for stores within ~5 miles of South Orange NJ or Flatiron Manhattan.

NJ day-trip orchards: Demarest Farms (Hillsdale), Alstede Farms (Chester), Terhune Orchards (Princeton), Battleview Orchards (Freehold), Melick's Town Farm (Oldwick).

## Flavor axes

Used for the Taste Fingerprint radar and keyword charts:

```python
FLAVOR_AXES = {
    "Sweet":   ["sweet", "sugar", "honey", "caramel", ...],
    "Tart":    ["tart", "tangy", "acidic", "sharp", ...],
    "Crisp":   ["crisp", "crunchy", "firm", ...],
    "Juicy":   ["juicy", "juice", "moist", ...],
    "Floral":  ["floral", "flower", "rose", "anise", ...],
    "Earthy":  ["earthy", "herbal", "grassy", "russet", ...],
    "Spiced":  ["spice", "cinnamon", "nutmeg", "vanilla", ...],
    "Bitter":  ["bitter", "astringent", "tannic", ...],
}
```

If you add a new axis, add it to `FLAVOR_AXES` in `app.py` and update the radar helper `_make_radar()`.

## Adding a new tab

1. Add a new variable to the `st.tabs(...)` call in `app.py`
2. Add a `with tab_xxx:` block near the bottom (before the sidebar block)
3. Keep heavy imports inside the `with` block to avoid slowing startup

## What NOT to do

- Do not change the Google Sheets column names — `sheets.py` maps them by exact string match
- Do not add non-taste content to `Prof. Tasting Notes` — the `_TASTE_PATTERN` filter and LLM prompt are intentionally strict about taste-only content
- Do not bypass `_find_header()` by hardcoding a row index
- Do not add new colour values outside the design tokens
- Do not store secrets in code — all keys go in `.env`
- Do not rename `APPLE_SEASONS` keys in `planner.py` without updating `_AR_SLUG_MAP` in `enrichment.py` (they use the same variety name conventions)

## Environment variables

```
GOOGLE_SERVICE_ACCOUNT_JSON   path to service account JSON key (required)
APPLE_SPREADSHEET_ID          Google Sheet ID from the URL (required)
APPLE_SHEET_NAME              tab name, default "apples" (optional)
OPENROUTER_API_KEY            required for all AI features
TAVILY_API_KEY                required for enrichment and rec images
OPENROUTER_MODEL              default "openai/gpt-4.1-mini" (optional)
```
