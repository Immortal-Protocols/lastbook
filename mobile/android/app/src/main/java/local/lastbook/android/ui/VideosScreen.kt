package local.lastbook.android.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.PlayCircle
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.AssistChip
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import local.lastbook.core.LastbookCore
import local.lastbook.core.Rec
import local.lastbook.core.d
import local.lastbook.core.s
import local.lastbook.core.str
import local.lastbook.core.truthy
import java.io.File

data class VideoItem(
    val id: String, val title: String, val publisher: String, val duration: Double,
    val thumb: String?, val hasTranscript: Boolean,
) {
    companion object {
        fun from(r: Rec) = VideoItem(r.s("id"), r.s("title"), r.s("publisher"), r.d("duration"), r.str("thumb"), r.truthy("transcript"))
    }
}

data class VideoRow(val id: String, val title: String, val note: String?, val count: Int, val items: List<VideoItem>)

fun clock(t: Double): String { val s = t.toInt().coerceAtLeast(0); return "%d:%02d".format(s / 60, s % 60) }
fun durationText(t: Double): String {
    if (t <= 0) return ""
    val s = t.toInt(); val h = s / 3600; val m = (s % 3600) / 60
    return if (h > 0) "${h}h ${m}m" else "${m} min"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VideosScreen(onOpen: (String) -> Unit, onRow: (String) -> Unit) {
    var rows by remember { mutableStateOf<List<VideoRow>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var query by remember { mutableStateOf("") }
    var length by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<VideoItem>>(emptyList()) }
    var searching by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        rows = withContext(Dispatchers.IO) {
            LastbookCore.videos.home().map { r ->
                VideoRow(r.s("id"), r.s("title"), r.str("note"), (r["count"] as? Number)?.toInt() ?: 0,
                    (r["items"] as? List<*>)?.mapNotNull { (it as? Map<*, *>)?.let { m -> VideoItem.from(m.entries.associate { e -> e.key.toString() to e.value }) } } ?: emptyList())
            }
        }
        loading = false
    }

    LaunchedEffect(query, length) {
        val q = query.trim()
        if (q.isEmpty() && length.isEmpty()) { results = emptyList(); searching = false; return@LaunchedEffect }
        searching = true
        delay(180)
        results = withContext(Dispatchers.IO) {
            (LastbookCore.videos.list("all", q, length, "", 0, 60)["items"] as? List<*>)?.mapNotNull {
                (it as? Map<*, *>)?.let { m -> VideoItem.from(m.entries.associate { e -> e.key.toString() to e.value }) }
            } ?: emptyList()
        }
        searching = false
    }

    Scaffold(topBar = {
        TopAppBar(title = {
            Column {
                Text("Videos", fontWeight = FontWeight.Bold)
                Text("Watch it done — practical how-tos first", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        })
    }) { pad ->
        Column(Modifier.fillMaxSize().padding(pad)) {
            OutlinedTextField(
                value = query, onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                singleLine = true, placeholder = { Text("Search video titles") },
                leadingIcon = { Icon(Icons.Default.Search, null) },
                trailingIcon = { if (query.isNotEmpty()) androidx.compose.material3.TextButton(onClick = { query = "" }) { Text("Clear") } },
            )
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = length == "", onClick = { length = "" }, label = { Text("Any length") })
                FilterChip(selected = length == "short", onClick = { length = "short" }, label = { Text("Under 10 min") })
                FilterChip(selected = length == "medium", onClick = { length = "medium" }, label = { Text("10–30 min") })
                FilterChip(selected = length == "long", onClick = { length = "long" }, label = { Text("Over 30 min") })
            }
            when {
                loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                query.isNotBlank() || length.isNotEmpty() -> {
                    if (searching) Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                    else if (results.isEmpty()) Text("No videos match. Try fewer or different words.", Modifier.padding(24.dp))
                    else LazyVerticalGrid(GridCells.Adaptive(164.dp), contentPadding = PaddingValues(16.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                        items(results, key = { it.id }) { v -> VideoTile(v, Modifier.fillMaxWidth()) { onOpen(v.id) } }
                    }
                }
                else -> LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(vertical = 12.dp)) {
                    for (r in rows) {
                        item(key = "h-${r.id}") {
                            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text(r.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                    if (!r.note.isNullOrEmpty()) Text(r.note, style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                if (r.count > 10) androidx.compose.material3.TextButton(onClick = { onRow(r.id) }) { Text("Show all ${r.count}") }
                            }
                        }
                        item(key = "r-${r.id}") {
                            LazyRow(contentPadding = PaddingValues(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                items(r.items, key = { it.id }) { v -> VideoTile(v, Modifier.width(190.dp)) { onOpen(v.id) } }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun VideoTile(v: VideoItem, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Column(modifier.clickable(onClick = onClick)) {
        Box(Modifier.fillMaxWidth().aspectRatio(16f / 9f).clip(RoundedCornerShape(12.dp)).background(MaterialTheme.colorScheme.surfaceVariant)) {
            val file = v.thumb?.let { LastbookCore.library.lib?.resolve(it) }
            if (file != null) AsyncImage(model = file, contentDescription = null, modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
            else Icon(Icons.Outlined.PlayCircle, null, Modifier.align(Alignment.Center).width(42.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
            if (v.duration > 0) Text(clock(v.duration), Modifier.align(Alignment.BottomEnd)
                .padding(6.dp).background(Color.Black.copy(alpha = .75f), RoundedCornerShape(4.dp)).padding(horizontal = 5.dp, vertical = 2.dp),
                color = Color.White, style = MaterialTheme.typography.labelSmall)
        }
        Spacer(Modifier.height(6.dp))
        Text(v.title, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
        Text(v.publisher, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CategoryScreen(rowId: String, onOpen: (String) -> Unit, onBack: () -> Unit) {
    var items by remember { mutableStateOf<List<VideoItem>>(emptyList()) }
    var title by remember { mutableStateOf("Videos") }
    var loading by remember { mutableStateOf(true) }
    var length by remember { mutableStateOf("") }
    var sort by remember { mutableStateOf("") }

    LaunchedEffect(rowId, length, sort) {
        loading = true
        val r = withContext(Dispatchers.IO) { LastbookCore.videos.list(rowId, "", length, sort, 0, 300) }
        title = r.s("title").ifEmpty { "Videos" }
        items = (r["items"] as? List<*>)?.mapNotNull {
            (it as? Map<*, *>)?.let { m -> VideoItem.from(m.entries.associate { e -> e.key.toString() to e.value }) }
        } ?: emptyList()
        loading = false
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text(title) }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } })
    }) { pad ->
        Column(Modifier.fillMaxSize().padding(pad)) {
            Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = length == "", onClick = { length = "" }, label = { Text("Any length") })
                FilterChip(selected = length == "short", onClick = { length = "short" }, label = { Text("Under 10") })
                FilterChip(selected = length == "medium", onClick = { length = "medium" }, label = { Text("10–30") })
                FilterChip(selected = length == "long", onClick = { length = "long" }, label = { Text("Over 30") })
            }
            Row(Modifier.padding(horizontal = 16.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(onClick = { sort = "" }, label = { Text("Best") })
                AssistChip(onClick = { sort = "new" }, label = { Text("Newest") })
                AssistChip(onClick = { sort = "az" }, label = { Text("A–Z") })
            }
            if (loading) Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            else LazyVerticalGrid(GridCells.Adaptive(164.dp), contentPadding = PaddingValues(16.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                items(items, key = { it.id }) { v -> VideoTile(v, Modifier.fillMaxWidth()) { onOpen(v.id) } }
            }
        }
    }
}
