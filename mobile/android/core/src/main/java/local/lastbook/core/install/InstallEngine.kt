package local.lastbook.core.install

import android.content.Context
import local.lastbook.core.LastbookPaths
import local.lastbook.core.Library
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import java.util.zip.ZipFile
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

data class InstallProgress(
    val itemKey: String,
    val itemTitle: String,
    val state: ItemState,
    val itemDone: Long,
    val itemTotal: Long,
    val overallDone: Long,
    val overallTotal: Long,
    val message: String = "",
    val error: String? = null,
)

class InstallEngine(
    private val context: Context,
    private val paths: LastbookPaths,
    private val library: Library,
    private val catalog: InstallCatalog,
) {
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.MINUTES)
        .followRedirects(true)
        .build()

    fun installedPack(root: File? = library.root): String? = root?.resolve("pack.json")?.let { f ->
        runCatching { JSONObject(f.readText()).optString("name").takeIf { it.isNotEmpty() } }.getOrNull()
    }

    fun installedMap(root: File? = library.root): String? = root?.resolve("map-set.json")?.let { f ->
        runCatching { JSONObject(f.readText()).optString("name").takeIf { it.isNotEmpty() } }.getOrNull()
    } ?: root?.resolve("pack.json")?.let { f -> runCatching { JSONObject(f.readText()).optString("map").takeIf { it.isNotEmpty() } }.getOrNull() }

    fun addressInstalled(id: String, root: File? = library.root): Boolean {
        val e = catalog.address(id) ?: return false
        val f = root?.resolve("derived/geo/addresses/$id.sqlite") ?: return false
        return f.isFile && f.length() == e.installedBytes
    }

    fun modelInstalled(entry: CatalogEntry, root: File? = library.root): Boolean {
        val name = entry.files.firstOrNull()?.name ?: return false
        val f = root?.resolve("models/$name") ?: return false
        return f.isFile && f.length() == entry.files.first().size
    }

    fun plan(packId: String, stateId: String?, wantAI: Boolean, modelId: String?): Plan {
        val root = library.root
        val hasLib = root != null && Library.looksLikeLibrary(root)
        val currentPack = installedPack(root)
        val currentMap = installedMap(root)
        val free = (root?.parentFile ?: paths.defaultRoot.parentFile ?: context.filesDir).usableSpace
        val totalRam = totalMemory()
        val items = ArrayList<PlanItem>()

        val pack = catalog.pack(packId)
        val packState = when {
            !hasLib -> ItemState.TO_DOWNLOAD
            currentPack == packId -> ItemState.INSTALLED
            else -> ItemState.TO_DOWNLOAD
        }
        items += PlanItem("pack:$packId", CatalogEntry.Kind.PACK, "Library: ${pack?.title ?: packId}", pack, true,
            packState, note = if (packState == ItemState.TO_DOWNLOAD && hasLib) "Replaces the ${currentPack ?: "current"} library; the old one is kept." else null)

        if (stateId != null) {
            val map = catalog.map(stateId)
            val mapState = if (hasLib && currentMap == stateId) ItemState.INSTALLED
                else if (map?.available == true) ItemState.TO_DOWNLOAD else ItemState.UNAVAILABLE
            items += PlanItem("map:$stateId", CatalogEntry.Kind.MAP, "${map?.title ?: stateId} map", map, true, mapState,
                note = if (mapState == ItemState.UNAVAILABLE) "The ${map?.title ?: stateId} map is not on the download site yet." else null)
            val addr = catalog.address(stateId)
            val addrState = if (hasLib && addressInstalled(stateId, root)) ItemState.INSTALLED
                else if (addr?.available == true) ItemState.TO_DOWNLOAD else ItemState.UNAVAILABLE
            items += PlanItem("addresses:$stateId", CatalogEntry.Kind.ADDRESSES, "${addr?.title ?: stateId} street addresses", addr, true, addrState,
                note = if (addrState == ItemState.UNAVAILABLE) "Street addresses are not published yet; town, ZIP and place search still work." else null)
        }

        if (modelId != null && wantAI) {
            val model = catalog.model(modelId)
            val fitsRam = model != null && model.memoryBytes < totalRam
            val st = when {
                model == null -> ItemState.UNAVAILABLE
                hasLib && modelInstalled(model, root) -> ItemState.INSTALLED
                !fitsRam -> ItemState.UNAVAILABLE
                model.available -> ItemState.TO_DOWNLOAD
                else -> ItemState.UNAVAILABLE
            }
            items += PlanItem("model:${modelId}", CatalogEntry.Kind.MODEL, "Local AI (${model?.title ?: modelId})", model, false, st,
                note = if (!fitsRam) "This device may not have enough memory; you can still install it and Lastbook will check the fit." else null)
        } else {
            items += PlanItem("model:none", CatalogEntry.Kind.MODEL, "Local AI", null, false, ItemState.OPTED_OUT)
        }
        return Plan(packId, stateId, if (wantAI) modelId else null, items, free)
    }

    private fun totalMemory(): Long = runCatching {
        val f = File("/proc/meminfo")
        f.readLines().firstOrNull { it.startsWith("MemTotal:") }?.split(Regex("\\s+"))?.getOrNull(1)?.toLong()?.times(1024)
            ?: Runtime.getRuntime().maxMemory()
    }.getOrDefault(Runtime.getRuntime().maxMemory())

    suspend fun run(plan: Plan, onProgress: (InstallProgress) -> Unit, isCancelled: () -> Boolean = { false }) = withContext(Dispatchers.IO) {
        val items = plan.items.filter { it.state == ItemState.TO_DOWNLOAD }
        val overallTotal = items.sumOf { it.downloadBytes }
        var overallDone = 0L
        val work = paths.workDir().apply { mkdirs() }
        val downloads = File(work, "downloads").apply { mkdirs() }

        for (item in items) {
            if (isCancelled()) throw CancellationException("cancelled")
            val entry = item.entry ?: continue
            var itemDone = 0L
            fun emit(state: ItemState, msg: String = "", error: String? = null) = onProgress(
                InstallProgress(item.key, item.title, state, itemDone, item.downloadBytes, overallDone, overallTotal, msg, error))

            try {
                emit(ItemState.DOWNLOADING, "Starting…")
                val dests = ArrayList<File>()
                for ((idx, file) in entry.files.withIndex()) {
                    val dest = when (entry.kind) {
                        CatalogEntry.Kind.MODEL -> File(work, "downloads/${file.name}")
                        else -> File(downloads, file.name)
                    }
                    download(file, dest,
                        onBytes = { done, _ ->
                            itemDone = entry.files.take(idx).sumOf { it.size } + done
                            emit(ItemState.DOWNLOADING)
                        },
                        isCancelled = isCancelled)
                    emit(ItemState.CHECKING, "Checking the download")
                    verify(file, dest)
                    dests += dest
                }
                itemDone = item.downloadBytes
                emit(ItemState.CHECKING, "Checked")
                when (entry.kind) {
                    CatalogEntry.Kind.PACK -> {
                        emit(ItemState.UNPACKING, "Unpacking the library")
                        val newLib = installPack(dests.first(), work)
                        emit(ItemState.FINISHING, "Putting the library in place")
                        activatePack(newLib)
                    }
                    CatalogEntry.Kind.MAP -> {
                        emit(ItemState.UNPACKING, "Unpacking the map")
                        installMap(dests.first(), entry.id)
                    }
                    CatalogEntry.Kind.ADDRESSES -> {
                        emit(ItemState.UNPACKING, "Unpacking street addresses")
                        installAddresses(dests.first(), entry.id)
                    }
                    CatalogEntry.Kind.MODEL -> {
                        emit(ItemState.FINISHING, "Adding the local AI")
                        installModel(dests.first(), entry)
                    }
                    CatalogEntry.Kind.VIDEO_COPIES -> Unit
                }
                overallDone += item.downloadBytes
                emit(ItemState.DONE, "Done")
                dests.forEach { runCatching { it.delete() } }
            } catch (e: CancellationException) {
                emit(ItemState.TO_DOWNLOAD, "Paused")
                throw e
            } catch (e: Exception) {
                emit(ItemState.FAILED, e.message ?: "Install failed", e.message ?: "Install failed")
                throw e
            }
        }
        library.locate()
    }

    private fun download(file: CatalogFile, dest: File, onBytes: (Long, Long) -> Unit, isCancelled: () -> Boolean) {
        dest.parentFile?.mkdirs()
        val part = File(dest.path + ".part")
        if (dest.isFile && dest.length() == file.size) { onBytes(file.size, file.size); return }
        var have = if (part.isFile) part.length() else 0L
        val builder = Request.Builder().url(file.url).header("Accept-Encoding", "identity")
        if (have > 0) builder.header("Range", "bytes=$have-")
        val response = http.newCall(builder.build()).execute()
        response.use { r ->
            if (!r.isSuccessful) throw IllegalStateException("The download server answered ${r.code}.")
            val body = r.body ?: throw IllegalStateException("The download had no content.")
            val append = have > 0 && r.code == 206
            if (!append) have = 0
            FileOutputStream(part, append).use { out ->
                val buf = ByteArray(256 * 1024)
                body.byteStream().use { input ->
                    while (true) {
                        if (isCancelled()) throw CancellationException("cancelled")
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        have += n
                        onBytes(have, file.size)
                    }
                }
            }
        }
        if (part.length() != file.size) throw IllegalStateException("The download stopped early.")
        if (!part.renameTo(dest)) throw IllegalStateException("Could not put the download in place.")
    }

    private fun verify(file: CatalogFile, path: File) {
        val actual = sha256(path)
        if (!actual.equals(file.sha256, ignoreCase = true)) {
            path.delete()
            throw IllegalStateException("The file is not the one Lastbook published (its SHA-256 differs). Try again.")
        }
    }

    fun sha256(path: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        path.inputStream().use { input ->
            val buf = ByteArray(256 * 1024)
            while (true) { val n = input.read(buf); if (n < 0) break; md.update(buf, 0, n) }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }

    private fun safeEntries(zip: ZipFile): List<java.util.zip.ZipEntry> = zip.entries().toList().filter { !it.isDirectory }.onEach { e ->
        val name = e.name.replace('\\', '/')
        if (name.startsWith("/") || name.split('/').any { it == ".." }) throw IllegalStateException("The zip holds an unsafe path.")
    }

    private fun installPack(zipFile: File, work: File): File {
        val out = File(work, "unpack/LastbookData")
        out.deleteRecursively(); out.mkdirs()
        ZipFile(zipFile).use { z ->
            for (e in safeEntries(z)) {
                var rel = e.name.replace('\\', '/')
                if (rel.startsWith("LastbookData/")) rel = rel.removePrefix("LastbookData/")
                if (rel.isEmpty()) continue
                val f = File(out, rel)
                if (!f.canonicalPath.startsWith(out.canonicalPath + File.separator)) throw IllegalStateException("The zip escapes its folder.")
                f.parentFile?.mkdirs()
                z.getInputStream(e).use { input -> FileOutputStream(f).use { input.copyTo(it) } }
            }
        }
        if (!Library.looksLikeLibrary(out)) throw IllegalStateException("The unpacked library has no catalog in it.")
        return out
    }

    private fun activatePack(newLib: File) {
        val target = library.root ?: paths.defaultRoot
        target.parentFile?.mkdirs()
        var old: File? = null
        if (target.exists()) {
            val stamp = java.text.SimpleDateFormat("yyyyMMdd-HHmmss", java.util.Locale.US).format(java.util.Date())
            old = File(target.parentFile, "${target.name}.old-$stamp")
            if (!target.renameTo(old)) throw IllegalStateException("Could not move the old library aside.")
        }
        if (!newLib.renameTo(target)) {
            if (old != null) old.renameTo(target)
            throw IllegalStateException("Could not put the new library in place.")
        }
        // The person's models and address indexes move with them.
        old?.let { o ->
            File(o, "models").takeIf { it.isDirectory }?.listFiles()?.forEach { f ->
                val d = File(target, "models/${f.name}")
                if (f.isFile && !d.exists()) { d.parentFile?.mkdirs(); f.renameTo(d) }
            }
            File(o, "derived/geo/addresses").takeIf { it.isDirectory }?.listFiles()?.forEach { f ->
                val d = File(target, "derived/geo/addresses/${f.name}")
                if (f.isFile && !d.exists()) { d.parentFile?.mkdirs(); f.renameTo(d) }
            }
        }
        paths.root = target
        library.locate()
    }

    private fun installMap(zipFile: File, stateId: String) {
        val root = library.root ?: throw IllegalStateException("Install a library first.")
        val tmp = File(paths.workDir(), "unpack-map").apply { deleteRecursively(); mkdirs() }
        var mapSetName: String? = null
        ZipFile(zipFile).use { z ->
            for (e in safeEntries(z)) {
                var rel = e.name.replace('\\', '/')
                if (rel.startsWith("LastbookData/")) rel = rel.removePrefix("LastbookData/")
                if (rel.isEmpty()) continue
                val ok = rel == "map-set.json" || rel == "derived/geo/national-status.json" || rel == "derived/geo/socal-cells.json" ||
                    rel == "library-data/geography/resources/atlas.sqlite" ||
                    (rel.startsWith("derived/geo/") && rel.endsWith(".sqlite") &&
                        rel.removePrefix("derived/geo/").removeSuffix(".sqlite").matches(Regex("[A-Za-z0-9._-]+")))
                if (!ok) continue
                val f = File(tmp, rel); f.parentFile?.mkdirs()
                z.getInputStream(e).use { input -> FileOutputStream(f).use { input.copyTo(it) } }
                if (rel == "map-set.json") mapSetName = runCatching { JSONObject(f.readText()).optString("name") }.getOrNull()
            }
        }
        if (mapSetName == null) throw IllegalStateException("The map has no map-set.json in it.")
        if (stateId.isNotEmpty() && mapSetName != stateId) throw IllegalStateException("The map is $mapSetName, not $stateId.")
        val set = runCatching { JSONObject(File(tmp, "map-set.json").readText()) }.getOrNull() ?: throw IllegalStateException("The map has no map-set.json.")
        val files = set.optJSONObject("files") ?: JSONObject()
        for (rel in files.keys()) {
            val src = File(tmp, rel); if (!src.isFile) continue
            val dst = File(root, rel); dst.parentFile?.mkdirs()
            src.copyTo(dst, overwrite = true)
        }
        files.keys().asSequence().forEach { }
        File(root, "map-set.json").writeText(File(tmp, "map-set.json").readText())
        // Remove the SQLite side files of the map being replaced.
        root.resolve("derived/geo").listFiles()?.filter { it.name.endsWith(".sqlite-wal") || it.name.endsWith(".sqlite-shm") }?.forEach { it.delete() }
        tmp.deleteRecursively()
        library.locate()
    }

    private fun installAddresses(zipFile: File, stateId: String) {
        val root = library.root ?: throw IllegalStateException("Install a library first.")
        val tmp = File(paths.workDir(), "unpack-addresses").apply { deleteRecursively(); mkdirs() }
        val rel = "derived/geo/addresses/$stateId.sqlite"
        var found: File? = null
        ZipFile(zipFile).use { z ->
            for (e in safeEntries(z)) {
                var r = e.name.replace('\\', '/')
                if (r.startsWith("LastbookData/")) r = r.removePrefix("LastbookData/")
                if (r != rel) continue
                val f = File(tmp, r); f.parentFile?.mkdirs()
                z.getInputStream(e).use { input -> FileOutputStream(f).use { input.copyTo(it) } }
                found = f
            }
        }
        val src = found ?: throw IllegalStateException("The download has no address index for $stateId.")
        val dst = File(root, rel); dst.parentFile?.mkdirs()
        src.copyTo(dst, overwrite = true)
        val entry = catalog.address(stateId)
        File(root, "derived/geo/addresses/$stateId.json").writeText(JSONObject(mapOf(
            "files" to mapOf(entry?.files?.firstOrNull()?.name to entry?.files?.firstOrNull()?.sha256)
        )).toString())
        tmp.deleteRecursively()
    }

    private fun installModel(src: File, entry: CatalogEntry) {
        val root = library.root ?: throw IllegalStateException("Install a library first.")
        val name = entry.files.first().name
        val dst = File(root, "models/$name"); dst.parentFile?.mkdirs()
        src.copyTo(dst, overwrite = true)
    }
}
