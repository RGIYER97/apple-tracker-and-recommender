# 🍎 Apple Tracker & Discovery Engine

A personal Streamlit dashboard for logging, analyzing, and discovering apple varieties. Tracks your tasting history in Google Sheets, enriches entries with professional notes and [AppleRankings.com](https://applerankings.com) scores, and uses an LLM to recommend what to try next — with store locations specific to South Orange, NJ and the Flatiron / Union Square area of Manhattan.

---

## Features

### 📊 Dashboard
- Score distribution histogram
- Average score by store / source
- Score over time with LOWESS trend line
- Taste Fingerprint radar chart (Sweet · Tart · Crisp · Juicy · Floral · Earthy · Spiced · Bitter), weighted by your scores
- Top flavor keywords bar chart
- World origin map shaded by average score

### 🍎 My Collection
- Sortable table of all logged varieties
- **Enrich All Varieties** — fetches a variety image, AppleRankings.com score & review, and professional tasting notes (taste/flavor/aroma only) for every entry, then writes results back to the sheet
- **Compare Varieties** — side-by-side score + radar chart for 2–3 varieties

### ➕ Add Entry
- Log a new variety with name, date, score, tasting notes, and source
- **Auto-fill** — one click looks up the variety's type (eating/cooking/cider), origin region, and country via LLM
- Pre-fill from wishlist when marking a variety as tried

### ✨ Recommendations
Three recommendation modes, all powered by OpenRouter:

| Mode | What it does |
|---|---|
| **AI Recommendations** | Analyses your top-rated apples and tasting notes to suggest new varieties with store locations |
| **Smart Match (AR + Your Taste)** | Finds varieties where your score and AppleRankings.com agree, then recommends untried AR-catalog varieties with similar profiles |
| **Find Me Something Like…** | Pick any variety from your collection; get 3 closely matched alternatives |

All recommendations include flavor profile, tasting note tags, price estimate, and where to find the variety near you.

### 📋 Wishlist
- Save recommendations to a persistent wishlist (Google Sheets tab)
- Mark as Tried to pre-fill the Add Entry form
- Remove entries you've decided against

### 🛒 Store Planner
Pick a store and month to generate a three-section visit plan:
- **From Your Wishlist** — wishlist items in season at that store type
- **Favorites to Re-stock** — your 8+/10 varieties available now
- **Varieties to Scout** — untried varieties available now, sorted by rarity (shortest season first)

Includes a **Coming up** expander (new arrivals in the next 2 months) and a copyable plain-text shopping list.

**Pre-configured stores** — grouped by proximity:
- Within 5 miles of South Orange, NJ (Whole Foods Short Hills, Trader Joe's Millburn, Kings Maplewood, ShopRite, Stop & Shop, ALDI)
- Within 5 miles of Flatiron, Manhattan (Union Square Greenmarket ★★, Whole Foods Union Square, Trader Joe's 14th St, Fairway)
- NJ day-trip orchards (Demarest Farms, Alstede Farms, Terhune Orchards, Battleview Orchards, Melick's Town Farm)
- Union Square Greenmarket vendors (Locust Grove, Fishkill Farms, Samascott Orchards, Wilklow Orchards)

---

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd "Apple Tracker"
pip install -r requirements.txt
```

### 2. Google Sheets

1. [Google Cloud Console](https://console.cloud.google.com/) → enable **Sheets API** and **Drive API**
2. Create a **Service Account** → download the JSON key file
3. Create a Google Sheet with a tab named `apples` (or any name — the app scans for an `Apple Variety` header)
4. Share the sheet with the service account email (Editor role)

Required columns in your sheet (the app will add enrichment columns automatically):

| Column | Required | Notes |
|---|---|---|
| Apple Variety | ✅ | Can also be named "Apple Type" |
| Date | | Format: `Month YYYY` (e.g. `October 2024`) |
| From Where | | Store or source |
| Score | ✅ | Numeric 1–10 |
| Tasting Notes | | Your personal notes |

### 3. Environment variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
# Required
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/your/service-account-key.json
APPLE_SPREADSHEET_ID=<your-sheet-id-from-the-url>

# Required for AI features (recommendations, auto-fill, enrichment)
OPENROUTER_API_KEY=sk-or-...

# Required for web enrichment (images, tasting notes, AR scores)
TAVILY_API_KEY=tvly-...

# Optional
APPLE_SHEET_NAME=apples          # default tab name
OPENROUTER_MODEL=openai/gpt-4.1-mini   # default model
```

Get your keys:
- **OpenRouter**: [openrouter.ai](https://openrouter.ai) — routes to GPT-4.1-mini by default
- **Tavily**: [tavily.com](https://tavily.com) — used for image search and tasting note extraction

### 4. Run

```bash
streamlit run app.py
```

---

## Architecture

```
app.py              — Streamlit UI, all 6 tabs, CSS design tokens
sheets.py           — Google Sheets I/O (load, enrich, append, wishlist)
enrichment.py       — Tavily web search + LLM tasting note extraction + applerankings.com scraper
recommendations.py  — OpenRouter recommendation prompts (standard, AR-smart, similar-variety)
planner.py          — Season data for 70 varieties + store visit plan logic
```

### Data flow

```
Google Sheets  ──load──▶  app.py (cached 5 min)
                               │
               ┌───────────────┼────────────────────┐
               ▼               ▼                    ▼
          enrichment.py  recommendations.py     planner.py
          (Tavily + AR)   (OpenRouter LLM)    (local logic,
               │               │               no API call)
               ▼               ▼
          sheets.py ◀─ write back results
```

### Enrichment columns written to the sheet

| Column | Source | Notes |
|---|---|---|
| Image | Tavily image search | Stored as `=IMAGE(url, 1)` formula |
| Prof. Tasting Notes | Tavily → LLM extract | Taste/flavor/aroma only |
| Notes Source | — | `web` or `LLM` |
| AR Score | applerankings.com | 1–100 numeric score |
| AR Notes | applerankings.com | Tagline + tier + review snippet |
| Type | OpenRouter | `eating` / `cooking` / `cider` / `dual-purpose` |
| Origin | OpenRouter | Region (e.g. Pacific Northwest) |
| Country | OpenRouter | Country of origin |

---

## Design

**Palette:** warm off-white background `#FAF7F2` · deep forest-green sidebar `#1A3B2A` · red-apple accent `#C0392B`

**Flavor axes (Taste Fingerprint radar):**
Sweet · Tart · Crisp · Juicy · Floral · Earthy · Spiced · Bitter

Each axis is scored by keyword matching against tasting notes; the radar is weighted by score so higher-rated apples pull the shape more strongly.

---

## Caching

- Sheet data: cached 5 minutes (`st.cache_data(ttl=300)`)
- Wishlist: cached 60 seconds
- AI recommendations: persisted to `recommendations_cache.json` (survives page reloads)
- Smart Match recommendations: persisted to `smart_recommendations_cache.json`
