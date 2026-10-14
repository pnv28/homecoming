# Step 2 autonomous source and routing audit

Original geometry, attributes and gradients are preserved. A source investigation does not turn missing or contradictory evidence into a confirmed correction.

## Explanation for the team

82 affected source records match the original geodatabase and frozen Step 1. 29 cost-boundary subdivisions preserve usable portions beside invalid intervals. 26 sources still have unavailable time: 25 contain vertical intervals and 1 have unrepresentable Tobler costs.

Rejected clusters are inspected using original endpoint identities. Existing source routes, routes through other sources, and unreachable directions are reported separately. No tolerance is relaxed.

| Graph | Cluster interpretation | Healthy piece directions on affected sources |
|---|---|---:|
| general_distance | original_source_paths_connect_all_endpoint_sites: 11 | 58 |
| general_time | original_source_paths_connect_all_endpoint_sites: 11 | 58 |
| wheelchair_distance | fewer_than_two_mode_eligible_endpoint_sites: 1; original_source_paths_connect_all_endpoint_sites: 10 | 40 |
| wheelchair_time | fewer_than_two_mode_eligible_endpoint_sites: 1; original_source_paths_connect_all_endpoint_sites: 10 | 40 |

## Steps we will take

- [X] Verify affected XYZ and every original attribute against raw and frozen data.
- [X] Verify selected archive, extracted files and provider dictionary.
- [X] Audit source intervals and per-piece routes in both modes and metrics.
- [X] Preserve evidence in `source_routing_audit.json` and verify JSON save/reopen.
- [ ] Resolve unsupported original vertical geometry and extreme-gradient time limitations; no replacement data is established by this audit.
