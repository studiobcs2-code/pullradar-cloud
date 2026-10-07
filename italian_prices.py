"""CardTrader asking-price snapshots for Italian Near Mint Pokémon singles."""

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from statistics import mean

BASE = "https://api.cardtrader.com/api/v2"
METRIC = "cardtrader.it.nm.lowest5.mean"
EXPANSION_TERMS = {
    "30th": ("30th", "anniversary"),
    "me04": ("chaos rising",),
    "me05": ("pitch black",),
}


def get_json(path, token):
    request = urllib.request.Request(BASE + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "PullRadar/1.0 (Italian-language market monitoring)",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def catalog_rows(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "games", "expansions", "blueprints"):
            if key in data:
                return catalog_rows(data[key])
        return [value for value in data.values() if isinstance(value, dict)]
    raise ValueError("Formato catalogo CardTrader non riconosciuto")


def resolve_blueprints(configs, token):
    games = catalog_rows(get_json("/games", token))
    pokemon_ids = {game["id"] for game in games if "pokemon" in game.get("name", "").lower()}
    if not pokemon_ids:
        raise ValueError("Gioco Pokémon assente dal catalogo CardTrader")
    expansions = catalog_rows(get_json("/expansions", token))
    relevant = []
    for expansion in expansions:
        if expansion.get("game_id") not in pokemon_ids:
            continue
        name = expansion.get("name", "").lower()
        if any(term in name for terms in EXPANSION_TERMS.values() for term in terms):
            relevant.append(expansion)
    wanted = {int(cfg["idProduct"]) for cfg in configs}
    found = {}
    for expansion in relevant:
        rows = catalog_rows(get_json("/blueprints/export?" + urllib.parse.urlencode({"expansion_id": expansion["id"]}), token))
        for row in rows:
            if row.get("game_id") not in pokemon_ids:
                continue
            for market_id in row.get("card_market_ids") or []:
                if int(market_id) in wanted:
                    found.setdefault(int(market_id), set()).add(int(row["id"]))
    return {product_id: next(iter(ids)) for product_id, ids in found.items() if len(ids) == 1}


def italian_nm_price(blueprint_id, token):
    path = "/marketplace/products?" + urllib.parse.urlencode({"blueprint_id": blueprint_id, "language": "it"})
    result = get_json(path, token)
    offers = result.get(str(blueprint_id)) or []
    prices = []
    for offer in offers:
        props = offer.get("properties_hash") or {}
        price = offer.get("price") or {}
        if (offer.get("blueprint_id") != blueprint_id or props.get("pokemon_language") != "it"
                or props.get("condition") != "Near Mint" or offer.get("graded")
                or offer.get("on_vacation") or offer.get("bundle_size") != 1
                or price.get("currency") != "EUR" or not isinstance(price.get("cents"), int)
                or price["cents"] <= 0):
            continue
        prices.append(price["cents"])
    prices.sort()
    if len(prices) < 5:
        raise ValueError(f"Meno di cinque offerte italiane Near Mint per blueprint {blueprint_id}")
    return round(mean(prices[:5]) / 100, 2), len(prices)


if __name__ == "__main__":
    token = os.environ.get("CARDTRADER_API_TOKEN")
    if not token:
        raise SystemExit("Manca CARDTRADER_API_TOKEN")
    cards = json.loads((Path(__file__).resolve().parent / "cards.json").read_text())
    blueprints = resolve_blueprints(cards, token)
    valid = 0
    for card in cards:
        card_id = card["id"]
        blueprint = blueprints.get(int(card["idProduct"]))
        if not blueprint:
            print(card_id, "stampa non trovata")
            continue
        try:
            value, count = italian_nm_price(blueprint, token)
        except ValueError as error:
            print(card_id, str(error))
            continue
        print(card_id, f"€ {value:.2f}", f"{count} offerte IT NM")
        valid += 1
    if valid < 3:
        raise SystemExit("Meno di tre carte con prezzi italiani verificati")
