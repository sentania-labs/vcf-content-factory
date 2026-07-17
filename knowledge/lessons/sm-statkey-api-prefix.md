# SM statkeys on the stats API are `Super Metric|sm_<uuid>`, not bare `sm_<uuid>`

**Date:** 2026-07-16. **Cost:** three independent false-negative "SM is
not computing" verdicts in one day, a wrongly-filed platform bug
(FB-016 as originally written), and a nearly-wrong defect closure
narrative — all from one missing key prefix.

## The trap

Super metrics are *defined* with id `sm_<uuid>` (that's what
`/api/supermetrics` returns, what policy XML references, and what the
factory's own YAML/renderer use). It is natural to assume the stat
series lands under the same key. It does not.

On the public Suite API stats surface (`GET
/api/resources/{id}/stats[/latest]`, `POST /api/resources/stats/query`),
SM series are keyed:

```
Super Metric|sm_<uuid>
```

Querying the bare `sm_<uuid>` returns `{"values": []}` — indistinguishable
from "SM never computed." The endpoint gives no error, no hint. Meanwhile
the UI charts the same series fine (its picker resolves the prefixed key),
so the failure presents as a spooky "UI shows data, API says empty"
discrepancy that invites platform-bug theories.

## How it bit us (DEF-010 closure, 2026-07-16)

1. A time-boxed verify pass queried `sm_c0c98494…` on one host: empty →
   "SM not computing yet" (plausible: known ~1h compute lag).
2. A full 9-host + 3-cluster recon sweep queried the same bare keys:
   uniformly empty → "user's UI observation not corroborated."
3. A browser pass then *confirmed* the UI charts real values, and FB-016
   was filed as a platform data-path discrepancy.
4. Only a statkeys listing (`GET /api/resources/{id}/statkeys`) exposed
   the actual key format — re-querying with the prefix returned the full
   series on every host and cluster (73+ datapoints, values matching the
   UI exactly).

## The rule

- **Reading SM data via API:** always `Super Metric|sm_<uuid>`.
- **Referencing the SM elsewhere** (definitions, policy XML, view
  attributes, cross-SM formulas): bare `sm_<uuid>` remains correct —
  the prefix exists only on the stats surface.
- **Before concluding any metric "has no data": list the resource's
  statkeys and grep for the key you think you're querying.** An empty
  stats response proves nothing about the metric; it may just prove
  your key is wrong. (`/api/resources/{id}/statkeys` is the ground
  truth for how a series is actually keyed.)

Related quirk, same day, same class: policy XML *export* lowercases
built-in metric ids (see `knowledge/context/api-surface/install_and_enable.md`) —
the stats surface and the policy surface each have their own key-shape
gotcha.
