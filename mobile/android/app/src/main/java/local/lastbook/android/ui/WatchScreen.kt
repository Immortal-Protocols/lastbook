package local.lastbook.android.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.PictureInPictureAlt
import android.app.PictureInPictureParams
import android.util.Rational
import android.view.WindowManager
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import local.lastbook.android.data.Services
import local.lastbook.core.LastbookCore
import local.lastbook.core.Rec
import local.lastbook.core.arr
import local.lastbook.core.d
import local.lastbook.core.s
import local.lastbook.core.str
import org.json.JSONObject
import java.io.File

private data class Cue(val t: Double?, val text: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WatchScreen(id: String, onBack: () -> Unit, onOpen: (String) -> Unit, onAsk: (String, String) -> Unit) {
    val context = LocalContext.current
    var doc by remember { mutableStateOf<Rec?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var cues by remember { mutableStateOf<List<Cue>>(emptyList()) }
    var txNote by remember { mutableStateOf<String?>(null) }
    var related by remember { mutableStateOf<List<VideoItem>>(emptyList()) }
    var tab by remember { mutableIntStateOf(0) }
    var find by remember { mutableStateOf("") }
    var currentTime by remember { mutableDoubleStateOf(0.0) }
    var player by remember { mutableStateOf<ExoPlayer?>(null) }
    var askedResume by remember { mutableStateOf(false) }
    var resumeAt by remember { mutableDoubleStateOf(0.0) }

    DisposableEffect(Unit) {
        val p = ExoPlayer.Builder(context).build()
        player = p
        onDispose { p.release(); player = null }
    }

    LaunchedEffect(id) {
        val d = withContext(Dispatchers.IO) { LastbookCore.videos.doc(id) }
        doc = d
        if (d == null) { error = "This video is not in the library."; return@LaunchedEffect }
        val f = withContext(Dispatchers.IO) { LastbookCore.videos.file(d.s("path")) }
        if (f == null || !f.isFile) { error = "This video's file isn't on this phone. The transcript still works." }
        else {
            val p = player ?: return@LaunchedEffect
            val saved = Services.progress.get(id)
            val start = saved.takeIf { it > 15 && (d.d("duration") <= 0 || it < d.d("duration") - 20) } ?: 0.0
            resumeAt = start
            p.setMediaItem(MediaItem.fromUri(f.toURI().toString()))
            p.prepare()
            if (start > 0) p.seekTo((start * 1000).toLong())
        }
        val tx = withContext(Dispatchers.IO) { LastbookCore.videos.transcript(id) }
        val raw = tx?.arr("cues") ?: emptyList()
        cues = raw.map { c -> Cue((c["t"] as? Number)?.toDouble(), c.s("text")) }
        txNote = tx?.str("notes")
        related = withContext(Dispatchers.IO) { LastbookCore.videos.related(id).map { VideoItem.from(it) } }
    }

    DisposableEffect(player) {
        val p = player
        val activity = context as? android.app.Activity
        fun keepOn(on: Boolean) {
            if (on) activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            else activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) = keepOn(isPlaying)
        }
        p?.addListener(listener)
        onDispose {
            p?.removeListener(listener)
            keepOn(false)
        }
    }

    LaunchedEffect(player) {
        while (true) {
            delay(3000)
            val p = player ?: continue
            if (p.isPlaying) {
                currentTime = p.currentPosition / 1000.0
                Services.progress.set(id, currentTime)
            }
        }
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text("Video", maxLines = 1, overflow = TextOverflow.Ellipsis) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } },
            actions = {
                val activity = context as? android.app.Activity
                if (activity != null) IconButton(onClick = {
                    runCatching {
                        activity.enterPictureInPictureMode(PictureInPictureParams.Builder()
                            .setAspectRatio(Rational(16, 9)).build())
                    }
                }) { Icon(Icons.Default.PictureInPictureAlt, "Picture in picture") }
                TextButton(onClick = { onAsk("video:$id:${currentTime.toInt()}", doc?.s("title") ?: "Video") }) { Text("Ask about this") }
            })
    }) { pad ->
        Column(Modifier.fillMaxSize().padding(pad).verticalScroll(rememberScrollState())) {
            Box(Modifier.fillMaxWidth().aspectRatio(16f / 9f).background(Color.Black), contentAlignment = Alignment.Center) {
                if (player != null) AndroidView(factory = { ctx ->
                    PlayerView(ctx).apply { this.player = player; useController = true; setShowBuffering(PlayerView.SHOW_BUFFERING_WHEN_PLAYING) }
                }, modifier = Modifier.fillMaxSize())
                error?.let { Text(it, color = Color.White, modifier = Modifier.padding(20.dp)) }
            }
            val d = doc
            if (d == null) Box(Modifier.fillMaxWidth().height(200.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            else Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(d.s("title"), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("${d.s("publisher")}${if (d.d("duration") > 0) " · ${durationText(d.d("duration"))}" else ""} · ${d.s("trust")}",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (resumeAt > 0 && currentTime < 1) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("You stopped at ${clock(resumeAt)}.", modifier = Modifier.weight(1f))
                        TextButton(onClick = { player?.seekTo(0) }) { Text("Start over") }
                        TextButton(onClick = { player?.seekTo((resumeAt * 1000).toLong()); player?.play() }) { Text("Resume") }
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    TabRow(selectedTabIndex = tab, modifier = Modifier.fillMaxWidth()) {
                        Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("Transcript") })
                        Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("Up next") })
                    }
                }
                if (tab == 0) {
                    if (cues.isEmpty()) Text("No transcript was saved for this video, so search and chat can't see what's said in it.",
                        style = MaterialTheme.typography.bodySmall)
                    else {
                        txNote?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        OutlinedTextField(value = find, onValueChange = { find = it }, modifier = Modifier.fillMaxWidth(),
                            singleLine = true, placeholder = { Text("Find words in the transcript") },
                            leadingIcon = { Icon(Icons.Default.Search, null) })
                        val shown = if (find.isBlank()) cues else cues.filter { it.text.contains(find, true) }
                        LazyColumn(Modifier.fillMaxWidth().height(420.dp)) {
                            items(shown.size) { i ->
                                val c = shown[i]
                                Row(Modifier.fillMaxWidth().clickable(enabled = c.t != null) {
                                    c.t?.let { player?.seekTo((it * 1000).toLong()); player?.play() }
                                }.padding(vertical = 8.dp), verticalAlignment = Alignment.Top) {
                                    Text(c.t?.let { clock(it) } ?: "", modifier = Modifier.width(52.dp),
                                        style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text(c.text, style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }
                } else {
                    if (related.isEmpty()) Text("No related videos in this library.")
                    for (v in related) {
                        Row(Modifier.fillMaxWidth().clickable { onOpen(v.id) }.padding(vertical = 8.dp), verticalAlignment = Alignment.Top) {
                            Box(Modifier.width(150.dp).aspectRatio(16f / 9f).background(MaterialTheme.colorScheme.surfaceVariant)) {
                                v.thumb?.let { t -> LastbookCore.library.lib?.resolve(t)?.let { f ->
                                    coil3.compose.AsyncImage(model = f, contentDescription = null, modifier = Modifier.fillMaxSize())
                                } }
                            }
                            Spacer(Modifier.width(12.dp))
                            Column {
                                Text(v.title, maxLines = 3, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.SemiBold)
                                Text(v.publisher, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}
