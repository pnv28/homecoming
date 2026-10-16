# Step 1 validation report

Status: **passed_with_warnings**. 0 errors; 14 warnings.

These checks establish preparation integrity, not route connectivity or accessibility.

## Checks

- **estates:accepted_crs_assumption**: "User-accepted WGS84 assumption: ha_hahdweb_dataspec.pdf defines latitude/longitude but does not explicitly specify their datum."
- **hospitals:accepted_crs_assumption**: "User-accepted WGS84 assumption: the supplied Hospital Authority specification defines latitude/longitude but does not explicitly specify their datum."
- **bus_stops:accepted_crs_assumption**: "User-accepted WGS84 assumption: the bus GeoJSON specification identifies latitude/longitude but does not explicitly specify a datum; derived stop coordinates match both raw inputs."
- **inventory**: {"selected_files": 23, "reference_copies_verified": 7}
- **network:source_gradient_evidence**: {"units_confirmed": "radians", "source_sign_and_aggregation_documented": false, "model_interpretation": "Recorded in model_policy.json; applied in later routing, raw values retained"}
- **network:mode_candidates**: {"general": {"True": 465887, "False": 5}, "wheelchair": {"True": 430522, "False": 35370}, "rows_removed": 0, "wheelchair_barrier_true_excluded": true}
- **model_policy**: {"recorded": true, "graph_or_route_costs_computed": false, "walking_model": "standard_tobler", "wheelchair_speed_deferred": false, "final_combination_decided": false}
- **canonical_site_references**: {"unique_sites": 3362, "castle_peak_record": {"SiteID": 1503020249, "ChineseName": "青山醫院", "EnglishName": "CASTLE PEAK HOSPITAL", "SiteType": 5, "CreationDate": "2026/07/09 00:00:00", "ModifiedBy": "LANDSD", "LastAmendmentDate": "2026/07/13 00:00:00", "source_fid": 3348, "record_id": "network:PedRouteRelSitePoly:3348"}}
- **estates:coordinate_roundtrip_max_deg**: 4.463117875275202e-09
- **hospitals:coordinate_roundtrip_max_deg**: 4.455714019968582e-09
- **mtr_exits:coordinate_roundtrip_max_deg**: 4.4351651240504e-09
- **mtr_exits:grid_residual_m**: {"min": 0.0304923257066219, "max": 1.7686805289549539, "threshold": 3.0}
- **railway_stations:coordinate_roundtrip_max_deg**: 4.433658773450588e-09
- **railway_stations:grid_residual_m**: {"min": 0.08982853925762531, "max": 1.4736873681425435, "threshold": 3.0}
- **bus_stops:coordinate_roundtrip_max_deg**: 4.577998424792895e-09
- **housing_district_counts**: {"Urban": 109, "New Territories": 60, "Extended Urban": 70, "Islands": 5}
- **mtr_exits:station_matches**: {"matched": 611, "ambiguous": 0, "unmatched": 0}
- **railway_stations:station_matches**: {"matched": 98, "ambiguous": 0, "unmatched": 0}
- **reference:mtr_exits:station_id**: {"parent": "mtr_stations", "unresolved_ids": 0, "affected_rows": 0}
- **reference:railway_stations:station_id**: {"parent": "mtr_stations", "unresolved_ids": 0, "affected_rows": 0}
- **reference:mtr_mobility_access:station_id**: {"parent": "mtr_stations", "unresolved_ids": 0, "affected_rows": 0}
- **reference:mtr_legacy_station_id_map:station_id**: {"parent": "mtr_stations", "unresolved_ids": 0, "affected_rows": 0}
- **reference:mtr_facilities:station_id**: {"parent": "mtr_stations", "unresolved_ids": 0, "affected_rows": 0}
- **reference:mtr_access_facility_links:facility_record_id**: {"parent": "mtr_facilities", "unresolved_ids": 0, "affected_rows": 0}
- **reference:mtr_access_facility_links:access_id**: {"parent": "mtr_exits", "unresolved_ids": 0, "affected_rows": 0}
- **mtr_master**: {"source_station_points": 98, "physical_stations": 98, "source_station_line_rows": 273, "blank_rows_ignored": 3, "line_rows_used_for_identity_only": 270, "legacy_station_ids_mapped": 100, "source_access_points": 611, "access_points_station_matched": 611, "mobility_access_records": 276, "access_points_without_mobility_evidence": 335, "access_points_without_exit_codes": 10, "source_facilities": 3564, "facilities_decoded": 3564, "unmapped_facility_rows": 72, "source_access_subcategories": {"unspecified": 362, "MTRLIF": 119, "MTRSLV": 61, "MTRRAM": 56, "MTRSTL": 11, "MTRWCA": 2}, "stations_with_mobility_access": 95, "equipment_evidence_differences": 3}
- **mtr_master_review**: {"unmapped_legacy_station_ids": 2, "access_points_without_mobility_evidence": 335, "access_points_without_exit_codes": 10, "positive_facilities_without_named_station_exit": 9, "positive_named_facilities_without_coordinate_match": 22, "equipment_evidence_differences": 3, "stations_without_mapped_mobility_access": 3}
- **bus_reconciliation**: {"raw_route_records": 69364, "distinct_raw_stop_ids": 9264, "prepared_stop_ids": 9264, "naming_variant_stops": 2980}
- **bus_boarding_candidates**: {"source_codes": {"2": 3831, "3": 61312, "1": 4196, "0": 25}, "derived_codes": {"2": 3831, "3": 61312, "1": 4196, "99": 25}, "assumed_code_rows": 25, "general_stops": 8848, "wheelchair_stops": 4130, "records_removed": 0}
- **network:shape**: {"vertices": 1963912, "line_parts": 465892, "zero_planar_length": 0, "z_min": -14.129400000005262, "z_max": 933.4017000000022}
- **network:wgs84_extent**: [113.84345638832238, 22.156392435714604, 114.44119053555679, 22.554575667544334]
- **network:provider_measurements**: {"gradient_unit": "radians", "gradient_min_rad": 0.0, "gradient_max_rad": 1.57065363, "negative_gradient_records": 0, "shape_length_unit": "metres", "shape_length_measurement": "horizontal XY polyline length", "horizontal_length_max_difference_m": 0.0, "horizontal_length_records_compared": 465892, "source_sign_convention": "not explicitly documented", "source_within_path_aggregation": "not explicitly documented"}
- **network:records**: {"source": 465892, "retained": 465892, "quarantined": 0}
- **network:missing_names**: 1718
- **estates:records**: {"source": 244, "retained": 244, "quarantined": 0}
- **estates:missing_names**: 0
- **hospitals:records**: {"source": 44, "retained": 44, "quarantined": 0}
- **hospitals:missing_names**: 0
- **mtr_exits:records**: {"source": 611, "retained": 611, "quarantined": 0}
- **mtr_exits:missing_names**: 0
- **railway_stations:records**: {"source": 98, "retained": 98, "quarantined": 0}
- **railway_stations:missing_names**: 0
- **bus_stops:records**: {"source": 9264, "retained": 9264, "quarantined": 0}
- **bus_stops:missing_names**: 0
- **PedRouteRelTerminalPoly:records**: {"source": 669, "retained": 669}
- **PedRouteRelFloorPoly:records**: {"source": 2596, "retained": 2596}
- **PedRouteRelDistancePost:records**: {"source": 3431, "retained": 3431}
- **PedRouteRelBldgPoly:records**: {"source": 9084, "retained": 9084}
- **PedRouteRelSitePoly:records**: {"source": 3363, "retained": 3363}
- **bus_route_stop_records:records**: {"source": 69364, "retained": 69364}
- **reference:network:TerminalID**: {"parent": "PedRouteRelTerminalPoly", "unresolved_ids": 9, "affected_rows": 11}
- **reference:network:FloorID**: {"parent": "PedRouteRelFloorPoly", "unresolved_ids": 3, "affected_rows": 34}
- **reference:network:SiteID**: {"parent": "PedRouteRelSitePoly", "unresolved_ids": 107, "affected_rows": 280}
- **reference:network:BuildingID_1**: {"parent": "PedRouteRelBldgPoly", "unresolved_ids": 44, "affected_rows": 248}
- **reference:network:BuildingID_2**: {"parent": "PedRouteRelBldgPoly", "unresolved_ids": 0, "affected_rows": 0}
- **reference:PedRouteRelDistancePost:PedestrianRouteID**: {"parent": "network", "unresolved_ids": 9, "affected_rows": 9}
- **access_policy**: {"always_open": true, "excluded_tables": ["AccessTime", "AccessTimeDetails"], "schedule_references_evaluated": false}
- **support_tables**: {"PedRouteRelTerminalPoly": 669, "PedRouteRelFloorPoly": 2596, "PedRouteRelDistancePost": 3431, "PedRouteRelBldgPoly": 9084, "PedRouteRelSitePoly": 3363, "canonical_site_references": 3362, "housing_crosswalk": 244, "mtr_stations": 98, "mtr_legacy_station_id_map": 100, "mtr_facility_categories": 36, "mtr_facilities": 3564, "mtr_station_crosswalk": 709, "mtr_facility_exit_references": 285, "mtr_access_facility_links": 261, "mtr_mobility_access": 276, "bus_route_stop_records": 69364, "bus_name_variants": 2980}
- **estate_hospital_location_policy**: {"user_accepted_map_point_approximation": true, "verified_entrance_collection_required": false, "network_connectors_computed": false}
- **network:spatial_roundtrip**: {"rows_checked": 465892, "all_fields": true, "wkb_exact": true, "timestamp_storage": "text (source strings retained)", "geometry_tolerance_m": 0.0}
- **estates:spatial_roundtrip**: {"rows_checked": 244, "all_fields": true, "wkb_exact": true, "timestamp_storage": "text (source strings retained)", "geometry_tolerance_m": 0.0}
- **hospitals:spatial_roundtrip**: {"rows_checked": 44, "all_fields": true, "wkb_exact": true, "timestamp_storage": "text (source strings retained)", "geometry_tolerance_m": 0.0}
- **mtr_exits:spatial_roundtrip**: {"rows_checked": 611, "all_fields": true, "wkb_exact": true, "timestamp_storage": "text (source strings retained)", "geometry_tolerance_m": 0.0}
- **railway_stations:spatial_roundtrip**: {"rows_checked": 98, "all_fields": true, "wkb_exact": true, "timestamp_storage": "text (source strings retained)", "geometry_tolerance_m": 0.0}
- **bus_stops:spatial_roundtrip**: {"rows_checked": 9264, "all_fields": true, "wkb_exact": true, "timestamp_storage": "text (source strings retained)", "geometry_tolerance_m": 0.0}
- **PedRouteRelTerminalPoly:sqlite_roundtrip**: {"rows_checked": 669, "all_fields": true}
- **PedRouteRelFloorPoly:sqlite_roundtrip**: {"rows_checked": 2596, "all_fields": true}
- **PedRouteRelDistancePost:sqlite_roundtrip**: {"rows_checked": 3431, "all_fields": true}
- **PedRouteRelBldgPoly:sqlite_roundtrip**: {"rows_checked": 9084, "all_fields": true}
- **PedRouteRelSitePoly:sqlite_roundtrip**: {"rows_checked": 3363, "all_fields": true}
- **canonical_site_references:sqlite_roundtrip**: {"rows_checked": 3362, "all_fields": true}
- **housing_crosswalk:sqlite_roundtrip**: {"rows_checked": 244, "all_fields": true}
- **mtr_stations:sqlite_roundtrip**: {"rows_checked": 98, "all_fields": true}
- **mtr_legacy_station_id_map:sqlite_roundtrip**: {"rows_checked": 100, "all_fields": true}
- **mtr_facility_categories:sqlite_roundtrip**: {"rows_checked": 36, "all_fields": true}
- **mtr_facilities:sqlite_roundtrip**: {"rows_checked": 3564, "all_fields": true}
- **mtr_station_crosswalk:sqlite_roundtrip**: {"rows_checked": 709, "all_fields": true}
- **mtr_facility_exit_references:sqlite_roundtrip**: {"rows_checked": 285, "all_fields": true}
- **mtr_access_facility_links:sqlite_roundtrip**: {"rows_checked": 261, "all_fields": true}
- **mtr_mobility_access:sqlite_roundtrip**: {"rows_checked": 276, "all_fields": true}
- **bus_route_stop_records:sqlite_roundtrip**: {"rows_checked": 69364, "all_fields": true}
- **bus_name_variants:sqlite_roundtrip**: {"rows_checked": 2980, "all_fields": true}
- **network:geodataframe_roundtrip**: {"rows_checked": 465892, "actual_type": "geopandas.GeoDataFrame", "all_attributes_and_nulls": true, "wkb_exact": true, "vertical_crs": "EPSG:5738", "nullable_types": {"PedestrianRouteID": "Int32", "Location": "Int32", "FeatureType": "Int32", "AliasNameEN": "string", "AliasNameTC": "string", "CrossingFeature": "Int32", "WeatherProof": "Int32", "WheelchairBarrier": "Int32", "WheelchairAccess": "Int32", "ObstaclesType": "Int32", "Gradient": "Float64", "Direction": "Int32", "PositionCertainty": "Int16", "Enabled": "Int32", "DataSource": "Int32", "LevelSource": "Int32", "StreetNameEN": "string", "StreetNameTC": "string", "ST_CODE": "Int32", "FloorID": "Int32", "BuildingID_1": "Int32", "BuildingID_2": "Int32", "SiteID": "Int32", "TerminalID": "Int32", "AccessTimeID": "Int32", "CreationDate": "string", "ModifiedBy": "string", "LastAmendmentDate": "string", "Shape_Length": "Float64", "id": "string", "source_id": "string", "name_en": "string", "name_zh_hant": "string", "name": "string", "entity_type": "string", "provenance": "string", "gradient_raw": "Float64", "Location_label": "string", "FeatureType_label": "string", "CrossingFeature_label": "string", "WeatherProof_label": "string", "WheelchairBarrier_label": "string", "WheelchairAccess_label": "string", "ObstaclesType_label": "string", "Direction_label": "string", "PositionCertainty_label": "string", "Enabled_label": "string", "DataSource_label": "string", "LevelSource_label": "string", "WheelchairBarrier_bool": "boolean", "WheelchairAccess_bool": "boolean", "Enabled_bool": "boolean", "PositionCertainty_bool": "boolean", "general_mode_candidate": "boolean", "wheelchair_mode_candidate": "boolean"}}
- **estates:geodataframe_roundtrip**: {"rows_checked": 244, "actual_type": "geopandas.GeoDataFrame", "all_attributes_and_nulls": true, "wkb_exact": true, "vertical_crs": null, "nullable_types": {"latitude": "Float64", "longitude": "Float64", "id": "string", "source_id": "string", "name": "string", "name_en": "string", "name_zh_hant": "string", "name_zh_hans": "string", "entity_type": "string", "location_role": "string", "entrance_evidence": "string", "source_identity_name": "string", "source_administrative_district": "string", "source_region": "string", "block_count_raw": "string", "block_names_json": "string", "raw_json": "string", "source_record": "Int64", "provenance": "string", "easting": "Float64", "northing": "Float64", "housing_district": "string", "crosswalk_residual_m": "Float64", "housing_district_provenance": "string"}}
- **hospitals:geodataframe_roundtrip**: {"rows_checked": 44, "actual_type": "geopandas.GeoDataFrame", "all_attributes_and_nulls": true, "wkb_exact": true, "vertical_crs": null, "nullable_types": {"has_ae": "boolean", "latitude": "Float64", "longitude": "Float64", "id": "string", "source_id": "string", "name": "string", "name_en": "string", "name_zh_hant": "string", "name_zh_hans": "string", "entity_type": "string", "location_role": "string", "entrance_evidence": "string", "cluster": "string", "address": "string", "raw_json": "string", "source_record": "Int64", "provenance": "string", "easting": "Float64", "northing": "Float64"}}
- **mtr_exits:geodataframe_roundtrip**: {"rows_checked": 611, "actual_type": "geopandas.GeoDataFrame", "all_attributes_and_nulls": true, "wkb_exact": true, "vertical_crs": null, "nullable_types": {"source_grid_easting": "Float64", "source_grid_northing": "Float64", "latitude": "Float64", "longitude": "Float64", "GEONAMEID": "Int64", "ENGLISHNAME": "string", "CHINESENAME": "string", "CLASS": "string", "TYPE": "string", "SUBCAT": "string", "SOURCE": "Int64", "E_FLOOR": "string", "C_FLOOR": "string", "E_SITENAME": "string", "C_SITENAME": "string", "E_AREA": "string", "C_AREA": "string", "E_DISTRICT": "string", "C_DISTRICT": "string", "E_REGION": "string", "C_REGION": "string", "E_ADDRESS": "string", "C_ADDRESS": "string", "TEL_NO": "string", "FAX_NO": "string", "WEB_SITE": "string", "REV_DATE": "string", "id": "string", "source_id": "string", "name": "string", "name_en": "string", "name_zh_hant": "string", "name_zh_hans": "string", "entity_type": "string", "location_role": "string", "raw_json": "string", "provenance": "string", "easting": "Float64", "northing": "Float64", "source_grid_residual_m": "Float64", "station_id": "string", "station_match_status": "string", "station_match_evidence": "string", "exit_code": "string", "access_id": "string", "has_mobility_evidence": "boolean", "mobility_types_json": "string", "access_evidence_json": "string", "access_evidence_difference": "boolean", "general_mode_candidate": "boolean", "wheelchair_mode_candidate": "boolean", "exit_only_evidence": "boolean"}}
- **railway_stations:geodataframe_roundtrip**: {"rows_checked": 98, "actual_type": "geopandas.GeoDataFrame", "all_attributes_and_nulls": true, "wkb_exact": true, "vertical_crs": null, "nullable_types": {"source_grid_easting": "Float64", "source_grid_northing": "Float64", "latitude": "Float64", "longitude": "Float64", "GEONAMEID": "Int64", "ENGLISHNAME": "string", "CHINESENAME": "string", "CLASS": "string", "TYPE": "string", "SUBCAT": "string", "SOURCE": "Int64", "E_FLOOR": "string", "C_FLOOR": "string", "E_SITENAME": "string", "C_SITENAME": "string", "E_AREA": "string", "C_AREA": "string", "E_DISTRICT": "string", "C_DISTRICT": "string", "E_REGION": "string", "C_REGION": "string", "E_ADDRESS": "string", "C_ADDRESS": "string", "TEL_NO": "string", "FAX_NO": "string", "WEB_SITE": "string", "REV_DATE": "string", "id": "string", "source_id": "string", "name": "string", "name_en": "string", "name_zh_hant": "string", "name_zh_hans": "string", "entity_type": "string", "location_role": "string", "raw_json": "string", "provenance": "string", "easting": "Float64", "northing": "Float64", "source_grid_residual_m": "Float64", "station_id": "string", "station_match_status": "string", "station_match_evidence": "string", "exit_code": "string"}}
- **bus_stops:geodataframe_roundtrip**: {"rows_checked": 9264, "actual_type": "geopandas.GeoDataFrame", "all_attributes_and_nulls": true, "wkb_exact": true, "vertical_crs": null, "nullable_types": {"latitude": "Float64", "longitude": "Float64", "GMB": "boolean", "KMB": "boolean", "CTB": "boolean", "id": "string", "source_id": "string", "name": "string", "name_en": "string", "name_zh_hant": "string", "name_zh_hans": "string", "entity_type": "string", "location_role": "string", "boarding_accessibility": "string", "operators_json": "string", "raw_json": "string", "provenance": "string", "easting": "Float64", "northing": "Float64", "general_boarding_candidate": "boolean", "wheelchair_boarding_candidate": "boolean"}}
- **source_hashes_rechecked_before_publication**: 23
- **mtr_master_json_roundtrip**: {"files": 8, "all_values": true}

## Issues

- **warning / estates / housing_boundary_proxies**: Town-area boundaries are geographic proxies, not HA-issued allocation polygons; assignments retain crosswalk provenance.
- **warning / mtr / mtr_master_review**: unmapped_legacy_station_ids
  Details: {"records": 2, "report": "mtr_master/mtr_master_review.json"}
- **warning / mtr / mtr_master_review**: access_points_without_mobility_evidence
  Details: {"records": 335, "report": "mtr_master/mtr_master_review.json"}
- **warning / mtr / mtr_master_review**: access_points_without_exit_codes
  Details: {"records": 10, "report": "mtr_master/mtr_master_review.json"}
- **warning / mtr / mtr_master_review**: positive_facilities_without_named_station_exit
  Details: {"records": 9, "report": "mtr_master/mtr_master_review.json"}
- **warning / mtr / mtr_master_review**: positive_named_facilities_without_coordinate_match
  Details: {"records": 22, "report": "mtr_master/mtr_master_review.json"}
- **warning / mtr / mtr_master_review**: equipment_evidence_differences
  Details: {"records": 3, "report": "mtr_master/mtr_master_review.json"}
- **warning / mtr / mtr_master_review**: stations_without_mapped_mobility_access
  Details: {"records": 3, "report": "mtr_master/mtr_master_review.json"}
- **warning / PedRouteRelSitePoly / reference_versions**: Multiple source records share an entity ID; all versions retained; canonical_site_references records the accepted selection
  Details: {"entity_field": "SiteID", "duplicates": {"1503020249": 2}}
- **warning / network / reference**: Unresolved TerminalID references to PedRouteRelTerminalPoly.TerminalID
  Details: {"unresolved": {"1511001551": 1, "1810001995": 3, "1810002543": 1, "1810002996": 1, "1511000791": 1, "1513000245": 1, "1810002345": 1, "1511000569": 1, "1810002677": 1}, "affected_rows": 11}
- **warning / network / reference**: Unresolved FloorID references to PedRouteRelFloorPoly.FloorID
  Details: {"unresolved": {"290000437": 15, "280000011": 2, "1810133737": 17}, "affected_rows": 34}
- **warning / network / reference**: Unresolved SiteID references to PedRouteRelSitePoly.SiteID
  Details: {"unresolved": {"1810027637": 1, "1503015099": 1, "1503015180": 2, "1503015172": 2, "1502015212": 1, "1810009513": 5, "1503015832": 1, "1502015390": 1, "1503018102": 1, "1503018110": 2, "1503018324": 2, "1910055412": 4, "1502005588": 4, "1810050891": 1, "1503022792": 1, "1503025561": 4, "1810033226": 1, "1810034908": 1, "1502010185": 1, "1503010607": 5, "1503010005": 1, "1503010090": 2, "1502010029": 1, "1810016102": 1, "1810032761": 3, "1503015177": 1, "1503016100": 3, "1910052687": 9, "1503025406": 1, "1810015121": 3, "1503020997": 1, "1810020811": 3, "1810034403": 2, "1503015739": 1, "1810012575": 1, "1502015240": 1, "1503015759": 2, "1503022616": 2, "1503022170": 1, "1810031881": 2, "1503018211": 17, "1503005742": 1, "1502015289": 2, "1810012654": 1, "1502010193": 7, "1502015141": 1, "1810052645": 5, "1810034724": 2, "1503015922": 1, "1502015291": 1, "1503018130": 4, "1503018148": 8, "1810049632": 1, "1810016007": 3, "1502010226": 14, "1810049649": 2, "1810024675": 8, "1503020412": 1, "1810032482": 7, "1503022731": 1, "1810024401": 4, "1810049644": 1, "1503025035": 3, "1502010209": 3, "1810049630": 2, "1502010220": 1, "1503018162": 7, "1503018149": 1, "1503018159": 1, "1503018050": 2, "1503018049": 2, "1810027217": 1, "1503015206": 2, "1503020569": 1, "1503025641": 1, "1503025635": 1, "1503025649": 1, "1503000017": 1, "1503025719": 2, "1810044272": 1, "1503025624": 2, "1502025150": 1, "1503010926": 1, "1810015423": 1, "1502025180": 1, "1503025584": 1, "1503025304": 4, "1503025306": 1, "1503025363": 2, "1503025342": 3, "1503025422": 1, "1503025369": 2, "1503018067": 1, "1503025508": 2, "1503018321": 10, "1810032981": 1, "1503018319": 1, "1503018323": 1, "1503018322": 1, "1503018101": 1, "1503018106": 1, "1503022655": 8, "1810010775": 1, "1503018231": 1, "1503022031": 1, "1502022186": 1, "1910064351": 22}, "affected_rows": 280}
- **warning / network / reference**: Unresolved BuildingID_1 references to PedRouteRelBldgPoly.BuildingID
  Details: {"unresolved": {"1103125959": 1, "1103117332": 1, "1103131449": 1, "1103126530": 1, "1103126385": 37, "1810082812": 8, "1810109468": 1, "1810094771": 1, "1810089577": 1, "1108247030": 24, "1108246984": 13, "1810121297": 2, "1101763535": 28, "1101763584": 6, "1810139261": 1, "1810071330": 1, "1103138158": 3, "1103119112": 37, "1810187806": 3, "1106128223": 3, "1810203325": 1, "1108524566": 1, "1810147806": 1, "1810176779": 1, "1108244372": 1, "1108244416": 1, "1108244368": 1, "1108247151": 15, "1108247442": 28, "1109910711": 1, "1101776180": 1, "1106128222": 1, "1810166717": 1, "1106127744": 1, "1106127895": 1, "1106127306": 1, "1106128178": 1, "1106128525": 3, "1106128285": 3, "1810160017": 1, "1810151795": 1, "1106130900": 1, "1810179303": 1, "1910235029": 7}, "affected_rows": 248}
- **warning / PedRouteRelDistancePost / reference**: Unresolved PedestrianRouteID references to network.PedestrianRouteID
  Details: {"unresolved": {"290040135": 1, "290040131": 1, "290040132": 1, "290040263": 1, "290040133": 1, "290040134": 1, "290040128": 1, "290040130": 1, "210018472": 1}, "affected_rows": 9}
