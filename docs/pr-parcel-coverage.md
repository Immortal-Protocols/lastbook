# Puerto Rico rural address search by municipio

The November 17, 2026 build found **62,164 distinct parcels with a searchable numbered-road address** in Planning Board permits. All 78 municipios have matches. The CRIM map supplied boundaries for **1,292,468 distinct land numbers**. Thirteen numbers occur in two municipios. Each appears in both boundary counts below. The builder skips those numbers when attaching addresses.

The permit column counts each land number once, however many permits or accounts mention it. A record needs a numbered road and a matching parcel boundary. Some records also supply a kilometer, lot, sector or interior access. This build used only the public inputs. A locally prepared CRIM physical-address CSV can add records for land that has no usable permit address. [Parcel and permit sources](MAPS.md#puerto-rico-street-addresses-and-land-parcels)

| Municipio | Land numbers with a boundary | Land numbers with a numbered-road permit address |
| --- | ---: | ---: |
| Adjuntas | 7,199 | 604 |
| Aguada | 17,252 | 1,710 |
| Aguadilla | 25,500 | 1,939 |
| Aguas Buenas | 9,011 | 970 |
| Aibonito | 10,278 | 788 |
| Arecibo | 38,665 | 1,866 |
| Arroyo | 8,447 | 290 |
| Añasco | 10,905 | 1,017 |
| Barceloneta | 10,078 | 395 |
| Barranquitas | 8,999 | 785 |
| Bayamón | 66,346 | 619 |
| Cabo Rojo | 28,821 | 2,166 |
| Caguas | 47,089 | 1,119 |
| Camuy | 14,826 | 1,009 |
| Canóvanas | 15,720 | 585 |
| Carolina | 45,458 | 667 |
| Cataño | 7,844 | 115 |
| Cayey | 18,040 | 1,168 |
| Ceiba | 5,884 | 254 |
| Ciales | 7,858 | 520 |
| Cidra | 15,092 | 986 |
| Coamo | 16,549 | 928 |
| Comerío | 5,677 | 412 |
| Corozal | 11,906 | 904 |
| Culebra | 1,512 | 107 |
| Dorado | 13,937 | 521 |
| Fajardo | 15,685 | 547 |
| Florida | 4,905 | 178 |
| Guayama | 19,391 | 576 |
| Guayanilla | 7,493 | 393 |
| Guaynabo | 25,363 | 873 |
| Gurabo | 16,266 | 795 |
| Guánica | 8,198 | 276 |
| Hatillo | 15,417 | 1,059 |
| Hormigueros | 6,970 | 430 |
| Humacao | 23,101 | 1,061 |
| Isabela | 23,051 | 1,869 |
| Jayuya | 5,253 | 471 |
| Juana Díaz | 18,974 | 710 |
| Juncos | 15,820 | 731 |
| Lajas | 12,197 | 957 |
| Lares | 11,890 | 873 |
| Las Marías | 4,104 | 455 |
| Las Piedras | 14,984 | 1,102 |
| Loíza | 7,693 | 298 |
| Luquillo | 8,346 | 463 |
| Manatí | 16,607 | 891 |
| Maricao | 2,334 | 184 |
| Maunabo | 5,298 | 378 |
| Mayagüez | 31,420 | 1,512 |
| Moca | 16,119 | 1,565 |
| Morovis | 9,637 | 593 |
| Naguabo | 11,291 | 702 |
| Naranjito | 8,544 | 611 |
| Orocovis | 8,373 | 719 |
| Patillas | 8,331 | 586 |
| Peñuelas | 8,819 | 582 |
| Ponce | 55,492 | 358 |
| Quebradillas | 11,000 | 936 |
| Rincón | 7,620 | 733 |
| Río Grande | 19,486 | 1,033 |
| Sabana Grande | 10,262 | 652 |
| Salinas | 14,222 | 492 |
| San Germán | 14,932 | 1,141 |
| San Juan | 91,258 | 839 |
| San Lorenzo | 15,266 | 1,132 |
| San Sebastián | 21,239 | 1,820 |
| Santa Isabel | 9,409 | 310 |
| Toa Alta | 24,325 | 848 |
| Toa Baja | 27,833 | 589 |
| Trujillo Alto | 18,875 | 1,103 |
| Utuado | 13,777 | 1,012 |
| Vega Alta | 12,716 | 660 |
| Vega Baja | 22,050 | 922 |
| Vieques | 6,071 | 273 |
| Villalba | 6,730 | 567 |
| Yabucoa | 13,214 | 981 |
| Yauco | 15,937 | 879 |

## Testing the directions

The offline test selected three distinct parcel numbers per municipio from ARPE permits that included a municipio prefix, one named road number and one kilometer marker. It selected by hash before checking for a parcel boundary or a match. The expected result was the land number on the permit. The table below compares the two builds before original permit wording was indexed. The test followed every page of candidates and ran with the model disabled.

| Check on the same source records | Earlier index | With municipality-prefixed permits |
| --- | ---: | ---: |
| Source permits selected | 234 | 234 |
| Permit land number present in the boundary layer | 154 | 154 |
| Expected parcel among candidates for road, km and municipio | 24 | 140 |
| Expected parcel among candidates for the permit's full directions, adding municipio if absent | 9 | 78 |

These results measure recovery of the recorded parcel on this sample. Geometry vintages, differences between the municipality on the permit and the map, and free-form directions can affect the result. A parcel can contain more than one building.

Run `python tools/check_pr_permit_coverage.py path/to/PR.sqlite path/to/parcel-inputs` against the same inputs to repeat the test. The build also writes every municipio's permit-backed, CRIM-address-backed and combined parcel counts to `PR.coverage.json` under `parcels.address_coverage_by_municipio`.

| Public source | Input records | SHA-256 of uncompressed snapshot records |
| --- | ---: | --- |
| [CRIM parcel boundaries](https://sigejp.pr.gov/server/rest/services/crim/crim_feb_2025/MapServer/0) | 1,292,823 | `e94ab3e8398832ea8b6da24e1344f0c20e4ec8b0788367f8cdf80c4f79d2246f` |
| [SIP permits](https://sigejp.pr.gov/server/rest/services/MIPR/Permisos/MapServer/8) | 221,173 | `783f2239cfd60e0d88f80ab297e51b2c08ff1122ac69feef8a8a5819b7609a73` |
| [ARPE permits](https://sigejp.pr.gov/server/rest/services/MIPR/Permisos/MapServer/16) | 431,605 | `3b028fa55743b962fcf157dbfee297a03a2a7dc9ec8e37467727878221bd7671` |

### Replaying the same 234 directions with Medium Gemma

Before original permit wording was indexed, enabling Gemma returned the same **78 of 234** parcels as the deterministic reader. In 37 of the 78, it was the only parcel candidate. The fallback called Gemma on 105 of the 156 misses. Lastbook accepted 43 of those readings under its checks that the road, kilometer and qualifiers come from the query. None added the expected parcel. To repeat the paired benchmark on that index, add `--gemma` to the command above with the local runner and Medium model installed.

A second experiment scored a Gemma reading for every direction, including those the normal fallback skipped. It used the same validation and parcel lookup, and supplied only the directions to the model. Gemma alone recovered **74 of 234**. All 74 were also parser hits. In the other four parser hits, the model reading failed validation. Falling back to the parser in those cases restored all four.

| Why the expected parcel was missing | Cases |
| --- | ---: |
| The recorded land number had no boundary in the index | 80 |
| The boundary was in a different municipio from the permit, and road/km/municipio lookup missed | 10 |
| The boundary was in the same municipio but had no address row for that road | 4 |
| Road/km/municipio found the parcel, and a spelling or formatting substitution also recovered it using the full directions | 5 |
| Road/km/municipio found the parcel, but the permit's barrio wording differed from the mapped barrio | 24 |
| Road/km/municipio found the parcel, but additional words such as a camino, building or parcela number entered the locality field | 33 |

The five substitutions covered an unhyphenated ZIP+4, `Mameyes 1` / `Mameyes I`, `Saint Just` / `St. Just`, and two alternate barrio spellings. Each brought the expected parcel into the results. Only one produced a single parcel candidate. The 24 barrio differences need local evidence before treating the names as interchangeable. Of the four parcels without an address row for the road, three permits had conflicting municipio prefixes. The fourth named both a carretera and a ramal, which the index builder could not represent as a single road.

We also tested keeping the permit's full wording. We matched normalized directions within the permit municipio against the public ARPE snapshot, kept all candidate land numbers, and required the existing account-prefix and boundary-municipio checks. Adding those results to normal search recovered **61 additional recorded parcels (139/234 total)**. In 58 of the 61, the wording matched just one joined parcel. This test reuses the wording on the sampled permit. Only 13 of those 61 had a second ARPE record ID with the same normalized wording and parcel. Separately collected or independently rephrased directions would be needed to measure how well this approach handles a resident's own wording.

### Searching the rebuilt index with rephrased directions

The public build stores 230,317 distinct combinations of parcel, permit source and original wording across 116,649 land numbers in all 78 municipios. These counts include permits without a numbered road or kilometer. When a complete wording matches, the reader displays it beside its source and ranks the parcel ahead of the broader structured matches. The municipio-prefix and boundary checks still apply.

We tested the same 234 permits with AI off during search. A hit means the recorded land number appeared among the possible parcels. The last column counts queries that returned parcels but missed the one recorded on the sampled permit. Eighty expected land numbers had no boundary in either index.

| Directions, 234 per row | Previous hits | Rebuilt hits | Only candidate was correct | Other parcels only |
| --- | ---: | ---: | ---: | ---: |
| Original permit wording | 78 | 139 | 92 | 43 |
| Source details retained, road and kilometer read aloud | 0 | 124 | 102 | 25 |
| Spanish text-message paraphrase, digits requested | 1 | 87 | 69 | 17 |
| Free Spanish phone paraphrase | 0 | 59 | 46 | 13 |

The controlled read-aloud version expands common abbreviations, renders the road and kilometer in Spanish words, and keeps the remaining source details in order. For the two free rewrites, local Medium Gemma received only the public directions and a style prompt. It had no access to the parcel answer or search results. Both indexes received exactly the same saved queries. The results describe simulated speech. An automated read-back of the phone rewrites found 194 with the same road and kilometer, 26 with a different number and 14 it could not verify. All 234 remain in the denominator. Desktop and compiled iPad searches agreed on ordered results across 958 pages for the four forms.

With the optional Medium fallback enabled, text-message hits increased from **69 to 100** and phone-style hits increased from **1 to 59** between the previous and rebuilt indexes. The rebuilt reader returned only the recorded parcel for 76 text messages and 46 phone directions. It returned other parcels only for 41 and 18 respectively. The comparison used live fallback responses from the previous reader and replayed those same answers whenever the rebuilt reader requested Gemma. It retained every previous hit.

To repeat the comparison, freeze the generated queries once and replay that file on both indexes. The generator needs the local model. The default scorer runs offline with AI off. Add `--gemma` to the scorer to run the live fallback.

```sh
python tools/rephrase_pr_permits.py new/PR.sqlite parcel-inputs queries.jsonl
python tools/check_pr_permit_coverage.py old/PR.sqlite parcel-inputs --rephrasings queries.jsonl
python tools/check_pr_permit_coverage.py new/PR.sqlite parcel-inputs --rephrasings queries.jsonl
```

## Locally prepared CRIM physical-address supplement

The local collection completed on November 19, 2026 (UTC), covering all **23,071 mapped grid prefixes** for **1,292,468 land numbers across all 78 municipios** through the public CRIM viewer's Parcela form. It saved returned nonblank physical-address wording for mapped land numbers, with each land number and reported municipio, to a local CSV. Every saved CSV field was checked against the checkpoint. All **17 reported-empty grids** were rechecked with exact searches, bracketed by known nonempty controls.

The resulting index has CRIM wording on **1,156,106 distinct parcels**. Combining those records with the existing SIP and ARPE wording reaches **1,166,265 parcels**, compared with **116,649** from those permits alone. SIP/ARPE wording counts any recorded permit wording; it is broader than the numbered-road column in the first table (62,164). The table below isolates these three sources; optional Planning Board consultation rows are excluded from the comparison. The tested local index retains its earlier consultation supplement.

The import excluded **20,352 placeholder-only records**, **10,863 records with conflicting reported municipios**, **16 administrative-only records**, and **12 records whose mapped land number had an ambiguous or missing municipio**. Every eligible collected tuple was checked for inclusion, and the previous wordings and map tables were checked for preservation. The collector retained **2 distinct records with unusable land numbers** separately, without assigning them to a parcel.

**2,612 sampled source-based map cases** covered all 78 municipios with AI off, including original wording, reordered raw fields, street-style inputs, ZIPs, field-ending periods, shared wording and the highest-multiplicity wording in each municipio. Desktop's socket-free bridge and compiled Swift agreed on the checked result pages, counts, order, coordinates and boundaries. **2,214 negative cases passed**: unused ZIP and lot queries returned no parcels; altered-municipio queries did not return the original reference parcels. **116 cases** exercised more than 200 candidates, checking the first, middle and last pages. Sets of 200 or fewer were checked on every page. Python modules loaded directly from the installed Mac executable's embedded archive replayed the same 2,612 map cases against the installed index, with the same results. This check does not operate the app window.

A recorded wording is evidence that a source links that description to a land boundary. Several parcels can share it. These are source-availability and regression results; they do not measure unique homes or entrances. Additional street queries removed recognized country fillers and moved one municipio field to the end; unrecognized suffixes stayed in place. Reordered cases preserve each original field. Signature-derived renderings were supplementary checks. Raw data and local indexes remain local. The contribution supplies the collector, builder, instructions, invented fixtures and these aggregate counts. [Preparation instructions](MAPS.md#collect-crim-physical-addresses-for-selected-areas) · [Public viewer](https://catastro.crimpr.net/cdprpc/)

| Municipio | Mapped land numbers | SIP/ARPE wording | CRIM wording | Combined SIP/ARPE/CRIM |
| --- | ---: | ---: | ---: | ---: |
| Adjuntas | 7,199 | 879 | 6,092 | 6,186 |
| Aguada | 17,252 | 2,222 | 15,045 | 15,302 |
| Aguadilla | 25,500 | 2,704 | 23,653 | 23,791 |
| Aguas Buenas | 9,011 | 1,268 | 8,257 | 8,320 |
| Aibonito | 10,278 | 1,178 | 9,204 | 9,313 |
| Añasco | 10,905 | 1,396 | 9,500 | 9,677 |
| Arecibo | 38,665 | 2,947 | 32,938 | 33,212 |
| Arroyo | 8,447 | 749 | 7,398 | 7,509 |
| Barceloneta | 10,078 | 577 | 8,525 | 8,592 |
| Barranquitas | 8,999 | 957 | 7,025 | 7,207 |
| Bayamón | 66,346 | 1,885 | 63,117 | 63,218 |
| Cabo Rojo | 28,821 | 3,083 | 26,652 | 26,847 |
| Caguas | 47,089 | 2,644 | 44,629 | 44,766 |
| Camuy | 14,826 | 1,232 | 12,441 | 12,594 |
| Canóvanas | 15,720 | 1,200 | 14,672 | 14,781 |
| Carolina | 45,458 | 2,116 | 43,496 | 43,622 |
| Cataño | 7,844 | 696 | 6,723 | 6,769 |
| Cayey | 18,040 | 2,197 | 16,796 | 16,889 |
| Ceiba | 5,884 | 527 | 5,397 | 5,442 |
| Ciales | 7,858 | 670 | 6,447 | 6,531 |
| Cidra | 15,092 | 1,218 | 14,035 | 14,113 |
| Coamo | 16,549 | 1,584 | 14,794 | 14,945 |
| Comerío | 5,677 | 587 | 4,353 | 4,477 |
| Corozal | 11,906 | 1,177 | 9,463 | 9,661 |
| Culebra | 1,512 | 257 | 1,311 | 1,327 |
| Dorado | 13,937 | 1,526 | 12,857 | 12,973 |
| Fajardo | 15,685 | 1,677 | 14,194 | 14,303 |
| Florida | 4,905 | 262 | 4,050 | 4,090 |
| Guánica | 8,198 | 740 | 7,357 | 7,422 |
| Guayama | 19,391 | 1,857 | 17,499 | 17,630 |
| Guayanilla | 7,493 | 731 | 6,304 | 6,401 |
| Guaynabo | 25,363 | 2,127 | 22,907 | 23,053 |
| Gurabo | 16,266 | 1,495 | 15,297 | 15,376 |
| Hatillo | 15,417 | 1,359 | 13,086 | 13,256 |
| Hormigueros | 6,970 | 762 | 6,343 | 6,396 |
| Humacao | 23,101 | 2,144 | 21,256 | 21,421 |
| Isabela | 23,051 | 2,468 | 20,547 | 20,735 |
| Jayuya | 5,253 | 638 | 4,406 | 4,486 |
| Juana Díaz | 18,974 | 1,527 | 17,105 | 17,249 |
| Juncos | 15,820 | 1,279 | 14,745 | 14,831 |
| Lajas | 12,197 | 1,357 | 10,832 | 10,932 |
| Lares | 11,890 | 1,090 | 9,148 | 9,312 |
| Las Marías | 4,104 | 529 | 3,399 | 3,473 |
| Las Piedras | 14,984 | 1,544 | 13,621 | 13,749 |
| Loíza | 7,693 | 559 | 6,957 | 7,056 |
| Luquillo | 8,346 | 927 | 7,741 | 7,818 |
| Manatí | 16,607 | 1,498 | 14,257 | 14,385 |
| Maricao | 2,334 | 238 | 1,797 | 1,838 |
| Maunabo | 5,298 | 596 | 4,439 | 4,514 |
| Mayagüez | 31,420 | 4,141 | 28,358 | 28,631 |
| Moca | 16,119 | 1,893 | 14,061 | 14,294 |
| Morovis | 9,637 | 822 | 8,064 | 8,170 |
| Naguabo | 11,291 | 1,096 | 10,168 | 10,267 |
| Naranjito | 8,544 | 774 | 7,684 | 7,784 |
| Orocovis | 8,373 | 864 | 6,593 | 6,743 |
| Patillas | 8,331 | 885 | 7,057 | 7,163 |
| Peñuelas | 8,819 | 947 | 7,481 | 7,586 |
| Ponce | 55,492 | 1,358 | 51,054 | 51,166 |
| Quebradillas | 11,000 | 1,138 | 10,025 | 10,120 |
| Rincón | 7,620 | 896 | 6,809 | 6,886 |
| Río Grande | 19,486 | 1,926 | 18,462 | 18,578 |
| Sabana Grande | 10,262 | 1,141 | 8,917 | 9,055 |
| Salinas | 14,222 | 1,302 | 12,483 | 12,650 |
| San Germán | 14,932 | 1,705 | 12,773 | 12,992 |
| San Juan | 91,258 | 10,860 | 82,751 | 83,180 |
| San Lorenzo | 15,266 | 1,714 | 13,393 | 13,505 |
| San Sebastián | 21,239 | 2,291 | 18,612 | 18,835 |
| Santa Isabel | 9,409 | 648 | 8,738 | 8,803 |
| Toa Alta | 24,325 | 1,715 | 22,381 | 22,514 |
| Toa Baja | 27,833 | 2,697 | 24,762 | 24,914 |
| Trujillo Alto | 18,875 | 2,072 | 17,689 | 17,827 |
| Utuado | 13,777 | 1,275 | 9,931 | 10,135 |
| Vega Alta | 12,716 | 1,209 | 10,758 | 10,912 |
| Vega Baja | 22,050 | 1,912 | 19,062 | 19,226 |
| Vieques | 6,071 | 687 | 5,470 | 5,541 |
| Villalba | 6,730 | 789 | 5,583 | 5,728 |
| Yabucoa | 13,214 | 1,417 | 11,308 | 11,520 |
| Yauco | 15,937 | 1,595 | 13,572 | 13,750 |

13 land numbers occur in two municipios and appear in both mapped counts; wording columns and island totals count each land number once.
