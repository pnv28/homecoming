"""Record agreed policies and derive candidates without computing routes."""
from collections import Counter
import math

from .ingest import read_json


def load_policy(path):
    policy = read_json(path)
    if policy["policy_version"] != 1 or policy["always_open"] is not True:
        raise ValueError("Unsupported policy version or access-schedule policy")
    if policy["boarding"]["unknown_derived_code"] != 99:
        raise ValueError("Unknown boarding codes must use the agreed derived code 99")
    if not (policy["boarding"]["unknown_allows_pickup"]
            and policy["boarding"]["unknown_allows_dropoff"]
            and policy["boarding"]["preserve_source_code"]):
        raise ValueError("Unknown boarding codes must retain raw evidence and allow both")
    sample = policy["gradient"]["equal_height"]
    if sample["points_per_round"] != 4 or sample["maximum_rounds"] != 2:
        raise ValueError("Equal-height sampling must use at most two rounds of four")
    if policy["transport_time"]["walking_model"] != "standard_tobler":
        raise ValueError("The agreed walking model is standard Tobler")
    for key in ["lift_travel_seconds", "lift_wait_seconds"]:
        value = policy["transport_time"][key]
        if not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid equipment-time policy: " + key)
    return policy


def boarding_fields(raw_code, operator_codes, policy):
    # Numeric strings are possible across source versions. Avoid treating bool
    # as code 1, or a nonintegral number as a known pickup/dropoff definition.
    text = str(raw_code).strip() if raw_code is not None else ""
    known = {"1": 1, "2": 2, "3": 3}
    code = known.get(text, policy["boarding"]["unknown_derived_code"])
    pickup, dropoff = code in {2, 3, 99}, code in {1, 3, 99}
    operators = set(operator_codes.split("+"))
    general = bool(operators & set(policy["modes"]["general"]["bus_operators"]))
    wheelchair = bool(operators & set(policy["modes"]["wheelchair"]["bus_operators"]))
    return {"stop_pick_drop_derived": code, "boarding_code_assumed": code == 99,
            "allows_pickup": pickup, "allows_dropoff": dropoff,
            "general_operator_in_scope": general, "wheelchair_operator_in_scope": wheelchair,
            "general_boarding_candidate": general and pickup,
            "wheelchair_boarding_candidate": wheelchair and pickup}


def add_network_candidates(network, policy, report):
    """Tri-state base eligibility; unknowns stay unknown, all rows retained."""
    general, wheelchair = [], []
    excluded_general = set(policy["modes"]["general"]["excluded_path_types"])
    excluded_wheelchair = set(policy["modes"]["wheelchair"]["excluded_path_types"])
    for i in range(len(network)):
        kind = network.value("FeatureType_label", i)
        barrier = network.value("WheelchairBarrier_bool", i)
        general.append(None if kind is None else kind not in excluded_general)
        wheelchair.append(False if kind in excluded_wheelchair or barrier is True else
                          None if kind is None or barrier is None else True)
    network.add("general_mode_candidate", general, "bool")
    network.add("wheelchair_mode_candidate", wheelchair, "bool")
    network.metadata["mode_candidates"] = {
        "scope": "Only agreed feature-type and wheelchair-barrier rules; not routing or reachability",
        "enabled_filter_applied": False, "schedules_evaluated": False,
        "maximum_ramp_slope": None, "all_source_rows_retained": True}
    report.checks["network:mode_candidates"] = {
        "general": dict(Counter(str(v) for v in general)),
        "wheelchair": dict(Counter(str(v) for v in wheelchair)),
        "rows_removed": 0, "wheelchair_barrier_true_excluded": True}
    report.checks["model_policy"] = {
        "recorded": True, "graph_or_route_costs_computed": False,
        "walking_model": "standard_tobler", "wheelchair_speed_deferred": False,
        "final_combination_decided": False}


def canonical_sites(tables, policy, report):
    """Preserve all source versions; expose a unique, explicitly selected lookup."""
    from datetime import datetime
    from .models import Table
    table = next(t for t in tables if t.name == "PedRouteRelSitePoly")
    groups = {}
    for row in table.rows():
        groups.setdefault(row["SiteID"], []).append(row)
    selected = []
    choice = policy["source_review"]["canonical_site"]
    for key, rows in sorted(groups.items()):
        if len(rows) > 1:
            if key != choice["SiteID"]:
                raise ValueError("Unreviewed site versions: " + str(key))
            rows.sort(key=lambda r: datetime.strptime(r["LastAmendmentDate"], "%Y/%m/%d %H:%M:%S"))
            if rows[-1]["LastAmendmentDate"] != choice["LastAmendmentDate"]:
                raise ValueError("Canonical site date differs from accepted snapshot")
        selected.append(rows[-1])
    canonical = Table.from_rows("canonical_site_references", selected, types=table.types,
                               metadata={"selection": choice, "all_original_versions_preserved": True})
    report.checks["canonical_site_references"] = {"unique_sites": len(selected),
        "castle_peak_record": next(r for r in selected if r["SiteID"] == choice["SiteID"])}
    return canonical
