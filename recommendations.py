import os
import re
import json
import time
import pandas as pd
from openai import OpenAI
from tavily import TavilyClient


class RecommendationError(Exception):
    pass


def _tag_profile(df: pd.DataFrame) -> str:
    parts = []
    for col, label in [("Type", "Variety types tried"), ("Origin", "Origins tried"), ("Country", "Countries")]:
        if col not in df.columns:
            continue
        counts = df[col].dropna().str.strip().replace("", pd.NA).dropna().value_counts()
        if counts.empty:
            continue
        parts.append(f"{label}: {', '.join(counts.head(6).index)}")
    if not parts:
        return ""
    return "\nMY APPLE PROFILE (from tagged entries):\n" + "\n".join(f"- {p}" for p in parts) + "\n"


_STORE_TIERS = """\
★ = within 5 miles, no special trip needed   ★★ = top priority for rare/seasonal finds

WITHIN 5 MILES OF SOUTH ORANGE, NJ — check these first:
★ Whole Foods Market (Short Hills, NJ — ~3 miles) — best specialty apple selection in the immediate area
★ Trader Joe's (Millburn, NJ — ~4 miles) — good seasonal variety; Autumn Glory exclusive in fall
★ Kings Food Markets (Maplewood, NJ — ~1 mile from South Orange) — solid everyday selection
★ ShopRite (nearest South Orange / Maplewood location)
★ Stop & Shop (nearest South Orange location)
  ALDI (nearest NJ location — budget option)

WITHIN 5 MILES OF FLATIRON DISTRICT, MANHATTAN — prioritise the Greenmarket:
★★ Union Square Greenmarket (14th St & Broadway, Manhattan — IN Flatiron District)
   Open year-round: Mon · Wed · Fri · Sat
   Apple orchard vendors who regularly sell here (availability varies by season):
   · Locust Grove Fruit Farm (Highland, NY) — Hudson Valley; 30+ varieties including heirlooms
   · Fishkill Farms (Dutchess County, NY) — large orchard; rare and club varieties
   · Samascott Orchards (Kinderhook, NY) — Hudson Valley heritage varieties
   · Wilklow Orchards (Highland, NY) — Hudson Valley; cider and eating apples
   → These vendors carry varieties never stocked in any supermarket — always ask what's freshest
★ Whole Foods Market (4 Union Square South — steps from the Greenmarket)
★ Trader Joe's (14th St & 6th Ave, Manhattan — ~0.4 miles from Union Square)
  Fairway Market (nearest Manhattan location)

NJ ORCHARDS — day trips from South Orange (call ahead for variety availability):
- Alstede Farms (Chester, NJ — ~35 miles) — wide variety selection, PYO in season
- Demarest Farms (Hillsdale, NJ — ~30 miles) — 30+ varieties, family orchard
- Terhune Orchards (Princeton, NJ — ~40 miles) — heritage and heirloom focus
- Battleview Orchards (Freehold, NJ — ~45 miles) — PYO and farm store
- Melick's Town Farm (Oldwick, NJ — ~45 miles) — eating and cider apples

Always list ★ locations first — they require no special trip."""

_REC_SCHEMA = """\
Return ONLY a valid JSON array — no markdown fences, no prose. Each element:
{
  "name": "Full apple variety name",
  "origin": "Country, Region (e.g. New Zealand, United States/Pacific Northwest)",
  "type": "eating / cooking / cider / dual-purpose",
  "season": "e.g. Fall, Late Summer, Year-round",
  "flavor_profile": "Vivid 2-3 sentence tasting description covering sweetness, tartness, texture, aroma",
  "why_youll_love_it": "Start with 'Because you gave [specific apple from MY COLLECTION] X/10 for [exact quality]…' then explain what shared trait makes this a match. Always cite a real apple name and score from the list above.",
  "tasting_notes": ["note1", "note2", "note3", "note4"],
  "price_range": "~$X/lb or ~$X/bag",
  "confidence": 9.2,
  "ar_score_estimate": 82,
  "stores": [
    {
      "name": "Store or orchard name",
      "location": "Address or City, State",
      "notes": "Availability tip or season"
    }
  ],
  "pairs_with": ["sharp cheddar", "caramel", "pork", "etc."]
}"""


def _format_top_apples(top: pd.DataFrame) -> str:
    has_prof = "Prof. Tasting Notes" in top.columns
    lines = []
    for _, row in top.iterrows():
        lines.append(
            f"- {row['Apple Variety']} — {row['Score']}/10  (from {row.get('From Where', '?')})"
        )
        personal = str(row.get("Tasting Notes") or "").strip()
        if personal:
            lines.append(f"    My notes: {personal}")
        if has_prof:
            prof = str(row.get("Prof. Tasting Notes") or "").strip()
            if prof:
                lines.append(f"    Prof. notes: {prof}")
    return "\n".join(lines) if lines else "None"


def _tried_names_section(df: pd.DataFrame) -> str:
    names = sorted(df["Apple Variety"].dropna().str.strip().unique().tolist())
    if not names:
        return ""
    bullets = "\n".join(f"- {n}" for n in names)
    return f"\nDO NOT RECOMMEND any of these — I have already tried them:\n{bullets}\n"


def _build_prompt(df: pd.DataFrame, num_recs: int, already_pinned: list[str] | None = None) -> str:
    top = df[df["Score"] >= 8].sort_values("Score", ascending=False)
    disliked = df[df["Score"] < 6]

    top_str = _format_top_apples(top)
    disliked_str = (
        disliked[["Apple Variety", "Score", "Tasting Notes"]].to_string(index=False)
        if not disliked.empty
        else "None"
    )

    tried_section = _tried_names_section(df)

    pinned_section = ""
    if already_pinned:
        bullet_list = "\n".join(f"- {name}" for name in already_pinned)
        pinned_section = f"""
ALREADY SAVED TO MY WISHLIST (do NOT recommend any of these again):
{bullet_list}
"""

    tag_section = _tag_profile(df)

    return f"""I'm an apple enthusiast who has tried and scored these apple varieties:

TOP RATED (8+/10):
{top_str}

LESS ENJOYED (below 6/10):
{disliked_str}

OVERALL AVERAGE SCORE: {df["Score"].mean():.1f}/10
{tag_section}{tried_section}{pinned_section}
IMPORTANT — when "My notes" and "Prof. notes" describe different characteristics for the same variety, \
trust "My notes". They reflect what I actually tasted; professional descriptions are a reference only.

Based on this history, recommend {num_recs} apple varieties I have NOT tried yet that I would love. \
For each variety list the specific stores or orchards where I can find it, using this strict priority order:

{_STORE_TIERS}

{_REC_SCHEMA}"""


def _build_similar_prompt(
    apple_name: str,
    df: pd.DataFrame,
    num_recs: int,
    already_pinned: list[str] | None = None,
) -> str:
    match = df[df["Apple Variety"].str.strip().str.lower() == apple_name.lower()]
    if not match.empty:
        row = match.iloc[0]
        score = row.get("Score", "?")
        notes = str(row.get("Tasting Notes") or "")
        extras = ", ".join(
            v for v in [
                str(row.get("Type") or ""),
                str(row.get("Origin") or ""),
                str(row.get("Country") or ""),
            ] if v.strip()
        )
        apple_desc = f'"{apple_name}" ({score}/10)'
        if notes:
            apple_desc += f" — {notes}"
        if extras:
            apple_desc += f" [{extras}]"
    else:
        apple_desc = f'"{apple_name}"'

    tried_section = _tried_names_section(df)

    pinned_section = ""
    if already_pinned:
        bullet_list = "\n".join(f"- {name}" for name in already_pinned)
        pinned_section = f"""
Do NOT recommend any of these (already in my wishlist):
{bullet_list}
"""

    schema = _REC_SCHEMA.replace(
        '"why_youll_love_it": "Start with \'Because you gave [specific apple from MY COLLECTION] X/10 for [exact quality]…\' then explain what shared trait makes this a match. Always cite a real apple name and score from the list above."',
        f'"why_youll_love_it": "Explain precisely what flavour or texture trait this variety shares with {apple_name}, and why that makes it a great follow-on."',
    )

    return f"""I'm an apple enthusiast. I love {apple_desc} and want to find similar varieties I haven't tried.
{tried_section}{pinned_section}
Please recommend {num_recs} apple varieties that are similar to "{apple_name}" and that I would enjoy.

For each variety list specific stores or orchards using this priority:
{_STORE_TIERS}

{schema}"""


def _filter_recs(
    recs: list[dict],
    df: pd.DataFrame,
    already_pinned: list[str],
) -> list[dict]:
    """
    Post-processing guard: remove duplicates within the set and any variety
    already in the user's collection or wishlist, regardless of what the LLM returned.
    """
    tried_lower = {str(v).strip().lower() for v in df["Apple Variety"].dropna()}
    pinned_lower = {n.strip().lower() for n in already_pinned}
    exclude = tried_lower | pinned_lower

    seen: set[str] = set()
    out: list[dict] = []
    for rec in recs:
        key = (rec.get("name") or "").strip().lower()
        if not key or key in seen or key in exclude:
            continue
        seen.add(key)
        out.append(rec)
    return out


def get_recommendations(
    df: pd.DataFrame,
    num_recs: int = 6,
    already_pinned: list[str] | None = None,
) -> list[dict]:
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
    pinned = already_pinned or []
    prompt = _build_prompt(df, num_recs, already_pinned=pinned)
    model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "system",
                "content": "You are an apple variety recommendation assistant. Return strict JSON only with no markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    text = (response.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecommendationError(
            f"Model returned invalid JSON: {exc}\n\nResponse (first 300 chars):\n{text[:300]}"
        ) from exc
    return _filter_recs(parsed, df, pinned)


def get_similar_recommendations(
    apple_name: str,
    df: pd.DataFrame,
    num_recs: int = 3,
    already_pinned: list[str] | None = None,
) -> list[dict]:
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
    pinned = already_pinned or []
    prompt = _build_similar_prompt(apple_name, df, num_recs, already_pinned=pinned)
    model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    response = client.chat.completions.create(
        model=model,
        max_tokens=2048,
        messages=[
            {
                "role": "system",
                "content": "You are an apple variety recommendation assistant. Return strict JSON only with no markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    text = (response.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecommendationError(
            f"Model returned invalid JSON: {exc}\n\nResponse (first 300 chars):\n{text[:300]}"
        ) from exc
    return _filter_recs(parsed, df, pinned)


def _fetch_image_url(tavily: TavilyClient, name: str) -> str:
    for query in [
        f"{name} apple variety site:orangepippin.com",
        f"{name} apple site:en.wikipedia.org",
        f"{name} apple variety",
    ]:
        try:
            resp = tavily.search(query, search_depth="basic", max_results=3, include_images=True)
            images = resp.get("images", [])
            if images:
                return images[0]
        except Exception as exc:
            print(f"[recommendations] image fallback failed for {name}: {exc}")
        time.sleep(0.3)
    return ""


def add_images(recommendations: list[dict]) -> list[dict]:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        for rec in recommendations:
            rec.setdefault("picture_url", "")
            rec.setdefault("link", "")
        return recommendations

    tavily = TavilyClient(api_key=key)
    for rec in recommendations:
        try:
            resp = tavily.search(
                f"{rec['name']} apple variety",
                search_depth="basic",
                max_results=3,
                include_images=True,
            )
            results = resp.get("results", [])
            rec["link"] = results[0]["url"] if results else ""
            images = resp.get("images", [])
            if images:
                rec["picture_url"] = images[0]
            else:
                rec["picture_url"] = _fetch_image_url(tavily, rec["name"])
        except Exception as exc:
            print(f"[recommendations] search failed for {rec['name']}: {exc}")
            rec.setdefault("link", "")
            rec["picture_url"] = _fetch_image_url(tavily, rec["name"])
        time.sleep(0.4)

    return recommendations


def tag_apple(name: str) -> dict:
    """
    Infer type (eating/cooking/cider), origin region, and country for an apple variety.
    Returns {"type": str, "origin": str, "country": str}.
    """
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
    model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    response = client.chat.completions.create(
        model=model,
        max_tokens=120,
        messages=[
            {
                "role": "system",
                "content": "You are a pomology expert. Return strict JSON only, no markdown.",
            },
            {
                "role": "user",
                "content": (
                    f'What are the primary use type, origin region, and country for the "{name}" apple variety?\n'
                    'Return exactly: {"type": "eating|cooking|cider|dual-purpose", '
                    '"origin": "Region or state/area of origin (e.g. Pacific Northwest, New Zealand, England)", '
                    '"country": "Country name"}\n'
                    "If unknown, use an empty string."
                ),
            },
        ],
    )

    text = (response.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
        return {
            "type":    result.get("type", ""),
            "origin":  result.get("origin", ""),
            "country": result.get("country", ""),
        }
    except Exception:
        return {"type": "", "origin": "", "country": ""}


def _build_ar_smart_prompt(
    df: pd.DataFrame,
    num_recs: int,
    already_pinned: list[str] | None = None,
) -> str:
    from enrichment import _AR_SLUG_MAP

    tried_lower = {str(v).strip().lower() for v in df["Apple Variety"].dropna()}
    untried_ar = sorted({
        k.title() for k in _AR_SLUG_MAP
        if k not in tried_lower
    })

    def _ar_int(row) -> int | None:
        try:
            v = str(row.get("AR Score") or "").strip()
            n = int(v)
            return n if 1 <= n <= 100 else None
        except Exception:
            return None

    both_high: list[tuple] = []
    user_high_only: list[tuple] = []
    ar_high_only: list[tuple] = []

    for _, row in df.iterrows():
        name = str(row.get("Apple Variety") or "").strip()
        user_s = float(row["Score"]) if pd.notna(row.get("Score")) else None
        ar_s = _ar_int(row)
        notes = (
            str(row.get("Tasting Notes") or "").strip()
            or str(row.get("Prof. Tasting Notes") or "").strip()
        )
        if user_s is None:
            continue
        if user_s >= 8 and ar_s is not None and ar_s >= 75:
            both_high.append((name, user_s, ar_s, notes))
        elif user_s >= 8:
            user_high_only.append((name, user_s, ar_s, notes))
        elif ar_s is not None and ar_s >= 80 and user_s < 6:
            ar_high_only.append((name, user_s, ar_s, notes))

    def _fmt(tup: tuple) -> str:
        name, u, ar, notes = tup
        ar_str = f", AR {ar}/100" if ar is not None else ""
        note_str = f" — {notes[:100]}" if notes else ""
        return f"- {name}: My {u:.0f}/10{ar_str}{note_str}"

    both_str   = "\n".join(_fmt(t) for t in both_high)   or "None yet"
    user_str   = "\n".join(_fmt(t) for t in user_high_only) or "None"
    ar_only_str = "\n".join(_fmt(t) for t in ar_high_only) or "None"
    untried_str = ", ".join(untried_ar[:60]) if untried_ar else "(none listed)"

    tried_section = _tried_names_section(df)

    pinned_section = ""
    if already_pinned:
        pinned_section = (
            "\nDo NOT recommend any of these (already in my wishlist):\n"
            + "\n".join(f"- {n}" for n in already_pinned)
            + "\n"
        )

    return f"""I'm an apple enthusiast. I want recommendations that leverage both my personal \
ratings and AppleRankings.com (AR) scores (scale 1–100).

APPLES I LOVE THAT ALSO RATE HIGHLY ON AR — strongest signal, my taste and objective quality agree:
{both_str}

APPLES I LOVE BUT WITHOUT HIGH AR SCORES — personal taste diverging from AR consensus:
{user_str}

AR-LOVED APPLES I RATED LOWER — styles AR endorses that I don't seem to enjoy:
{ar_only_str}
{tried_section}{pinned_section}
UNTRIED VARIETIES FROM THE APPLERANKINGS.COM CATALOG:
{untried_str}

Recommend {num_recs} apple varieties from the untried catalog above. Prioritise varieties that:
1. Are likely to score highly on AR (75+/100) based on their known characteristics and reputation
2. Share flavour or texture traits with the apples where BOTH my score and AR agree (the first list \
above is the strongest signal); if that list is empty, use my personal favourites

For each variety list specific stores or orchards using this priority:
{_STORE_TIERS}

{_REC_SCHEMA}"""


def get_ar_smart_recommendations(
    df: pd.DataFrame,
    num_recs: int = 6,
    already_pinned: list[str] | None = None,
) -> list[dict]:
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
    pinned = already_pinned or []
    prompt = _build_ar_smart_prompt(df, num_recs, already_pinned=pinned)
    model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "system",
                "content": "You are an apple variety recommendation assistant. Return strict JSON only with no markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    text = (response.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecommendationError(
            f"Model returned invalid JSON: {exc}\n\nResponse (first 300 chars):\n{text[:300]}"
        ) from exc
    return _filter_recs(parsed, df, pinned)


def _local_confidence(rec: dict, df: pd.DataFrame) -> float | None:
    """
    Score 1–10: how well a recommendation's tags (type, origin, country)
    match the user's top-rated apples (score >= 7), weighted by score.
    Returns None when no tag columns exist to compare against.
    """
    top = df[df["Score"] >= 7].copy()
    if top.empty:
        return None
    total_w = float(top["Score"].sum())
    if total_w == 0:
        return None

    signals: list[float] = []

    rec_type = (rec.get("type") or "").strip().lower()
    if rec_type and "Type" in top.columns:
        mask = top["Type"].fillna("").str.strip().str.lower() == rec_type
        signals.append(float(top.loc[mask, "Score"].sum()) / total_w)

    rec_origin_words = set((rec.get("origin") or "").lower().split())
    if rec_origin_words and "Origin" in top.columns:
        mask = top["Origin"].fillna("").apply(
            lambda s: bool(rec_origin_words & set(s.lower().split()))
        )
        signals.append(float(top.loc[mask, "Score"].sum()) / total_w)

    rec_country = (rec.get("origin") or "").split(",")[0].strip().lower()
    if rec_country and "Country" in top.columns:
        mask = top["Country"].fillna("").str.strip().str.lower() == rec_country
        signals.append(float(top.loc[mask, "Score"].sum()) / total_w)

    if not signals:
        return None
    return round(1.0 + (sum(signals) / len(signals)) * 9.0, 1)


def add_ar_scores(recommendations: list[dict]) -> list[dict]:
    """Fetch real AR scores from applerankings.com, replacing LLM estimates."""
    from enrichment import _fetch_applerankings
    for rec in recommendations:
        name = rec.get("name", "")
        if not name:
            continue
        try:
            score, notes = _fetch_applerankings(name)
            if score:
                rec["ar_score"] = int(score)
            if notes:
                rec["ar_notes"] = notes
        except Exception as exc:
            print(f"[add_ar_scores] {name}: {exc}")
        time.sleep(0.3)
    return recommendations
