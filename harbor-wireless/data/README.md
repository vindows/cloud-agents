# Harbor Wireless synthetic ticket data

ServiceNow-shaped synthetic dataset for the CIO Phase 1 triage demo. No real customer data.

Regenerate with a fixed seed (`20261124`):

```bash
python3 harbor-wireless/scripts/generate_synthetic_data.py
```

## Files

| File | Contents |
|------|----------|
| `tickets.json` | ~6,000 tickets spanning ~6 years of `opened_at` |
| `agents.json` | ~180 agents across 4 assignment groups |
| `golden-set.json` | ~200 labeled tickets for eval readout |
| `dataset-meta.json` | Counts / distributions from the last generation run |

## Ticket fields

`sys_id`, `number`, `short_description`, `description`, `category` (`access` \| `hardware` \| `network` \| `applications`), `priority`, `urgency`, `state`, `assignment_group`, `assigned_to`, `opened_at`, `caller_id`, `parent` (duplicate → original `number`, else `null`), `is_duplicate`, `recency_tier` (`recent` \| `middle` \| `stale`), `channel`.

## Targets

- ~30% duplicates (`parent` set)
- Recency tiers: last ~15 days / ~16–180 days / multi-year stale
- Assignment groups: `HW-Access-Identity`, `HW-Endpoint-Hardware`, `HW-Network-Ops`, `HW-Enterprise-Apps`
- Golden labels: `label_category`, `label_is_duplicate`, `label_urgency`
