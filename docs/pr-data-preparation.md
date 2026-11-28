# Optional Puerto Rico index preparation

Lastbook's offline lookup uses the index installed on the reader. It cannot find house numbers or parcel
wording that are absent from that index. The companion preparation tools are intended to let residents
build a more useful index from authorized source material for their own offline use, without requiring
Lastbook to collect or host the records. A small address-only index does not supply the parcel coverage.

This tooling depends on the offline reader and builder in [PR #142](https://github.com/Immortal-Protocols/lastbook/pull/142).
The web and app readers do not call the data providers. The builder can already assemble a pack from
authorized local inputs; this separate change contains the connected acquisition and selected-area
preparation tools. It contains no address records, snapshots, caches, prepared indexes, or pack artifacts.

## Source evidence and open questions

Checked November 22, 2026. These are provenance notes, not a declaration that a source is licensed.
Access through a public form or API, including technical support for pagination, is not by itself
permission for bulk automation, local retention or redistribution. Those are three separate questions.

| Source used in the tools | What the publisher documents | What remains to be confirmed before live use |
| --- | --- | --- |
| CRIM [Catastro Digital viewer](https://catastro.crimpr.net/cdprpc/) and [user guide](https://catastro.crimpr.net/cdprpc/help/CDPRPC_ManualUsuario_20200708.pdf) | Public, no-fee interactive access and a Parcela prefix query. The guide describes certified cartographic downloads separately. CRIM's [main portal terms](https://portal.crim360.com/crimpr/CMS/18.html) link Catastro Digital and restrict overloading the service or using means not intentionally made available; applicability to the separate viewer was not verified. | Whether and at what scale the viewer may be queried automatically; whether parcel numbers, physical-address text and municipality may be retained locally, and whether any derived index may be shared. |
| Planning Board [CRIM parcel-boundary snapshot, February 2025](https://sigejp.pr.gov/server/rest/services/crim/crim_feb_2025/MapServer/0) | Public ArcGIS metadata describes a polygon layer with query support. The layer's copyright field is blank; the [publisher item](https://sigejp.pr.gov/portal/sharing/rest/content/items/cb0f3da3de93455b9515e6a3392d795b?f=pjson) is public and has no license or attribution value. This is not the CRIM physical-address viewer. | Publisher authorization for bulk retrieval, permitted fields and uses, local retention, attribution and any onward distribution. |
| Planning Board [SIP](https://sigejp.pr.gov/server/rest/services/MIPR/Permisos/MapServer/8), [ARPE](https://sigejp.pr.gov/server/rest/services/MIPR/Permisos/MapServer/16) and [consulta](https://sigejp.pr.gov/server/rest/services/MIPR/Permisos/MapServer/20) | Public ArcGIS layer metadata documents query capabilities; copyright fields are blank and the [shared publisher item](https://sigejp.pr.gov/portal/sharing/rest/content/items/168b95f4796a4c69b485105639f4b3b4?f=pjson) is public with no license or attribution value. The [MiPR map disclaimer](https://gis.jp.gov/mipr/mapa2.html?orig=pDigital) describes reference use and data limitations, not a redistribution license. | Publisher-approved API usage and reasonable load, whether address text and cadastral identifiers may be kept and joined for personal offline use, and whether any derived recirculation is allowed. |

The base inputs have separate provenance: [OpenStreetMap/ODbL](https://www.openstreetmap.org/copyright)
via [Geofabrik](https://download.geofabrik.de/north-america/us/puerto-rico.html),
[Census boundaries](https://tigerweb.geo.census.gov/),
[FHWA measured roads](https://catalog.data.gov/dataset/highway-performance-monitoring-system-hpms-2024)
and [NCES school locations](https://catalog.data.gov/dataset/public-school-locations-2024-25).
Attribution and any redistribution obligations for those inputs are not a grant for the CRIM or permit
sources or for a combined pack. Playwright for Python is Apache-2.0; its browser belongs only on the
preparation computer, not in the reader.

## Review and release gate

- Review with invented records and no live requests. From a local checkout with both this change and #142,
  run `python -B -m unittest tools.test_fetch_pr_crim tools.test_prepare_pr_municipio`.
- Keep connected scripts experimental pending source-specific confirmation. Do not enable scheduled or bulk
  collection, distribute any raw records or joined index, or ship an official pack based on this draft.
- Confirm the authorized endpoints, request rate and scope, fields, retention, attribution and permitted
  local and onward use with the applicable publisher. Keep personal data out of samples, artifacts and logs.
  A locally generated index should stay local unless all contributing sources permit sharing it.
