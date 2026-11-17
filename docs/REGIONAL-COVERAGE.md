# Regional coverage in the guides and library: a proposal

This is a proposal for discussion, not a decision. Lastbook is meant to help anyone, anywhere. Most of its guides are
already written for any reader. The regional material it does have, though, comes almost entirely from coastal Southern
California. A reader somewhere else who asks about their own area gets the nearest regional pages the library has, and
those are Los Angeles pages.

The proposal is to treat regional material as a set of slots that every region fills the same way, rather than adding
one more region by hand. It uses northeastern Pennsylvania (the Lehigh Valley and the Pocono Mountains) as a first
worked example, because a reader there noticed the gap: asked about that area, Chat answered with Los Angeles County
material.

Nothing here changes the app, the engine, a guide or a build. Builds package `web/` and `content/` only, so this file
does not ship. Where something below could not be checked, it says so.

## What a reader sees today

Counted from `content/topics/*.json` on 17 November 2026. A reading counts as regional when its label, note or source
names California, a California place, or University of California extension.

| Guide | Readings | Regional (all California) |
|---|---|---|
| `grow` | 59 | 20 |
| `disaster` | 67 | 4 |
| `land` | 53 | 3 |
| `preserve` | 50 | 1 |
| `shelter` | 57 | 1 |
| The other nine guides | 507 | 0 |

- **Growing food is where it shows most.** The `grow` intro says its "readings lean on University of California
  extension guides for coastal Southern California". Step 2 of its route is "Learn local timing for coastal Southern
  California", and one of its choices is "What can I plant now in coastal Southern California?". Its keywords include
  `Los Angeles` and `Southern California`. Planting dates are where location matters most. In a cold-winter climate,
  the coastal Southern California calendar is wrong by months.
- **Earthquakes.** The regional readings in `disaster`, `land` and `shelter` are California earthquake and Red Cross
  Northern California material. That is right for California. Elsewhere, the local hazards (floods, winter storms,
  ice, heat, wildfire, hurricanes) have no regional counterpart.
- **The map.** `docs/REGIONS.md` already notes that the fish, boating and well layers are labelled California and stay
  empty elsewhere.
- **Chat follows the library.** Chat answers only from library pages and cites them. When the library holds regional
  pages for one place only, a question about any other place finds those pages. So the fix belongs in the library and
  the guides, not in Chat.

## The proposal: general first, then the same slots for every region

1. **Keep the general guides general.** They already work for any reader. Nothing in them should assume a place.
2. **Name the place when a reading is regional.** A label or note should say which region a page is about (as `grow`
   already does). That way a reader elsewhere knows to look for their own.
3. **Fill the same slots for each region.** Each slot is a kind of source that exists, in some form, for every US state,
   and for many other places:

| Slot | What it answers | Where it usually comes from |
|---|---|---|
| Growing season | When to plant here; first and last frost; hardiness zone; what grows well | The state's land-grant extension service and its county Master Gardeners; USDA plant hardiness zones; NOAA frost and freeze normals |
| Keeping the harvest | Canning, freezing and drying methods tested for home use | The state extension service; the USDA and the National Center for Home Food Preservation, already in the library |
| Local hazards | What actually happens here: floods, storms, ice, heat, quakes, fire | The state emergency management agency's preparedness guide; the county hazard mitigation plan |
| Warnings | Who issues warnings here, and which NOAA Weather Radio station covers it | The local National Weather Service office |
| Wildlife and plants | Dangerous animals and plants here; what is safe to forage | The state wildlife agency; the state extension service |
| Water and floods | Which rivers flood, and how | USGS; river basin commissions; the county plan |

4. **Prefer federal sources where they fit.** Works of the US federal government are generally not under copyright
   in the US, so NWS, NOAA, USDA, USGS and FEMA material can go into the library for every state the same way. State and
   university sources need their reuse terms checked one by one (see "Reuse terms" below).
5. **Consider tying regional documents to the state chosen in setup.** Setup already asks the person to pick a state for
   the detailed map, and Lastbook never detects location. A region's documents could arrive with that state's map, so
   every library carries its reader's own region without carrying all fifty. This is a design question for the
   maintainers.
6. **Record what is missing.** Once a region's sources are checked against a real library, what could not be found goes
   in `content/gaps.json`, as the guides already do.

## Worked example: northeastern Pennsylvania

The Lehigh Valley (Lehigh and Northampton counties, including Allentown, Bethlehem and Easton) and the Pocono Mountains
(Monroe, Carbon, Pike and Wayne counties, including Stroudsburg). The area has cold winters, a growing season months
shorter and later than coastal Southern California's, river flooding on the Delaware and Lehigh and their creeks,
winter storms and black bears.

Each source below is marked **opened** (the page or file was fetched and read on 17 November 2026) or **found** (it
turned up in a search but was not opened). Every source still has to be read in full and checked before it goes into the
library.

### Growing food

This is the slot that matters most, and Penn State Extension covers it well.

| Source | Publisher | What it adds | Checked |
|---|---|---|---|
| Vegetables (extension.psu.edu/forage-and-food-crops/vegetables) | Penn State Extension | "Pennsylvania is in 5, 6, and 7 USDA plant hardiness zones". First frost ranges from 13 September (Ridgway) to 28 October (Philadelphia), last frost from 14 April (Philadelphia) to 7 June (Ridgway), with "approximately 150 days between the last and first frost". Also soil temperatures for planting sweet corn, broccoli and peppers. | Opened |
| Cool-season vs. Warm-season Vegetables (extension.psu.edu/cool-season-vs-warm-season-vegetables) | Penn State Extension | Which crops go in weeks before the last frost, which wait for warm soil, and which can be grown twice a year. This is the idea a cold-winter gardener needs first. | Opened |
| Season Extenders and Growing Fall Vegetables (extension.psu.edu/season-extenders-and-growing-fall-vegetables) | Penn State Extension | Finding local frost and freeze dates by ZIP code (its example: University Park, 12 October to 10 May, about 155 days), and growing past them with season extenders. | Opened |
| Vegetable Seed Planting Guide (PDF, 3 pages; extension.psu.edu, Master Gardeners of York County) | Penn State Extension | A chart per crop: cool or warm season, pH, sowing depth and spacing, earliest and last sowing dates, days to germinate and to maturity, and last harvest before frost. Set for a 1 May last frost and a 1 October first frost. The file was created in 2009 and last changed in 2020. York County is warmer than the Poconos, so a reader there would shift the dates. | Opened |
| Vegetable Transplanting Guide (abe.psu.edu, Master Gardeners of York County) | Penn State Extension | The companion chart for crops set out as transplants | Found |
| Philadelphia Planting Guide (extension.psu.edu, Master Gardeners of Philadelphia County) | Penn State Extension | First and last planting dates per crop. Gives the average last frost for central Philadelphia as 20 April, "a week or two later" in higher and outlying parts. | Opened |
| Vegetable Gardening From Scratch (extension.psu.edu, Master Gardeners of Pike County) | Penn State Extension | A short series written in a Pocono county: container and raised-bed gardening, choosing crops, designing the space, soil, tools and reading a seed packet. | Opened |
| Let's Preserve fact sheets (extension.psu.edu/food-safety-and-quality/home-food-preservation-and-safety/lets-preserve) | Penn State Extension | Tested methods to can, freeze and dry fruits, vegetables and meats, with troubleshooting. Also available in Spanish. | Opened (the index page; the sheets themselves were not) |
| USDA Plant Hardiness Zone Map | USDA Agricultural Research Service | Zones for every state | Found |

No planting chart was found for Lehigh, Northampton or Monroe County. Penn State's pages direct readers to their county
Master Gardeners and Garden Hotlines for local dates.

### Local hazards and warnings

| Source | Publisher | What it adds | Checked |
|---|---|---|---|
| Pennsylvania Emergency Preparedness Guide (pa.gov/en/agencies/ready/get-prepared/emergency-preparedness-guide.html) | Ready PA (Commonwealth of Pennsylvania) | A 24-page booklet. Its "Top 10 Emergencies" begin with floods, fires and winter storms, then tropical storms, tornadoes and thunderstorms, flu pandemic, hazardous materials, earthquakes and landslides, nuclear threat, dam failures and terrorism. Also family plans, home and vehicle kit checklists, and planning for older people and people with disabilities. Offered in English, large print, Spanish, German, Russian and Simplified and Traditional Chinese. The English file was made in 2017 and last changed in 2021. | Opened |
| National Weather Service | NOAA | The NWS county zone records (api.weather.gov) put Lehigh, Northampton, Monroe and Carbon counties under the Mount Holly office (PHI), and Pike and Wayne counties under the Binghamton office (BGM). So a guide card for "who warns this area" differs within the Poconos. | Opened |
| Monroe County Multi-Jurisdictional Hazard Mitigation Plan (2025 draft; 2021 plan) | Monroe County Office of Emergency Management | The hazards the county itself ranks, with their history. It is long; only the hazard sections would help a reader. | Found |
| Northampton County hazard mitigation plan | Northampton County | Not found. Only a 2024 township annex turned up. | — |
| Flood material for the Delaware River basin | Delaware River Basin Commission | Basin flooding history and mitigation | Found |

### Wildlife

| Source | Publisher | What it adds | Checked |
|---|---|---|---|
| Black Bears (extension.psu.edu/black-bears) | Penn State Extension | Keeping bears away from homes, crops and beehives: removing what attracts them, securing garbage, electric fencing. Says bears are protected under the Pennsylvania Game Commission's jurisdiction. | Opened |
| Wildlife Notes: Black Bear (pgc.pa.gov) | Pennsylvania Game Commission | The state wildlife agency's own fact sheet | Found |

### Not found

- A Pennsylvania guide to safe wild edible plants from an agency or the extension service.
- Flood material written for Easton or the Lehigh Valley itself.
- A planting chart for the Lehigh Valley or Pocono counties.

## Reuse terms

The library already carries University of California extension guides, so the maintainers have a way of deciding
whether a university or state document may be included. That same decision is needed for each source above:

- **Penn State Extension.** Its pages carry "© 2026 The Pennsylvania State University". No reuse statement for
  extension publications turned up, and Penn State's general copyright guidance says permission is generally needed to
  reuse a substantial part of a copyrighted work. Asking Penn State Extension directly may be simplest, and one answer
  would cover the growing, preserving and wildlife sources together.
- **Commonwealth of Pennsylvania.** The Ready PA page carries "Copyright © 2026 Commonwealth of Pennsylvania. All rights
  reserved." No general Commonwealth reuse policy turned up, so Ready PA (readypa@pa.gov, as printed in the guide) would
  need to be asked. The Game Commission would need to be asked separately.
- **Federal sources** (NWS, NOAA, USDA, USGS, FEMA) are generally not under copyright in the US.

## Still undecided

Each of these needs the maintainers' decision:

1. **Packs or setup.** Whether regional documents go in Small, Medium or All, or arrive with the state map chosen in
   setup.
2. **How guides show them.** For example, a `grow` choice such as "What can I plant now where I live?" that shows the
   readings for the state chosen in setup, with coastal Southern California as one region among many.
3. **The first regions.** Whether to start with one region to set the pattern, or the federal slots for every state at
   once.
4. **Gaps.** Which `content/gaps.json` entries to add once a region's sources have been checked against a real library.

## What was checked

- The counts in "What a reader sees today" were computed from `content/topics/*.json` at the commit this file was added
  in.
- Sources marked "Opened" were fetched on 17 November 2026, and the quotations and facts given for them were read from
  the fetched page or file. File dates come from the PDFs' own metadata.
- Sources marked "Found" turned up in web searches on the same day and were not opened. Their contents, editions and
  reuse terms are not confirmed.
