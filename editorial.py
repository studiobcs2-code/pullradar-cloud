"""Small, dated source readers. Headlines are leads, never invented facts."""

import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup


UA = "PullRadar/2.0 (independent Pokemon TCG news monitor)"
JP_NEWS = "https://www.pokemon-card.com/info/"
POKEBEACH = "https://www.pokebeach.com/"
DELTA_PREVIEW = "https://www.pokemon.com/us/features/sneak-a-peek-at-cards-from-the-mega-evolution-delta-reign-expansion"


def get_text(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", "replace")


def italian_summary(original, kind):
    """Use only the headline's explicit category and set name, without machine-made facts."""
    quoted = re.search(r"[“\"「]([^”\"」]{3,48})[”\"」]", original)
    subject = f" «{quoted.group(1)}»" if quoted else ""
    lower = original.lower()
    if kind == "ufficiale":
        return "Annuncio ufficiale dal Giappone" + subject
    if kind == "giappone":
        return "Novità dal Giappone" + subject
    if kind == "indiscrezione":
        return "Indiscrezione non confermata" + subject
    if "card" in lower and "reveal" in lower:
        return "Nuove carte svelate" + subject
    return "Novità su un set Pokémon" + subject


def date_is_fresh(published, now, days=4):
    date = published.date() if isinstance(published, datetime) else published
    return now.date() - timedelta(days=days) <= date <= now.date()


def japanese_official(now):
    soup = BeautifulSoup(get_text(JP_NEWS), "html.parser")
    events = []
    for row in soup.select("#newsTab_pro .List_item"):
        anchor = row.select_one("a.List_item_inner")
        date_tag = row.select_one(".Date")
        if not anchor or not date_tag:
            continue
        try:
            published = datetime.strptime(date_tag.get_text(strip=True), "%Y.%m.%d").date()
        except ValueError:
            continue
        if not date_is_fresh(published, now):
            continue
        headline = " ".join(row.select_one(".List_body").stripped_strings)
        headline = headline.replace(date_tag.get_text(strip=True), "").replace("商品", "").strip()
        url = urllib.parse.urljoin(JP_NEWS, anchor.get("href", ""))
        if not url.startswith("https://www.pokemon-card.com/") and not url.startswith("https://www.30th.pokemon-card.com/"):
            continue
        if not headline or not re.search(r"パック|カード|セット|商品|拡張", headline):
            continue
        events.append({"kind": "ufficiale", "source": "Pokémon Card Game Giappone",
                       "title": italian_summary(headline, "ufficiale"), "original": headline,
                       "published": published.isoformat(), "url": url})
    return events


def pokebeach_leads(now):
    soup = BeautifulSoup(get_text(POKEBEACH), "html.parser")
    events = []
    for article in soup.select("article.category-tcg"):
        title_node = article.select_one(".entry-title a")
        meta = article.select_one(".entry-meta.frontpage")
        if not title_node or not meta:
            continue
        url = title_node.get("href", "")
        if not url.startswith("https://www.pokebeach.com/20"):
            continue
        date_match = re.search(r"[A-Z][a-z]{2} \d{1,2}, 20\d{2}", meta.get_text(" ", strip=True))
        if not date_match:
            continue
        try:
            published = datetime.strptime(date_match.group(), "%b %d, %Y").date()
        except ValueError:
            continue
        if not date_is_fresh(published, now):
            continue
        original = title_node.get_text(" ", strip=True)
        lower = original.lower()
        if "pocket" in lower or not re.search(r"set|expansion|booster|pack|cards?", lower):
            continue
        if re.search(r"leak|rumou?r|trademark|registered|unconfirmed", lower) and re.search(r"set|expansion|pack", lower):
            kind = "indiscrezione"
        elif re.search(r"japan|japanese", lower):
            kind = "giappone"
        elif re.search(r"set|expansion|booster|english cards", lower) and re.search(r"reveal|releas|launch|announc", lower):
            kind = "novita_set"
        else:
            continue
        events.append({"kind": kind, "source": "PokéBeach", "title": italian_summary(original, kind),
                       "original": original, "published": published.isoformat(), "url": url})
    return events


def news_candidates(now):
    events = []
    # Verified official source supplied for launch coverage. It expires naturally.
    delta_date = datetime(2026, 10, 5).date()
    if date_is_fresh(delta_date, now):
        events.append({"kind": "ufficiale", "source": "Pokémon.com",
                       "title": "Anteprima ufficiale di Dominio Delta",
                       "original": "Sneak a Peek at Cards from the Mega Evolution—Delta Reign Expansion",
                       "published": delta_date.isoformat(), "url": DELTA_PREVIEW,
                       "detail": "Uscita ufficiale: 6 novembre 2026", "art": "art/delta-dragon.jpg"})
    for reader in (japanese_official, pokebeach_leads):
        try:
            events.extend(reader(now))
        except Exception as error:
            print("Fonte notizie non disponibile:", reader.__name__, type(error).__name__, error)
    if any(event["url"] == DELTA_PREVIEW for event in events):
        events = [event for event in events if event["url"] == DELTA_PREVIEW
                  or "delta reign" not in event["original"].lower()]
    priority = {"ufficiale": 0, "giappone": 1, "novita_set": 2, "indiscrezione": 3}
    return sorted(events, key=lambda row: (row["published"], -priority[row["kind"]]), reverse=True)


def global_search_ranking(cards):
    """Compare up to five named card searches worldwide, not the whole catalogue."""
    from pytrends.request import TrendReq

    queries = list(dict.fromkeys(card["query"] for card in cards if card.get("query")))[:5]
    if len(queries) < 3:
        return None
    trends = TrendReq(hl="en-US", tz=0, timeout=(10, 20))
    trends.build_payload(queries, timeframe="now 7-d", geo="")
    frame = trends.interest_over_time()
    if frame.empty:
        return None
    if "isPartial" in frame:
        frame = frame[~frame["isPartial"]]
    if len(frame) < 24:
        return None
    scores = {query: round(float(frame[query].mean()), 1) for query in queries}
    if sum(scores.values()) <= 0:
        return None
    return {"source": "Google Trends", "period": "ultimi 7 giorni", "scope": "mondo",
            "sample": len(frame), "query_count": len(queries),
            "updated": frame.index[-1].replace(tzinfo=timezone.utc).isoformat(),
            "scores": sorted(scores.items(), key=lambda item: item[1], reverse=True)}
