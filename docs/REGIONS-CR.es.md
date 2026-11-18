# Mapas detallados para Costa Rica: una propuesta

> Versión en español de [REGIONS-CR.md](REGIONS-CR.md). Si las dos difieren, vale la versión en inglés, que es la que se
> discute en el repositorio.

Esta es una propuesta para discutir, no una decisión. Responde, para Costa Rica, las preguntas que [MAPS.md](MAPS.md) pide
contestar antes de que la cobertura vaya más allá de Estados Unidos: qué fuente abierta reemplaza a cada lista federal,
con qué licencia, qué es un "estado" en el país y cómo se escriben las direcciones. Sigue la forma de
[REGIONS.md](REGIONS.md), [REGIONS-PY.md](REGIONS-PY.md) y [REGIONS-LK.md](REGIONS-LK.md) y busca alimentar la misma
discusión de diseño (issues #23, #25 y #31). La versión legible por máquina es
[regions-cr-proposed.json](regions-cr-proposed.json).

Nada de esto cambia la app, el motor ni una compilación. Ningún código lee el JSON, y nada de esto se distribuye: las
compilaciones empaquetan solo `web/` y `content/`.

**Cómo se verificó.** La investigación se hizo el 18 de noviembre de 2026. Cada dato lleva una de estas marcas:

- **abierta**: se abrió y se leyó la página, el archivo o la respuesta de la API;
- **calculada**: la cifra se calculó aquí a partir de un archivo descargado (se nombran el archivo y el método);
- **solo búsqueda**: el dato se vio en un resultado de búsqueda, pero no se abrió la página;
- **conocimiento general**: dicho de memoria, sin abrir ninguna fuente; necesita la revisión de alguien del país;
- **sin verificar**: no se pudo llegar a la página o leerla; la fila dice qué falta.

"No se encontró" quiere decir que no se encontró buscando en la web. Varios sitios del gobierno no se pudieron leer
completos: `geoportal-saracc.cne.go.cr` no se resolvió, `www.cne.go.cr` respondió 403, `www.sinac.go.cr` falló la
verificación del certificado y la única dirección del INVU que se probó devolvió 404. No se usó la API de Overpass; las
cifras de OSM se contaron sobre el extracto de Geofabrik.

## Qué es una región

Costa Rica tiene 7 provincias, 84 cantones y 492 distritos (conteo de elementos del COD-AB de OCHA, calculado; el propio
archivo avisa que le falta el cantón de Caldera, creado en 2014, abierta). La propuesta es **una región para todo el
país**, con código `CR`, como REGIONS-PY.md propone para Paraguay y REGIONS-LK.md para Sri Lanka. Un `CR` solo no choca con
ningún código de `STATE_CODES` (`engine/address_search.py`, línea 26, abierta; la lista tiene `CA`, `CO` y `CT`, pero no
`CR`).

Por qué una sola región:

- **Tamaño.** El polígono de nivel 0 del COD-AB cubre 51 168 km² (su atributo `area_sqkm`, que incluye la Isla del Coco;
  la cifra oficial es de unos 51 100 km², conocimiento general). Es menos que West Virginia (62 756 km², conocimiento
  general), así que cabe de sobra en lo que Lastbook ya distribuye como un mapa de estado. El extracto de OSM de todo el
  país pesa 37,4 MB, una cuarta parte de los 147 MB de Paraguay.
- **Las provincias no son chicas, pero la gente las cruza.** La mayor, Puntarenas, tiene 11 298 km² y la menor, Heredia,
  2 664 km² (`area_sqkm` del nivel 1). La mayor parte de la población vive en el Valle Central, donde se juntan San José,
  Alajuela, Heredia y Cartago (conocimiento general; no se comparó con el censo 2022). Quien escogiera el mapa de una sola
  provincia perdería parte de la ciudad donde vive, el mismo problema que REGIONS-AR.md describe para Buenos Aires.
- **En los bordes vive poca gente.** Buena parte de Guanacaste, Limón y el sur de Puntarenas está poco poblada
  (conocimiento general); un mapa de todo el país casi no ganaría ahí.

Si quienes mantienen el proyecto prefieren regiones más chicas, abajo están los rectángulos de las provincias. El caso del
Valle Central se trata como una agrupación aparte al final de esta sección.

### Rectángulo

El rectángulo recomendado es el **continental**. La Isla del Coco es territorio costarricense (en el COD-AB forma parte de
la provincia de Puntarenas, abierta), pero queda muy adentro del Pacífico, y un rectángulo que la incluya más que duplica
el área con casi puro mar.

| Código | Nombre | Rectángulo (oeste, sur, este, norte) | Con margen de 0,15° | Sacado de |
|---|---|---|---|---|
| `CR` | Costa Rica continental (**recomendado**) | -85,9503, 8,0402, -82,5528, 11,2196 | -86,11, 7,89, -82,40, 11,37 | COD-AB de OCHA, nivel 0, sin los 24 polígonos de la Isla del Coco (calculado) |
| `CR` | Costa Rica con la Isla del Coco | -87,1019, 5,4991, -82,5528, 11,2196 | -87,26, 5,34, -82,40, 11,37 | COD-AB de OCHA, nivel 0, todos los vértices (calculado) |
| (no es región) | Solo la Isla del Coco | -87,1019, 5,4991, -87,0278, 5,5635 | -87,26, 5,34, -86,87, 5,72 | los 24 polígonos al oeste de 86° O (calculado) |

El rectángulo es la extensión de todos los vértices del polígono de nivel 0 de OCHA (`cri_admin0.geojson`, fuente INEC,
vigente desde el 3 de diciembre de 2024, registro de HDX modificado por última vez el 14 de agosto de 2026; descargado y
calculado el 18 de noviembre de 2026), menos/más 0,15° y redondeado hacia afuera a 0,01°, el mismo margen que usa
`map_sets.state` para los estados de EE. UU. El archivo de nivel 0 es un solo elemento cuya geometría tiene polígonos para
el continente, la península de Nicoya y otras islas, y 24 para la Isla del Coco y sus islotes (todos al oeste de 86° O;
separados por longitud, calculado).

El polígono de recorte de Geofabrik (`costa-rica.poly`, abierta) da un rectángulo de -87,82473, 4,937746, -82,34952,
11,2237. También cubre la Isla del Coco y es más holgado que cualquiera de los anteriores, como es de esperar de un
polígono dibujado alrededor de la frontera.

**Qué hacer con la Isla del Coco.** Se sugiere el rectángulo continental para `CR`, anotando que el Coco queda fuera del
rectángulo. El extracto de Geofabrik sí la incluye (el polígono llega a 87,8° O), así que los datos de OSM de la isla
entrarían a una compilación y solo los quitaría el recorte. Si se quiere conservar la isla, lo limpio es un segundo
rectángulo diminuto (la tercera fila), no ensanchar `CR`. La isla no tiene habitantes, salvo guardaparques (conocimiento
general), así que importa más por completitud que por uso. Si `map_sets` admite dos rectángulos para un mismo id es una
pregunta de código que esta propuesta no responde.

**Vecinos dentro del rectángulo continental** (conocimiento general; no se midió). Al norte, el sur de Nicaragua: el
departamento de Rivas con San Juan del Sur, la orilla sur del Lago de Nicaragua y el sur del departamento de Río San Juan.
Al sureste, una franja de Panamá a lo largo de la frontera (Chiriquí y la punta oeste de Bocas del Toro). El resto es mar.
Pasos fronterizos con pueblo a cada lado: Paso Canoas y Sixaola con Guabito. El extracto de Geofabrik está cortado fuera
de la frontera, así que una primera compilación trae algo de esos lugares; cuánto, no se midió. La sugerencia es la misma
que para Paraguay: la frontera como borde de una primera compilación y decidir una franja después.

### Un límite en disputa: el norte de Isla Portillos

Costa Rica y Nicaragua se disputaron un humedal de unos 3 km² en el norte de Isla Portillos, en la desembocadura del Río
San Juan en el Caribe. El 16 de diciembre de 2015 la Corte Internacional de Justicia resolvió, por 14 votos contra 2, que
Costa Rica tiene soberanía sobre ese "territorio en disputa", y que el dragado de caños y la presencia militar de
Nicaragua ahí violaron esa soberanía (abierta: el resumen de la sentencia en el sitio de la Corte). La misma página dice
que ambas partes aceptan que la Laguna Los Portillos (Harbor Head) es nicaragüense. Una segunda sentencia, del 2 de
febrero de 2018, fijó el límite terrestre en la costa: Costa Rica tiene soberanía sobre todo el norte de Isla Portillos,
costa incluida, salvo la laguna y la barra de arena que la separa del mar (solo búsqueda, a partir de material de prensa
de la Corte; la sentencia de 2018 no se abrió).

Qué significa para el mapa, sin rodeos: el COD-AB muestra esa zona como Costa Rica (su distrito Colorado, del cantón de
Pococí, provincia de Limón, tiene vértices hasta 10,9424° N, calculado; no se revisó si su borde sigue la línea de 2018),
lo cual coincide con la Corte. Cómo la dibuja OSM no se revisó. Lastbook no necesita un trato especial más allá de dibujar
el límite donde lo puso la Corte; se anota para decidirlo una sola vez para todas las regiones (punto 6 de REGIONS.md).

### Provincias, si se quieren regiones más chicas

ISO 3166-2:CR da `CR-SJ` San José, `CR-A` Alajuela, `CR-C` Cartago, `CR-H` Heredia, `CR-G` Guanacaste, `CR-P` Puntarenas y
`CR-L` Limón (conocimiento general; no se comparó con el sitio de ISO). Los códigos p del COD-AB son `CR1` a `CR7`, en el
orden San José, Alajuela, Cartago, Heredia, Guanacaste, Puntarenas, Limón (calculado), que no es el orden de las letras
ISO; todo cruce entre ambos debe hacerse por nombre.

Los rectángulos se calcularon con los polígonos de nivel 1 de OCHA (`cri_admin1.geojson`, 7 elementos) con la misma regla.
Puntarenas es la única provincia que contiene la Isla del Coco, por eso tiene dos rectángulos.

| Código ISO | Código p COD-AB | Nombre | Rectángulo (oeste, sur, este, norte) | Con margen de 0,15° | Área (km², `area_sqkm`) |
|---|---|---|---|---|---|
| `CR-SJ` | CR1 | San José | -84,5927, 9,0751, -83,4294, 10,1910 | -84,75, 8,92, -83,27, 10,35 | 4 971 |
| `CR-A` | CR2 | Alajuela | -85,4493, 9,8401, -84,1612, 11,0843 | -85,60, 9,69, -84,01, 11,24 | 9 773 |
| `CR-C` | CR3 | Cartago | -84,0882, 9,4841, -83,3119, 10,1475 | -84,24, 9,33, -83,16, 10,30 | 3 094 |
| `CR-H` | CR4 | Heredia | -84,2002, 9,9594, -83,7100, 10,7925 | -84,36, 9,80, -83,55, 10,95 | 2 664 |
| `CR-G` | CR5 | Guanacaste | -85,9503, 9,7269, -84,7661, 11,2196 | -86,11, 9,57, -84,61, 11,37 | 10 192 |
| `CR-P` | CR6 | Puntarenas, continental | -85,2798, 8,0402, -82,7120, 10,3375 | -85,43, 7,89, -82,56, 10,49 | 11 298 (incluye el Coco) |
| `CR-P` | CR6 | Puntarenas, con la Isla del Coco | -87,1019, 5,4991, -82,7120, 10,3375 | -87,26, 5,34, -82,56, 10,49 | |
| `CR-L` | CR7 | Limón | -83,9474, 9,0748, -82,5528, 10,9424 | -84,10, 8,92, -82,40, 11,10 | 9 177 |

Las siete áreas suman los 51 168 km² del nivel 0 (calculado). Los rectángulos de provincias vecinas se traslapan mucho: el
Valle Central queda donde se juntan los rectángulos de San José, Alajuela, Heredia y Cartago, así que el mapa de una sola
provincia, cortado por su rectángulo, trae buena parte de la tierra de las otras.

### La Gran Área Metropolitana (GAM), como agrupación aparte

La GAM es la región urbana del Valle Central. Es una región de planificación, no un nivel administrativo. El Plan Regional
de Ordenamiento Territorial de la Gran Área Metropolitana, "Plan GAM 2013-2030", lo aprobó el Consejo Nacional de
Planificación Urbana el 20 de enero de 2014 y se oficializó con el Decreto 38145 (en los resultados también aparece un
reglamento 38334-H de 2014) (solo búsqueda, de la Plataforma Urbana de la CEPAL). La Dirección de Urbanismo del INVU y la
secretaría del Consejo le dan seguimiento (solo búsqueda). Una fuente de búsqueda lo ubica en 31 cantones y 165 distritos
(solo búsqueda), repartidos entre San José, Alajuela, Cartago y Heredia.

Lo que no se sabe:

- **La lista exacta de cantones.** Una lista parcial del texto del decreto incluye San José, Escazú, Desamparados, Mora,
  Goicoechea, Santa Ana, Aserrí, Alajuelita, Vázquez de Coronado, Tibás, Moravia y Montes de Oca (solo búsqueda, texto
  cortado). La lista completa, y si algunos cantones entran en todo o en parte, no se leyó.
- **Un polígono descargable.** No se encontró. El "Atlas Digital del Plan GAM 2013" tiene 83 mapas y 172 capas y figura en
  el repositorio del Instituto Tecnológico de Costa Rica (solo búsqueda); no se encontró cómo obtener los archivos. La
  página del INVU que se probó devolvió 404 y la de la CEPAL respondió 403. Sin archivo no hay licencia que citar.
- **Licencia.** No se encontró, así que no se supone ninguna.

Dos formas de armar la agrupación, si se quiere. (1) La unión de los cantones que nombra el plan, tomados del nivel 2 del
COD-AB (CC BY-IGO, abierta), una vez confirmada la lista; no necesita ningún archivo del INVU. (2) El polígono propio del
plan, que necesita permiso del INVU. Como Bangkok en REGIONS-TH.md y Asunción en REGIONS-PY.md, sería una agrupación aparte
con su propio id (por ejemplo `CR-GAM`; el id lo deciden quienes mantienen el proyecto), no un `CR-SJ` que signifique más
que la provincia de San José. No se calculó su rectángulo porque la lista de cantones no está confirmada.

**Ya en marcha.** Ningún pull request abierto propone Costa Rica como región (búsqueda del 18 de noviembre de 2026). El
PR #35 trae un recuadro de capital `cr-san`, -84,39, 9,64, -83,79, 10,24, recortado del mismo extracto de Geofabrik. Ese
cuadrado contiene las ciudades de San José, Alajuela, Heredia y Cartago, así que se acerca al núcleo de la GAM, pero es
un cuadrado fijo de 0,6° y no el límite del plan. Una región de todo el país lo contiene.

**Posible contraste.** El archivo ADM1 de geoBoundaries para Costa Rica podría servir para revisar los rectángulos. No se
miró.

## Fuentes, capa por capa

OpenStreetMap es la base de una primera compilación. El instituto de estadística (INEC) aporta los límites por medio de
OCHA. El geoportal nacional (SNIT, que opera el Instituto Geográfico Nacional dentro del Registro Nacional) tiene capas
oficiales de terreno, agua y otras, pero no se encontraron abiertos sus términos. La capa de direcciones de Overture no
lista Costa Rica, y su capa de lugares no da cifras por país.

| Capa (archivo) | Fuente actual en EE. UU. | Propuesta para Costa Rica | Quién publica | Licencia | Marca |
|---|---|---|---|---|---|
| Calles, agua, tierra (mapa base) | extracto de OSM | extracto de OSM `costa-rica-latest.osm.pbf` (37,4 MB; el `.shp.zip` gratuito pesa 79 MB y el `.gpkg.zip` 81 MB), datos hasta el 17 de noviembre de 2026 21:24 UTC | colaboradores de OSM, vía Geofabrik | ODbL 1.0 | abierta |
| Puntos de interés (`poi`) | OSM | OSM (conteos abajo) | colaboradores de OSM | ODbL 1.0 | calculada |
| Lugares (`places.sqlite`) | GNIS, gazetteers del Censo, OSM | COD-AB de OCHA niveles 1 a 3 (7 provincias, 84 cantones, 492 distritos) y sus `adminpoints`; lugares con nombre de OSM | OCHA, a partir del INEC; colaboradores de OSM | CC BY-IGO; ODbL 1.0 | registro de HDX, archivos y conteos abiertos |
| Terreno (`terrain.sqlite`) | USGS 3DEP | Copernicus DEM GLO-30, como se propone para Guyana y Paraguay | ESA / Airbus | licencia Copernicus WorldDEM-30 | página de la colección abierta (gratis para el público general bajo la licencia Copernicus); avisos como en REGIONS.md |
| Terreno, alternativa nacional | | curvas de nivel (10 m y 2 m) y modelos de elevación del SNIT / IGN | IGN, Registro Nacional | **no se encontró**: la página del SNIT dice "Todos los derechos reservados" y ninguna licencia abierta | solo búsqueda para las capas; página del SNIT abierta para la línea de derechos |
| Agua (`water.sqlite`) | NHD | cauces y cuerpos de agua de OSM; hidrografía 1:5000 del IGN, si sus términos lo permiten | colaboradores de OSM; IGN | ODbL 1.0; sin aclarar | solo búsqueda (capa del IGN) |
| Presas | NID | OSM `waterway=dam` y `water=reservoir`; no se encontró inventario abierto de presas | colaboradores de OSM | ODbL 1.0 | calculada |
| Cultivos (`crops.sqlite`) | USDA Cropland Data Layer | ESA WorldCover 2021 (cobertura de 10 m, v200); no se encontró mapa nacional de cultivos | consorcio ESA WorldCover | CC BY 4.0 | abierta (página del registro de AWS) |
| Edificios (`buildings.sqlite`) | huellas de Microsoft EE. UU., alturas de OSM | Microsoft Global ML Building Footprints (21 teselas, 1 460 785 filas para Costa Rica); edificios de Overture como alternativa; alturas de OSM | Microsoft; Overture Maps Foundation; colaboradores de OSM | CDLA Permissive 2.0 (Microsoft); ODbL (Overture) | teselas y filas calculadas; licencia del README, abierta |
| Direcciones (`addresses/<código>.sqlite`) | direcciones de Overture | **No se encontró ninguna.** La capa de direcciones de Overture lista 41 países y Costa Rica no está entre ellos | | | abierta |

### Puntos de ayuda y de recursos

Los conteos se hicieron con pyosmium sobre el extracto de Geofabrik de arriba (datos hasta el 17 de noviembre de 2026
21:24 UTC). Cada conteo incluye nodos, vías y relaciones con la etiqueta.

| Tipo | Etiqueta de OSM | Cantidad | Otra fuente | Marca |
|---|---|---|---|---|
| Hospitales | `amenity=hospital` | 119 | listas del Ministerio de Salud / CCSS, no se buscaron | calculada |
| Clínicas y médicos | `amenity=clinic`, `amenity=doctors` | 1 576 (1 152 clínicas, 424 médicos) | igual | calculada |
| Farmacias | `amenity=pharmacy` | 714 | no se encontró | calculada |
| Estaciones de bomberos | `amenity=fire_station` | 80 | Cuerpo de Bomberos, no se buscó | calculada |
| Policía | `amenity=police` | 690 | no se encontró | calculada |
| Estaciones de ambulancia | `emergency=ambulance_station` | 127 | Cruz Roja, no se buscó | calculada |
| Agua potable | `amenity=drinking_water`, `man_made=water_tap`, `amenity=water_point` | 91 (54, 28, 9) | no se encontró | calculada |
| Pozos, torres y tanques de agua | `man_made=water_well`, `water_tower`, `storage_tank` | 491 (16 pozos, 120 torres, 355 tanques, el contenido no se revisó) | no se encontró | calculada |
| Embalses y presas | `water=reservoir`, `waterway=dam` | 134 embalses (`landuse=reservoir` no se contó), 25 presas | no se encontró | calculada |
| Combustible | `amenity=fuel` | 441 | no se encontró | calculada |
| Refugios y puntos de reunión | `amenity=shelter`, `social_facility=shelter`, `emergency=assembly_point` | 393 (379, 14, 1) | CNE, ver notas | calculada |
| Escuelas | `amenity=school` | 4 442 | Ministerio de Educación (MEP), no se buscó | calculada |
| Puestos de guardaparques | `amenity=ranger_station` | 52 | SINAC, ver notas | calculada |
| Volcanes y aguas termales | `natural=volcano`, `natural=hot_spring` | 57 (35, 22) | OVSICORI, ver notas | calculada |
| Áreas protegidas | `boundary=protected_area` | 111 | SINAC, ver notas | calculada |

Notas:

- **Contar filas no es contar lugares.** En OSM un mismo hospital suele estar como punto y otra vez como cada uno de sus
  edificios. Los conteos de arriba son cotas superiores; aquí no se agruparon por distancia.
- **"Shelter" en OSM.** `amenity=shelter` marca techitos, no albergues de emergencia. De los 379 de Costa Rica, por
  `shelter_type` (calculado): 138 de transporte público, 115 de cobertizo abierto, 69 sin tipo, 26 de merendero, 20
  glorietas, 5 pabellones, 3 refugios de erupción, 2 chozas básicas y 1 contra la intemperie. No deben dibujarse como
  albergues de emergencia. El único `emergency=assembly_point` es el único punto de reunión de emergencia del extracto.
  Los 3 refugios de erupción son un caso propio de Costa Rica que vale revisar a mano.
- **Etiqueta de volcán.** 35 objetos `natural=volcano` son más que los volcanes activos del país (conocimiento general:
  cinco o seis están activos); la etiqueta incluye conos y cráteres extintos. En OSM no traen aquí un estado.
- **Terreno.** Copernicus GLO-30 es un modelo de superficie: bajo el bosque sigue la copa de los árboles, no el suelo.
  Buena parte de Costa Rica es bosque (conocimiento general), así que la vista 3D mostrará las copas. Las curvas y modelos
  del propio IGN podrían ser mejores, pero no se encontró licencia abierta para ellos.
- **Cultivos.** WorldCover mapea clases de cobertura (árboles, cultivos, urbano y así), no tipos de cultivo, así que la
  correspondencia de clases para `tools/build_crops.py` necesita una decisión (como el punto 4 de REGIONS.md). No se buscó
  más allá una capa nacional de cultivos o uso de la tierra; ninguna apareció.
- **Edificios.** Las huellas de Microsoft se parten por país y por quadkey de nivel 9; Costa Rica tiene 21 teselas en
  `dataset-links.csv` (calculado), con fecha 23 de febrero de 2026, y 1 460 785 líneas en total (calculado: se
  descomprimió cada tesela y se contaron sus líneas; una línea es una huella, como implica el GeoJSON por líneas del
  README). Una tesela (quadkey `032221002`, 57,7 MB) trae 693 762, el 47 %, que debería ser el Valle Central, pero no se
  ubicó la tesela en el mapa. OSM tiene 201 480 vías de edificio en el mismo extracto (calculado, solo vías; no se
  contaron relaciones ni nodos), así que el archivo de Microsoft es mucho más denso que OSM. Los edificios de Overture
  ponen primero a OpenStreetMap y suman huellas de Microsoft y de Google (abierta, página de edificios de Overture), por
  eso una compilación de Overture y una de Microsoft se traslapan. Las huellas no se compararon con edificios reales.
- **Lugares de Overture.** La página de lugares de Overture (abierta) da conteos por fuente pero ninguno por país, y dice
  que las cifras por país se publicarán cuando estén confirmadas. Se desconoce, entonces, la parte de Costa Rica. Sus
  licencias son CDLA Permissive 2.0, Apache 2.0 y CC0, según la fuente.
- **Límites oficiales.** El COD-AB dice que contiene dos errores topológicos de traslape y cinco de hueco, y que le falta
  el cantón de Caldera (abierta, del registro de HDX). Su ADM3 "Alfaro Ruiz" aparece como Zarcero en el COD-AB (misma
  nota).
- **Portal de datos abiertos.** `datos.go.cr` es el portal nacional (abierta). Su página de inicio lista un conjunto en
  "Ambiente", y ahí no apareció ninguno de la CNE, el SINAC, el IGN ni el INVU; no indica una licencia general.
- **Direcciones.** OSM tiene 11 803 objetos con `addr:housenumber`, 33 402 con `addr:street` y 8 560 con `addr:postcode`
  (todos calculados). La cifra baja de números de puerta no es un hueco del mapa: la mayoría de las direcciones
  costarricenses no tiene (ver abajo). Un primer mapa de Costa Rica saldría como "mapa de calles, lugares y puntos de
  ayuda" sin búsqueda de direcciones, como se sugiere para Paraguay y Sri Lanka.

### Amenazas: una capa opcional para Costa Rica

Costa Rica tiene varias amenazas que importan en una biblioteca de supervivencia: sismos, volcanes, inundaciones,
deslizamientos y tsunami (conocimiento general). Nada de lo siguiente se propone para una primera compilación. La idea es
decir qué podría alimentar esa capa y ser honestos con la licencia.

| Capa | Quién publica | Qué se encontró | Licencia | Marca |
|---|---|---|---|---|
| Mapas de amenazas por cantón | CNE (Comisión Nacional de Prevención de Riesgos y Atención de Emergencias) | Su geoportal `geoportal-saracc.cne.go.cr` figura con servicios OGC (WMS, WFS, WCS, WMTS) y un catálogo; el servidor no se resolvió desde aquí. Hay capas de amenazas por cantón citadas en estudios; no se encontró si se pueden descargar | **no se encontró** | solo búsqueda |
| Datos de volcanes y sismos | OVSICORI-UNA | El menú del sitio muestra un conteo sísmico diario, sismicidad histórica, boletines mensuales y una sección "Descargas"; no se leyó su contenido. El informe anual de sismicidad 2025 lleva CC BY 4.0 en su propia página, y otros informes del mismo repositorio llevan CC BY-NC-SA 4.0 | el pie del sitio dice "Todos los derechos reservados" (abierta); las licencias de los documentos varían (solo búsqueda) | página de inicio abierta; el resto, solo búsqueda |
| Red sísmica nacional | RSN (UCR-ICE) | No se encontró nada | **no se encontró** | sin verificar |
| Áreas silvestres protegidas | SINAC | Un periódico da 169 (solo búsqueda). El INVU tiene un mapa de ellas para el plan GAM (2013). No se encontró archivo descargable de límites; `www.sinac.go.cr` falló la verificación del certificado. OSM tiene 111 objetos `boundary=protected_area` (calculado) | **no se encontró** | solo búsqueda |
| OSM | | Los volcanes, aguas termales y puestos de guardaparques de OSM (conteos arriba) están disponibles hoy bajo ODbL | ODbL 1.0 | calculada |

O sea, de las tres capas consultadas, ninguna tiene licencia abierta encontrada. Los servicios OGC de la CNE y las
descargas del OVSICORI necesitarían una licencia o un sí por escrito antes de copiar un archivo a un conjunto de mapas.
Por ahora solo OSM puede mostrar volcanes, aguas termales y áreas protegidas, con la salvedad de que la etiqueta de volcán
mezcla activos y extintos.

## Licencias y atribución

- **CC BY-IGO** (COD-AB de OCHA, abierta por la API de HDX: fuente "Costa Rica National Statistics Office (NSO)"; registro
  de HDX modificado por última vez el 14 de agosto de 2026; límites vigentes desde el 3 de diciembre de 2024). Hay que dar
  crédito a OCHA y a su fuente.
- **ESA WorldCover** es CC BY 4.0 (abierta, registro de AWS). Un mapa debe llevar el crédito que da REGIONS.md.
- **Copernicus GLO-30**: gratis para el público general bajo la licencia Copernicus (abierta, registro de AWS); los avisos
  que hay que llevar están en REGIONS.md.
- **Microsoft Global ML Building Footprints**: CDLA Permissive 2.0 (abierta, el README del repositorio, resumido); una
  compilación de Overture es ODbL porque incluye OSM.
- **ODbL y CC BY 4.0:** como en REGIONS.md.
- **SNIT / IGN, CNE, OVSICORI, SINAC:** no se encontró licencia abierta. La página del SNIT dice "Todos los derechos
  reservados" y "La oficialidad es responsabilidad de la institución que la publique" (abierta). No hay que copiar estas
  capas sin preguntar.

## Cómo se escriben las direcciones

Esta parte necesita la revisión de alguien de Costa Rica.

- **Indicaciones desde un punto de referencia.** La mayoría de las direcciones no lleva nombre de calle ni número. Dan un
  punto de partida, una dirección y una distancia, en cuadras o en metros: "De la pulpería La Chanchita, 400 al este, 200
  al sur y 25 al norte" (abierta: una columna de La Nación de 1997), o "De la Iglesia de Zapote 200 mts al Sur" (solo
  búsqueda: dada como la dirección de la sede de Correos). El punto de partida es una iglesia, una escuela, un negocio o un
  edificio que ya no existe. La dirección no es una cadena única: el mismo nombre de referencia se repite en muchos
  pueblos, así que importan el distrito y el cantón.
- **Intentos oficiales.** Correos y las municipalidades han intentado numerar calles y casas; en 2012 empezó un proyecto
  de nombres de calles en San José (solo búsqueda). Un reporte de 2005 dice que Correos planeaba nuevas direcciones (solo
  búsqueda). Cuánto avanzó no se encontró. Correos estima que el 40 % de las direcciones de sus clientes está mal
  (abierta: La Nación, 2009).
- **Código postal.** Cinco dígitos: el primero es la provincia, los dos siguientes el cantón y los dos últimos el
  distrito. Por ejemplo, `30502` es La Suiza (02), Turrialba (05), Cartago (3) (abierta: La Nación; Wikipedia da la misma
  estructura). Los números coinciden con la división territorial del INEC, así que hay un código por distrito, y los 492
  distritos del COD-AB coinciden con los "492 códigos" que dio un resultado de búsqueda (otra base de datos lista 487). Es
  gratis en el sitio de Correos o en cualquier sucursal. **Dos fechas chocan:** la página de La Nación es del 28 de abril
  de 2009 y Wikipedia dice que los códigos se introdujeron en marzo de 2013. Qué tan usados son no se encontró; Correos
  dice que un cartero lee una dirección en unos 7 segundos y que con código el tiempo se reduce a la mitad (abierta, La
  Nación 2009), lo que es una afirmación, no una medición. OSM trae `addr:postcode` en 8 560 objetos (calculado).
- **Qué hace el código actual con eso.**
  - Los cinco dígitos calzan con lo que acepta `engine/address_search.py` (`\d{5}`, línea 65), pero significan otra cosa:
    en EE. UU. son un ZIP; aquí nombran un distrito. El buscador no lo sabe, así que un código costarricense solo se
    reconocería como ZIP si el índice tuviera esa fila. El problema de seis dígitos de REGIONS-PY.md aquí no existe.
  - `_parts()` espera un número de casa como primera palabra de la consulta ("number, remainder = query.strip().split(None,
    1)"), lo que sirve para "10 Calle X" y no para "200 m norte de la Iglesia". La búsqueda en Costa Rica sería por nombre
    de lugar, no por dirección.
  - `normalize()` conserva solo `a-z`, `0-9` y espacios, así que cualquier otra letra se vuelve espacio: "200 m norte de la
    Iglesia de Zapote, San José 10101" queda `200 m norte de la iglesia de zapote san jos 10101`, y "Pérez Zeledón" queda
    `p rez zeled n` (la expresión regular de `normalize()`, ejecutada el 18 de noviembre de 2026). Hace falta quitar los
    acentos de los dos lados; REGIONS-PY.md y REGIONS-DE.md encontraron lo mismo, y #79 propone que cada índice declare su
    propia regla.
  - El buscador de lugares usa un índice FTS5 con el tokenizador `unicode61`, que ignora los acentos (como probó
    REGIONS-PY.md con nombres en español y guaraní). No se volvió a probar con nombres costarricenses.

## Idioma

El español es el idioma oficial; las lenguas indígenas están reconocidas (conocimiento general). Los nombres de lugar son
en español, con muchos nombres indígenas (Guanacaste, Turrialba, Irazú). Las tildes (á, é, í, ó, ú, ñ) son las únicas
letras especiales que casi todos los nombres necesitan, que es el problema de `normalize()` de arriba. Qué nombre muestra
el mapa donde también existe uno indígena o en inglés no se miró; eso es parte de la pregunta de idioma de los issues #3 y
#54.

## Todavía sin decidir

Cada punto necesita la decisión de quienes mantienen el proyecto antes de cambiar código. Los puntos 1, 2, 4 y 5
corresponden a los puntos 1, 2, 4 y 3 de REGIONS.md, y el 9 a su punto 7.

1. **Códigos en la instalación.** Si `CR` sirve como `id` del manifiesto, en `map-set.json` y en `Lastbook-Map-CR.zip` y,
   si se quieren provincias, si sirven códigos con guion como `CR-SJ`.
2. **La regla del rectángulo.** Si el rectángulo continental es el borde de una primera compilación, si el recorte es la
   frontera o una franja, y qué pasa con la Isla del Coco (un segundo rectángulo diminuto, o dejarla fuera).
3. **Una región, siete, o una más una agrupación GAM.** Todo el país (lo propuesto), siete provincias, o el país más una
   agrupación `CR-GAM` (su id y su lista de cantones los deciden quienes mantienen el proyecto y falta confirmarlos).
4. **Clases de cultivo.** Cómo se corresponden las clases de ESA WorldCover con huertos, viñedos y bayas, como el punto 4
   de REGIONS.md.
5. **Búsqueda de direcciones.** Si se publica sin ella (lo propuesto), si una dirección por referencia se puede soportar
   siquiera, y cómo distinguir un código de distrito de cinco dígitos de un ZIP de EE. UU.
6. **Puntos de ayuda sin fuente abierta.** Establecimientos de salud, estaciones de bomberos, albergues de la CNE, capas
   de amenazas. A quién preguntar, y si OSM solo basta para una primera compilación.
7. **Capas oficiales sin licencia.** Si se pide por escrito al IGN, la CNE, el OVSICORI y el SINAC sus términos.
8. **El polígono de la GAM.** Si se pide al INVU el polígono del plan o se arma la agrupación con cantones del COD-AB.
9. **Las capas solo de California.** Como el punto 7 de REGIONS.md.

## Compilación de prueba

El recuadro recomendado se compiló con `tools/build_region_map.py` de #80 sin cambios (commit `a453274`), a partir del
extracto de Geofabrik de arriba. El registro completo, las sumas de verificación y las capturas están en
[MAP-CR.md](MAP-CR.md); aquí van las cifras que importan para esta propuesta.

| | |
|---|---|
| Fuente | `costa-rica-latest.osm.pbf`, 39.192.879 bytes, MD5 `f046e22921a2e1837a3bde4e8c00e3a0` (coincide con el de Geofabrik), datos de OSM hasta 2026-11-17T21:24:30Z |
| Recuadro | -86,11, 7,89, -82,40, 11,37 (el recuadro continental con margen) |
| Compilado | 18 de noviembre de 2026, Ubuntu 24.04, Python 3.12.3, pyosmium 4.3.2 |
| Tiempo y memoria | 25 segundos, 0,78 GB de memoria residente máxima |
| Conjunto de mapa | 99.123.261 bytes: `national.sqlite` 95,3 MB, `places.sqlite` 3,7 MB |
| Mismos bytes dos veces | dos compilaciones dieron el mismo SHA-256 en los cinco archivos |

Qué contiene: 163.431 vías (78.843 con nombre o número), 202.360 contornos de edificios, 15.221 ríos y quebradas,
28.892 áreas de uso del suelo, 1.541 cuerpos de agua, 516 humedales, 356 playas, 275 líneas de tren y 8.847 etiquetas
de lugares. Puntos de ayuda: 22.246 en 40 clases, entre ellos 119 hospitales, 1.152 clínicas, 424 consultorios, 714
farmacias, 690 puestos de policía, 79 estaciones de bomberos, 441 gasolineras, 1.345 supermercados, 2.442 minisúper,
4.441 escuelas y 241 refugios. El buscador de lugares tiene 27.435 filas.

`tools/check_region_map.py` pasó todas las pruebas de archivos y, con `--engine` y toda conexión bloqueada, todas las del
motor: teselas en zoom 10, 13 y 16 en San José, pines, ayuda más cercana y búsqueda de "Calderón Guardia", "Hospital
México", "Cartago" y "Liberia". El motor informa que el mapa abarca -85,91, 8,09, -82,54, 11,22, así que el extracto
casi no trajo nada de Nicaragua ni de Panamá: en la práctica, el borde de una primera compilación es la frontera.

Lo que la compilación muestra para esta propuesta:

- **El país entero es pequeño.** 25 segundos y 99 MB para todo. Dividir por provincia no ahorra tamaño, lo que apoya
  una sola región `CR` (punto 3 de arriba).
- **Refugios.** Los 241 puntos `shelter` son lo que queda de `amenity=shelter` después de que #80 descarta las paradas
  de bus: sobre todo techos abiertos, ranchos de picnic y glorietas (ver "Shelter" en OSM arriba). Mostrados como
  "Refugio" en un mapa de emergencia prometen más de lo que son. No es un problema solo de Costa Rica.
- **La Isla del Coco queda fuera.** El recorte por recuadro la descarta, como se propone.
- **Lo que todavía supone Estados Unidos** (visto en la interfaz, en claro y oscuro): el mapa abre sobre Estados Unidos
  y tiene un botón "US"; la búsqueda dice "address, town or ZIP"; la vista amplia da distancias en millas; la línea de
  créditos nombra USGS, USDA, NOAA, USACE, CDFW y CalGEM, y ninguno de sus datos está en este mapa. Son los mismos puntos
  que MAPS.md enumera en "What is tied to the United States".

## Qué se verificó

- Abiertas el 18 de noviembre de 2026: la página de Costa Rica de Geofabrik (tamaños, fecha de los datos) y
  `costa-rica.poly`; el registro del COD-AB de OCHA para Costa Rica por la API de HDX (licencia, fuente, fechas, archivos,
  advertencias); la guía de direcciones de Overture (41 países, sin Costa Rica), su página de lugares (conteos por fuente,
  ninguno por país) y su página de edificios (fuentes, ODbL); el README de GlobalMLBuildingFootprints de Microsoft (CDLA
  Permissive 2.0, organización por país y quadkey) y `dataset-links.csv`; las páginas del registro de datos abiertos de
  AWS para Copernicus DEM GLO-30 y ESA WorldCover (licencias); el resumen de la CIJ de la sentencia de 2015; el artículo de
  La Nación de 2009 sobre el código postal y su columna de 1997 sobre direcciones; la página de Wikipedia sobre códigos
  postales; la página de inicio del SNIT (línea de derechos, sin descarga); `datos.go.cr`; la página de inicio del
  OVSICORI (línea de derechos); `engine/address_search.py` y `tools/build_addresses.py`.
- Descargadas y calculadas el 18 de noviembre de 2026: el GeoJSON del COD-AB de OCHA (niveles 0 y 1 para los rectángulos,
  con y sin la Isla del Coco; niveles 0 a 3 para conteos y áreas); `costa-rica-latest.osm.pbf` de Geofabrik (los conteos
  de OSM); las 21 teselas de Costa Rica de Microsoft (conteo de filas).
- Solo búsqueda: los códigos ISO 3166-2:CR (conocimiento general en la tabla, no se buscaron), la sentencia de 2018 de la
  CIJ, la aprobación del plan GAM, los números de decreto, los conteos de cantones y distritos y la lista parcial, el
  atlas del TEC, el geoportal de la CNE y sus servicios OGC, las licencias de informes del OVSICORI, el conteo de áreas
  protegidas del SINAC, las capas del IGN, los proyectos de direcciones y calles de 2005 y 2012, y las cifras de códigos
  postales de Wikipedia y La Nación (492 y 487).
- Conocimiento general, para que lo confirme alguien del país: el área oficial del país, el área de West Virginia, dónde
  vive la gente, quién vive en la Isla del Coco, qué vecinos caen en el rectángulo, los pueblos fronterizos, la cantidad de
  volcanes activos, el idioma oficial, la cobertura de bosque.
- Sin verificar: el sitio de ISO, las páginas y la consulta de Correos de Costa Rica, los sitios del MEP y del Ministerio
  de Salud, `geoportal-saracc.cne.go.cr`, `www.cne.go.cr`, `www.sinac.go.cr`, la lista de servicios del SNIT, las páginas
  de descarga del OVSICORI, el sitio del INVU, cualquier polígono del Plan GAM, cuánta tierra vecina trae el rectángulo o el
  extracto, si el borde del distrito Colorado del COD-AB sigue la línea de 2018, la ubicación de la tesela más grande de
  Microsoft, la parte de Costa Rica en los edificios o lugares de Overture, la exactitud de las huellas de Microsoft y la
  cobertura de fuentes.
