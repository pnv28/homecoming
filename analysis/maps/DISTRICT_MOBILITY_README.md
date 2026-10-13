# Yuen Long and North: mobility screening

Computed results: district_mobility_summary.json.
Reproduce after the gradient analysis: `.venv/bin/python analysis/maps/analyse_district_mobility.py`.
This uses the original FGDB attributes and district membership / clipped horizontal
lengths from the two district gradient CSVs. Routes crossing district lines can contribute
to both; only their in-district horizontal length contributes to length statistics.

Slope bands are grade percentages (100 × tan(angle)), not degrees:
5% = 2.8624 degrees; 1:12 = 8.3333% = 4.7636 degrees.
These are screening bands informed by Hong Kong's barrier-free ramp design guidance,
not a certification of outdoor route accessibility. The Buildings Department's
Design Manual Barrier Free Access 2008 (2025 Edition), printed pages 27–31,
normally limits ramps to 1:12, with specified short-rise exceptions. Width, landings,
handrails and surfaces are also relevant. Short-rise exceptions mean a recorded ramp
over 8.33% is not necessarily non-compliant; the source values can also include artefacts.
Source: https://www.bd.gov.hk/doc/en/resources/codes-and-references/code-and-design-manuals/BFA2008_e.pdf

Ordinary walking-path slope totals include ramps; stairs, elevators, escalators,
travelators and stairlifts are excluded from that denominator. This does not remove
all other possible barriers. Feature counts count route records, not physical machines
or facilities; multiple records may represent one installation.

WheelchairAccess=True (code 1) means an accessible entrance connection to a public
facility/building/site. False is not evidence that an ordinary footway is inaccessible.
WheelchairBarrier=True/False are preserved as raw values because the embedded domain's
description says 'suitable' despite its name saying 'Barrier'. True predominantly occurs
on stairs/escalators, and False on lifts/ramps, but this association alone is not an
authoritative resolution of the ambiguity. Do not use False to certify accessibility.
Named obstacles may hinder passage; the presence of a tree/pole does not establish
whether clear width is insufficient. Enabled indicates source-record public availability,
not live lift status. Opening hours also require checking.

A practical wheelchair route must have continuous passable connections, dropped kerbs,
sufficient width, appropriate cross-slope and surfaces, and compatible operating lifts
where needed. Those properties are not established by district averages. Stairlifts
require verification of equipment type and wheelchair compatibility.

Yuen Long has a gentler recorded slope profile: 90.48% of ordinary-path horizontal length
is at most 5% grade, versus 85.31% in North. Length above 8.33% grade is 4.59% versus 7.85%.
The result ranks recorded slope profiles, not overall wheelchair accessibility.
