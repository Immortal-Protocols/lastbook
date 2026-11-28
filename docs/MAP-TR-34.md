# Istanbul (TR-34): an independently buildable offline map

Streets, building outlines, named places, emergency help points, earthquake assembly areas and civic addresses for
Istanbul (`TR-34`), built from redistributable open sources. Outputs follow [MAPS.md](MAPS.md) and stay under
`derived/regions/TR-34/`.

This is the builder/docs/fixtures split requested in [#134](https://github.com/Immortal-Protocols/lastbook/pull/134#issuecomment-7070924454),
prepared against main `96456866f166d1baa9fed38e11f1df39ecbe94bf`. It changes no shared address engine, server,
map UI, setup, release manifest or packager. It does **not** enable Turkish address search or an assembly-area layer
in the current app. Those requirements are recorded in the shared review in
[#31](https://github.com/Immortal-Protocols/lastbook/issues/31#issuecomment-7071932197).

## Build and inspect

```sh
python3 tools/build_region_tr_34.py fetch    # network: ~1.59 GB, mostly Geofabrik Turkey
python3 tools/build_region_tr_34.py build    # offline: writes derived/regions/TR-34/data/
python3 tools/build_region_tr_34.py check    # offline: validates the data, not the shared runtime
python3 tools/build_region_tr_34.py demo
python3 server.py --data derived/regions/TR-34/demo --no-index
```

Python 3.9+ standard library only; no GDAL, pyosmium or added dependencies. `fetch` is the only network step.
`build.json` records source URLs, dated filenames, data dates, licences, byte sizes and SHA-256 digests, plus every
output's size and digest. Reuse a previous `source/` folder to rebuild without downloading it again.

The builder first filters the GeoPackage to the Istanbul clip box, then calls the unchanged `tools/build_map.py`
converter and writes Istanbul source/date/bounds metadata. Build-time `tr-1` normalization lives in the region builder;
it defines the stored index keys, not a second runtime address parser.

`demo` creates an empty library beside the data. In current main, use the existing map layers and native-spelling
place queries such as `Kadıköy` and `Caferağa`. For example:

- `http://127.0.0.1:8890/#/map?lat=40.9905&lon=29.0265&z=15&layers=hospital,pharmacy,fire,police,water`
- `http://127.0.0.1:8890/#/map?lat=41.0425&lon=28.9720&z=15&layers=hospital,pharmacy,fire,police,water`

This is a local preview, **not** a normal Setup installation or proof of upgrade preservation. Do not copy the demo's
empty catalog over an existing library.

## Sources

| What | Source | Licence | Attribution |
|---|---|---|---|
| Streets, water, land use, buildings, named places and points | OpenStreetMap via Geofabrik, `turkey-YYMMDD-free.gpkg.zip`, clipped to `27.82,40.65,30.08,41.74` | ODbL 1.0 | © OpenStreetMap contributors |
| Civic addresses (`addr:housenumber` + `addr:street`), assembly areas (`emergency=assembly_point`) | OpenStreetMap via Overpass inside `ISO3166-2=TR-34` | ODbL 1.0 | © OpenStreetMap contributors |
| Hospitals, clinics, family health centres, doctors, dentists, pharmacies, vets, care homes | [İBB health institutions](https://data.ibb.gov.tr/dataset/istanbul-saglik-kurum-ve-kuruluslari-verisi/resource/f2154883-68e3-41dc-b2be-a6c2eb721c9e) (`saglik-tesisleri.xlsx`) | [İstanbul Büyükşehir Belediyesi Açık Veri Lisansı 1.0](https://data.ibb.gov.tr/license) | İstanbul Büyükşehir Belediyesi Açık Veri Portalı. "Atıf 4.0 Uluslararası (CC BY 4.0) kapsamında lisanslanan kamu sektörü bilgilerini içerir." |
| Fire stations | [İBB fire stations](https://data.ibb.gov.tr/dataset/itfaiye-istasyonlari-konum-bilgileri/resource/d3efb4ce-90b4-46b6-a96e-bbbe5b1e0234) (`itfaiye-istasyon-konumlar.2025.xlsx`) | [İstanbul Büyükşehir Belediyesi Açık Veri Lisansı 1.0](https://data.ibb.gov.tr/license) | İstanbul Büyükşehir Belediyesi Açık Veri Portalı. "Atıf 4.0 Uluslararası (CC BY 4.0) kapsamında lisanslanan kamu sektörü bilgilerini içerir." |
| Neighbourhood headmen offices and mahalle centres | [İBB muhtarlık addresses](https://data.ibb.gov.tr/dataset/muhtarlik-adres-bilgileri/resource/71f75529-7fae-4a85-b05f-664c62eda422) (`muhtarlik_lokasyon.geojson`) | [İstanbul Büyükşehir Belediyesi Açık Veri Lisansı 1.0](https://data.ibb.gov.tr/license) | İstanbul Büyükşehir Belediyesi Açık Veri Portalı. "Atıf 4.0 Uluslararası (CC BY 4.0) kapsamında lisanslanan kamu sektörü bilgilerini içerir." |
| Public toilets | [İBB public toilets](https://data.ibb.gov.tr/dataset/sehir-tuvaletleri-veri-seti/resource/9585ab4a-d160-4541-8a41-b86eeec4c1cc) (`sehir_tuvaletleri_verisi.geojson`) | [İstanbul Büyükşehir Belediyesi Açık Veri Lisansı 1.0](https://data.ibb.gov.tr/license) | İstanbul Büyükşehir Belediyesi Açık Veri Portalı. "Atıf 4.0 Uluslararası (CC BY 4.0) kapsamında lisanslanan kamu sektörü bilgilerini içerir." |
| Active fuel stations | [İBB fuel stations](https://data.ibb.gov.tr/dataset/akaryakit-istasyonlari/resource/5625860c-d79a-446f-898e-2aa2b9099bc8) (`akaryakt_istasyonlar_veri_seti_20261012t130600.csv`) | [İstanbul Büyükşehir Belediyesi Açık Veri Lisansı 1.0](https://data.ibb.gov.tr/license) | İstanbul Büyükşehir Belediyesi Açık Veri Portalı. "Atıf 4.0 Uluslararası (CC BY 4.0) kapsamında lisanslanan kamu sektörü bilgilerini içerir." |
| Province (`TUR034`) and 39 district (ilçe) boundaries | OCHA HDX COD-AB Türkiye, `tur_admin_boundaries.geojson.zip`, General Command of Mapping / HGM | CC BY-IGO | OCHA / General Command of Mapping (HGM) |

The official İBB terms page names the licence **İstanbul Büyükşehir Belediyesi Açık Veri Lisansı**; this project records its version as **1.0**. The required fallback attribution is the quoted sentence in the table above. It is attribution wording only: no CC BY, ODC-By or other equivalence classification is claimed for the İBB licence.

For hospitals, pharmacies and fire stations, İBB's municipal registers replace OSM points in the province. Other
municipal classes supplement OSM. Output metadata retains both OSM and İBB source credit; the shared runtime must
preserve the source of each address index and surface regional attribution, not replace it with US-only credits.

## Output contract

All paths below are relative to `derived/regions/TR-34/data/`:

| File | Holds |
|---|---|
| `derived/geo/national.sqlite` | `feat`, `feat_idx`, `poi`, `meta`: clipped roads, buildings, water, land, rail, places and help points |
| `derived/geo/map.sqlite` | Empty map tables, with Istanbul source, date and province bounds |
| `derived/geo/places.sqlite` | `place`, `place_fts`: province, districts, neighbourhoods, postcode areas, streets, named points and places |
| `derived/geo/addresses/TR-34.sqlite` | Separate civic-address sidecar; `meta.region=TR-34`, `meta.norm=tr-1`, `meta.source` credits OSM and İBB |
| `map-set.json` | `name=TR-34`, map-file sizes; the address sidecar remains separate, as for US maps |

The address schema is `addr(num,street,norm,city,state,zip,lat,lon,district)` with `addr_norm(norm,num)` and
`addr_zip(zip)` indexes. `state` stores `TR-34`, `city` the ilçe, and `district` the mahalle. `meta(key,value)` also
records count, source date and build time. Display text retains Turkish spelling; normalized keys fold `İ/I/ı`,
`ğ/ü/ş/ö/ç`, circumflex vowels and street abbreviations.

The original 17 November build used Geofabrik `turkey-261116-free.gpkg.zip` (OSM as of `2026-11-16T21:22:36Z`),
Overpass `2026-11-17T17:55:37Z`, İBB datasets and OCHA boundaries. Historical counts were 330,581 road features,
915,991 buildings, 51,482 civic addresses and 132 assembly points; map/address SQLite files totalled about 250 MB.
These are reference figures, not checksums for a new build; use the new `build.json` for exact counts and hashes.

## Independent checks

Run the source-address parser regressions without downloading or building data:

```sh
python3 -B -m unittest app.tests.test_build_region_tr_34
```

İBB house-number extraction keeps a separate door suffix (`No:25 F YALIKÖY/…` → `25F`), but does not
consume a neighbourhood's first letter (`No:75 FENERYOLU/KADIKÖY` → `75`).

`check` exits non-zero on data failures and validates:

- Every output's recorded size and SHA-256; map-set name and sizes; SQLite integrity for all four databases.
- Road/building and help-class counts, help/address bounds and five-digit postcodes where present.
- Address scheme/source metadata and stored normalized street keys, plus exact raw-SQL address retrieval.
- Province, district and neighbourhood entries through native SQLite FTS.

It deliberately does not call `engine.address_search` or `server.places`. Passing it proves the independently built
map/index, **not** Turkish runtime search, ASCII place folding, assembly-layer display or Setup/upgrade compatibility.

## Turkish query fixtures and shared runtime requirements

[`app/tests/fixtures/tr_34_queries.json`](../app/tests/fixtures/tr_34_queries.json) extracts the original PR's
small regression dataset and expected queries into data. Its seven rows are synthetic regression fixtures with public
street names, not a claim that every sample is present in a live source build. They can seed an isolated
`addresses/TR-34.sqlite` for the common engine's tests. Normalization examples define the persisted `tr-1` contract.

The shared runtime review needs:

- Per-index scheme dispatch using `meta.norm=tr-1`, without changing published US indexes or US query results.
- Street-first parsing, optional `No:`, `Cad./Cd.`, `Sk.`, `Blv.`, door suffixes (`7/B` → `7B`), numbers within
  street names (`19 Mayıs`), five-digit postcodes, ilçe/mahalle disambiguation and original source credit.
- No guessed door number or ignored wrong postcode/qualifier. `34710 Kadıköy` must remain a place query;
  `Route 66` must retain place-search fallthrough.
- Place FTS matching of ASCII `Kadikoy` to `Kadıköy` and `ISTIKLAL CADDESI` to `İstiklâl Caddesi`.
  SQLite `unicode61` leaves dotless `ı` distinct from `i`; ordinary diacritic removal alone is insufficient.
- Acceptance and upgrade carry-over of an address-index id/filename such as `TR-34` / `TR-34.sqlite`.
  Map ids already accept this shape; address-index manifest validation and carry-over still require two letters.
- An `assembly_point` layer and help/tile support, clearly labelled as **open-air gathering areas, not indoor shelters**.
- Region-aware map availability for place results (`onMap`), rather than assuming a published pack or Southern California.
- Normal Setup installation of a region and preservation of separately installed maps and sidecar indexes on upgrade.

These are integration requirements, not changes included in this branch. The original PR and the prepared scheme-engine
route remain available; shared address changes will be reviewed together, preserving both contributors' credit.

## Coverage limits

- UAVT / MERNİS is not open data, and Overture lists no Turkish address source. Civic addresses combine OSM `addr:*`
  and İBB facility/muhtarlık records; streets without mapped door numbers provide place-level coverage only.
- Assembly points are OSM records, not a complete official AFAD inventory. AFAD/e-Devlet uses interactive login;
  İBB's portal does not provide a complete bulk assembly-area file here.
- Terrain, crops, dam storage and the US resource atlas are not included.
- Region-neutral chrome, units and attribution display remain shared work in #25/#31.
