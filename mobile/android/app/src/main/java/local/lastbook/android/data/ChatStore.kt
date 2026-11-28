package local.lastbook.android.data

import android.content.Context
import local.lastbook.core.LastbookCore
import local.lastbook.core.Rec
import local.lastbook.core.d
import local.lastbook.core.i
import local.lastbook.core.s
import local.lastbook.core.str
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class ChatSource(
    val key: String, val kind: String, val docId: String, val title: String,
    val publisher: String = "", val page: Int? = null, val t: Double? = null, val excerpt: String? = null,
) {
    val where: String
        get() = when {
            kind == "video" && t != null -> "at ${clock(t)}"
            kind == "video" -> "video"
            page != null -> "page $page"
            else -> ""
        }
    companion object {
        fun from(r: Rec) = ChatSource(
            r.s("key"), r.s("kind"), r.s("doc_id").ifEmpty { r.s("id") }, r.s("title"), r.s("publisher"),
            (r["page"] as? Number)?.toInt(), (r["t"] as? Number)?.toDouble(), r.str("excerpt"),
        )
        fun clock(t: Double): String {
            val s = t.toInt(); return "%d:%02d".format(s / 60, s % 60)
        }
    }
}

class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: String,
    content: String = "",
    sources: List<ChatSource> = emptyList(),
    fallback: List<ChatSource> = emptyList(),
    error: String? = null,
    running: Boolean = false,
    phase: String? = null,
) {
    var content by mutableStateOf(content)
    var sources by mutableStateOf(sources)
    var fallback by mutableStateOf(fallback)
    var error by mutableStateOf(error)
    var running by mutableStateOf(running)
    var phase by mutableStateOf(phase)
}

data class Conversation(
    val id: String = UUID.randomUUID().toString(),
    var title: String,
    var updated: Long = System.currentTimeMillis(),
    val messages: MutableList<ChatMessage> = mutableStateListOf(),
    var about: String? = null,
    var aboutLabel: String? = null,
)

class ChatStore(private val context: Context) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    var revision by mutableIntStateOf(0)
        private set
    private val prefs = context.getSharedPreferences("lastbook", Context.MODE_PRIVATE)
    private val dir = File(context.filesDir, "Chats").apply { mkdirs() }
    private val file = File(dir, "chats.json")

    var keep: Boolean
        get() = prefs.getBoolean("keepChats", true)
        set(value) {
            prefs.edit().putBoolean("keepChats", value).apply()
            if (value) persist() else file.delete()
        }

    val chats = ArrayList<Conversation>()
    var current: Conversation? = null
    var pendingAbout: String? = null
    var pendingAboutLabel: String? = null
    var status: Rec = LastbookCore.chat.status()
    @Volatile private var inFlight = false

    init { load() }

    private fun load() {
        chats.clear()
        if (!keep || !file.isFile) return
        runCatching {
            val a = JSONArray(file.readText())
            for (i in 0 until a.length()) {
                val o = a.optJSONObject(i) ?: continue
                val c = Conversation(o.optString("id"), o.optString("title"), o.optLong("updated"))
                c.about = if (o.has("about") && !o.isNull("about")) o.optString("about").takeIf { it.isNotEmpty() } else null
                c.aboutLabel = if (o.has("aboutLabel") && !o.isNull("aboutLabel")) o.optString("aboutLabel").takeIf { it.isNotEmpty() } else null
                val ms = o.optJSONArray("messages") ?: JSONArray()
                for (j in 0 until ms.length()) {
                    val m = ms.optJSONObject(j) ?: continue
                    val msg = ChatMessage(m.optString("id"), m.optString("role"), m.optString("content"))
                    msg.error = m.optString("error").takeIf { it.isNotEmpty() }
                    msg.sources = sourcesFrom(m.optJSONArray("sources"))
                    msg.fallback = sourcesFrom(m.optJSONArray("fallback"))
                    c.messages += msg
                }
                chats += c
            }
        }
    }

    private fun sourcesFrom(a: JSONArray?): List<ChatSource> {
        if (a == null) return emptyList()
        return (0 until a.length()).mapNotNull { i ->
            a.optJSONObject(i)?.let { o ->
                ChatSource(
                    o.optString("key"), o.optString("kind"), o.optString("docId"), o.optString("title"),
                    o.optString("publisher"), if (o.has("page") && !o.isNull("page")) o.optInt("page") else null,
                    if (o.has("t") && !o.isNull("t")) o.optDouble("t") else null,
                    o.optString("excerpt").takeIf { it.isNotEmpty() },
                )
            }
        }
    }

    private fun sourcesTo(list: List<ChatSource>): JSONArray = JSONArray().apply {
        for (s in list) put(JSONObject().apply {
            put("key", s.key); put("kind", s.kind); put("docId", s.docId); put("title", s.title); put("publisher", s.publisher)
            put("page", s.page ?: JSONObject.NULL); put("t", s.t ?: JSONObject.NULL); put("excerpt", s.excerpt ?: JSONObject.NULL)
        })
    }

    fun persist() {
        if (!keep) return
        runCatching {
            val a = JSONArray()
            for (c in chats.take(100)) {
                val o = JSONObject()
                o.put("id", c.id); o.put("title", c.title); o.put("updated", c.updated)
                o.put("about", c.about ?: JSONObject.NULL); o.put("aboutLabel", c.aboutLabel ?: JSONObject.NULL)
                val ms = JSONArray()
                for (m in c.messages) {
                    val mo = JSONObject()
                    mo.put("id", m.id); mo.put("role", m.role); mo.put("content", m.content)
                    mo.put("error", m.error ?: JSONObject.NULL); mo.put("sources", sourcesTo(m.sources)); mo.put("fallback", sourcesTo(m.fallback))
                    ms.put(mo)
                }
                o.put("messages", ms)
                a.put(o)
            }
            file.writeText(a.toString())
        }
    }

    fun newChat() {
        current = null
        pendingAbout = null
        pendingAboutLabel = null
        revision++
    }

    fun open(c: Conversation) { current = c }

    fun delete(c: Conversation) {
        chats.remove(c)
        if (current == c) current = null
        persist()
    }

    fun deleteAll() {
        chats.clear(); current = null; persist()
    }

    fun refreshStatus() { status = LastbookCore.chat.status() }

    fun send(text: String) {
        val q = text.trim(); if (q.isEmpty()) return
        if (inFlight) return
        inFlight = true
        var c = current
        if (c == null) {
            c = Conversation(title = q.take(70))
            c.about = pendingAbout; c.aboutLabel = pendingAboutLabel
            chats.add(0, c); current = c
        }
        c.messages += ChatMessage(role = "user", content = q)
        val reply = ChatMessage(role = "assistant", running = true, phase = "searching")
        c.messages += reply
        c.updated = System.currentTimeMillis()
        pendingAbout = null; pendingAboutLabel = null
        // Show the user's question and a typing indicator at once; retrieval and model checks run off the main thread.
        revision++
        val conv = c
        val about = conv.about
        val original = q
        scope.launch {
            try {
                val st = withContext(Dispatchers.IO) { LastbookCore.chat.status() }
                // Resolve "Ask about this" into the real page or transcript text, not just search words.
                val aboutRec = about?.let { marker ->
                    withContext(Dispatchers.IO) { runCatching { LastbookCore.chat.contextFor(marker) }.getOrNull() }
                }
                val searchText = if (aboutRec != null) "$original ${aboutRec.str("excerpt").orEmpty()}" else original
                val found = withContext(Dispatchers.IO) {
                    runCatching { LastbookCore.chat.sources(searchText, 8) }.getOrDefault(emptyList())
                }
                // Keep source keys aligned with the prompt's [S1], [S2]… labels, with the asked-about item first.
                val sourceRecs = (if (aboutRec != null) listOf(aboutRec) + found else found)
                    .mapIndexed { i, r -> r + mapOf("key" to "S${i + 1}") }
                val sources = sourceRecs.map { ChatSource.from(it) }
                val can = withContext(Dispatchers.IO) { LastbookCore.chat.canGenerate() }
                withContext(Dispatchers.Main) {
                    status = st
                    reply.fallback = sources
                    if (!can) {
                        reply.running = false
                        reply.phase = null
                        reply.error = if (sources.isEmpty()) "The library has nothing on this question. Try fewer or different words."
                        else "No written answer: the local AI is not installed, so these library pages match your question."
                        persist(); revision++
                    } else {
                        reply.phase = "writing"; revision++
                    }
                }
                if (!can) return@launch
                scope.launch {
                    kotlinx.coroutines.delay(600_000)
                    if (reply.running) {
                        LastbookCore.chat.stop()
                        withContext(Dispatchers.Main) {
                            reply.running = false
                            reply.phase = null
                            reply.error = "The local AI is taking too long on this phone. These library pages match your question."
                            persist(); revision++
                        }
                    }
                }
                val answer = runCatching { LastbookCore.chat.generate(original, sourceRecs) }.getOrNull()
                withContext(Dispatchers.Main) {
                    reply.running = false
                    reply.phase = null
                    if (answer.isNullOrBlank()) {
                        reply.error = LastbookCore.chat.lastError()
                            ?: "The local AI could not write an answer. These library pages match your question."
                    } else {
                        reply.content = answer
                        reply.sources = sources.filter { answer.contains("[${it.key}]") }.ifEmpty { sources.take(3) }
                        reply.error = null
                    }
                    conv.updated = System.currentTimeMillis()
                    persist(); revision++
                }
            } finally {
                inFlight = false
            }
        }
    }

    fun stop() {
        LastbookCore.chat.stop()
        current?.messages?.lastOrNull { it.running }?.let { it.running = false; it.error = "Stopped." }
        persist(); revision++
    }
}
