# 🗽 NYC Crypto & Bocconi Events Dashboard

A self-updating dashboard of NYC crypto/web3, Bocconi, Italian, MBA/MS, and AI events. Hosted on GitHub Pages.

**Live site:** https://bearlusconi-bera.github.io/nyc-crypto-events-dashboard/

## How it works

- **`events.json`** — the source of truth. Every event ever surfaced lives here with a stable `id`, `firstSeen`/`lastSeen` dates, a `dismissed` flag, a `going` flag, and the latest machine-readable `collectionStatus`.
- **`index.html`** — a single-file dashboard (vanilla JS, no build). It buckets events into **This Week / Next Week / Upcoming / Past** relative to today, with category filters, search, and per-event removal.
- **Weekly auto-feed** — the PAI scheduled task `weekly-nyc-crypto-bocconi-events` re-scans the sources each week and **merges** new events into `events.json` (preserving `dismissed` and `going` flags), then commits. Removed events stay removed even if they re-appear in a later scan.
- **Source health** — each run records per-source status such as `ok_events`, `ok_empty_rendered`, `failed_blocked`, or `failed_dead_url`. A render/proxy capability outage aborts before merge/commit so stale data is not stamped as fresh.

## Saving events ("I'll go")

Click **✓ I'll go** on any card to file it into your **going list** and hide it from the main view (so you stop seeing events you've already decided on). Open the list with the **★ My going list** toggle; remove an event from it with **↩ Not going**. Like removals, the going list is committed back to `events.json` when a token is configured (and the weekly job preserves it).

## Removing events ("not interesting")

Click **✕ Not interesting** on any card.

- Removal is applied instantly on your device (localStorage).
- If you've configured a **GitHub token** (⚙︎ Sync button → fine-grained PAT, Contents: Read & write, scoped to this repo only), the removal is **committed back to `events.json`**, so it syncs across devices and the weekly job respects it.
- **Restore** any removed event with the "Show removed" toggle → ↩ Restore.

### Security note
The token is stored in your browser's `localStorage`. Use a **fine-grained token scoped to this one repo** with only **Contents: Read & write**, and revoke it if the device is shared. Without a token the dashboard is fully usable — removals just stay local to that browser.

## Data schema (`events.json`)

```jsonc
{
  "generated": "2026-06-14",
  "window": { "start": "2026-06-13", "end": "2026-06-27" },
  "events": [
    {
      "id": "tokenizethis-2026-06-23",   // stable: slug + start date
      "name": "TokenizeThis 2026",
      "start": "2026-06-23", "end": "2026-06-25",
      "time": "8:00 AM–5:00 PM EDT", "dayOfWeek": "Tue–Thu",
      "venue": "The Glasshouse, 660 12th Ave",
      "category": "crypto",              // crypto | bocconi | italian | ai | mba | mba-online
      "source": "Cryptonomads + Luma",
      "link": "https://lu.ma/3armqtbg",
      "canonicalLink": "https://lu.ma/3armqtbg",
      "sourceEventId": "3armqtbg",
      "description": "...", "cost": "Paid",
      "highSignal": true,
      "firstSeen": "2026-06-14", "lastSeen": "2026-06-14",
      "dismissed": false, "dismissedAt": null,
      "going": false, "goingAt": null
    }
  ],
  "collectionStatus": {
    "runDate": "2026-06-14",
    "overall": "green",
    "renderCapability": "ok",
    "sources": [
      {
        "source": "luma",
        "url": "https://luma.com/",
        "requiredMethod": "render-required",
        "status": "ok_events",
        "eventsFound": 8,
        "evidence": "Rendered search results and extracted event cards"
      }
    ]
  }
}
```

Collection windows: crypto, AI, Bocconi, and Italian events are scanned for the next 14 days; MBA and MBA-online events are scanned for the next 90 days.

Sources scanned weekly: luma.com, cryptonomads.org, eventbrite.com, meetup.com, partiful.com, bocconialumni.it, friendsofbocconiusa.org, italchamber.org, i3nyc.org, NYU Stern, Stanford MSx, MIT Sloan Fellows, INSEAD, and Kellogg.
