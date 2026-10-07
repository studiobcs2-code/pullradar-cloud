"""PullRadar: verified market snapshots -> static Instagram assets -> Buffer.

No card scans are downloaded or published. `prepare` is safe without credentials;
`publish` requires a Buffer key and refuses fixture data.
"""

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont
from editorial import global_search_ranking, news_candidates


ROOT = Path(__file__).resolve().parent
ROME = ZoneInfo("Europe/Rome")
NOW = datetime.now(ROME)
DAY = NOW.date().isoformat()
PUBLIC = ROOT / "public" / DAY
STATE = ROOT / "state.json"
PLAN = ROOT / "plan.json"
SNAPSHOTS = ROOT / "snapshots.json"
INSIGHTS = ROOT / "insights.json"
API = "https://api.tcgdex.net/v2/it/cards/"
PRICE_GUIDE = "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_6.json"
BUFFER = "https://api.buffer.com"
PLAN_VERSION = 2


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


def price_change(card, history):
    """Compare only the same Cardmarket trend metric for the same card."""
    previous = [x for x in history.get(card["id"], []) if x.get("date", "") < DAY
                and x.get("metric") == "cardmarket.trend" and isinstance(x.get("value"), (int, float))
                and x["value"] > 0]
    if not previous:
        return "Variazione: storico non disponibile"
    latest = max(previous, key=lambda x: x["date"])
    old = latest["value"]
    pct = (card["trend"] / old - 1) * 100
    return f"Variazione vs {latest['date']}: {pct:+.1f}%"


def record_prices(cards, history):
    for card in cards:
        rows = [x for x in history.get(card["id"], []) if x.get("date") != DAY]
        rows.append({"date": DAY, "metric": "cardmarket.trend", "value": card["trend"],
                     "source_updated": card["updated"]})
        history[card["id"]] = rows[-60:]
    write_json(SNAPSHOTS, history)


def buffer_query(key, query):
    request = urllib.request.Request(BUFFER, data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(str(result["errors"]))
    return result.get("data") or {}


def read_insights():
    """Read sent-post metrics; keep raw insights off the public repository."""
    key, channel = os.environ.get("BUFFER_API_KEY"), os.environ.get("BUFFER_CHANNEL_ID")
    if not key or not channel:
        raise RuntimeError("Mancano credenziali Buffer per gli insight")
    info = buffer_query(key, "query { channel(input:{id:" + json.dumps(channel) + "}) { organizationId } }")
    org = (info.get("channel") or {}).get("organizationId")
    if not org:
        raise RuntimeError("Organizzazione Buffer non disponibile")
    query = ("query { posts(first:50,input:{organizationId:" + json.dumps(org) +
             ",filter:{status:[sent],channelIds:[" + json.dumps(channel) +
             "]}}) { edges { node { id text metricsUpdatedAt metrics { type value } } } } }")
    data = buffer_query(key, query)
    scores = {card["id"]: [] for card in read_json(ROOT / "cards.json", [])}
    for edge in (data.get("posts") or {}).get("edges") or []:
        post = edge.get("node") or {}
        metrics = {m["type"]: m["value"] for m in post.get("metrics") or []}
        denominator = metrics.get("views") or metrics.get("impressions") or 0
        if denominator <= 0:
            continue
        for card_id in scores:
            if "/" + card_id in post.get("text", ""):
                engagement = sum(metrics.get(k, 0) for k in ("saves", "shares", "comments"))
                scores[card_id].append((engagement + 1) / (denominator + 30))
    choice = None
    eligible = {cid: values for cid, values in scores.items() if len(values) >= 3}
    if eligible:
        choice = max(eligible, key=lambda cid: sum(eligible[cid]) / len(eligible[cid]))
    write_json(INSIGHTS, {"date": DAY, "preferred_card_id": choice,
                          "sample_count": {cid: len(values) for cid, values in scores.items()}})
    print("Insight Buffer letti; priorità editoriale:", choice or "rotazione neutra")


def font(size, bold=False):
    paths = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
    )
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fetch_price_guide():
    request = urllib.request.Request(PRICE_GUIDE, headers={"User-Agent": "PullRadar/1.0"})
    with urllib.request.urlopen(request, timeout=35) as response:
        guide = json.load(response)
    stamp = guide.get("createdAt")
    if not stamp:
        raise ValueError("Guida Cardmarket senza data")
    updated = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S%z")
    age = NOW.astimezone(timezone.utc) - updated.astimezone(timezone.utc)
    if age < timedelta(minutes=-15) or age > timedelta(hours=48):
        raise ValueError(f"Guida Cardmarket fuori finestra di aggiornamento: {stamp}")
    rows = {row["idProduct"]: row for row in guide.get("priceGuides", [])}
    return rows, updated


def fetch_card(card_id, product_id, guide):
    fixture = os.environ.get("PULLRADAR_TEST_FIXTURE")
    if fixture:
        card = read_json(Path(fixture), {})[card_id]
    else:
        request = urllib.request.Request(API + card_id,
            headers={"User-Agent": "PullRadar/1.0 (editorial market monitoring)"})
        with urllib.request.urlopen(request, timeout=20) as response:
            card = json.load(response)
    if card.get("id") != card_id or not card.get("name") or not card.get("set", {}).get("name"):
        raise ValueError(f"Scheda incompleta: {card_id}")
    if fixture:
        price = (card.get("pricing") or {}).get("cardmarket") or {}
        updated = datetime.fromisoformat(price["updated"].replace("Z", "+00:00"))
    else:
        rows, updated = guide
        price = rows.get(product_id)
    if not price:
        raise ValueError(f"Prodotto assente nella guida Cardmarket: {product_id}")
    # Use the same published metric for all cards. It describes EU marketplace
    # prices, not Italian-language transactions or a specific condition.
    value = price.get("trend")
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"Trend Cardmarket non disponibile: {card_id}")
    return {
        "id": card_id,
        "name": card["name"],
        "set": card["set"]["name"],
        "setSize": (card["set"].get("cardCount") or {}).get("official") or "?",
        "localId": card.get("localId", ""),
        "trend": round(float(value), 2),
        "updated": updated.astimezone(ROME).strftime("%d/%m/%Y %H:%M"),
        "url": API + card_id,
    }


def text(draw, xy, value, size=44, fill="white", bold=False):
    draw.text(xy, value, font=font(size, bold), fill=fill, stroke_width=0)


def canvas(art_path, title, lines, out, story=False, section="MERCATO GCC", note=None):
    size = (1080, 1920) if story else (1080, 1350)
    im = Image.new("RGB", size, "#071522")
    art = Image.open(ROOT / art_path).convert("RGB")
    target_h = 1160 if story else 860
    scale = max(1080 / art.width, target_h / art.height)
    art = art.resize((int(art.width * scale), int(art.height * scale)), Image.Resampling.LANCZOS)
    x = (1080 - art.width) // 2
    im.paste(art, (x, 110))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    footer_y = 1130 if story else 800
    od.rectangle((0, 0, 1080, 164), fill=(4, 15, 27, 235))
    od.rectangle((0, footer_y, 1080, size[1]), fill=(4, 15, 27, 235))
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(im)
    text(draw, (62, 47), "PULLRADAR  /  " + section, 35, "#67e7ed", True)
    text(draw, (60, footer_y + 55), title[:30], 53, "#ffffff", True)
    y = footer_y + 140
    note_y = size[1] - 102
    max_width = 956
    for line in lines:
        words = str(line).split()
        chunks, current = [], ""
        for word in words:
            proposed = (current + " " + word).strip()
            if draw.textbbox((0, 0), proposed, font=font(36))[2] > max_width and current:
                chunks.append(current)
                current = word
            else:
                current = proposed
        if current:
            chunks.append(current)
        for chunk in chunks[:2]:
            if y > note_y - 53:
                break
            text(draw, (62, y), chunk, 36, "#dce9ed")
            y += 53
        y += 7
    text(draw, (62, note_y), note or "Illustrazione originale · non immagine della carta", 23, "#9fb6c5")
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=86, optimize=True)


def prepare():
    existing = read_json(PLAN, {})
    if (not os.environ.get("PULLRADAR_TEST_FIXTURE")
            and existing.get("date") == DAY and existing.get("source") == "live"
            and existing.get("version") == PLAN_VERSION
            and existing.get("items")
            and all((ROOT / file).exists() for item in existing["items"] for file in item["files"])):
        print("Piano odierno già pronto; riuso i contenuti per la storia serale")
        return

    cards_cfg = read_json(ROOT / "cards.json", [])
    guide = fetch_price_guide() if not os.environ.get("PULLRADAR_TEST_FIXTURE") else None
    cards = []
    for cfg in cards_cfg:
        if not (ROOT / cfg["art"]).exists():
            raise FileNotFoundError(cfg["art"])
        try:
            item = fetch_card(cfg["id"], cfg["idProduct"], guide)
        except (ValueError, KeyError, OSError) as error:
            print("Carta esclusa per dati incompleti:", cfg["id"], error)
            continue
        item["art"] = cfg["art"]
        item["query"] = cfg.get("query", "")
        cards.append(item)
    if len(cards) < 3:
        raise ValueError("Servono almeno tre schede con prezzo aggiornato")

    history = read_json(SNAPSHOTS, {})
    for card in cards:
        card["change"] = price_change(card, history)
    record_prices(cards, history)

    rotation = NOW.date().toordinal() % len(cards)
    ordered = cards[rotation:] + cards[:rotation]
    insight = read_json(INSIGHTS, {})
    preferred = insight.get("preferred_card_id") if insight.get("date") == DAY else None
    if preferred:
        ordered.sort(key=lambda card: card["id"] != preferred)
    a, b, c = ordered[:3]
    s = read_json(STATE, {"scheduled": {}})
    write_json(STATE, s)

    plan = []

    def add_post(number, hour, card, title, slides, caption, format_name, event_url=None, art_override=None):
        files = []
        section = "NEWS GCC" if format_name in ("ufficiale", "giappone", "novita_set", "indiscrezione") else (
            "RICERCHE" if format_name == "ricerche" else "MERCATO GCC")
        for slide, (slide_title, lines) in enumerate(slides, 1):
            p = PUBLIC / f"post-{number}-{slide}.jpg"
            artwork = art_override if art_override and slide < 3 else card["art"]
            canvas(artwork, slide_title, lines, p, section=section)
            files.append(p.relative_to(ROOT).as_posix())
        item = {"key": f"post-{number}", "type": "post", "hour": hour, "files": files,
                "caption": caption, "format": format_name, "title": title, "art": art_override or card["art"]}
        if event_url:
            item["event_url"] = event_url
        plan.append(item)

    def market_post(number, hour, card):
        number_label = f"{card['localId']}/{card['setSize']}"
        slides = [
            ("CHASE CARD", [card["name"], card["set"], f"Carta {number_label}", f"Trend UE € {card['trend']:.2f}"]),
            ("ANDAMENTO", [card["name"] + " · " + number_label, card["change"],
                            f"Trend Cardmarket € {card['trend']:.2f}", f"Aggiornato {card['updated']} Roma"]),
            ("COME LEGGERLO", ["Prezzo indicativo mercato UE", "Non è una vendita conclusa",
                                "Lingua e stato cambiano il valore", f"Fonte {card['updated']} Roma"]),
        ]
        caption = (f"📡 {card['name']} · {card['set']} #{number_label}: trend € {card['trend']:.2f}. "
                   f"{card['change']}. Cardmarket, aggiornato {card['updated']} (Roma). "
                   "Dato indicativo UE, non prezzo di una copia italiana specifica. "
                   "Illustrazione originale ispirata al soggetto, non scansione della carta. "
                   f"Scheda: {card['url']}\n#PokemonTCG #PullRadar #ChaseCards")
        add_post(number, hour, card, card["name"] + " " + number_label, slides, caption, "mercato")

    market_post(1, 9, a)

    ranking = None
    if not os.environ.get("PULLRADAR_TEST_FIXTURE"):
        try:
            ranking = global_search_ranking(cards)
        except Exception as error:
            print("Google Trends non disponibile; classifica omessa:", type(error).__name__, error)

    seen = s.get("covered_events", {})
    candidates = [] if os.environ.get("PULLRADAR_TEST_FIXTURE") else news_candidates(NOW)
    news = [event for event in candidates if event["url"] not in seen][:2]

    def news_post(number, hour, event, card):
        label = {"ufficiale": "ANNUNCIO UFFICIALE", "giappone": "NEWS DAL GIAPPONE",
                 "novita_set": "NEWS NUOVO SET", "indiscrezione": "INDISCREZIONE"}[event["kind"]]
        status = "NON CONFERMATA" if event["kind"] == "indiscrezione" else "Fonte datata e verificata"
        closing = "Dettagli nella fonte ufficiale" if event.get("detail") else "Nessuna uscita dedotta dal titolo"
        slides = [
            (label, [event["title"], f"Fonte: {event['source']}", f"Pubblicato: {event['published']}"]),
            ("COSA SAPPIAMO", [event.get("detail", "Titolo sintetizzato dalla fonte"), status,
                                "Apri il link nella didascalia", closing]),
            ("MERCATO OGGI", [f"{card['name']} · {card['set']}",
                              f"Trend UE € {card['trend']:.2f}", f"Cardmarket {card['updated']} Roma",
                              "Dato separato dalla notizia"]),
        ]
        prefix = ("⚠️ Indiscrezione non confermata." if event["kind"] == "indiscrezione" else
                  "📣 Annuncio ufficiale Pokémon." if event["kind"] == "ufficiale" else
                  "🇯🇵 Notizia dal Giappone." if event["kind"] == "giappone" else
                  "📰 Novità su un nuovo set riportata da PokéBeach.")
        caption = (f"{prefix} {event['title']}\nTitolo originale: {event['original']}\n"
                   f"Fonte: {event['source']}, {event['published']}. {event['url']}\n" +
                   (event.get("detail", "") + ". " if event.get("detail") else "") +
                   "Il carosello riporta il titolo della fonte; verifica i dettagli nell'articolo. "
                   f"Dato mercato separato: {card['name']} trend UE € {card['trend']:.2f}, "
                   f"Cardmarket {card['updated']} Roma. Illustrazione originale, non scansione. "
                   "#PokemonTCG #PullRadar #PokemonNews")
        add_post(number, hour, card, event["title"], slides, caption, event["kind"], event["url"], event.get("art"))

    def ranking_post(number, hour):
        top = ranking["scores"][:3]
        query = top[0][0]
        card = next(card for card in cards if card["query"] == query)
        name = lambda term: term.replace(" pokemon card", "")
        slides = [
            ("PIÙ CERCATE", ["Google Trends · mondo · 7 giorni", f"Tra {ranking['query_count']} ricerche monitorate",
                              *[f"{pos}. {name(q)} · indice {score:.1f}" for pos, (q, score) in enumerate(top, 1)]]),
            ("COME SI MISURA", ["Query: nome + pokemon card", "Indice Google Trends relativo",
                                "Non è numero di ricerche", "Non identifica una stampa precisa"]),
            ("CARTA IN EVIDENZA", [f"{card['name']} · {card['set']}",
                                    f"Trend UE € {card['trend']:.2f}", f"Cardmarket {card['updated']} Roma",
                                    "Prezzo distinto dall'indice ricerca"]),
        ]
        listed = ", ".join(f"{name(q)} {score:.1f}" for q, score in ranking["scores"])
        caption = (f"🔎 Quali nomi di carte Pokémon sono più cercati nel mondo tra i {ranking['query_count']} monitorati? "
                   f"Google Trends, ultimi 7 giorni: {listed}. "
                   "Indice relativo medio, non numero assoluto di ricerche e non classifica di tutte le carte. "
                   f"Rilevazione {ranking['updated']} UTC. "
                   f"Mercato separato: {card['name']} trend UE € {card['trend']:.2f}, "
                   f"Cardmarket {card['updated']} Roma. Illustrazione originale. "
                   "Fonte: https://trends.google.com/trends/explore?date=now%207-d "
                   "#PokemonTCG #PullRadar #GoogleTrends")
        add_post(number, hour, card, "Ricerche globali", slides, caption, "ricerche")

    if len(news) >= 2:
        news_post(2, 13, news[0], b)
        news_post(3, 19, news[1], c)
    elif len(news) == 1:
        if ranking:
            ranking_post(2, 13)
        else:
            market_post(2, 13, b)
        news_post(3, 19, news[0], c)
    else:
        if ranking:
            ranking_post(2, 13)
        else:
            market_post(2, 13, b)
        market_post(3, 19, c)

    for idx, (hour, card, label) in enumerate([(11, a, "IL DATO DEL GIORNO"),
                                               (20, c, "NUOVO POST SUL PROFILO")], 1):
        p = PUBLIC / f"story-{idx}.jpg"
        lines = [f"{card['name']} · € {card['trend']:.2f}", "Trend Cardmarket UE",
                 f"Aggiornato: {card['updated']}"]
        if idx == 2:
            post3 = next(item for item in plan if item["key"] == "post-3")
            lines = ["Il carosello delle 19 è online", "Scorri il nuovo post", "Apri @pull.radar"]
        story_art = "art/radar.jpg" if idx == 2 else card["art"]
        story_section = "DAL PROFILO" if idx == 2 else "MERCATO GCC"
        canvas(story_art, label, lines, p, story=True, section=story_section,
               note="Grafica originale PullRadar" if idx == 2 else None)
        plan.append({"key": f"story-{idx}", "type": "story", "hour": hour, "files": [p.relative_to(ROOT).as_posix()], "caption": ""})

    write_json(PLAN, {"version": PLAN_VERSION, "date": DAY,
                      "source": "fixture" if os.environ.get("PULLRADAR_TEST_FIXTURE") else "live",
                      "cards": cards, "items": plan})
    source_label = "fixture di prova" if os.environ.get("PULLRADAR_TEST_FIXTURE") else "dati live verificati"
    print(f"Preparati {len(plan)} contenuti per {DAY}; {source_label}")


def gql_value(obj):
    # Input is generated by this program only; json values are valid GraphQL
    # except object keys, which can be emitted without quotation marks.
    if isinstance(obj, dict):
        return "{" + ",".join(f"{key}:{gql_value(value)}" for key, value in obj.items()) + "}"
    if isinstance(obj, list):
        return "[" + ",".join(gql_value(x) for x in obj) + "]"
    return json.dumps(obj, ensure_ascii=False)


def persist_state(state):
    write_json(STATE, state)
    subprocess.run(["git", "add", "state.json"], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode:
        subprocess.run(["git", "commit", "-m", "Record Buffer schedule"], cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)


def buffer_post_status(key, post_id):
    query = "query { post(input:{id:" + json.dumps(post_id) + "}) { id status } }"
    request = urllib.request.Request(BUFFER, data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(str(result["errors"]))
    return (result.get("data", {}).get("post") or {}).get("status")


def audit():
    """Fail a cloud run when any expected daily item was not sent."""
    key = os.environ.get("BUFFER_API_KEY")
    if not key:
        raise RuntimeError("Manca la chiave Buffer per il controllo serale")
    scheduled = read_json(STATE, {"scheduled": {}}).get("scheduled", {}).get(DAY, {})
    expected = ["post-1", "story-1", "post-2", "post-3", "story-2"]
    problems = []
    for item in expected:
        post_id = scheduled.get(item)
        if not post_id:
            problems.append(f"{item}: non programmato")
            continue
        status = buffer_post_status(key, post_id)
        print(f"{item}: {status or 'stato sconosciuto'}")
        if status != "sent":
            problems.append(f"{item}: {status or 'stato sconosciuto'}")
    if problems:
        raise RuntimeError("Controllo serale: " + "; ".join(problems))
    print("Tutti e cinque i contenuti risultano inviati da Buffer")


def publish():
    key = os.environ.get("BUFFER_API_KEY", "")
    channel = os.environ.get("BUFFER_CHANNEL_ID", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not key or not channel or not repo or "/" not in repo:
        raise RuntimeError("Mancano secret/variable Buffer o GITHUB_REPOSITORY")
    plan = read_json(PLAN, {})
    if plan.get("date") != DAY or plan.get("source") != "live":
        raise RuntimeError("Piano assente o non verificato oggi")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    state = read_json(STATE, {"scheduled": {}})
    state.setdefault("scheduled", {}).setdefault(DAY, {})
    for item in plan["items"]:
        if item["key"] in state["scheduled"][DAY]:
            continue
        if item["key"] == "story-2":
            if datetime.now(ROME).hour < 19:
                print("Storia di rimando: attendo il post delle 19")
                continue
            preceding_id = state["scheduled"][DAY].get("post-3")
            if not preceding_id or buffer_post_status(key, preceding_id) != "sent":
                print("Storia di rimando: il post precedente non risulta inviato")
                continue
        due = datetime.combine(NOW.date(), datetime.min.time(), ROME).replace(hour=item["hour"])
        if due <= datetime.now(ROME) + timedelta(minutes=20):
            print(f"Slot passato: {item['key']}")
            continue
        urls = [f"https://raw.githubusercontent.com/{repo}/{sha}/{file}" for file in item["files"]]
        for url in urls:
            with urllib.request.urlopen(url, timeout=20) as check:
                if not check.headers.get("content-type", "").startswith("image/"):
                    raise ValueError(f"URL media non è immagine: {url}")
        inp = {
            "text": item["caption"],
            "channelId": channel,
            "schedulingType": "automatic",
            "mode": "customScheduled",
            "dueAt": due.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "aiAssisted": True,
            "assets": [{"image": {"url": u}} for u in urls],
            "metadata": {"instagram": {"type": item["type"], "shouldShareToFeed": item["type"] == "post", "isAiGenerated": True}},
        }
        # GraphQL enum values must not be quoted.
        input_str = gql_value(inp)
        for enum in ("automatic", "customScheduled", item["type"]):
            input_str = input_str.replace(f'"{enum}"', enum)
        query = "mutation { createPost(input:" + input_str + ") { ... on PostActionSuccess { post { id dueAt status } } ... on MutationError { message } } }"
        request = urllib.request.Request(BUFFER, data=json.dumps({"query": query}).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        if result.get("errors"):
            raise RuntimeError(str(result["errors"]))
        payload = result.get("data", {}).get("createPost", {})
        post = payload.get("post")
        if not post or not post.get("id"):
            raise RuntimeError(str(payload))
        state["scheduled"][DAY][item["key"]] = post["id"]
        if item.get("event_url"):
            state.setdefault("covered_events", {})[item["event_url"]] = DAY
        persist_state(state)
        print(f"Programma {item['key']}: {post['id']} {post.get('dueAt')}")


if __name__ == "__main__":
    commands = {"prepare": prepare, "publish": publish, "insights": read_insights, "audit": audit}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit("Uso: python pullradar.py prepare|publish|insights|audit")
    commands[sys.argv[1]]()
