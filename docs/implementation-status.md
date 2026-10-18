# Current implementation status

Reviewed against the standalone application on 18 October 2026. See the [README](../README.md) for current setup and operator behavior. [PLAN.md](../PLAN.md) and the [engine guides](engine/) preserve historical decisions and implementation records.

Step 5 implements final scoring and ranking in [src/estate_ranking/step_5.py](../src/estate_ranking/step_5.py). It scores cached Step 4 journey measurements without running new route searches. The packaged Step 5 run is `20261016T122956Z-21343da6`, using amended Step 4 `20261016T102523Z-8e69faad`; its [scoring policy](../precomputed/outputs/step_5/runs/20261016T122956Z-21343da6/scoring_policy.json) and [validation report](../precomputed/outputs/step_5/runs/20261016T122956Z-21343da6/validation_report.json) record the saved build.

The following fields in [config/routing_policy.json](../config/routing_policy.json) are historical modelling-policy placeholders, not the application's current implementation status:

| Preserved field | Current behavior |
| --- | --- |
| `estate_subcosts.final_combination: null` | Each component is scaled as `100*x/(x+k)`, with bus `k=600 seconds`, MTR `k=900 seconds`, and hospital `k=5000 metres`. The total is the normalized weighted sum, with equal weights by default. Lower is better. |
| `estate_subcosts.unreachable_final_score: null` | An estate missing a positive-weight component has no total or numerical rank. It remains listed after complete estates. Zero-weight components are excluded from the total and completeness check. |
| `implementation_status.final_ranking: "not_implemented"` | Final ranking is implemented. Exact unrounded equal totals share competition ranks (`1,2,2,4`); changing the allocation category recomputes ranks within that category. |

The routing policy records source preparation and graph-model assumptions originating in Step 1, with later graph-policy additions. Successful builds retain policy snapshots, frozen inputs, and manifest hashes. Its legacy status fields are preserved here alongside the original policies and artifacts; they should not be updated to report application progress. Record current implementation status in this document and operational behavior in the README.

The archived [Step 5 guide](engine/step_5_implementation.md) explains the ranking API and saved fields. Its notice links to the original development workspace for plans and reports omitted from the standalone application.
