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
TEXT_MUTED = "#4A3728"   # warm dark brown — readable at small sizes
GRID       = "#D8CEBC"   # slightly darker warm grid — visible in charts
```

Do not introduce new colour values. All charts use `PLOT_LAYOUT` and `apply_axes()`.

`PLOT_LAYOUT` includes `font=dict(size=13)` as a base; `apply_axes()` sets explicit `tickfont` size 12 and `title_font` size 13 on both axes. Always call `apply_axes(fig)` after `fig.update_layout(**PLOT_LAYOUT)`.

## Sheet schema

Primary tab: `apples` (or whatever `APPLE_SHEET_NAME` is set to).

Required columns: `Apple Variety`, `Score` (1–10).
Optional: `Date` (format `Month YYYY`), `From Where`, `Tasting Notes`.
Enrichment columns (written by the app): `Image`, `Prof. Tasting Notes`, `Notes Source`, `AR Score`, `AR Notes`.
Auto-tag columns: `Type`, `Origin`, `Country`.

`sheets.py` detects the header row dynamically via `_find_header()` — do not assume a fixed row number.

## Key patterns

**Session state keys used across tabs:**
- `recommendations` — main AI rec list (persisted to `recommendations_cache.json`)
- `rec_generated_at` — ISO timestamp when main recs were generated
- `rec_entry_count` — `len(df)` at generation time; used for stale-cache detection
- `smart_recs` — AR-smart rec list (persisted to `smart_recommendations_cache.json`)
- `smart_generated_at` / `smart_entry_count` — same metadata for smart recs
- `similar_recs` / `similar_to` — "Find Me Something Like" results
- `pinned_names` — set of variety names saved to wishlist
- `add_auto_name`, `add_tags`, `_prefill_source`, `prefill_from_rec` — Add Entry prefill flow

**Cache file format** (`recommendations_cache.json`, `smart_recommendations_cache.json`):
```json
{
  "generated_at": "2026-05-05T22:00:00+00:00",
  "entry_count": 42,
  "recs": [ ... ]
}
```
Old flat-list format is handled by `_load_rec_cache()` for backward compatibility.

**Enrichment flow** (`enrichment.py`):
1. Tavily searches apple-specific sites (orangepippin.com, pomiferous.com) for tasting notes
2. `_extract_notes()` filters sentences: must pass boilerplate filter AND `_TASTE_PATTERN` (taste vocabulary required per sentence)
3. If the fast path yields nothing, `_llm_extract_notes()` synthesises from raw snippets — taste/flavor/aroma ONLY, no history or growing info
4. `_fetch_applerankings()` scrapes applerankings.com for a numeric score + review snippet

**Recommendation flow** (`recommendations.py`):
- `RecommendationError` — custom exception raised when `json.loads()` fails on the LLM response; caught in `app.py` and shown as `st.error` with a retry prompt
- `_STORE_TIERS` — the store priority list injected into every prompt; locations are specific to South Orange NJ and Flatiron Manhattan (★ = within 5 miles)
- `_REC_SCHEMA` — JSON schema all three rec functions share
- Three prompt builders: `_build_prompt` (standard), `_build_ar_smart_prompt` (AR + user correlation), `_build_similar_prompt` (similar variety)
- All return the same JSON array format; `add_ar_scores()` fetches real AR scores, then `add_images()` enriches with Tavily image URLs

**Stale cache banner** (`app.py`, Recommendations tab):
- After each generation, `rec_entry_count` is saved to the cache JSON and session state
- On tab render, if `rec_entry_count != len(df)`, an `st.info` banner prompts regeneration
- Same logic applied independently to smart recs via `smart_entry_count`

**Duplicate entry warning** (`app.py`, Add Entry tab):
- Triggered when `auto_name` is non-empty; checks `df["Apple Variety"]` case-insensitively
- Displayed via `st.warning` before the form, showing the existing score, date, and source
- User can still submit to log a second entry (useful for seasonal re-tastings)

**Dashboard — You vs. AR scatter** (`app.py`, tab_dash):
- Only rendered when `"AR Score"` column exists and has at least one numeric value
- Quadrant labels: "Both love it" (your ≥7, AR ≥70), "Your hidden gem", "Overhyped", "Both pass"
- Dashed crosshairs at score 7 / AR 70; Pearson correlation caption shown for ≥3 enriched varieties

**Planner** (`planner.py`):
- `APPLE_SEASONS` — ~70 varieties with `orchard` months, `market` months, `stores` tier (`all`/`premium`/`specialty`/`orchard-only`), and a short note
- `classify_store(name)` maps a store name to `orchard`, `farmers_market`, `premium`, `supermarket`, or `unknown`
- `plan_visit()` returns `{wishlist_hits, restock, scout}` — pure Python, no API calls
- `UNION_SQUARE_VENDORS` — four named orchard vendors displayed as a callout in the UI (Locust Grove, Fishkill Farms, Samascott, Wilklow)

**Sidebar in-season alert** (`app.py`, sidebar block):
- Calls `available_at(store_type, month)` for all four store types and unions the results
- Matches against `load_wishlist_data()` names (lowercased); shows count + up to 5 variety names
- Wrapped in `try/except` — never crashes the sidebar if planner data is missing

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
