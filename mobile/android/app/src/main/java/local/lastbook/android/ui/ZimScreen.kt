package local.lastbook.android.ui

import android.annotation.SuppressLint
import android.webkit.WebView
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import local.lastbook.core.LastbookCore
import org.json.JSONArray

@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun ZimScreen(name: String, onBack: () -> Unit) {
    val context = LocalContext.current
    var web by remember { mutableStateOf<WebView?>(null) }
    var loading by remember { mutableStateOf(true) }
    var canBack by remember { mutableStateOf(false) }
    var canForward by remember { mutableStateOf(false) }
    var searching by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    var full by remember { mutableStateOf(false) }
    var results by remember { mutableStateOf<List<Triple<String, String, String>>>(emptyList()) }
    val title = name.removeSuffix(".zim").replace('_', ' ')

    DisposableEffect(Unit) { onDispose { web?.destroy(); web = null } }

    // System back first closes search, then steps back one article, and only then leaves the reader.
    BackHandler {
        when {
            searching -> { searching = false; results = emptyList() }
            canBack -> web?.goBack()
            else -> onBack()
        }
    }

    LaunchedEffect(query, searching) {
        if (!searching) return@LaunchedEffect
        val q = query.trim()
        if (q.isEmpty()) { results = emptyList(); return@LaunchedEffect }
        delay(160)
        search(name, q, full) { results = it }
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text(title, maxLines = 1) },
            navigationIcon = { IconButton(onClick = { if (canBack) web?.goBack() else onBack() }) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, if (canBack) "Previous article" else "Back to Library")
            } },
            actions = {
                IconButton(onClick = { web?.goBack() }, enabled = canBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "Previous article")
                }
                IconButton(onClick = { web?.goForward() }, enabled = canForward) {
                    Icon(Icons.AutoMirrored.Filled.ArrowForward, "Next article")
                }
                IconButton(onClick = { searching = false; web?.loadUrl("https://lastbook.local/zim/$name/") }) {
                    Icon(Icons.Default.Home, "Main page")
                }
                IconButton(onClick = { searching = !searching; if (!searching) results = emptyList() }) {
                    Icon(Icons.Default.Search, "Search")
                }
            })
    }) { pad ->
        Column(Modifier.fillMaxSize().padding(pad)) {
            if (searching) {
                OutlinedTextField(value = query, onValueChange = { query = it }, modifier = Modifier.fillMaxWidth().padding(10.dp),
                    singleLine = true, placeholder = { Text("Search this encyclopedia") }, leadingIcon = { Icon(Icons.Default.Search, null) })
                Row(Modifier.padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { full = false; search(name, query, false) { results = it } }) {
                        Text("Titles", fontWeight = if (!full) FontWeight.Bold else FontWeight.Normal)
                    }
                    TextButton(onClick = { full = true; search(name, query, true) { results = it } }) {
                        Text("Full text", fontWeight = if (full) FontWeight.Bold else FontWeight.Normal)
                    }
                }
                LazyColumn(Modifier.fillMaxSize()) {
                    items(results, key = { it.second + it.first }) { r ->
                        Column(Modifier.fillMaxWidth().clickable {
                            web?.loadUrl("https://lastbook.local/zim/$name/${r.second.trimStart('/')}")
                            searching = false
                        }.padding(14.dp)) {
                            Text(r.first, fontWeight = FontWeight.SemiBold)
                            if (r.third.isNotEmpty()) Text(r.third.replace(Regex("<[^>]+>"), ""), style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            } else {
                Box(Modifier.fillMaxSize()) {
                    AndroidView(modifier = Modifier.fillMaxSize(), factory = { ctx ->
                        WebView(ctx).apply {
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.allowFileAccess = false
                            settings.builtInZoomControls = true
                            settings.displayZoomControls = false
                            webViewClient = object : LocalWebViewClient() {
                                override fun onPageFinished(view: WebView?, url: String?) {
                                    loading = false
                                    canBack = view?.canGoBack() == true
                                    canForward = view?.canGoForward() == true
                                }
                            }
                            loadUrl("https://lastbook.local/zim/$name/")
                            web = this
                        }
                    })
                    if (loading) CircularProgressIndicator(Modifier.align(Alignment.Center))
                }
            }
        }
    }
}

private fun search(name: String, q: String, full: Boolean, done: (List<Triple<String, String, String>>) -> Unit) {
    if (q.isBlank()) { done(emptyList()); return }
    kotlinx.coroutines.MainScope().launch {
        val list = withContext(Dispatchers.IO) {
            runCatching {
                val a = JSONArray(String(LastbookCore.zim.search(name, q, full, 30)))
                (0 until a.length()).mapNotNull { i -> a.optJSONObject(i)?.let { o -> Triple(o.optString("title"), o.optString("path"), o.optString("snippet")) } }
            }.getOrDefault(emptyList())
        }
        done(list)
    }
}
