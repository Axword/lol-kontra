"""
Leaguepedia Cargo API client
Docs: https://lol.fandom.com/wiki/Special:CargoQuery
"""
import httpx
import time

BASE = "https://lol.fandom.com/wiki/Special:CargoExport"

def cargo_query(tables: str, fields: str, where: str = "", join_on: str = "", limit: int = 500, offset: int = 0):
    params = {
        "tables": tables,
        "fields": fields,
        "format": "json",
        "limit": str(limit),
        "offset": str(offset),
    }
    if where:
        params["where"] = where
    if join_on:
        params["join_on"] = join_on
    # respect rate limit
    time.sleep(0.5)
    r = httpx.get(BASE, params=params, timeout=30.0, follow_redirects=True)
    r.raise_for_status()
    return r.json()

def iter_cargo(tables, fields, where="", join_on=""):
    offset = 0
    limit = 500
    while True:
        data = cargo_query(tables, fields, where, join_on, limit, offset)
        # API returns list or dict ?
        rows = data if isinstance(data, list) else data.get('cargoquery', [])
        if not rows:
            break
        # normalize cargoquery format
        norm = []
        for row in rows:
            if 'title' in row:
                norm.append(row['title'])
            else:
                norm.append(row)
        yield from norm
        if len(rows) < limit:
            break
        offset += limit
