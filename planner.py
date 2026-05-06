"""
Store visit planner: given a store and month, produces three lists —
wishlist items available now, top-rated favorites to re-stock, and
untried varieties worth scouting (sorted rarest-season-first).
"""
from __future__ import annotations
import pandas as pd

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# stores field meaning:
#   "all"          → common supermarkets carry it
#   "premium"      → Whole Foods / Wegmans / specialty chains
#   "specialty"    → farmers markets, orchard stores, ethnic/specialty
#   "orchard-only" → must go to an orchard
#
# orchard: months freshly harvested at US Northeast orchards
# market:  months typically findable in stores (CA storage / imports extend this)
APPLE_SEASONS: dict[str, dict] = {
    "ambrosia":         {"orchard": [9, 10],       "market": [10, 11, 12, 1, 2, 3],      "stores": "all",          "notes": "Widely available fall–spring"},
    "arkansas black":   {"orchard": [10, 11],      "market": [11, 12, 1, 2, 3],          "stores": "specialty",    "notes": "Heritage keeper; orchards & specialty"},
    "aura":             {"orchard": [7, 8],         "market": [7, 8],                     "stores": "orchard-only", "notes": "Very early; orchard direct only"},
    "autumn glory":     {"orchard": [9, 10],        "market": [10, 11, 12, 1],            "stores": "premium",      "notes": "Trader Joe's exclusive; fall–winter"},
    "blondee":          {"orchard": [8],             "market": [8, 9],                     "stores": "specialty",    "notes": "Early yellow; orchard stands & specialty"},
    "braeburn":         {"orchard": [10, 11],       "market": [10, 11, 12, 1, 2, 3],      "stores": "all",          "notes": "Good keeper; widely available fall–spring"},
    "cameo":            {"orchard": [10, 11],       "market": [10, 11, 12, 1, 2, 3],      "stores": "premium",      "notes": "Pacific NW; Wegmans / Whole Foods"},
    "candy crisp":      {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "specialty",    "notes": "Regional; orchard stores"},
    "cortland":         {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "all",          "notes": "Classic NE fall apple; short storage"},
    "cosmic crisp":     {"orchard": [10, 11],       "market": list(range(1, 13)),         "stores": "all",          "notes": "Year-round; excellent long-storage keeper"},
    "crimson gold":     {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "orchard-only", "notes": "Heirloom; orchards only"},
    "cripps pink":      {"orchard": [10, 11],       "market": [10, 11, 12, 1, 2, 3, 4],  "stores": "all",          "notes": "Pink Lady parent; fall through spring"},
    "empire":           {"orchard": [9, 10],        "market": [9, 10, 11, 12],            "stores": "all",          "notes": "NY state variety; good keeper through winter"},
    "envy":             {"orchard": [4, 5],          "market": list(range(1, 13)),         "stores": "all",          "notes": "NZ + WA grown; year-round"},
    "evercrisp":        {"orchard": [10, 11],       "market": [11, 12, 1, 2, 3, 4],       "stores": "premium",      "notes": "Excellent late-season keeper; Whole Foods"},
    "fuji":             {"orchard": [10, 11],       "market": list(range(1, 13)),         "stores": "all",          "notes": "Year-round staple; best Oct–Mar"},
    "gala":             {"orchard": [8, 9],          "market": list(range(1, 13)),         "stores": "all",          "notes": "Year-round staple"},
    "golden delicious": {"orchard": [9, 10],        "market": list(range(1, 13)),         "stores": "all",          "notes": "Year-round staple"},
    "golden russet":    {"orchard": [10, 11],       "market": [10, 11, 12],               "stores": "orchard-only", "notes": "Heritage heirloom; orchards only"},
    "goldrush":         {"orchard": [10, 11],       "market": [11, 12, 1, 2, 3],          "stores": "specialty",    "notes": "Outstanding late keeper; specialty & orchards"},
    "granny smith":     {"orchard": [10, 11],       "market": list(range(1, 13)),         "stores": "all",          "notes": "Year-round staple"},
    "green dragon":     {"orchard": [9, 10],        "market": [9, 10, 11, 12],            "stores": "specialty",    "notes": "WA Fuji type; Asian grocery & specialty"},
    "honeycrisp":       {"orchard": [9],             "market": [8, 9, 10, 11, 12, 1, 2],  "stores": "all",          "notes": "Peak Sep–Oct; stored through winter"},
    "hunnyz":           {"orchard": [9, 10],        "market": [9, 10, 11, 12, 1],         "stores": "specialty",    "notes": "BC Canada; limited US availability"},
    "jazz":             {"orchard": [3, 4],          "market": list(range(1, 13)),         "stores": "all",          "notes": "NZ harvest; year-round in most stores"},
    "jonathan":         {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "specialty",    "notes": "Classic Midwest variety; specialty & farm stands"},
    "jonagold":         {"orchard": [10],             "market": [10, 11, 12, 1],            "stores": "premium",      "notes": "Large sweet-tart; Wegmans / specialty, fall"},
    "juici":            {"orchard": [9, 10],        "market": [9, 10, 11, 12, 1],         "stores": "specialty",    "notes": "WA state; limited distribution"},
    "kanzi":            {"orchard": [3, 4],          "market": [1, 2, 3, 4, 5],            "stores": "premium",      "notes": "Belgian import; Whole Foods, spring"},
    "kiku":             {"orchard": [9, 10],        "market": [10, 11, 12, 1],            "stores": "specialty",    "notes": "Fuji variant; Japanese specialty stores"},
    "king david":       {"orchard": [10, 11],       "market": [10, 11, 12],               "stores": "orchard-only", "notes": "Heritage; orchard direct only"},
    "kissabel rouge":   {"orchard": [9, 10],        "market": [9, 10, 11, 12],            "stores": "specialty",    "notes": "French pink-flesh variety; specialty"},
    "koru":             {"orchard": [4, 5],          "market": [1, 2, 3, 4, 5],            "stores": "premium",      "notes": "NZ import; spring window only"},
    "lady alice":       {"orchard": [10, 11],       "market": [10, 11, 12, 1, 2],         "stores": "premium",      "notes": "WA state; Whole Foods / specialty"},
    "lemonade":         {"orchard": [3, 4, 5],      "market": [1, 2, 3, 4, 5],            "stores": "specialty",    "notes": "NZ import; spring only; specialty / Eataly"},
    "lucy glo":         {"orchard": [9],             "market": [9, 10, 11],                "stores": "specialty",    "notes": "Pink flesh; WA specialty"},
    "lucy rose":        {"orchard": [9],             "market": [9, 10, 11],                "stores": "specialty",    "notes": "Pink flesh; WA specialty"},
    "ludacrisp":        {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "specialty",    "notes": "Limited club variety"},
    "macoun":           {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "specialty",    "notes": "NE orchard favorite; poor keeper"},
    "mcintosh":         {"orchard": [9],             "market": [9, 10, 11],                "stores": "all",          "notes": "Classic NE fall apple; short storage"},
    "melrose":          {"orchard": [10, 11],       "market": [10, 11, 12, 1, 2],         "stores": "specialty",    "notes": "Ohio state apple; regional specialty"},
    "miapple":          {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "specialty",    "notes": "Limited distribution"},
    "modi":             {"orchard": [9, 10],        "market": [10, 11, 12, 1],            "stores": "specialty",    "notes": "Italian variety; Eataly & Italian specialty"},
    "mutsu":            {"orchard": [10],             "market": [10, 11, 12, 1, 2],         "stores": "premium",      "notes": "Also Crispin; large crisp fall apple"},
    "newtown pippin":   {"orchard": [10, 11],       "market": [11, 12, 1, 2],             "stores": "specialty",    "notes": "Heritage; specialty & heirloom orchards"},
    "opal":             {"orchard": [9, 10],        "market": [10, 11, 12, 1, 2, 3],      "stores": "premium",      "notes": "Non-browning; Whole Foods / Wegmans"},
    "pazazz":           {"orchard": [10, 11],       "market": [11, 12, 1, 2, 3],          "stores": "premium",      "notes": "MN variety; select premium chains"},
    "pink lady":        {"orchard": [10, 11],       "market": [10, 11, 12, 1, 2, 3, 4],  "stores": "all",          "notes": "Late fall through spring; widely available"},
    "pink pearl":       {"orchard": [8, 9],          "market": [8, 9, 10],                 "stores": "orchard-only", "notes": "Rare pink-flesh heirloom; orchards only"},
    "pinova":           {"orchard": [10],             "market": [10, 11, 12, 1, 2],         "stores": "specialty",    "notes": "European; ALDI seasonal, specialty stores"},
    "rave":             {"orchard": [7, 8],          "market": [7, 8, 9],                  "stores": "premium",      "notes": "Very early season; Whole Foods / Wegmans"},
    "red delicious":    {"orchard": [9, 10],        "market": list(range(1, 13)),         "stores": "all",          "notes": "Year-round staple"},
    "rockit":           {"orchard": [4, 5],          "market": list(range(1, 13)),         "stores": "all",          "notes": "NZ miniature apple; year-round"},
    "rome":             {"orchard": [10],             "market": [10, 11, 12, 1, 2],         "stores": "all",          "notes": "Classic cooking apple; fall–winter"},
    "ruby frost":       {"orchard": [10],             "market": [10, 11, 12, 1],            "stores": "specialty",    "notes": "NY state variety; regional specialty"},
    "ruby jon":         {"orchard": [9, 10],        "market": [9, 10, 11, 12],            "stores": "specialty",    "notes": "Jonathan cross; regional specialty"},
    "silken":           {"orchard": [8, 9],          "market": [8, 9, 10],                 "stores": "specialty",    "notes": "BC Canada; very limited US distribution"},
    "smitten":          {"orchard": [9, 10],        "market": [10, 11, 12, 1],            "stores": "specialty",    "notes": "NZ/UK variety; specialty stores"},
    "snapdragon":       {"orchard": [9, 10],        "market": [9, 10, 11, 12],            "stores": "premium",      "notes": "NY state exclusive; Wegmans / Whole Foods"},
    "snowsweet":        {"orchard": [9, 10],        "market": [9, 10, 11, 12],            "stores": "specialty",    "notes": "MN variety; specialty stores & co-ops"},
    "stayman winesap":  {"orchard": [10, 11],       "market": [10, 11, 12, 1, 2],         "stores": "specialty",    "notes": "Heritage variety; rich flavor; specialty"},
    "sugarbee":         {"orchard": [9, 10],        "market": [10, 11, 12, 1, 2],         "stores": "premium",      "notes": "WA state; Costco, Whole Foods"},
    "sundowner":        {"orchard": [10, 11],       "market": [10, 11, 12, 1, 2],         "stores": "specialty",    "notes": "Australian Cripps Red; specialty stores"},
    "sunrise magic":    {"orchard": [8, 9],          "market": [8, 9, 10],                 "stores": "specialty",    "notes": "Early season; limited"},
    "sweetango":        {"orchard": [8, 9],          "market": [8, 9, 10],                 "stores": "premium",      "notes": "Exclusive early season; Whole Foods / Wegmans"},
    "sweetie":          {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "specialty",    "notes": "Limited distribution"},
    "sweet orin":       {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "specialty",    "notes": "Japanese variety; very limited US"},
    "top secret":       {"orchard": [10],             "market": [10, 11, 12, 1],            "stores": "specialty",    "notes": "Club variety; specialty retailers"},
    "wild twist":       {"orchard": [10],             "market": [10, 11, 12],               "stores": "specialty",    "notes": "WA state; specialty stores"},
    "winecrisp":        {"orchard": [10, 11],       "market": [10, 11, 12, 1, 2],         "stores": "specialty",    "notes": "Heritage cross; specialty & farm stores"},
    "wolf river":       {"orchard": [9, 10],        "market": [9, 10, 11],                "stores": "orchard-only", "notes": "Very large heritage apple; orchards only"},
    "zestar":           {"orchard": [8, 9],          "market": [8, 9, 10],                 "stores": "premium",      "notes": "Early MN variety; Whole Foods / Wegmans"},
}

_STORE_PATTERNS: list[tuple[str, list[str]]] = [
    ("orchard",        ["demarest", "battleview", "terhune", "alstede", "melick",
                        "locust grove", "fishkill farms", "samascott", "wilklow",
                        "orchard", "farm stand", "pick-your-own", "pyo", "farmstead"]),
    ("farmers_market", ["greenmarket", "farmers market", "farm market", "union square"]),
    ("premium",        ["whole foods", "wholefoods", "wegmans", "amazon fresh",
                        "fresh market", "fairway"]),
    ("supermarket",    ["trader joe", "shoprite", "stop & shop", "stop and shop",
                        "aldi", "walmart", "costco", "target", "key food", "food town",
                        "kings food", "kings market"]),
]

# Which stores-tier tags are reachable when visiting a given store type
_REACHABLE: dict[str, frozenset[str]] = {
    "orchard":        frozenset({"all", "premium", "specialty", "orchard-only"}),
    "farmers_market": frozenset({"all", "premium", "specialty"}),
    "premium":        frozenset({"all", "premium"}),
    "supermarket":    frozenset({"all"}),
    "unknown":        frozenset({"all"}),
}

# ★ = within ~5 miles of South Orange NJ or Flatiron Manhattan, no special trip needed
# Grouped for display in the planner tab
KNOWN_STORES: list[str] = [
    # ── Within 5 miles of South Orange, NJ ───────────────────────────────────
    "★ Whole Foods (Short Hills, NJ — ~3 mi from South Orange)",
    "★ Trader Joe's (Millburn, NJ — ~4 mi from South Orange)",
    "★ Kings Food Markets (Maplewood, NJ — ~1 mi from South Orange)",
    "★ ShopRite (Maplewood / South Orange, NJ)",
    "★ Stop & Shop (nearest South Orange, NJ)",
    "★ ALDI (nearest South Orange, NJ)",
    # ── Within 5 miles of Flatiron, Manhattan ────────────────────────────────
    "★★ Union Square Greenmarket (14th St & Broadway, Manhattan)",
    "★ Whole Foods (4 Union Square South, Manhattan)",
    "★ Trader Joe's (14th St & 6th Ave, Manhattan)",
    "Fairway Market (nearest Manhattan location)",
    # ── NJ Orchards — day trips ───────────────────────────────────────────────
    "Demarest Farms (Hillsdale, NJ — ~30 mi)",
    "Alstede Farms (Chester, NJ — ~35 mi)",
    "Terhune Orchards (Princeton, NJ — ~40 mi)",
    "Battleview Orchards (Freehold, NJ — ~45 mi)",
    "Melick's Town Farm (Oldwick, NJ — ~45 mi)",
    # ── Union Square Greenmarket orchard vendors ──────────────────────────────
    "Locust Grove Fruit Farm at Union Square Greenmarket",
    "Fishkill Farms at Union Square Greenmarket",
    "Samascott Orchards at Union Square Greenmarket",
    "Wilklow Orchards at Union Square Greenmarket",
]

# Orchard vendors that sell at Union Square Greenmarket — shown as a callout in the UI
UNION_SQUARE_VENDORS: list[dict] = [
    {
        "name":    "Locust Grove Fruit Farm",
        "origin":  "Highland, NY (Hudson Valley)",
        "notes":   "One of the most consistent apple vendors; 30+ varieties including heirlooms",
    },
    {
        "name":    "Fishkill Farms",
        "origin":  "Dutchess County, NY",
        "notes":   "Large orchard; carries rare club varieties and heirlooms rarely found in stores",
    },
    {
        "name":    "Samascott Orchards",
        "origin":  "Kinderhook, NY (Hudson Valley)",
        "notes":   "Heritage and antique varieties; great source for uncommon apples",
    },
    {
        "name":    "Wilklow Orchards",
        "origin":  "Highland, NY (Hudson Valley)",
        "notes":   "Hudson Valley eating and cider apples; smaller stand, very seasonal",
    },
]

STORE_TYPE_LABELS: dict[str, str] = {
    "orchard":        "🌳 Orchard",
    "farmers_market": "🌾 Farmers Market",
    "premium":        "🏪 Premium Grocery",
    "supermarket":    "🛒 Supermarket",
    "unknown":        "🏪 Store",
}


def classify_store(store_name: str) -> str:
    name = store_name.lower()
    for visit_type, patterns in _STORE_PATTERNS:
        if any(p in name for p in patterns):
            return visit_type
    return "unknown"


def available_at(visit_type: str, month: int) -> dict[str, dict]:
    """Return {name_lower: data} for varieties available at visit_type in month."""
    reachable = _REACHABLE.get(visit_type, frozenset({"all"}))
    season_key = "orchard" if visit_type in ("orchard", "farmers_market") else "market"
    return {
        name: data
        for name, data in APPLE_SEASONS.items()
        if data["stores"] in reachable and month in data[season_key]
    }


def plan_visit(
    store_name: str,
    month: int,
    df: pd.DataFrame,
    wishlist: list[dict],
) -> dict:
    """
    Returns a structured visit plan:
      wishlist_hits — wishlist items findable at this store/month
      restock       — user's 8+ rated varieties available now
      scout         — untried, non-wishlisted varieties, sorted rarest first
    """
    visit_type = classify_store(store_name)
    available = available_at(visit_type, month)
    season_key = "orchard" if visit_type in ("orchard", "farmers_market") else "market"

    tried: dict[str, float] = {}
    tried_display: dict[str, str] = {}
    tried_source: dict[str, str] = {}
    for _, row in df.iterrows():
        name = str(row.get("Apple Variety") or "").strip()
        if not name:
            continue
        key = name.lower()
        score = float(row["Score"]) if pd.notna(row.get("Score")) else None
        if score is not None:
            tried[key] = score
        tried_display[key] = name
        tried_source[key] = str(row.get("From Where") or "").strip()

    wishlist_lower: set[str] = {
        str(item.get("Name") or "").strip().lower() for item in wishlist
    }

    # 1. Wishlist hits
    wishlist_hits = []
    for item in wishlist:
        name = str(item.get("Name") or "").strip()
        key = name.lower()
        if key in available:
            wishlist_hits.append({
                "name": name,
                "notes": available[key]["notes"],
                "tasting_notes": str(item.get("Tasting Notes") or "").strip(),
                "price": str(item.get("Price") or "").strip(),
            })

    # 2. Restock: tried 8+ available now
    restock = []
    for key, score in tried.items():
        if score < 8 or key not in available:
            continue
        restock.append({
            "name": tried_display[key],
            "score": score,
            "from_where": tried_source.get(key, ""),
            "notes": available[key]["notes"],
        })
    restock.sort(key=lambda x: -x["score"])

    # 3. Scout: untried + not on wishlist, rarest (shortest season) first
    scout = []
    for key, data in available.items():
        if key in tried or key in wishlist_lower:
            continue
        window = len(data[season_key])
        scout.append({
            "name": key.title(),
            "notes": data["notes"],
            "stores": data["stores"],
            "window": window,
        })
    scout.sort(key=lambda x: x["window"])

    return {
        "store_name":      store_name,
        "visit_type":      visit_type,
        "month":           month,
        "month_name":      MONTH_NAMES[month],
        "available_count": len(available),
        "wishlist_hits":   wishlist_hits,
        "restock":         restock,
        "scout":           scout,
    }
