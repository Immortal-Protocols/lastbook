package local.lastbook.android.ui

import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.outlined.History
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import local.lastbook.android.data.ChatMessage
import local.lastbook.android.data.ChatSource
import local.lastbook.android.data.Conversation
import local.lastbook.android.data.Services
import local.lastbook.core.obj
import local.lastbook.core.truthy
import local.lastbook.core.s

private val starters = listOf(
    "The tap water is off. How do I make water safe to drink?",
    "Someone has a deep cut that won’t stop bleeding. What do I do?",
    "How do I run a generator safely during a power outage?",
    "The fridge has been off for 6 hours. What food is still safe?",
    "The toilets don’t work. How do we make an emergency toilet?",
    "Phones are down. How can our household stay in contact?",
)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalComposeUiApi::class)
@Composable
fun ChatScreen(onOpenVideo: (String, Double?) -> Unit, onOpenDoc: (String, Int?) -> Unit, onManage: () -> Unit) {
    val store = Services.chat
    var tick by remember { mutableIntStateOf(0) }
    var draft by remember { mutableStateOf("") }
    var searchQuery by remember { mutableStateOf("") }
    var menu by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    var historyQuery by remember { mutableStateOf("") }
    val _tickRead = tick
    val _storeRev = store.revision
    var current by remember { mutableStateOf(store.current) }
    val sources = store.status
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current

    // Keep the visible conversation in step when the store starts a new chat (e.g. from the bottom nav).
    LaunchedEffect(store.revision) { current = store.current }

    fun send(text: String) {
        if (text.isBlank()) return
        store.send(text); current = store.current; draft = ""; tick++
        focus.clearFocus(); keyboard?.hide()
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text("Chat", fontWeight = FontWeight.Bold) }, actions = {
            if (current != null) IconButton(onClick = { store.newChat(); current = null; tick++ }) { Icon(Icons.Outlined.History, "Chat history") }
            Box {
                IconButton(onClick = { menu = true }) { Icon(Icons.Default.MoreVert, "More") }
                DropdownMenu(
                    expanded = menu, onDismissRequest = { menu = false },
                    modifier = Modifier.widthIn(min = 280.dp),
                ) {
                    DropdownMenuItem(
                        text = { Text("Keep chat history") },
                        trailingIcon = {
                            Switch(checked = store.keep, onCheckedChange = { store.keep = it; tick++ })
                        },
                        onClick = { store.keep = !store.keep; tick++ },
                    )
                    HorizontalDivider(Modifier.padding(vertical = 4.dp))
                    DropdownMenuItem(text = { Text("Delete all chats") }, onClick = { menu = false; confirmDelete = true })
                    DropdownMenuItem(text = { Text("Library and downloads…") }, onClick = { menu = false; onManage() })
                }
            }
        })
    }) { pad ->
        Column(Modifier.fillMaxSize().padding(pad).imePadding()) {
            if (current == null) {
                LazyColumn(Modifier.weight(1f), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Ask the library", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                            Text("Answers from the manuals and videos on this phone, with the exact page or moment for each point.",
                                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            if (!sources.truthy("online")) {
                                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                                    Column(Modifier.padding(12.dp)) {
                                        Text("Library pages only", fontWeight = FontWeight.SemiBold)
                                        Text("No local AI is running, so a question shows the library pages that match it.",
                                            style = MaterialTheme.typography.bodySmall)
                                        TextButton(onClick = onManage) { Text("Install local AI") }
                                    }
                                }
                            }
                        }
                    }
                    item { Text("Try one of these", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
                    items(starters) { q ->
                        Card(Modifier.fillMaxWidth().clickable { send(q) }) {
                            Text(q, Modifier.padding(14.dp), style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                    if (store.chats.isNotEmpty()) {
                        item {
                            Text("Recent chats", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            OutlinedTextField(
                                value = searchQuery, onValueChange = { searchQuery = it },
                                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                                singleLine = true, placeholder = { Text("Search chats") },
                            )
                        }
                        val filteredChats = store.chats.filter { c ->
                            searchQuery.isBlank() || c.title.contains(searchQuery, ignoreCase = true) ||
                                c.messages.any { it.content.contains(searchQuery, ignoreCase = true) }
                        }
                        items(filteredChats, key = { it.id }) { c ->
                            Card(Modifier.fillMaxWidth().clickable { store.open(c); current = c; tick++ }) {
                                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Column(Modifier.weight(1f)) {
                                        Text(c.title, maxLines = 1, fontWeight = FontWeight.SemiBold)
                                        Text("${c.messages.count { it.role == "user" }} question(s)", style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    IconButton(onClick = { store.delete(c); tick++ }) {
                                        Icon(Icons.Default.Close, "Delete chat")
                                    }
                                }
                            }
                        }
                    }
                }
            } else {
                val c = current!!
                LazyColumn(Modifier.weight(1f), contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    if (c.aboutLabel != null) item {
                        Text("Asking about: ${c.aboutLabel}", style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.primary)
                    }
                    items(c.messages, key = { it.id }) { m -> MessageView(m, onOpenVideo, onOpenDoc) }
                }
            }
            if (store.pendingAboutLabel != null && current == null) {
                Text("Asking about: ${store.pendingAboutLabel}", Modifier.padding(horizontal = 16.dp),
                    style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            }
            Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.Bottom) {
                OutlinedTextField(
                    value = draft, onValueChange = { draft = it }, modifier = Modifier.weight(1f),
                    placeholder = { Text("Ask a question…") }, maxLines = 5,
                    shape = RoundedCornerShape(22.dp),
                )
                Spacer(Modifier.width(8.dp))
                val running = current?.messages?.lastOrNull()?.running == true
                IconButton(onClick = { if (running) { store.stop(); tick++ } else send(draft) }, enabled = running || draft.isNotBlank(),
                    modifier = Modifier.size(48.dp).background(MaterialTheme.colorScheme.primary, RoundedCornerShape(24.dp))) {
                    Icon(if (running) androidx.compose.material.icons.Icons.Default.Close else Icons.Default.ArrowUpward,
                        if (running) "Stop" else "Send", tint = MaterialTheme.colorScheme.onPrimary)
                }
            }
        }
    }

    if (confirmDelete) AlertDialog(
        onDismissRequest = { confirmDelete = false },
        title = { Text("Delete all chats?") },
        text = { Text("This removes every chat from this phone. It can't be undone.") },
        confirmButton = { Button(onClick = { store.deleteAll(); current = null; confirmDelete = false; tick++ }) { Text("Delete all chats") } },
        dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
    )
}

@Composable
private fun MessageView(m: ChatMessage, onOpenVideo: (String, Double?) -> Unit, onOpenDoc: (String, Int?) -> Unit) {
    if (m.role == "user") {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            Text(m.content, Modifier.background(MaterialTheme.colorScheme.primary, RoundedCornerShape(18.dp))
                .padding(horizontal = 14.dp, vertical = 10.dp), color = MaterialTheme.colorScheme.onPrimary)
        }
        return
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (m.content.isNotEmpty()) Text(m.content, style = MaterialTheme.typography.bodyLarge)
        if (m.running && m.content.isEmpty()) {
            TypingIndicator(if (m.phase == "writing") "Writing the answer on this phone" else "Searching the library")
        }
        m.error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        val list = if (m.sources.isNotEmpty()) m.sources else m.fallback
        if (list.isNotEmpty()) {
            var expanded by remember(m.id) { mutableStateOf(false) }
            val collapsed = 2
            val showAll = expanded || list.size <= collapsed
            Column(Modifier.animateContentSize(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(if (m.content.isEmpty()) "Library pages that match" else "Sources",
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    if (list.size > collapsed) {
                        TextButton(onClick = { expanded = !expanded }) {
                            Text(if (expanded) "Show less" else "Show all ${list.size}")
                        }
                    }
                }
                for (s in if (showAll) list else list.take(collapsed)) {
                    SourceCard(s, onOpenVideo, onOpenDoc, compact = !expanded)
                }
            }
        }
    }
}

@Composable
private fun TypingIndicator(label: String) {
    val transition = rememberInfiniteTransition(label = "typing")
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        repeat(3) { i ->
            val alpha by transition.animateFloat(
                initialValue = 0.2f, targetValue = 1f,
                animationSpec = infiniteRepeatable(
                    animation = tween(durationMillis = 600, delayMillis = i * 150),
                    repeatMode = RepeatMode.Reverse,
                ),
                label = "dot$i",
            )
            Box(Modifier.size(6.dp).background(
                MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = alpha), CircleShape))
        }
    }
}

@Composable
private fun SourceCard(
    s: ChatSource, onOpenVideo: (String, Double?) -> Unit, onOpenDoc: (String, Int?) -> Unit,
    compact: Boolean = false,
) {
    Card(Modifier.fillMaxWidth().clickable {
        if (s.kind == "video") onOpenVideo(s.docId, s.t) else onOpenDoc(s.docId, s.page)
    }) {
        Column(Modifier.padding(if (compact) 10.dp else 12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("[${s.key}] ${s.title}", maxLines = if (compact) 1 else 2, style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold)
            val sub = listOfNotNull(s.publisher.takeIf { it.isNotEmpty() }, s.where.takeIf { it.isNotEmpty() }).joinToString(" · ")
            if (sub.isNotEmpty()) Text(sub, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (!compact) s.excerpt?.let { Text(it, maxLines = 3, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}
