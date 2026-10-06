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


ROOT = Path(__file__).resolve().parent
ROME = ZoneInfo("Europe/Rome")
NOW = datetime.now(ROME)
DAY = NOW.date().isoformat()
PUBLIC = ROOT / "public" / DAY
STATE = ROOT / "state.json"
PLAN = ROOT / "plan.json"
API = "https://api.tcgdex.net/v2/it/cards/"
BUFFER = "https://api.buffer.com"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


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


def fetch_card(card_id):
    fixture = os.environ.get("PULLRADAR_TEST_FIXTURE")
    if fixture:
        card = read_json(Path(fixture), {})[card_id]
    else:
        request = urllib.request.Request(API + card_id, headers={"User-Agent": "PullRadar/1.0 (editorial market monitoring)"})
        with urllib.request.urlopen(request, timeout=20) as response:
            card = json.load(response)
    if card.get("id") != card_id or not card.get("name") or not card.get("set", {}).get("name"):
        raise ValueError(f"Scheda incompleta: {card_id}")
    price = card.get("pricing", {}).get("cardmarket", {})
    stamp = price.get("updated")
    if not stamp:
        raise ValueError(f"Prezzo senza data: {card_id}")
    updated = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if updated.astimezone(timezone.utc) > NOW.astimezone(timezone.utc) + timedelta(minutes=15):
        raise ValueError(f"Data prezzo futura: {card_id}")
    if NOW.astimezone(timezone.utc) - updated.astimezone(timezone.utc) > timedelta(hours=48):
        raise ValueError(f"Prezzo oltre 48 ore: {card_id}, {stamp}")
    if price.get("unit") != "EUR":
        raise ValueError(f"Valuta diversa da EUR: {card_id}")
    # Use the same published metric for all cards. It describes EU marketplace
    # prices, not Italian-language transactions or a specific condition.
    value = price.get("trend")
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"Trend Cardmarket non disponibile: {card_id}")
    return {
        "id": card_id,
        "name": card["name"],
        "set": card["set"]["name"],
        "localId": card.get("localId", ""),
        "trend": round(float(value), 2),
        "updated": updated.astimezone(ROME).strftime("%d/%m/%Y %H:%M"),
        "url": API + card_id,
    }


def text(draw, xy, value, size=44, fill="white", bold=False):
    draw.text(xy, value, font=font(size, bold), fill=fill, stroke_width=0)


def canvas(art_path, title, lines, out, story=False):
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
    footer_y = 1130 if story else 830
    od.rectangle((0, 0, 1080, 164), fill=(4, 15, 27, 235))
    od.rectangle((0, footer_y, 1080, size[1]), fill=(4, 15, 27, 235))
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(im)
    text(draw, (62, 47), "PULLRADAR  /  MERCATO GCC", 35, "#67e7ed", True)
    text(draw, (60, footer_y + 55), title[:28], 58, "#ffffff", True)
    y = footer_y + 145
    for line in lines:
        text(draw, (62, y), line[:44], 40, "#dce9ed")
        y += 64
    note_y = size[1] - 102
    text(draw, (62, note_y), "Fan art originale · non immagine della carta", 24, "#9fb6c5")
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=86, optimize=True)


def prepare():
    cards_cfg = read_json(ROOT / "cards.json", [])
    cards = []
    for cfg in cards_cfg:
        if not (ROOT / cfg["art"]).exists():
            raise FileNotFoundError(cfg["art"])
        item = fetch_card(cfg["id"])
        item["art"] = cfg["art"]
        cards.append(item)
    if len(cards) != 2:
        raise ValueError("Servono due schede valide per il pilota")

    a, b = cards
    s = read_json(STATE, {"scheduled": {}})
    write_json(STATE, s)
    if DAY in s["scheduled"] and len(s["scheduled"][DAY]) == 5:
        print("Cinque contenuti già programmati oggi; nessun doppione")
        return

    # Three distinct market angles. Each slide visibly shows the source date.
    posts = [
        ("charizard", a, ["Trend Cardmarket UE", f"€ {a['trend']:.2f}", f"{a['set']} · {a['localId']}", f"Fonte: TCGdex/Cardmarket", f"Aggiornato: {a['updated']}"]),
        ("pikachu", b, ["Trend Cardmarket UE", f"€ {b['trend']:.2f}", f"{b['set']} · {b['localId']}", f"Fonte: TCGdex/Cardmarket", f"Aggiornato: {b['updated']}"]),
        ("confronto", a, ["Due chase card, due trend", f"{a['name']}: € {a['trend']:.2f}", f"{b['name']}: € {b['trend']:.2f}", "Stessa metrica: trend UE", "Non è un prezzo di vendita garantito"]),
    ]
    plan = []
    for idx, (slug, c, lines) in enumerate(posts, 1):
        files = []
        for slide in range(1, 4):
            p = PUBLIC / f"post-{idx}-{slide}.jpg"
            if slide == 1:
                content = lines[:3]
            elif slide == 2:
                content = [lines[0], lines[1], lines[3], lines[4]]
            else:
                content = ["Come leggere il dato", "Trend di mercato UE", "Lingua e stato incidono sul prezzo", "Controlla le vendite concluse", f"Fonte aggiornata: {c['updated']}"]
            canvas(c["art"], c["name"] if idx < 3 else "Confronto del giorno", content, p)
            files.append(p.relative_to(ROOT).as_posix())
        subject = (f"{c['name']} — {c['set']} #{c['localId']}: € {c['trend']:.2f}"
                   if idx < 3 else
                   f"{a['name']} € {a['trend']:.2f} / {b['name']} € {b['trend']:.2f}")
        caption = (
            f"📡 {subject}\nTrend Cardmarket indicativo UE. "
            f"Fonte: TCGdex / Cardmarket, aggiornamento {c['updated']} (Roma). "
            "Il dato non identifica lingua, stato o prezzo di vendita della tua copia. "
            "Illustrazione originale del soggetto, non immagine della carta. "
            f"Scheda: {c['url']}\n#PokemonTCG #PullRadar #ChaseCards"
        )
        plan.append({"key": f"post-{idx}", "type": "post", "hour": [9, 13, 19][idx-1], "files": files, "caption": caption})

    for idx, (hour, c, label) in enumerate([(11, a, "IL DATO DEL GIORNO"), (20, b, "NUOVO POST SUL PROFILO")], 1):
        p = PUBLIC / f"story-{idx}.jpg"
        lines = [f"{c['name']} · € {c['trend']:.2f}", "Trend Cardmarket UE", f"Aggiornato: {c['updated']}"]
        if idx == 2:
            lines.insert(0, "Apri il post nel profilo @pull.radar")
        canvas(c["art"], label, lines, p, story=True)
        plan.append({"key": f"story-{idx}", "type": "story", "hour": hour, "files": [p.relative_to(ROOT).as_posix()], "caption": ""})

    write_json(PLAN, {"date": DAY, "source": "fixture" if os.environ.get("PULLRADAR_TEST_FIXTURE") else "live", "cards": cards, "items": plan})
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
        persist_state(state)
        print(f"Programma {item['key']}: {post['id']} {post.get('dueAt')}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("prepare", "publish"):
        raise SystemExit("Uso: python pullradar.py prepare|publish")
    (prepare if sys.argv[1] == "prepare" else publish)()
