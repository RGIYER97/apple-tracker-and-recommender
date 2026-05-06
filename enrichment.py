import html as _html
import os
import re
import time
import requests
import pandas as pd
from typing import Callable, Optional
from tavily import TavilyClient

STORE_DOMAINS: dict[str, str] = {
    "trader joes":       "traderjoes.com",
    "trader joe's":      "traderjoes.com",
    "whole foods":       "wholefoodsmarket.com",
    "wholefoods":        "wholefoodsmarket.com",
    "wegmans":           "wegmans.com",
    "shoprite":          "shoprite.com",
    "stop & shop":       "stopandshop.com",
    "aldi":              "aldi.us",
    "walmart":           "walmart.com",
    "costco":            "costco.com",
    "amazon fresh":      "amazon.com",
}

_BOILERPLATE = re.compile(
    r"cookie|privacy|sign in|log in|add to cart|buy now|shop now|"
    r"free shipping|in stock|out of stock|subscribe|newsletter|"
    r"breadcrumb|click here|javascript|per lb|\$\d|\d+ reviews|"
    r"read more|see more|show more|back to|"
    r"facebook|instagram|twitter|youtube|pinterest|tiktok|snapchat|"
    r"\blinkedin\b|\bwhatsapp\b|"
    r"\b\w+\.(com|net|org|io|co|uk)\b|"
    r"\bgift\b|\bcart\b|\bcheckout\b|\bwishlist\b|\bfollow us\b|"
    r"all rights reserved|copyright ©|\bterms\b.*\buse\b",
    re.IGNORECASE,
)

# Sentences must contain at least one genuine taste/sensory word to be kept
_TASTE_PATTERN = re.compile(
    r"\b(?:flavor|flavour|taste|sweet|tart|tangy|sour|crisp|crunchy|juicy|"
    r"firm|soft|acidic|acidity|acid|bitter|mild|aroma|aromatic|fragrant|"
    r"texture|crunch|fresh|bright|nutty|floral|earthy|spice|spiced|cinnamon|"
    r"honeyed|honey|caramel|sugar|dense|herbal|tropical|citrus|berry|complex|"
    r"balanced|finish|aftertaste|palate|bite|mouthfeel|zest|russet|anise|"
    r"vanilla|astringent|tender|succulent|chewy|dry|rich|delicate|sharp|"
    r"creamy|buttery|winey|wine|cider|tannin)\b",
    re.IGNORECASE,
)


def _tavily() -> TavilyClient:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise EnvironmentError("TAVILY_API_KEY is not set")
    return TavilyClient(api_key=key)


def _store_domain(from_where: str) -> str:
    key = from_where.lower().strip()
    for store_key, domain in STORE_DOMAINS.items():
        if store_key in key:
            return domain
    return ""


_PRICE_PATTERNS = [
    re.compile(r"\$[\d,]+(?:\.\d{1,2})?\s*/\s*(?:lb|pound|bag|each)", re.IGNORECASE),
    re.compile(r"\$[\d,]+(?:\.\d{1,2})?\s*per\s*(?:lb|pound|bag)", re.IGNORECASE),
    re.compile(r"\$[\d,]+(?:\.\d{1,2})?(?:\s*/\s*(?:oz|each))?", re.IGNORECASE),
]


def _extract_price(texts: list[str]) -> str:
    for pattern in _PRICE_PATTERNS:
        for text in texts:
            m = pattern.search(text)
            if m:
                return m.group(0).strip()
    return ""


def _extract_notes(content: str) -> str:
    if not content or len(content) < 20:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    clean: list[str] = []
    for s in sentences:
        s = re.sub(r"^[\*\-•]\s*", "", s.strip())
        if len(s) < 30:
            continue
        if _BOILERPLATE.search(s):
            continue
        tokens = s.split()
        url_like = sum(1 for t in tokens if re.search(r"\.(com|net|org|io|co)\b", t, re.I))
        if url_like >= 2:
            continue
        if not _TASTE_PATTERN.search(s):
            continue
        clean.append(s)
        if len(clean) == 3:
            break
    return " ".join(clean)


_TASTING_VOCAB = {
    "flavor", "flavour", "taste", "aroma", "texture", "sweet", "tart", "tangy",
    "crisp", "crunchy", "juicy", "firm", "soft", "acidic", "bitter", "mild",
    "fragrant", "floral", "earthy", "spice", "spiced", "cinnamon", "honeyed",
    "honey", "caramel", "sugar", "fresh", "bright", "dense", "nutty", "herbal",
    "tropical", "citrus", "berry", "apple", "pear", "cherry", "complex",
    "balanced", "finish", "aftertaste", "skin", "flesh", "aromatic", "notes",
    "russet", "russeting", "anise", "vanilla", "wine", "cider", "astringent",
}


def _looks_like_tasting_notes(text: str) -> bool:
    words = set(re.findall(r"[a-z]+", text.lower()))
    return len(words & _TASTING_VOCAB) >= 3


def _llm_extract_notes(apple_name: str, snippets: list[str]) -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return ""
    try:
        from openai import OpenAI
        llm = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")
        combined = "\n\n---\n\n".join(snippets[:4])
        response = llm.chat.completions.create(
            model=model,
            max_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an apple sensory expert. From the provided search snippets, extract "
                        "or synthesize 1–3 sentences of TASTE-ONLY tasting notes for the named apple "
                        "variety. Cover ONLY: sweetness level, tartness/acidity, texture (crisp, firm, "
                        "soft, dense), juiciness, and any distinctive flavor notes (floral, spiced, "
                        "earthy, nutty, honey, caramel, citrus, berry, wine-like, etc.). "
                        "EXCLUDE everything else — growing region, history, availability, health "
                        "claims, awards, harvest info, or any marketing language. "
                        "Return ONLY the sensory description. If no taste information exists in the "
                        "snippets, return an empty string."
                    ),
                },
                {
                    "role": "user",
                    "content": f'Taste-only tasting notes for "{apple_name}" apple:\n\n{combined}',
                },
            ],
        )
        result = (response.choices[0].message.content or "").strip()
        if len(result) < 20 or result.lower() in ("", "none", "n/a", "not found", "unknown"):
            return ""
        return result
    except Exception as exc:
        print(f"[enrichment/llm-notes] {apple_name}: {exc}")
        return ""


def _fetch_tasting_notes(client: TavilyClient, apple_name: str) -> tuple[str, str]:
    """
    Fetch professional tasting notes for an apple variety.
    Returns (notes, source) where source is "web", "LLM", or "".

    Stage 1 — fast path: search apple-specific sites, then general tasting-notes query.
    Stage 2 — LLM fallback: synthesise from raw snippets when fast path fails quality check.
    """
    queries = [
        (f"{apple_name} apple variety site:orangepippin.com",        "web"),
        (f"{apple_name} apple site:pomiferous.com",                  "web"),
        (f'"{apple_name}" apple tasting notes flavor texture',        "web"),
        (f"{apple_name} apple variety flavor description crisp tart", "web"),
    ]
    raw_snippets: list[str] = []

    for query, source_label in queries:
        try:
            resp = client.search(query, search_depth="basic", max_results=3)
            for r in resp.get("results", []):
                content = r.get("content", "")
                if not content:
                    continue
                notes = _extract_notes(content)
                if notes and _looks_like_tasting_notes(notes):
                    return notes, source_label
                raw_snippets.append(content)
        except Exception as exc:
            print(f"[enrichment/notes] {apple_name}: {exc}")
        time.sleep(0.25)

    llm_notes = _llm_extract_notes(apple_name, raw_snippets)
    if llm_notes:
        return llm_notes, "LLM"
    return "", ""


def _fetch_off_nutrition(apple_name: str) -> str:
    try:
        resp = requests.get(
            "https://world.openfoodfacts.org/cgi/search.pl",
            params={
                "search_terms": f"{apple_name} apple",
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 5,
                "fields": "product_name,nutriments,allergens_tags",
            },
            timeout=8,
        )
        for product in resp.json().get("products", []):
            n = product.get("nutriments", {})
            if not n:
                continue
            parts = []
            for label, key in [("Carbs", "carbohydrates_100g"), ("Sugar", "sugars_100g"), ("Fiber", "fiber_100g")]:
                val = n.get(key)
                if val is not None:
                    parts.append(f"{label}: {float(val):.1f}g")
            kcal = n.get("energy-kcal_100g")
            if kcal:
                parts.append(f"{int(float(kcal))} kcal")
            if parts:
                return " | ".join(parts) + " (per 100g)"
    except Exception as exc:
        print(f"[enrichment/off] {apple_name}: {exc}")
    return ""


# ── applerankings.com ─────────────────────────────────────────────────────────

_AR_SLUG_MAP: dict[str, str] = {
    "ambrosia": "ambrosia",
    "arkansas black": "arkansas-black",
    "aura": "aura",
    "autumn glory": "autumn-glory",
    "blondee": "blondee",
    "braeburn": "braeburn",
    "cameo": "cameo",
    "candy crisp": "candy-crisp",
    "cortland": "cortland",
    "cosmic crisp": "cosmic-crisp",
    "crimson gold": "crimson-gold",
    "cripps pink": "cripps-pink",
    "empire": "empire",
    "envy": "envy",
    "evercrisp": "evercrisp",
    "ever crisp": "evercrisp",
    "fuji": "fuji",
    "gala": "gala",
    "golden delicious": "golden-delicious",
    "golden russet": "golden-russet",
    "goldrush": "goldrush",
    "gold rush": "goldrush",
    "granny smith": "granny-smith",
    "green dragon": "green-dragon",
    "honeycrisp": "honeycrisp",
    "honey crisp": "honeycrisp",
    "hunnyz": "hunnyz",
    "jazz": "jazz",
    "jonagold": "jonagold",
    "jonathan": "jonathan",
    "juici": "juici",
    "kanzi": "kanzi",
    "kiku": "kiku",
    "king david": "king-david",
    "kissabel rouge": "kissabel-rouge",
    "koru": "koru-plumac",
    "koru (plumac)": "koru-plumac",
    "lady alice": "lady-alice",
    "lemonade": "lemonade",
    "lucy glo": "lucy-glo",
    "lucy rose": "lucy-rose",
    "ludacrisp": "ludacrisp",
    "macoun": "macoun",
    "mcintosh": "mcintosh",
    "melrose": "melrose",
    "miapple": "miapple",
    "modi": "modi",
    "mutsu": "mutsu-crispin",
    "mutsu (crispin)": "mutsu-crispin",
    "crispin": "mutsu-crispin",
    "newtown pippin": "newtown-pippin",
    "opal": "opal",
    "pazazz": "pazazz",
    "pink lady": "pink-lady",
    "pink pearl": "pink-pearl",
    "pinova": "pinova-pinata",
    "piñata": "pinova-pinata",
    "pinata": "pinova-pinata",
    "rave": "rave",
    "red delicious": "red-delicious",
    "rockit": "rockit",
    "rome": "rome",
    "ruby frost": "ruby-frost",
    "ruby jon": "ruby-jon",
    "silken": "silken",
    "smitten": "smitten",
    "snapdragon": "snapdragon",
    "snap dragon": "snapdragon",
    "snowsweet": "snowsweet",
    "snow sweet": "snowsweet",
    "stayman winesap": "stayman-winesap",
    "winesap": "stayman-winesap",
    "sugarbee": "sugarbee",
    "sugar bee": "sugarbee",
    "sundowner": "sundowner-cripps-red",
    "cripps red": "sundowner-cripps-red",
    "sunrise magic": "sunrise-magic",
    "sweetango": "sweetango",
    "sweetie": "sweetie",
    "sweet orin": "sweet-orin",
    "top secret": "top-secret",
    "wild twist": "wild-twist",
    "winecrisp": "winecrisp",
    "wolf river": "wolf-river",
    "zestar": "zestar",
    "zestar!": "zestar",
}

_AR_TIER_LABELS = frozenset({
    "Nearly Perfect", "Superb", "Excellent", "Very Good", "Good",
    "Mediocre", "Bad", "Terrible", "Despicable", "Atrocious",
})

_AR_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def _ar_slug(apple_name: str) -> str:
    key = apple_name.lower().strip()
    if key in _AR_SLUG_MAP:
        return _AR_SLUG_MAP[key]
    return re.sub(r"[^a-z0-9]+", "-", key).strip("-")


def _fetch_applerankings(apple_name: str) -> tuple[str, str]:
    """
    Fetch score and notes from applerankings.com.
    Returns (score_str, notes_str) — both empty if the apple isn't listed.
    """
    slug = _ar_slug(apple_name)
    url  = f"https://applerankings.com/{slug}-apple-review/"
    try:
        resp = requests.get(url, timeout=10, headers=_AR_HEADERS)
        if resp.status_code != 200:
            return "", ""
        html = resp.text

        # Score: first elementor-heading-title div whose text is 1–100
        score = ""
        for m in re.finditer(
            r'class="elementor-heading-title[^"]*">\s*(\d+)\s*</', html
        ):
            val = int(m.group(1))
            if 1 <= val <= 100:
                score = str(val)
                break

        # Tagline: h4 with elementor-heading-title
        tagline = ""
        m = re.search(r'<h4[^>]*elementor-heading-title[^>]*>([^<]+)</h4>', html)
        if m:
            tagline = _html.unescape(m.group(1).strip())

        # Tier: non-numeric elementor-heading-title div text
        tier = ""
        for m in re.finditer(
            r'<div class="elementor-heading-title[^"]*">([^<]+)</div>', html
        ):
            text = m.group(1).strip()
            if text in _AR_TIER_LABELS:
                tier = text
                break

        # Review: first substantial paragraph before user comments
        review_text = ""
        for p in re.findall(r'<p>(.*?)</p>', html, re.DOTALL):
            clean = _html.unescape(re.sub(r'<[^>]+>', '', p)).strip()
            if len(clean) > 60 and not clean.upper().startswith("BONUS POINTS"):
                review_text = clean[:300]
                if len(clean) > 300:
                    last = review_text.rfind('.')
                    review_text = review_text[:last + 1] if last > 80 else review_text + '…'
                break

        parts: list[str] = []
        if tagline:
            parts.append(tagline)
        if tier:
            parts.append(f"[{tier}]")
        if review_text:
            parts.append(review_text)
        notes = " — ".join(parts)

        return score, notes
    except Exception as exc:
        print(f"[enrichment/ar] {apple_name}: {exc}")
        return "", ""


def _empty(val) -> bool:
    return not val or not str(val).strip()


def search_apple_info(
    apple_name: str,
    fetch_notes: bool = True,
    fetch_ar: bool = True,
) -> dict:
    client = _tavily()
    result = {"Image URL": "", "Prof. Tasting Notes": "", "Notes Source": "", "AR Score": "", "AR Notes": ""}

    try:
        img_resp = client.search(
            f"{apple_name} apple variety",
            search_depth="basic",
            max_results=3,
            include_images=True,
        )
        result["Image URL"] = (img_resp.get("images") or [""])[0]
    except Exception as exc:
        print(f"[enrichment/image] {apple_name}: {exc}")

    if fetch_notes:
        notes, source = _fetch_tasting_notes(client, apple_name)
        result["Prof. Tasting Notes"] = notes
        result["Notes Source"] = source

    if fetch_ar:
        ar_score, ar_notes = _fetch_applerankings(apple_name)
        result["AR Score"] = ar_score
        result["AR Notes"] = ar_notes

    return result


def enrich_dataframe(
    df: pd.DataFrame,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> pd.DataFrame:
    df = df.copy()
    if "Image URL" not in df.columns:
        df["Image URL"] = ""
    for col in ("Prof. Tasting Notes", "Notes Source", "AR Score", "AR Notes"):
        if col not in df.columns:
            df[col] = ""

    total = len(df)
    for i, (idx, row) in enumerate(df.iterrows()):
        name = row["Apple Variety"]

        needs_image = _empty(row.get("Image", ""))
        needs_notes = _empty(row.get("Prof. Tasting Notes", ""))
        needs_ar    = _empty(row.get("AR Score", ""))

        if not needs_image and not needs_notes and not needs_ar:
            if progress_cb:
                progress_cb((i + 1) / total, f"{name} (skipped – already enriched)")
            continue

        if progress_cb:
            progress_cb(i / total, name)

        info = search_apple_info(
            apple_name=name,
            fetch_notes=needs_notes,
            fetch_ar=needs_ar,
        )
        if needs_image and info["Image URL"]:           df.at[idx, "Image URL"]           = info["Image URL"]
        if needs_notes and info["Prof. Tasting Notes"]: df.at[idx, "Prof. Tasting Notes"] = info["Prof. Tasting Notes"]
        if needs_notes and info["Notes Source"]:        df.at[idx, "Notes Source"]        = info["Notes Source"]
        if needs_ar    and info["AR Score"]:            df.at[idx, "AR Score"]            = info["AR Score"]
        if needs_ar    and info["AR Notes"]:            df.at[idx, "AR Notes"]            = info["AR Notes"]

        time.sleep(0.5)

    if progress_cb:
        progress_cb(1.0, "Done")
    return df
