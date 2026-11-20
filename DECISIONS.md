# Decisions

## 2026-11-04 — Freeze the web page data pipeline
**Decided:** The web page keeps the 1997-2025 offense files it has; no further hosting work.
**Why:** Visitors already get every year; faster rebuilds change nothing they see.
**Rules out:** Mirroring the 11 GB of FBI zips as release files.

## 2026-11-20 — Agency names add the FBI unit and "County"
**Decided:** `agency_name` is the FBI name plus its unit; county agencies without a unit end in " County".
**Why:** TX 2023 had 958 names for 1,160 agencies; Austin police and Austin County sheriff were both "Austin".
**Rules out:** Keying the agency menu on ORI codes.
