package local.lastbook.android.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.Divider
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import local.lastbook.core.LastbookCore
import local.lastbook.core.Rec
import local.lastbook.core.d
import local.lastbook.core.s
import local.lastbook.core.str
import java.io.File

data class LibraryHit(val id: String, val title: String, val kind: String, val publisher: String, val page: Int?, val path: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LibraryScreen(onManage: () -> Unit, onOpen: (String, Int?) -> Unit, onOpenVideo: (String) -> Unit, onOpenZim: (String) -> Unit) {
    var query by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("all") }
    var hits by remember { mutableStateOf<List<LibraryHit>>(emptyList()) }
    val zims = remember { LastbookCore.library.zimFiles() }
    val root = LastbookCore.library.root
    val pack = LastbookCore.library.packInfo()
    val mapName = runCatching {
        root?.resolve("map-set.json")?.let { org.json.JSONObject(it.readText()).optString("name") }
    }.getOrNull() ?: "base"
    val addresses = root?.resolve("derived/geo/addresses")?.listFiles()?.filter { it.name.endsWith(".sqlite") }?.map { it.nameWithoutExtension } ?: emptyList()
    val model = LastbookCore.chat.localModelFile()

    LaunchedEffect(query, kind) {
        hits = withContext(Dispatchers.IO) {
            if (query.isBlank() && kind == "all") emptyList()
            else LastbookCore.chat.find(query, kind, 120).mapNotNull { r ->
                val id = r.s("id")
                if (id.isEmpty()) null else LibraryHit(id, r.s("title"), r.s("kind"), r.s("publisher"), null, r.s("path"))
            }
        }
    }

    Scaffold(topBar = { TopAppBar(title = { Text("Library", fontWeight = FontWeight.Bold) }) }) { pad ->
        LazyColumn(Modifier.fillMaxSize().padding(pad), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("On this phone", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        ReadinessRow(pack?.s("name")?.replaceFirstChar { it.uppercase() }?.let { "Library: $it" } ?: "Library", pack != null,
                            "${LastbookCore.catalog.records.count { it.s("kind") == "video" }} videos and reading work offline.")
                        ReadinessRow("Map: $mapName", mapName != "base", "Streets, help points and address search.")
                        ReadinessRow("Street addresses: ${addresses.joinToString(", ").ifEmpty { "none" }}", addresses.isNotEmpty(),
                            "Find a street address on the map.")
                        ReadinessRow("Local AI: ${model?.name ?: "not installed"}", model != null,
                            if (model != null) "Answers are written on this phone." else "Chat shows the library pages that match.")
                        ReadinessRow("Encyclopedias: ${zims.size}", true,
                            if (zims.isEmpty()) "No encyclopedia files in this library." else "${zims.size} installed.")
                        HorizontalDivider(Modifier.padding(vertical = 4.dp))
                        Text(root?.absolutePath ?: "No library folder", style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        OutlinedButton(onClick = onManage) { Text("Install or change library…") }
                    }
                }
            }
            item {
                OutlinedTextField(value = query, onValueChange = { query = it }, modifier = Modifier.fillMaxWidth(),
                    singleLine = true, placeholder = { Text("Search everything on this phone") },
                    leadingIcon = { Icon(Icons.Default.Search, null) })
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    AssistChip(onClick = { kind = "all" }, label = { Text("All") })
                    AssistChip(onClick = { kind = "read" }, label = { Text("Reading") })
                    AssistChip(onClick = { kind = "video" }, label = { Text("Videos") })
                    AssistChip(onClick = { kind = "zim" }, label = { Text("Encyclopedias") })
                }
            }
            if (hits.isNotEmpty()) {
                item { Text("${hits.size} results", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold) }
                items(hits, key = { it.id }) { h ->
                    Card(Modifier.fillMaxWidth().clickable {
                        if (h.kind == "video" || h.kind == "transcript") onOpenVideo(h.id) else onOpen(h.id, h.page)
                    }) {
                        Column(Modifier.padding(12.dp)) {
                            Text(h.title, maxLines = 2, fontWeight = FontWeight.SemiBold)
                            Text(listOf(h.kind.uppercase(), h.publisher).filter { it.isNotEmpty() }.joinToString(" · "),
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            } else if (query.isNotBlank()) {
                item { Text("Nothing matches “$query”.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            if (zims.isNotEmpty()) {
                item { Text("Encyclopedias", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
                items(zims, key = { it.name }) { z ->
                    Card(Modifier.fillMaxWidth().clickable { onOpenZim(z.name) }) {
                        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.AutoMirrored.Filled.MenuBook, null, tint = MaterialTheme.colorScheme.primary)
                            Spacer(Modifier.width(12.dp))
                            Column(Modifier.weight(1f)) {
                                Text(z.nameWithoutExtension.replace('_', ' '), fontWeight = FontWeight.SemiBold)
                                Text(android.text.format.Formatter.formatFileSize(LastbookCore.context, z.length()),
                                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(20.dp)) }
        }
    }
}

@Composable
private fun ReadinessRow(title: String, ok: Boolean, detail: String) {
    Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(if (ok) "✓" else "!", style = MaterialTheme.typography.titleMedium,
            color = if (ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
        Column {
            Text(title, fontWeight = FontWeight.SemiBold)
            Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
