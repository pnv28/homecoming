# Step 3 validation

Status: passed.

All input points are retained. Connector assumptions and unattached points remain visible.

```json
{
  "status": "passed",
  "run_id": "20261016T080509Z-4c604c82",
  "attachments": {
    "source_points": 10163,
    "counts_by_type": {
      "estate": 244,
      "hospital": 44,
      "mtr_access": 611,
      "bus_stop": 9264
    },
    "attachment_records": 20814,
    "baseline_attachment_records": 20238,
    "all_source_points_accounted_for": true,
    "coverage": {
      "baseline/bus_stop/general/time": {
        "records": 9264,
        "statuses": {
          "attached": 8848,
          "excluded": 416
        },
        "eligible": 8848,
        "distance_m": {
          "0.0": 0.00025793918223586724,
          "0.5": 1.6007012195568282,
          "0.9": 5.817799097783307,
          "0.95": 9.199137175891297,
          "1.0": 5209.270924347119
        },
        "warnings": {
          "level_uncertain": 8848,
          "alternative_level": 98,
          "distance_tie_lower_height_assumption": 24,
          "indoor_fallback": 6,
          "connector_above_threshold": 36
        }
      },
      "baseline/bus_stop/wheelchair/time": {
        "records": 9264,
        "statuses": {
          "attached": 4130,
          "excluded": 5134
        },
        "eligible": 4130,
        "distance_m": {
          "0.0": 0.0024255883674406797,
          "0.5": 1.7113517447183106,
          "0.9": 7.003907933283225,
          "0.95": 12.824871753090722,
          "1.0": 5161.978599620035
        },
        "warnings": {
          "level_uncertain": 4130,
          "distance_tie_lower_height_assumption": 19,
          "alternative_level": 57,
          "connector_above_threshold": 34,
          "indoor_fallback": 4
        }
      },
      "baseline/estate/general/time": {
        "records": 244,
        "statuses": {
          "attached": 244
        },
        "eligible": 244,
        "distance_m": {
          "0.0": 0.16846246687488706,
          "0.5": 8.33333598563861,
          "0.9": 21.289084406490684,
          "0.95": 27.862468714832275,
          "1.0": 145.99181863952435
        },
        "warnings": {
          "level_uncertain": 244,
          "alternative_level": 14,
          "long_connector": 3,
          "distance_tie_lower_height_assumption": 6
        }
      },
      "baseline/estate/wheelchair/time": {
        "records": 244,
        "statuses": {
          "attached": 244
        },
        "eligible": 244,
        "distance_m": {
          "0.0": 0.16846246687488706,
          "0.5": 8.33333598563861,
          "0.9": 21.724647738261783,
          "0.95": 29.221476503552253,
          "1.0": 145.99181863952435
        },
        "warnings": {
          "level_uncertain": 244,
          "alternative_level": 14,
          "long_connector": 3,
          "distance_tie_lower_height_assumption": 6
        }
      },
      "baseline/mtr_access/general/time": {
        "records": 611,
        "statuses": {
          "attached": 598,
          "excluded": 13
        },
        "eligible": 598,
        "distance_m": {
          "0.0": 0.009323968803800289,
          "0.5": 4.939988163646457,
          "0.9": 20.48364340535096,
          "0.95": 33.23422529871729,
          "1.0": 199.54311918780053
        },
        "warnings": {
          "level_uncertain": 598,
          "alternative_level": 46,
          "long_connector": 11,
          "distance_tie_lower_height_assumption": 18
        }
      },
      "baseline/mtr_access/wheelchair/time": {
        "records": 611,
        "statuses": {
          "excluded": 335,
          "attached": 276
        },
        "eligible": 276,
        "distance_m": {
          "0.0": 0.009323968803800289,
          "0.5": 5.743497532115647,
          "0.9": 25.840041818537337,
          "0.95": 38.15333556892733,
          "1.0": 199.54311918780053
        },
        "warnings": {
          "level_uncertain": 276,
          "long_connector": 7,
          "distance_tie_lower_height_assumption": 11,
          "alternative_level": 18
        }
      },
      "bus_stop/general/time": {
        "records": 9264,
        "statuses": {
          "attached": 8848,
          "excluded": 416
        },
        "eligible": 8848,
        "distance_m": {
          "0.0": 0.00025793918223586724,
          "0.5": 1.6007012195568282,
          "0.9": 5.817799097783307,
          "0.95": 9.199137175891297,
          "1.0": 5209.270924347119
        },
        "warnings": {
          "level_uncertain": 8848,
          "alternative_level": 98,
          "distance_tie_lower_height_assumption": 24,
          "indoor_fallback": 6,
          "connector_above_threshold": 36
        }
      },
      "bus_stop/wheelchair/time": {
        "records": 9264,
        "statuses": {
          "attached": 4130,
          "excluded": 5134
        },
        "eligible": 4130,
        "distance_m": {
          "0.0": 0.0024255883674406797,
          "0.5": 1.7113517447183106,
          "0.9": 7.003907933283225,
          "0.95": 12.824871753090722,
          "1.0": 5161.978599620035
        },
        "warnings": {
          "level_uncertain": 4130,
          "distance_tie_lower_height_assumption": 19,
          "alternative_level": 57,
          "connector_above_threshold": 34,
          "indoor_fallback": 4
        }
      },
      "estate/general/distance": {
        "records": 244,
        "statuses": {
          "attached": 244
        },
        "eligible": 244,
        "distance_m": {
          "0.0": 0.16846246687488706,
          "0.5": 8.33333598563861,
          "0.9": 21.289084406490684,
          "0.95": 27.862468714832275,
          "1.0": 145.99181863952435
        },
        "warnings": {
          "level_uncertain": 244,
          "alternative_level": 14,
          "long_connector": 3,
          "distance_tie_lower_height_assumption": 6
        }
      },
      "estate/general/time": {
        "records": 244,
        "statuses": {
          "attached": 244
        },
        "eligible": 244,
        "distance_m": {
          "0.0": 0.16846246687488706,
          "0.5": 8.33333598563861,
          "0.9": 21.289084406490684,
          "0.95": 27.862468714832275,
          "1.0": 145.99181863952435
        },
        "warnings": {
          "level_uncertain": 244,
          "alternative_level": 14,
          "long_connector": 3,
          "distance_tie_lower_height_assumption": 6
        }
      },
      "estate/wheelchair/distance": {
        "records": 244,
        "statuses": {
          "attached": 244
        },
        "eligible": 244,
        "distance_m": {
          "0.0": 0.16846246687488706,
          "0.5": 8.33333598563861,
          "0.9": 21.724647738261783,
          "0.95": 29.221476503552253,
          "1.0": 145.99181863952435
        },
        "warnings": {
          "level_uncertain": 244,
          "alternative_level": 14,
          "long_connector": 3,
          "distance_tie_lower_height_assumption": 6
        }
      },
      "estate/wheelchair/time": {
        "records": 244,
        "statuses": {
          "attached": 244
        },
        "eligible": 244,
        "distance_m": {
          "0.0": 0.16846246687488706,
          "0.5": 8.33333598563861,
          "0.9": 21.724647738261783,
          "0.95": 29.221476503552253,
          "1.0": 145.99181863952435
        },
        "warnings": {
          "level_uncertain": 244,
          "alternative_level": 14,
          "long_connector": 3,
          "distance_tie_lower_height_assumption": 6
        }
      },
      "hospital/general/distance": {
        "records": 44,
        "statuses": {
          "attached": 44
        },
        "eligible": 44,
        "distance_m": {
          "0.0": 0.8234647027089924,
          "0.5": 22.826733524962222,
          "0.9": 50.499713403050386,
          "0.95": 68.3685645615401,
          "1.0": 119.9956082844605
        },
        "warnings": {
          "level_uncertain": 44,
          "long_connector": 6,
          "distance_tie_lower_height_assumption": 1
        }
      },
      "hospital/wheelchair/distance": {
        "records": 44,
        "statuses": {
          "attached": 44
        },
        "eligible": 44,
        "distance_m": {
          "0.0": 0.8234647027089924,
          "0.5": 22.826733524962222,
          "0.9": 50.499713403050386,
          "0.95": 68.3685645615401,
          "1.0": 119.9956082844605
        },
        "warnings": {
          "level_uncertain": 44,
          "long_connector": 6,
          "distance_tie_lower_height_assumption": 1
        }
      },
      "mtr_access/general/time": {
        "records": 611,
        "statuses": {
          "attached": 598,
          "excluded": 13
        },
        "eligible": 598,
        "distance_m": {
          "0.0": 0.009323968803800289,
          "0.5": 4.939988163646457,
          "0.9": 20.48364340535096,
          "0.95": 33.23422529871729,
          "1.0": 199.54311918780053
        },
        "warnings": {
          "level_uncertain": 598,
          "alternative_level": 46,
          "long_connector": 11,
          "distance_tie_lower_height_assumption": 18
        }
      },
      "mtr_access/wheelchair/time": {
        "records": 611,
        "statuses": {
          "excluded": 335,
          "attached": 276
        },
        "eligible": 276,
        "distance_m": {
          "0.0": 0.009323968803800289,
          "0.5": 5.743497532115647,
          "0.9": 25.840041818537337,
          "0.95": 38.15333556892733,
          "1.0": 199.54311918780053
        },
        "warnings": {
          "level_uncertain": 276,
          "long_connector": 7,
          "distance_tie_lower_height_assumption": 11,
          "alternative_level": 18
        }
      }
    },
    "zero_distance_attachments": 0,
    "candidate_review_rows": 47409,
    "unknown_entity_heights_preserved": true,
    "profiles_verified": 7742,
    "split_parent_edges": 7268,
    "new_nodes": 9336,
    "added_pieces": 9336,
    "directional_cost_conservation": true,
    "original_profiles_preserved": true,
    "single_source_subdivisions": true
  },
  "spatial_roundtrip": {
    "nodes": 406561,
    "edges": 475742,
    "attachments": 41052,
    "connectors": 29256,
    "estate": 244,
    "hospital": 44,
    "mtr_access": 611,
    "bus_stop": 9264
  },
  "routing": {
    "general_time": {
      "states": 420456,
      "active_states": 420026,
      "stored_entries": 959676,
      "stored_zero_cost_entries": 3782,
      "weak_components": 507,
      "weak_largest_sizes": [
        336448,
        67136,
        8138,
        1247,
        828,
        663,
        553,
        321,
        133,
        130,
        113,
        113,
        109,
        99,
        84,
        84,
        71,
        67,
        63,
        57
      ],
      "strong_components": 10245,
      "strong_largest_sizes": [
        328878,
        65125,
        8031,
        1245,
        827,
        662,
        553,
        314,
        131,
        130,
        113,
        109,
        102,
        96,
        84,
        80,
        67,
        67,
        63,
        55
      ],
      "terminals": 10119,
      "terminal_statuses": {
        "attached": 9690,
        "excluded": 429
      },
      "connector_transitions": 9690,
      "one_way_terminal_roles_verified": true,
      "lift_arrivals_and_departures_verified": true,
      "no_terminal_shortcuts": true,
      "roundtrip": {
        "dijkstra_sources": [
          0,
          205292,
          326963
        ],
        "save_reopen_costs_exact": true,
        "relaxation_checks": true
      },
      "upstream_endpoint_regression": {
        "status": "passed",
        "anchors": [
          {
            "source_id": "250015300",
            "position": 2.0,
            "xyz": [
              834012.2463999996,
              815590.5471000001,
              51.26790000000619
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          },
          {
            "source_id": "250011610",
            "position": 3.0,
            "xyz": [
              834012.3323999997,
              815590.5866,
              51.24899999999616
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          }
        ],
        "horizontal_m": 0.09463746625017981,
        "height_m": 0.018900000010035,
        "alignment_cost": 0.0,
        "evidence": "Same accepted physical node; no stored numeric node indices are assumed."
      },
      "upstream_lift_regressions": [
        {
          "footway_id": "290063550",
          "lift_id": "260001786",
          "footway_endpoint_position": 0,
          "footway_endpoint_xyz": [
            841518.0831000004,
            815331.3900000006,
            5.526800000006915
          ],
          "equal_height_lift_parameter": 0.06170742753720227,
          "equal_height_lift_xyz": [
            841518.0648963092,
            815331.4027549258,
            5.526800000006915
          ],
          "equal_height_horizontal_separation_m": 0.022227516520851923,
          "accepted_lift_parameters": [
            0.056989734300481966
          ],
          "forward_lift_state_seconds": 30.0,
          "reverse_lift_state_seconds": 30.0,
          "direct_connection": true
        },
        {
          "footway_id": "290064373",
          "lift_id": "280005280",
          "footway_endpoint_position": 1,
          "footway_endpoint_xyz": [
            836276.1688000001,
            815790.3307000007,
            4.08969999999681
          ],
          "equal_height_lift_parameter": 0.007087160510193952,
          "equal_height_lift_xyz": [
            836276.1737638473,
            815790.3308708014,
            4.08969999999681
          ],
          "equal_height_horizontal_separation_m": 0.004966784888973172,
          "accepted_lift_parameters": [
            0.0029571135928673727
          ],
          "forward_lift_state_seconds": 30.0,
          "reverse_lift_state_seconds": 30.0,
          "direct_connection": true
        }
      ]
    },
    "general_distance": {
      "states": 406849,
      "active_states": 406848,
      "stored_entries": 942257,
      "stored_zero_cost_entries": 50,
      "weak_components": 507,
      "weak_largest_sizes": [
        326203,
        64456,
        7977,
        1248,
        827,
        663,
        553,
        312,
        130,
        127,
        113,
        109,
        102,
        96,
        84,
        80,
        67,
        67,
        63,
        55
      ],
      "strong_components": 821,
      "strong_largest_sizes": [
        325953,
        64381,
        7967,
        1245,
        827,
        662,
        553,
        312,
        130,
        127,
        113,
        109,
        102,
        96,
        84,
        80,
        67,
        67,
        63,
        55
      ],
      "terminals": 288,
      "terminal_statuses": {
        "attached": 288
      },
      "connector_transitions": 288,
      "one_way_terminal_roles_verified": true,
      "lift_arrivals_and_departures_verified": true,
      "no_terminal_shortcuts": true,
      "roundtrip": {
        "dijkstra_sources": [
          0,
          203403,
          326963
        ],
        "save_reopen_costs_exact": true,
        "relaxation_checks": true
      },
      "upstream_endpoint_regression": {
        "status": "passed",
        "anchors": [
          {
            "source_id": "250015300",
            "position": 2.0,
            "xyz": [
              834012.2463999996,
              815590.5471000001,
              51.26790000000619
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          },
          {
            "source_id": "250011610",
            "position": 3.0,
            "xyz": [
              834012.3323999997,
              815590.5866,
              51.24899999999616
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          }
        ],
        "horizontal_m": 0.09463746625017981,
        "height_m": 0.018900000010035,
        "alignment_cost": 0.0,
        "evidence": "Same accepted physical node; no stored numeric node indices are assumed."
      }
    },
    "general_time_baseline": {
      "states": 420456,
      "active_states": 420026,
      "stored_entries": 959624,
      "stored_zero_cost_entries": 3782,
      "weak_components": 510,
      "weak_largest_sizes": [
        336415,
        67133,
        8138,
        1247,
        828,
        663,
        553,
        321,
        133,
        130,
        113,
        113,
        109,
        99,
        84,
        84,
        71,
        67,
        63,
        57
      ],
      "strong_components": 10248,
      "strong_largest_sizes": [
        328845,
        65122,
        8031,
        1245,
        827,
        662,
        553,
        314,
        131,
        130,
        113,
        109,
        102,
        96,
        84,
        80,
        67,
        67,
        63,
        55
      ],
      "terminals": 10119,
      "terminal_statuses": {
        "attached": 9690,
        "excluded": 429
      },
      "connector_transitions": 9690,
      "one_way_terminal_roles_verified": true,
      "lift_arrivals_and_departures_verified": true,
      "no_terminal_shortcuts": true,
      "roundtrip": {
        "dijkstra_sources": [
          0,
          205292,
          326963
        ],
        "save_reopen_costs_exact": true,
        "relaxation_checks": true
      },
      "upstream_endpoint_regression": {
        "status": "passed",
        "anchors": [
          {
            "source_id": "250015300",
            "position": 2.0,
            "xyz": [
              834012.2463999996,
              815590.5471000001,
              51.26790000000619
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          },
          {
            "source_id": "250011610",
            "position": 3.0,
            "xyz": [
              834012.3323999997,
              815590.5866,
              51.24899999999616
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          }
        ],
        "horizontal_m": 0.09463746625017981,
        "height_m": 0.018900000010035,
        "alignment_cost": 0.0,
        "evidence": "Same accepted physical node; no stored numeric node indices are assumed."
      },
      "upstream_lift_regressions": [
        {
          "footway_id": "290063550",
          "lift_id": "260001786",
          "footway_endpoint_position": 0,
          "footway_endpoint_xyz": [
            841518.0831000004,
            815331.3900000006,
            5.526800000006915
          ],
          "equal_height_lift_parameter": 0.06170742753720227,
          "equal_height_lift_xyz": [
            841518.0648963092,
            815331.4027549258,
            5.526800000006915
          ],
          "equal_height_horizontal_separation_m": 0.022227516520851923,
          "accepted_lift_parameters": [
            0.056989734300481966
          ],
          "forward_lift_state_seconds": 30.0,
          "reverse_lift_state_seconds": 30.0,
          "direct_connection": true
        },
        {
          "footway_id": "290064373",
          "lift_id": "280005280",
          "footway_endpoint_position": 1,
          "footway_endpoint_xyz": [
            836276.1688000001,
            815790.3307000007,
            4.08969999999681
          ],
          "equal_height_lift_parameter": 0.007087160510193952,
          "equal_height_lift_xyz": [
            836276.1737638473,
            815790.3308708014,
            4.08969999999681
          ],
          "equal_height_horizontal_separation_m": 0.004966784888973172,
          "accepted_lift_parameters": [
            0.0029571135928673727
          ],
          "forward_lift_state_seconds": 30.0,
          "reverse_lift_state_seconds": 30.0,
          "direct_connection": true
        }
      ]
    },
    "wheelchair_time": {
      "states": 420456,
      "active_states": 403678,
      "stored_entries": 884990,
      "stored_zero_cost_entries": 3782,
      "weak_components": 8255,
      "weak_largest_sizes": [
        242625,
        50771,
        50236,
        4731,
        1370,
        1310,
        916,
        846,
        704,
        699,
        623,
        552,
        488,
        434,
        426,
        388,
        386,
        373,
        363,
        277
      ],
      "strong_components": 12952,
      "strong_largest_sizes": [
        239789,
        50253,
        49393,
        4647,
        1332,
        1291,
        914,
        846,
        703,
        691,
        622,
        551,
        475,
        434,
        426,
        386,
        384,
        369,
        351,
        271
      ],
      "terminals": 10119,
      "terminal_statuses": {
        "attached": 4650,
        "excluded": 5469
      },
      "connector_transitions": 4650,
      "one_way_terminal_roles_verified": true,
      "lift_arrivals_and_departures_verified": true,
      "no_terminal_shortcuts": true,
      "roundtrip": {
        "dijkstra_sources": [
          0,
          205234,
          326963
        ],
        "save_reopen_costs_exact": true,
        "relaxation_checks": true
      },
      "upstream_endpoint_regression": {
        "status": "passed",
        "anchors": [
          {
            "source_id": "250015300",
            "position": 2.0,
            "xyz": [
              834012.2463999996,
              815590.5471000001,
              51.26790000000619
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          },
          {
            "source_id": "250011610",
            "position": 3.0,
            "xyz": [
              834012.3323999997,
              815590.5866,
              51.24899999999616
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          }
        ],
        "horizontal_m": 0.09463746625017981,
        "height_m": 0.018900000010035,
        "alignment_cost": 0.0,
        "evidence": "Same accepted physical node; no stored numeric node indices are assumed."
      },
      "upstream_lift_regressions": [
        {
          "footway_id": "290063550",
          "lift_id": "260001786",
          "footway_endpoint_position": 0,
          "footway_endpoint_xyz": [
            841518.0831000004,
            815331.3900000006,
            5.526800000006915
          ],
          "equal_height_lift_parameter": 0.06170742753720227,
          "equal_height_lift_xyz": [
            841518.0648963092,
            815331.4027549258,
            5.526800000006915
          ],
          "equal_height_horizontal_separation_m": 0.022227516520851923,
          "accepted_lift_parameters": [
            0.056989734300481966
          ],
          "forward_lift_state_seconds": 30.0,
          "reverse_lift_state_seconds": 30.0,
          "direct_connection": true
        },
        {
          "footway_id": "290064373",
          "lift_id": "280005280",
          "footway_endpoint_position": 1,
          "footway_endpoint_xyz": [
            836276.1688000001,
            815790.3307000007,
            4.08969999999681
          ],
          "equal_height_lift_parameter": 0.007087160510193952,
          "equal_height_lift_xyz": [
            836276.1737638473,
            815790.3308708014,
            4.08969999999681
          ],
          "equal_height_horizontal_separation_m": 0.004966784888973172,
          "accepted_lift_parameters": [
            0.0029571135928673727
          ],
          "forward_lift_state_seconds": 30.0,
          "reverse_lift_state_seconds": 30.0,
          "direct_connection": true
        }
      ]
    },
    "wheelchair_distance": {
      "states": 406849,
      "active_states": 395540,
      "stored_entries": 872641,
      "stored_zero_cost_entries": 40,
      "weak_components": 8255,
      "weak_largest_sizes": [
        237470,
        49976,
        48745,
        4602,
        1330,
        1285,
        917,
        840,
        703,
        691,
        619,
        552,
        475,
        434,
        426,
        387,
        384,
        367,
        351,
        268
      ],
      "strong_components": 8543,
      "strong_largest_sizes": [
        237280,
        49941,
        48715,
        4593,
        1328,
        1285,
        914,
        840,
        703,
        691,
        618,
        551,
        475,
        434,
        426,
        386,
        384,
        367,
        351,
        268
      ],
      "terminals": 288,
      "terminal_statuses": {
        "attached": 288
      },
      "connector_transitions": 288,
      "one_way_terminal_roles_verified": true,
      "lift_arrivals_and_departures_verified": true,
      "no_terminal_shortcuts": true,
      "roundtrip": {
        "dijkstra_sources": [
          0,
          203283,
          326963
        ],
        "save_reopen_costs_exact": true,
        "relaxation_checks": true
      },
      "upstream_endpoint_regression": {
        "status": "passed",
        "anchors": [
          {
            "source_id": "250015300",
            "position": 2.0,
            "xyz": [
              834012.2463999996,
              815590.5471000001,
              51.26790000000619
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          },
          {
            "source_id": "250011610",
            "position": 3.0,
            "xyz": [
              834012.3323999997,
              815590.5866,
              51.24899999999616
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          }
        ],
        "horizontal_m": 0.09463746625017981,
        "height_m": 0.018900000010035,
        "alignment_cost": 0.0,
        "evidence": "Same accepted physical node; no stored numeric node indices are assumed."
      }
    },
    "wheelchair_time_baseline": {
      "states": 420456,
      "active_states": 403677,
      "stored_entries": 884948,
      "stored_zero_cost_entries": 3782,
      "weak_components": 8257,
      "weak_largest_sizes": [
        242623,
        50761,
        50236,
        4731,
        1370,
        1310,
        916,
        846,
        704,
        699,
        623,
        552,
        488,
        434,
        426,
        388,
        386,
        373,
        363,
        277
      ],
      "strong_components": 12954,
      "strong_largest_sizes": [
        239787,
        50243,
        49393,
        4647,
        1332,
        1291,
        914,
        846,
        703,
        691,
        622,
        551,
        475,
        434,
        426,
        386,
        384,
        369,
        351,
        271
      ],
      "terminals": 10119,
      "terminal_statuses": {
        "attached": 4650,
        "excluded": 5469
      },
      "connector_transitions": 4650,
      "one_way_terminal_roles_verified": true,
      "lift_arrivals_and_departures_verified": true,
      "no_terminal_shortcuts": true,
      "roundtrip": {
        "dijkstra_sources": [
          0,
          205234,
          326963
        ],
        "save_reopen_costs_exact": true,
        "relaxation_checks": true
      },
      "upstream_endpoint_regression": {
        "status": "passed",
        "anchors": [
          {
            "source_id": "250015300",
            "position": 2.0,
            "xyz": [
              834012.2463999996,
              815590.5471000001,
              51.26790000000619
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          },
          {
            "source_id": "250011610",
            "position": 3.0,
            "xyz": [
              834012.3323999997,
              815590.5866,
              51.24899999999616
            ],
            "node_id": "N-8605fd7da4a9cdcaed32b51f"
          }
        ],
        "horizontal_m": 0.09463746625017981,
        "height_m": 0.018900000010035,
        "alignment_cost": 0.0,
        "evidence": "Same accepted physical node; no stored numeric node indices are assumed."
      },
      "upstream_lift_regressions": [
        {
          "footway_id": "290063550",
          "lift_id": "260001786",
          "footway_endpoint_position": 0,
          "footway_endpoint_xyz": [
            841518.0831000004,
            815331.3900000006,
            5.526800000006915
          ],
          "equal_height_lift_parameter": 0.06170742753720227,
          "equal_height_lift_xyz": [
            841518.0648963092,
            815331.4027549258,
            5.526800000006915
          ],
          "equal_height_horizontal_separation_m": 0.022227516520851923,
          "accepted_lift_parameters": [
            0.056989734300481966
          ],
          "forward_lift_state_seconds": 30.0,
          "reverse_lift_state_seconds": 30.0,
          "direct_connection": true
        },
        {
          "footway_id": "290064373",
          "lift_id": "280005280",
          "footway_endpoint_position": 1,
          "footway_endpoint_xyz": [
            836276.1688000001,
            815790.3307000007,
            4.08969999999681
          ],
          "equal_height_lift_parameter": 0.007087160510193952,
          "equal_height_lift_xyz": [
            836276.1737638473,
            815790.3308708014,
            4.08969999999681
          ],
          "equal_height_horizontal_separation_m": 0.004966784888973172,
          "accepted_lift_parameters": [
            0.0029571135928673727
          ],
          "forward_lift_state_seconds": 30.0,
          "reverse_lift_state_seconds": 30.0,
          "direct_connection": true
        }
      ]
    }
  },
  "frozen_hashes_rechecked": true,
  "implementation_hashes_rechecked": true,
  "runtime_seconds": 430.851,
  "limitations": [
    "Straight flat connectors are accepted map-point approximations, not surveyed entrances or slopes.",
    "Every attached entity has unknown height; nearest path level is an assumption recorded for review.",
    "Unattached and excluded records remain visible; attachment does not establish estate-to-target reachability.",
    "Estate subcosts and ranking remain Step 4 and later work."
  ]
}
```
