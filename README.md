# 🗽 NYC Crypto & Bocconi Events Dashboard

A self-updating dashboard of NYC crypto/web3, Bocconi, and AI events. Hosted on GitHub Pages.

**Live site:** https://bearlusconi-bera.github.io/nyc-crypto-events-dashboard/

## How it works

- **`events.json`** — the source of truth. Every event ever surfaced lives here with a stable `id`, `firstSeen`/`lastSeen` dates, and a `dismissed` flag. This is how the dashboard *tracks events over time*.
- **`index.html`** — a single-file dashboard (vanilla JS, no build). It buckets events into **This Week / Next Week / Upcoming / Past** relative to today, with category filters, search, and per-event removal.
- **Weekly auto-feed** — the PAI scheduled task `weekly-nyc-crypto-bocconi-events` re-scans the sources each week and **merges** new events into `events.json` (preserving `dismissed` flags), then commits. Removed events stay removed even if they re-appear in a later scan.

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
      "category": "crypto",              // crypto | bocconi | ai
      "source": "Cryptonomads + Luma",
      "link": "https://lu.ma/3armqtbg",
      "description": "...", "cost": "Paid",
      "highSignal": true,
      "firstSeen": "2026-06-14", "lastSeen": "2026-06-14",
      "dismissed": false, "dismissedAt": null
    }
  ]
}
```

Sources scanned weekly: cryptonomads.org, luma.com, partiful.com, bocconialumni.it, friendsofbocconiusa.org.
