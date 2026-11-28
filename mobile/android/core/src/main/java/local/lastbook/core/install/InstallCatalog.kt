package local.lastbook.core.install

import android.content.Context
import local.lastbook.core.Rec
import local.lastbook.core.arr
import local.lastbook.core.d
import local.lastbook.core.i
import local.lastbook.core.l
import local.lastbook.core.s
import local.lastbook.core.str
import local.lastbook.core.toStringMap
import local.lastbook.core.truthy
import org.json.JSONObject

data class CatalogFile(val name: String, val url: String, val size: Long, val sha256: String, val kind: String)

data class CatalogEntry(
    val kind: Kind,
    val id: String,
    val title: String,
    val installedBytes: Long,
    val available: Boolean,
    val revision: String?,
    val files: List<CatalogFile>,
    val memoryBytes: Long = 0,
    val tier: String = "",
) {
    enum class Kind { PACK, MAP, ADDRESSES, MODEL, VIDEO_COPIES }
    val downloadBytes: Long get() = files.sumOf { it.size }
}

/** The download manifest: the desktop/iPad list plus the two phone model tiers. */
class InstallCatalog private constructor(val entries: List<CatalogEntry>) {
    val packs = entries.filter { it.kind == CatalogEntry.Kind.PACK }
    val maps = entries.filter { it.kind == CatalogEntry.Kind.MAP }
    val addresses = entries.filter { it.kind == CatalogEntry.Kind.ADDRESSES }
    val models = entries.filter { it.kind == CatalogEntry.Kind.MODEL }

    fun entry(kind: CatalogEntry.Kind, id: String): CatalogEntry? = entries.firstOrNull { it.kind == kind && it.id == id }
    fun pack(id: String) = entry(CatalogEntry.Kind.PACK, id)
    fun map(id: String) = entry(CatalogEntry.Kind.MAP, id)
    fun address(id: String) = entry(CatalogEntry.Kind.ADDRESSES, id)
    fun model(id: String) = entry(CatalogEntry.Kind.MODEL, id)

    fun bestModelFor(totalRam: Long): CatalogEntry? = models
        .filter { it.available && it.memoryBytes > 0 && it.memoryBytes < totalRam }
        .maxByOrNull { it.memoryBytes }
        ?: models.filter { it.available }.minByOrNull { it.memoryBytes }

    companion object {
        fun load(context: Context): InstallCatalog {
            val text = context.assets.open("install-catalog.json").bufferedReader().use { it.readText() }
            return parse(text)
        }

        fun parse(text: String): InstallCatalog {
            val o = JSONObject(text)
            val out = ArrayList<CatalogEntry>()
            fun files(a: Any?): List<CatalogFile> = a.let { v ->
                (v as? org.json.JSONArray)?.let { arr ->
                    (0 until arr.length()).mapNotNull { i -> arr.optJSONObject(i)?.let { f ->
                        CatalogFile(f.optString("name"), f.optString("url"), f.optLong("size"), f.optString("sha256"), f.optString("kind", "file"))
                    } }
                } ?: emptyList()
            }
            o.optJSONArray("packs")?.let { a -> for (i in 0 until a.length()) a.optJSONObject(i)?.let { p ->
                out += CatalogEntry(CatalogEntry.Kind.PACK, p.optString("id"), p.optString("title"), p.optLong("installed_bytes"),
                    p.optBoolean("available", true), p.optString("revision").takeIf { it.isNotEmpty() }, files(p.opt("files")))
            } }
            o.optJSONArray("maps")?.let { a -> for (i in 0 until a.length()) a.optJSONObject(i)?.let { p ->
                out += CatalogEntry(CatalogEntry.Kind.MAP, p.optString("id"), p.optString("title"), p.optLong("installed_bytes"),
                    p.optBoolean("available", true), null, files(p.opt("files")))
            } }
            o.optJSONArray("address_indexes")?.let { a -> for (i in 0 until a.length()) a.optJSONObject(i)?.let { p ->
                out += CatalogEntry(CatalogEntry.Kind.ADDRESSES, p.optString("id"), p.optString("title"), p.optLong("installed_bytes"),
                    p.optBoolean("available", true), null, files(p.opt("files")))
            } }
            o.optJSONArray("models")?.let { a -> for (i in 0 until a.length()) a.optJSONObject(i)?.let { p ->
                val fs = files(p.opt("files")).ifEmpty {
                    listOf(CatalogFile(p.optString("file"), p.optString("url"), p.optLong("size"), p.optString("sha256"), "gguf"))
                }
                out += CatalogEntry(CatalogEntry.Kind.MODEL, p.optString("id"), p.optString("title"), p.optLong("size"),
                    p.optBoolean("available", true), null, fs, p.optLong("memory_bytes"), p.optString("tier"))
            } }
            return InstallCatalog(out)
        }
    }
}

enum class ItemState { INSTALLED, TO_DOWNLOAD, DOWNLOADING, CHECKING, UNPACKING, FINISHING, DONE, FAILED, UNAVAILABLE, OPTED_OUT }

data class PlanItem(
    val key: String,
    val kind: CatalogEntry.Kind,
    val title: String,
    val entry: CatalogEntry?,
    val required: Boolean,
    val state: ItemState = ItemState.TO_DOWNLOAD,
    val bytesDone: Long = 0,
    val note: String? = null,
) {
    val downloadBytes: Long get() = entry?.downloadBytes ?: 0
    val installedBytes: Long get() = entry?.installedBytes ?: 0
}

data class Plan(
    val packId: String,
    val stateId: String?,
    val modelId: String?,
    val items: List<PlanItem>,
    val freeBytes: Long,
) {
    val toDo: List<PlanItem> get() = items.filter { it.state == ItemState.TO_DOWNLOAD }
    val downloadBytes: Long get() = items.sumOf { if (it.state == ItemState.TO_DOWNLOAD) it.downloadBytes else 0 }
    val peakBytes: Long get() {
        var kept = 0L; var peak = 0L
        for (i in items) if (i.state == ItemState.TO_DOWNLOAD) { peak = maxOf(peak, kept + i.downloadBytes + i.installedBytes); kept += i.installedBytes }
        return if (peak == 0L) 0 else peak + 2_000_000_000L
    }
    val fits: Boolean get() = peakBytes <= freeBytes
}
