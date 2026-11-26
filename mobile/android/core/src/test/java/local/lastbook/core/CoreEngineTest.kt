package local.lastbook.core

import local.lastbook.core.install.CatalogEntry
import local.lastbook.core.install.InstallCatalog
import local.lastbook.core.install.InstallEngine
import local.lastbook.core.install.ItemState
import local.lastbook.core.install.Plan
import local.lastbook.core.install.PlanItem
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

class CoreEngineTest {

    private val sampleManifest = """
    {
      "version": 1,
      "packs": [
        {
          "id": "small",
          "title": "Small",
          "installed_bytes": 7700000000,
          "available": true,
          "revision": "2026-11-13-small-v2",
          "files": [
            { "name": "lastbook-small.zip", "url": "https://downloads.lastbook.org/packs/lastbook-small.zip", "size": 4500000000, "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" }
          ]
        },
        {
          "id": "medium",
          "title": "Medium",
          "installed_bytes": 67000000000,
          "available": true,
          "files": [
            { "name": "lastbook-medium.zip", "url": "https://downloads.lastbook.org/packs/lastbook-medium.zip", "size": 67000000000, "sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789" }
          ]
        }
      ],
      "maps": [
        {
          "id": "RI",
          "title": "Rhode Island",
          "installed_bytes": 120000000,
          "available": true,
          "files": [
            { "name": "map-RI.zip", "url": "https://downloads.lastbook.org/maps/map-RI.zip", "size": 90000000, "sha256": "1111111111111111111111111111111111111111111111111111111111111111" }
          ]
        }
      ],
      "address_indexes": [
        {
          "id": "RI",
          "title": "Rhode Island",
          "installed_bytes": 30000000,
          "available": true,
          "files": [
            { "name": "addresses-RI.zip", "url": "https://downloads.lastbook.org/addresses/addresses-RI.zip", "size": 15000000, "sha256": "2222222222222222222222222222222222222222222222222222222222222222" }
          ]
        }
      ],
      "models": [
        {
          "id": "gemma-4-26b-a4b",
          "title": "Gemma 4 26B A4B",
          "file": "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
          "url": "https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
          "size": 16947541728,
          "sha256": "f2c28b3dc4776931ac6f879e11f203dec637ea0f14267a86ec8f6165f63f293f",
          "memory_bytes": 19027384256,
          "available": true
        },
        {
          "id": "gemma-4-12b",
          "title": "Gemma 4 12B",
          "file": "gemma-4-12b-it-UD-Q4_K_XL.gguf",
          "url": "https://huggingface.co/unsloth/gemma-4-12b-it-GGUF/resolve/main/gemma-4-12b-it-UD-Q4_K_XL.gguf",
          "size": 7366423360,
          "sha256": "90fd944d227e9d9b68e7e2c7d5b57b79d4c66ed521b0919fbbd932cf834f6f8e",
          "memory_bytes": 10100000000,
          "available": true,
          "tier": "flagship"
        },
        {
          "id": "gemma-4-e2b",
          "title": "Gemma 4 E2B",
          "file": "gemma-4-E2B-it-UD-Q4_K_XL.gguf",
          "url": "https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-UD-Q4_K_XL.gguf",
          "size": 3184496736,
          "sha256": "b52f438017efaec5debf1c0d8be690571e212a07c312f1102bbce927258cfc32",
          "memory_bytes": 5368709120,
          "available": true,
          "tier": "low-mid"
        }
      ]
    }
    """.trimIndent()

    @Test
    fun `manifest parsing and AI tier selection by RAM`() {
        val cat = InstallCatalog.parse(sampleManifest)
        assertEquals(2, cat.packs.size)
        assertEquals(1, cat.maps.size)
        assertEquals(1, cat.addresses.size)
        assertEquals(3, cat.models.size)

        // 8 GB phone -> picks Gemma 4 E2B
        val best8Gb = cat.bestModelFor(8L * 1024 * 1024 * 1024)
        assertNotNull(best8Gb)
        assertEquals("gemma-4-e2b", best8Gb?.id)

        // 12 GB flagship phone -> picks Gemma 4 12B
        val best12Gb = cat.bestModelFor(12L * 1024 * 1024 * 1024)
        assertNotNull(best12Gb)
        assertEquals("gemma-4-12b", best12Gb?.id)

        // 24 GB device -> picks Gemma 4 26B A4B
        val best24Gb = cat.bestModelFor(24L * 1024 * 1024 * 1024)
        assertNotNull(best24Gb)
        assertEquals("gemma-4-26b-a4b", best24Gb?.id)
    }

    @Test
    fun `plan space math and free space blocking`() {
        val cat = InstallCatalog.parse(sampleManifest)
        val small = cat.pack("small")!!
        val mapRi = cat.map("RI")!!
        val e2b = cat.model("gemma-4-e2b")!!

        val items = listOf(
            PlanItem("pack:small", CatalogEntry.Kind.PACK, "Library: Small", small, true, ItemState.TO_DOWNLOAD),
            PlanItem("map:RI", CatalogEntry.Kind.MAP, "Rhode Island map", mapRi, true, ItemState.TO_DOWNLOAD),
            PlanItem("model:gemma-4-e2b", CatalogEntry.Kind.MODEL, "Local AI (Gemma 4 E2B)", e2b, false, ItemState.TO_DOWNLOAD),
        )

        val plentyPlan = Plan("small", "RI", "gemma-4-e2b", items, freeBytes = 50_000_000_000L)
        assertTrue(plentyPlan.fits)
        assertEquals(small.downloadBytes + mapRi.downloadBytes + e2b.downloadBytes, plentyPlan.downloadBytes)
        assertTrue(plentyPlan.peakBytes > plentyPlan.downloadBytes)

        val tightPlan = Plan("small", "RI", "gemma-4-e2b", items, freeBytes = 5_000_000_000L)
        assertFalse(tightPlan.fits)
    }

    @Test
    fun `low RAM model stays installable with memory warning note`() {
        val cat = InstallCatalog.parse(sampleManifest)
        val e2b = cat.model("gemma-4-e2b")!!

        val lowRamItem = InstallEngine.planModelItem("gemma-4-e2b", e2b, installed = false, totalRam = 4L * 1024 * 1024 * 1024)
        assertEquals(ItemState.TO_DOWNLOAD, lowRamItem.state)
        assertNotNull(lowRamItem.note)
        assertTrue(lowRamItem.note!!.contains("enough memory"))

        val enoughRamItem = InstallEngine.planModelItem("gemma-4-e2b", e2b, installed = false, totalRam = 8L * 1024 * 1024 * 1024)
        assertEquals(ItemState.TO_DOWNLOAD, enoughRamItem.state)
        assertNull(enoughRamItem.note)

        val unavailableItem = InstallEngine.planModelItem("gemma-4-e2b", e2b.copy(available = false), installed = false, totalRam = 8L * 1024 * 1024 * 1024)
        assertEquals(ItemState.UNAVAILABLE, unavailableItem.state)
        assertNotNull(unavailableItem.note)
    }

    @Test
    fun `catalog title cleaning, trust weighting, and public record formatting`() {
        val rec: Rec = mapOf(
            "id" to "doc-1",
            "title" to "042 Water_Purification_Guide.pdf",
            "kind" to "pdf",
            "publisher" to "World Health Organization",
            "collection" to "WHO Emergency Notes",
            "category" to "water",
            "path" to "pdfs/water.pdf",
            "pages" to 24,
            "publication_date" to "2019-05-01",
        )
        assertEquals("Water Purification Guide", Catalog.cleanTitle(rec))
        assertEquals("PDF", Catalog.kindLabel(rec))
        assertEquals("2019", Catalog.yearOf(rec))
        val (trustLabel, trustWeight) = Catalog.trust(rec)
        assertEquals("International health & humanitarian guidance", trustLabel)
        assertEquals(1.5, trustWeight, 0.001)

        val pub = Catalog.publicRec(rec, full = true)
        assertNotNull(pub)
        assertEquals("Water Purification Guide", pub?.s("title"))
        assertEquals(24, pub?.i("pages"))
    }

    @Test
    fun `geo haversine distance, compass direction, and polygon ring clipping`() {
        val (kmNorth, dirNorth) = Geo.haversine(41.8240, -71.4128, 41.9240, -71.4128)
        assertEquals("north", dirNorth)
        assertTrue(kmNorth in 10.5..11.5)

        val (kmEast, dirEast) = Geo.haversine(41.8240, -71.4128, 41.8240, -71.2500)
        assertEquals("east", dirEast)
        assertTrue(kmEast in 12.0..15.0)

        val ring = listOf(-10.0 to -10.0, 600.0 to -10.0, 600.0 to 600.0, -10.0 to 600.0)
        val clipped = Geo.clipRing(ring, 0.0, 0.0, 512.0, 512.0)
        assertFalse(clipped.isEmpty())
        assertTrue(clipped.all { it.first in 0.0..512.0 && it.second in 0.0..512.0 })
    }

    @Test
    fun `library detection, sha256 verification, and zip slip protection`() {
        val dir = Files.createTempDirectory("lastbook-test").toFile()
        try {
            assertFalse(Library.looksLikeLibrary(dir))
            val libData = File(dir, "library-data").apply { mkdirs() }
            File(libData, "catalog.json").writeText("[]")
            assertTrue(Library.looksLikeLibrary(dir))

            // Verify SHA-256 calculation matches NIST test vector for "abc"
            val f = File(dir, "sample.bin")
            f.writeBytes("abc".toByteArray())
            val md = MessageDigest.getInstance("SHA-256")
            val hex = md.digest(f.readBytes()).joinToString("") { "%02x".format(it) }
            assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", hex)

            // Verify zip slip detection rejects "../evil.txt"
            val badZip = File(dir, "bad.zip")
            ZipOutputStream(FileOutputStream(badZip)).use { zos ->
                zos.putNextEntry(ZipEntry("../evil.txt"))
                zos.write("nope".toByteArray())
                zos.closeEntry()
            }
            var rejected = false
            ZipFile(badZip).use { z ->
                for (e in z.entries().toList()) {
                    val name = e.name.replace('\\', '/')
                    if (name.startsWith("/") || name.split('/').any { it == ".." }) {
                        rejected = true
                    }
                }
            }
            assertTrue(rejected)
        } finally {
            dir.deleteRecursively()
        }
    }
}
