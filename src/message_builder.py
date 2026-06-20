"""
AI-powered push notification message generator.
Calls Claude to produce a single natural-language sentence summarising
the weekend's astrophotography outlook for Adelaide.
"""
from __future__ import annotations

import anthropic
from typing import List

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        import config
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def generate_notification_message(
    city: str,
    rule_label: str,
    nights: List[dict],
    threshold: float = 60.0,
) -> str:
    """
    Generate a natural-language push notification summary using Claude.
    Falls back to the compact format if the API call fails.

    `nights` is the list of all 3 weekend nights (date, score, avg_cloud, raw).
    """
    try:
        return _ai_message(city, rule_label, nights, threshold)
    except Exception as exc:
        print(f"[message_builder] AI generation failed: {exc}. Using fallback.")
        return _fallback_message(city, rule_label, nights)


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------

def _night_summary(night: dict, threshold: float) -> str:
    date = night["date"]
    raw = night.get("raw", {})
    score = night["score"]
    cloud = night.get("avg_cloud", raw.get("avg_cloud", 0.0))
    moon_pres = float(raw.get("moon_presence", 0.0))
    moon_illum = float(raw.get("moon_illumination", 0.0))
    wind = float(raw.get("wind_speed_kph", 0.0))
    tag = "GOOD" if score >= threshold else "poor"
    return (
        f"  {date.strftime('%A')}: score={score:.0f} ({tag}), "
        f"cloud={cloud:.0f}%, "
        f"moon visible={moon_pres:.0f}% at {moon_illum:.0f}% full, "
        f"wind={wind:.0f}kph"
    )


def _ai_message(city: str, rule_label: str, nights: List[dict], threshold: float) -> str:
    client = _get_client()

    night_block = "\n".join(_night_summary(n, threshold) for n in nights)

    prompt = f"""\
You are writing a push notification for an astrophotographer, in the voice of a knowledgeable friend texting a quick heads-up.

Night scores (good = score ≥ {threshold:.0f}):
{night_block}

Structure the notification so it's almost entirely about the best night: name the day, its score, and one or two specific conditions worth noting (e.g. no moon, low wind, clear skies, cold/hot). Then close with one short remark that acknowledges the other two options (nights) together — just enough to say whether either is a real backup worth considering or whether they're both not worth bothering with. That closing remark should be brief, roughly a quarter of the message at most, not a separate breakdown of each night.

If no night clears {threshold:.0f}, say so plainly and skip the "best night" framing — just tell them to skip the weekend, with maybe a one-line reason why.

Hard rules:
- No opener like "Adelaide:", "This weekend:", "Here's the outlook" — start directly with the substance.
- Write like a person, not a report. Avoid mechanical listing.
- Construct the response without using full stops to make the notification flow fluently.
- Total output under 220 characters."""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )

    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    if not text:
        return _fallback_message(city, rule_label, nights)

    print(f"[message_builder] AI generated: {text!r}  ({len(text)} chars)")
    return text


def _fallback_message(city: str, rule_label: str, nights: List[dict]) -> str:
    _abbrev = {4: "Fri", 5: "Sat", 6: "Sun"}
    parts = [
        f"{_abbrev.get(n['date'].weekday(), n['date'].strftime('%a'))}:{n['score']:.0f}"
        for n in nights
    ]
    return f"{city} {rule_label} — {' · '.join(parts)}"
