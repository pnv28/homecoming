# Provider-document check: coordinates, gradient and length

Checked 13 October 2026 using the supplied local PDFs and the original network geometry. This review focuses on the first two questions only. Other MTR matching, entrance and boarding issues remain under separate review.

## What the documents establish

Page numbers below are PDF viewer page numbers, counting from one.

| Document | Relevant page | Finding | Status |
|---|---:|---|---|
| [3DPN portal metadata](../../original_data/portal.csdi.gov.hk_csdi-webpage_metadata_landsd_rcd_1637222018065_52265_html.pdf) | 1 | Identifies the horizontal reference system as EPSG:2326. The nine-page metadata document does not define Gradient or Shape_Length. | Network horizontal CRS confirmed. |
| [3DPN dictionary v2.2](../../original_data/3DPN_DataDictionary_v2.2.pdf) | 8 | HK1980 Grid horizontally; heights in metres above HKPD. | Confirms the horizontal/vertical interpretation used by the loader. |
| Same dictionary | 12 | Defines Gradient as the segment gradient in radians. Direction describes permissible travel relative to the drawn line, primarily for escalators/travelators. | Gradient units confirmed. Direction must not be interpreted as uphill/downhill sign. |
| Same dictionary | 14 | Defines SHAPE_Length as horizontal feature length in metres. The actual geodatabase field is Shape_Length. | Source length meaning confirmed. |
| [iGeoCom dictionary v5](../../original_data/data_dictionary_v5.pdf) | 6 | Explicitly specifies WGS84 point geometry and HK1980 Grid easting/northing attributes. | iGeoCom source CRS confirmed. |
| [Estate specification](../../original_data/ha_hahdweb_dataspec.pdf) | 6 | Defines Estate Map Latitude and Estate Map Longitude as numeric latitude/longitude. No explicit WGS84/datum statement was found in the document. | Coordinate fields confirmed; datum remains an explicit WGS84 assumption. |
| [Hospital specification](../../original_data/Data-Specification-for-List-of-HA-Hospitals-Institutions-SOPCs-FMCs-en.pdf) | 2 | Defines numeric latitude and longitude. No explicit WGS84/datum statement was found in the document. | Coordinate fields confirmed; datum remains an explicit WGS84 assumption. |
| [Bus GeoJSON specification](../../original_data/ptroutefare_geojson_dataspec.pdf) | 1 | Describes stop coordinates as latitude/longitude; does not explicitly name their datum. The actual input arrays are checked as longitude, latitude. | Coordinate fields confirmed; explicit provider datum confirmation remains open. |

The bus PDF also confirms stopPickDrop codes 1=drop-off only, 2=pick-up only, and 3=both. Its definition does not cover code 0, found in 25 raw rows at two stop IDs. The [updated resolution register](../../instructions/step_1/step_1_implementation_human_readable.md#resolution-register-what-is-confirmed-and-what-remains) separates these confirmed definitions from pending eligibility implementation and wheelchair boarding evidence.

## Independent checks against the selected network snapshot

- All 465,892 source Shape_Length values exactly equal the calculated XY polyline lengths: maximum difference **0 metres**.
- All 465,892 gradients are present and finite, ranging from **0 to 1.57065363 radians**.
- No supplied gradient is negative, although ordered vertices include 206,007 rising paths and 205,227 falling paths by endpoint elevation.
- Comparing the source gradient with an absolute endpoint-rise/horizontal-length angle produces a tiny median difference, but some paths differ substantially. Endpoint measurements therefore do not establish the publisher's calculation method for every path.

These checks corroborate the documented units and horizontal length. They do not turn the unspecified gradient sign/aggregation method into a confirmed provider definition.

## How the confirmed gradient can be used later

For an angle theta in radians:

```text
angle in degrees = theta * 180 / pi
rise/run slope = tan(theta)
percentage slope = 100 * tan(theta)
```

An angle-based route penalty can use the confirmed radians directly. A model defined in terms of rise/run needs the tangent conversion. Physical length still contributes to route cost: a gradient alone does not account for how far someone travels.

For different uphill/downhill costs, use an explicitly defined directional rule based on the ordered Z coordinates. A path that rises and then falls may require per-vertex-segment calculations rather than one endpoint slope. Lifts require a separate rule because horizontal distance can be zero or very small.

## Checklist outcome

- [X] Confirm Gradient units from the provider: radians.
- [X] Confirm Shape_Length meaning: horizontal polyline length in metres.
- [X] Preserve those definitions with PDF source/page references in the pipeline metadata and schema.
- [X] Verify all source horizontal lengths against the original XY geometry.
- [X] Confirm network CRS and iGeoCom coordinate interpretation.
- [ ] Obtain explicit datum confirmation for estate, hospital and bus coordinates; their new specifications establish coordinate fields, not the datum.
- [ ] Decide/verify the directional-slope and within-path aggregation rule needed by the later cost model. The dictionary does not explicitly define those details.

Access schedules remain ignored under the agreed always-open assumption.
