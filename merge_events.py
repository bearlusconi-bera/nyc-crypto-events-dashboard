#!/usr/bin/env python3
"""Merge freshly-scraped events into events.json, preserving history & removals.

Usage:
    python3 merge_events.py NEW_EVENTS.json [--date YYYY-MM-DD] \
        [--window-start YYYY-MM-DD] [--window-end YYYY-MM-DD] \
        [--status SOURCES_STATUS.json]

NEW_EVENTS.json is a JSON array of scraped events. Each item needs at least:
    name, start, category  (start = "YYYY-MM-DD")
Optional (recommended):
    end, time, dayOfWeek, venue, category,
    source, link, canonicalLink, sourceEventId, description, cost,
    highSignal(bool)

Merge rules:
  * Events are matched to existing ones by stable id, sourceEventId, canonical
    link + start, then finally fuzzy key (normalized name + start date), so the
    same event re-scraped next week updates in place.
  * On match: mutable fields (time, venue, link, description, cost, end,
    dayOfWeek, highSignal, source, category) are refreshed and lastSeen is
    bumped. firstSeen, dismissed, dismissedAt, going, goingAt are PRESERVED —
    a removed event stays removed and a saved ("going") event stays saved even
    if it re-appears.
  * New events get firstSeen = lastSeen = run date, dismissed/going = false.
  * Existing events not seen this run are kept untouched (history is never
    deleted; they age into the "Past" bucket by date on the dashboard).
"""
import json, re, sys, datetime, argparse
from urllib.parse import urlsplit, urlunsplit

MUTABLE = ["end", "time", "dayOfWeek", "venue", "category", "source",
           "link", "canonicalLink", "sourceEventId", "description", "cost",
           "highSignal", "startAt", "endAt"]

ALLOWED_CATEGORIES = {"crypto", "bocconi", "italian", "ai", "mba", "mba-online"}
CATEGORY_HORIZON_DAYS = {
    "crypto": 14,
    "ai": 14,
    "bocconi": 14,
    "italian": 14,
    "mba": 90,
    "mba-online": 90,
}
OK_STATUS = {"ok_events", "ok_empty_rendered"}
FAIL_STATUS = {
    "failed_blocked",
    "failed_dead_url",
    "failed_login",
    "failed_timeout",
    "failed_render_unavailable",
    "stale_content",
    "ambiguous_no_date",
}

class ValidationError(Exception):
    pass

def norm_key(name, start):
    slug = re.sub(r"[^a-z0-9]", "", (name or "").lower())[:25]
    return f"{slug}|{start}"

def slug_id(name, start):
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40]
    return f"{slug}-{start}"

def parse_ymd(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValidationError(f"{field} must be YYYY-MM-DD, got {value!r}")
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must be a valid date, got {value!r}") from exc

def canonical_url(value, field="link"):
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string URL, got {type(value).__name__}")
    raw = value.strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValidationError(f"{field} must be an http(s) URL, got {value!r}")
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))

def source_event_key(ev):
    sid = ev.get("sourceEventId") or ev.get("source_event_id")
    if sid in (None, ""):
        return None
    link = ev.get("canonicalLink") or ev.get("link")
    if link:
        source_scope = urlsplit(canonical_url(link, "canonicalLink/link")).netloc
    else:
        source_scope = re.sub(r"\s+", " ", str(ev.get("source", "")).strip().lower())
    return f"{source_scope}|{str(sid).strip().lower()}|{ev.get('start', '')}"

def link_start_key(ev):
    link = ev.get("canonicalLink") or ev.get("link")
    canonical = canonical_url(link, "canonicalLink/link") if link else ""
    if not canonical:
        return None
    return f"{canonical}|{ev.get('start', '')}"

def add_index(index, key, ev):
    if not key:
        return
    if key in index and index[key] is not ev:
        index[key] = None
    else:
        index[key] = ev

def indexed(index, key):
    if not key:
        return None
    return index.get(key)

def validate_event(ev, idx, today=None, scraped=False):
    label = f"scraped[{idx}]" if scraped else f"existing[{idx}]"
    if not isinstance(ev, dict):
        raise ValidationError(f"{label} must be an object")

    required = ["name", "start", "category"] if scraped else ["id", "name", "start", "category"]
    missing = [field for field in required if not ev.get(field)]
    if missing:
        raise ValidationError(f"{label} missing required field(s): {', '.join(missing)}")

    start = parse_ymd(ev["start"], f"{label}.start")
    ev.setdefault("end", ev["start"])
    end = parse_ymd(ev["end"], f"{label}.end")
    if end < start:
        raise ValidationError(f"{label}.end {ev['end']} is before start {ev['start']}")

    category = ev.get("category")
    if category not in ALLOWED_CATEGORIES:
        raise ValidationError(
            f"{label}.category must be one of {sorted(ALLOWED_CATEGORIES)}, got {category!r}"
        )

    if scraped and today:
        max_start = today + datetime.timedelta(days=CATEGORY_HORIZON_DAYS[category])
        if end < today:
            raise ValidationError(f"{label} is stale: end {ev['end']} is before run date {today}")
        if start > max_start:
            raise ValidationError(
                f"{label} exceeds {category} horizon: start {ev['start']} > {max_start}"
            )

    if ev.get("link"):
        ev["link"] = ev["link"].strip()
        ev["canonicalLink"] = canonical_url(ev["link"], f"{label}.link")
    elif ev.get("canonicalLink"):
        ev["canonicalLink"] = canonical_url(ev["canonicalLink"], f"{label}.canonicalLink")
        ev["link"] = ev["canonicalLink"]

    if ev.get("source_event_id") and not ev.get("sourceEventId"):
        ev["sourceEventId"] = ev["source_event_id"]
    if ev.get("sourceEventId") is not None:
        ev["sourceEventId"] = str(ev["sourceEventId"]).strip()

    if not scraped:
        ev.setdefault("dismissed", False)
        ev.setdefault("dismissedAt", None)
        ev.setdefault("going", False)
        ev.setdefault("goingAt", None)
        ev.setdefault("highSignal", False)

def load_status(path, today):
    if not path:
        return None
    with open(path) as f:
        status = json.load(f)
    if not isinstance(status, dict):
        raise ValidationError("--status must point to a JSON object")
    if status.get("runDate") != today.isoformat():
        raise ValidationError(f"status.runDate must be {today.isoformat()}, got {status.get('runDate')!r}")
    if status.get("renderCapability") != "ok":
        raise ValidationError("render/proxy capability unavailable; refusing to merge")
    if status.get("overall") == "red":
        raise ValidationError("collection status is red; refusing to merge")
    if status.get("overall") not in {"green", "yellow"}:
        raise ValidationError("status.overall must be green, yellow, or red")

    sources = status.get("sources")
    if not isinstance(sources, list):
        raise ValidationError("status.sources must be a list")
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValidationError(f"status.sources[{i}] must be an object")
        s = source.get("status")
        if s not in OK_STATUS | FAIL_STATUS:
            raise ValidationError(f"status.sources[{i}].status has unknown value {s!r}")
        if s == "ok_empty_rendered" and not source.get("evidence"):
            raise ValidationError(f"status.sources[{i}] ok_empty_rendered needs evidence")
    return status

def unique_id(base, by_id):
    candidate = base
    n = 2
    while candidate in by_id:
        candidate = f"{base}-{n}"
        n += 1
    return candidate

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("new_events")
    ap.add_argument("--data", default="events.json")
    ap.add_argument("--status", help="machine-readable per-source collection status JSON")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--window-start")
    ap.add_argument("--window-end")
    args = ap.parse_args()
    today = args.date
    today_date = parse_ymd(today, "--date")

    with open(args.data) as f:
        data = json.load(f)
    with open(args.new_events) as f:
        scraped = json.load(f)
    if isinstance(scraped, dict) and "events" in scraped:
        scraped = scraped["events"]
    if not isinstance(scraped, list):
        raise ValidationError("new events input must be a JSON array")

    status = load_status(args.status, today_date)

    existing = data.get("events", [])
    if not isinstance(existing, list):
        raise ValidationError("events.json must contain an events array")

    by_key, by_id, by_source_event, by_link_start = {}, {}, {}, {}
    for idx, ev in enumerate(existing):
        validate_event(ev, idx, scraped=False)
        if ev["id"] in by_id:
            raise ValidationError(f"duplicate existing id: {ev['id']}")
        by_id[ev["id"]] = ev
        add_index(by_key, norm_key(ev["name"], ev["start"]), ev)
        add_index(by_source_event, source_event_key(ev), ev)
        add_index(by_link_start, link_start_key(ev), ev)

    added, updated = 0, 0
    for idx, ev in enumerate(scraped):
        validate_event(ev, idx, today=today_date, scraped=True)
        key = norm_key(ev["name"], ev["start"])
        candidates = [
            indexed(by_source_event, source_event_key(ev)),
            indexed(by_link_start, link_start_key(ev)),
            indexed(by_key, key),
        ]
        if ev.get("id") and ev.get("id") in by_id and by_id[ev["id"]].get("start") == ev["start"]:
            candidates.append(by_id[ev["id"]])
        matches = []
        for candidate in candidates:
            if candidate is not None and all(candidate is not existing_match for existing_match in matches):
                matches.append(candidate)
        if len(matches) > 1:
            ids = ", ".join(m["id"] for m in matches)
            raise ValidationError(f"ambiguous match for scraped[{idx}] {ev['name']!r}: {ids}")

        match = matches[0] if matches else None
        if match:
            for fld in MUTABLE:
                if fld in ev and ev[fld] not in (None, ""):
                    match[fld] = ev[fld]
            match["lastSeen"] = today
            add_index(by_source_event, source_event_key(match), match)
            add_index(by_link_start, link_start_key(match), match)
            updated += 1
        else:
            base_id = ev.get("id") or slug_id(ev["name"], ev["start"])
            new = {
                "id": unique_id(base_id, by_id),
                "name": ev["name"], "start": ev["start"], "end": ev["end"],
                "time": ev.get("time", ""), "dayOfWeek": ev.get("dayOfWeek", ""),
                "venue": ev.get("venue", ""), "category": ev["category"],
                "source": ev.get("source", ""), "link": ev.get("link", ""),
                "canonicalLink": ev.get("canonicalLink", ""),
                "sourceEventId": ev.get("sourceEventId", ""),
                "description": ev.get("description", ""), "cost": ev.get("cost", ""),
                "highSignal": bool(ev.get("highSignal", False)),
                "firstSeen": today, "lastSeen": today,
                "dismissed": False, "dismissedAt": None,
                "going": False, "goingAt": None,
            }
            existing.append(new)
            by_id[new["id"]] = new
            add_index(by_key, key, new)
            add_index(by_source_event, source_event_key(new), new)
            add_index(by_link_start, link_start_key(new), new)
            added += 1

    data["events"] = existing
    data["generated"] = today
    if args.window_start: data.setdefault("window", {})["start"] = args.window_start
    if args.window_end: data.setdefault("window", {})["end"] = args.window_end
    if status is not None:
        data["collectionStatus"] = status

    with open(args.data, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Merged: +{added} new, ~{updated} updated, {len(existing)} total.")

if __name__ == "__main__":
    try:
        main()
    except ValidationError as exc:
        print(f"merge_events.py: validation failed: {exc}", file=sys.stderr)
        sys.exit(2)
