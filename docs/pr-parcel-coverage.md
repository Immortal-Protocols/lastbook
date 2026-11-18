# Puerto Rico rural address search by municipio

The November 17, 2026 build found **62,164 distinct parcels with a searchable numbered-road address** in Planning Board permits. All 78 municipios have matches. The CRIM map supplied boundaries for **1,292,468 distinct land numbers**. Thirteen numbers occur in two municipios. Each appears in both boundary counts below. The builder skips those numbers when attaching addresses.

The permit column counts each land number once, however many permits or accounts mention it. A record needs a numbered road and a matching parcel boundary. Some records also supply a kilometer, lot, sector or interior access. This build used only the public inputs. A CRIM physical-address export can add records for land that has no usable permit address. [Parcel and permit sources](MAPS.md#puerto-rico-street-addresses-and-land-parcels)

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

The offline test selected three distinct parcel numbers per municipio from ARPE permits that included a municipio prefix, one named road number and one kilometer marker. It selected by hash before checking for a parcel boundary or a match. The expected result was the land number on the permit. The test followed every page of candidates and ran with the model disabled.

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
