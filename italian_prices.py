"""CardTrader asking-price snapshots for Italian Near Mint Pokémon singles."""

import json
import urllib.parse
import urllib.request
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


def resolve_blueprints(configs, token):
    games = get_json("/games", token)
    pokemon_ids = {game["id"] for game in games if "pokemon" in game["name"].lower()}
    if not pokemon_ids:
        raise ValueError("Gioco Pokémon assente dal catalogo CardTrader")
    expansions = get_json("/expansions", token)
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
        rows = get_json("/blueprints/export?" + urllib.parse.urlencode({"expansion_id": expansion["id"]}), token)
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
