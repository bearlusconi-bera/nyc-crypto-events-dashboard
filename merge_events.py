#!/usr/bin/env python3
"""Merge freshly-scraped events into events.json, preserving history & removals.

Usage:
    python3 merge_events.py NEW_EVENTS.json [--date YYYY-MM-DD] \
        [--window-start YYYY-MM-DD] [--window-end YYYY-MM-DD]

NEW_EVENTS.json is a JSON array of scraped events. Each item needs at least:
    name, start            (start = "YYYY-MM-DD")
Optional (recommended):
    end, time, dayOfWeek, venue, category(crypto|bocconi|ai),
    source, link, description, cost, highSignal(bool)

Merge rules:
  * Events are matched to existing ones by a fuzzy key (normalized name + start
    date), so the same event re-scraped next week updates in place.
  * On match: mutable fields (time, venue, link, description, cost, end,
    dayOfWeek, highSignal, source, category) are refreshed and lastSeen is
    bumped. firstSeen, dismissed, dismissedAt are PRESERVED — a removed event
    stays removed even if it re-appears.
  * New events get firstSeen = lastSeen = run date, dismissed = false.
  * Existing events not seen this run are kept untouched (history is never
    deleted; they age into the "Past" bucket by date on the dashboard).
"""
import json, re, sys, datetime, argparse

MUTABLE = ["end", "time", "dayOfWeek", "venue", "category", "source",
           "link", "description", "cost", "highSignal"]

def norm_key(name, start):
    slug = re.sub(r"[^a-z0-9]", "", (name or "").lower())[:25]
    return f"{slug}|{start}"

def slug_id(name, start):
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40]
    return f"{slug}-{start}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("new_events")
    ap.add_argument("--data", default="events.json")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--window-start")
    ap.add_argument("--window-end")
    args = ap.parse_args()
    today = args.date

    with open(args.data) as f:
        data = json.load(f)
    with open(args.new_events) as f:
        scraped = json.load(f)
    if isinstance(scraped, dict) and "events" in scraped:
        scraped = scraped["events"]

    existing = data.get("events", [])
    by_key = {norm_key(e["name"], e["start"]): e for e in existing}
    by_id = {e["id"]: e for e in existing}

    added, updated = 0, 0
    for ev in scraped:
        if not ev.get("name") or not ev.get("start"):
            print(f"  ! skipped (missing name/start): {ev}", file=sys.stderr)
            continue
        ev.setdefault("end", ev["start"])
        key = norm_key(ev["name"], ev["start"])
        match = by_key.get(key) or (by_id.get(ev["id"]) if ev.get("id") else None)
        if match:
            for fld in MUTABLE:
                if fld in ev and ev[fld] not in (None, ""):
                    match[fld] = ev[fld]
            match["lastSeen"] = today
            updated += 1
        else:
            new = {
                "id": ev.get("id") or slug_id(ev["name"], ev["start"]),
                "name": ev["name"], "start": ev["start"], "end": ev["end"],
                "time": ev.get("time", ""), "dayOfWeek": ev.get("dayOfWeek", ""),
                "venue": ev.get("venue", ""), "category": ev.get("category", "crypto"),
                "source": ev.get("source", ""), "link": ev.get("link", ""),
                "description": ev.get("description", ""), "cost": ev.get("cost", ""),
                "highSignal": bool(ev.get("highSignal", False)),
                "firstSeen": today, "lastSeen": today,
                "dismissed": False, "dismissedAt": None,
            }
            # avoid id collision
            while new["id"] in by_id:
                new["id"] += "-2"
            existing.append(new)
            by_id[new["id"]] = new
            by_key[key] = new
            added += 1

    data["events"] = existing
    data["generated"] = today
    if args.window_start: data.setdefault("window", {})["start"] = args.window_start
    if args.window_end: data.setdefault("window", {})["end"] = args.window_end

    with open(args.data, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Merged: +{added} new, ~{updated} updated, {len(existing)} total.")

if __name__ == "__main__":
    main()
