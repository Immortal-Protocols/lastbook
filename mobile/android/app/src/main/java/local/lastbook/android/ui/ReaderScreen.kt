package local.lastbook.android.ui

import android.annotation.SuppressLint
import android.graphics.BitmapFactory
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import local.lastbook.core.LastbookCore
import local.lastbook.core.PdfPages
import local.lastbook.core.Rec
import local.lastbook.core.WebResponse
import local.lastbook.core.s
import java.io.ByteArrayInputStream
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun ReaderScreen(id: String, startPage: Int, onBack: () -> Unit, onAsk: (String, String) -> Unit) {
    var doc by remember { mutableStateOf<Rec?>(null) }
    var page by remember { mutableIntStateOf(startPage.coerceAtLeast(1)) }
    var pages by remember { mutableIntStateOf(0) }
    var png by remember { mutableStateOf<ByteArray?>(null) }
    var text by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(id) {
        doc = withContext(Dispatchers.IO) { LastbookCore.videos.doc(id) }
        val d = doc ?: return@LaunchedEffect
        val f = withContext(Dispatchers.IO) { LastbookCore.videos.file(d.s("path")) }
        if (f == null) { loading = false; return@LaunchedEffect }
        when {
            d.s("kind") == "pdf" -> pages = withContext(Dispatchers.IO) { PdfPages.pageCount(f) }
            d.s("kind") == "transcript" -> text = withContext(Dispatchers.IO) { runCatching { f.readText() }.getOrNull() }
            d.s("kind") == "html" -> Unit
            else -> Unit
        }
        loading = false
    }

    LaunchedEffect(page, pages) {
        val d = doc ?: return@LaunchedEffect
        if (d.s("kind") != "pdf" || pages == 0) { png = null; return@LaunchedEffect }
        val f = LastbookCore.videos.file(d.s("path")) ?: return@LaunchedEffect
        png = withContext(Dispatchers.IO) { PdfPages.render(f, page - 1) }
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text(doc?.s("title") ?: "Reading", maxLines = 1) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Back") } },
            actions = {
                TextButton(onClick = { onAsk("doc:$id:${page - 1}", doc?.s("title") ?: "This page") }) { Text("Ask about this") }
            })
    }) { pad ->
        Box(Modifier.fillMaxSize().padding(pad)) {
            val d = doc
            when {
                loading -> CircularProgressIndicator(Modifier.align(Alignment.Center))
                d == null -> Text("This item is not in the library.", Modifier.align(Alignment.Center))
                d.s("kind") == "pdf" -> Column(Modifier.fillMaxSize()) {
                    Box(Modifier.weight(1f).fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.TopCenter) {
                        val bytes = png
                        if (bytes == null) CircularProgressIndicator(Modifier.align(Alignment.Center))
                        else {
                            val bmp = remember(bytes) { BitmapFactory.decodeByteArray(bytes, 0, bytes.size) }
                            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
                                Image(bmp.asImageBitmap(), contentDescription = "Page $page", modifier = Modifier.fillMaxWidth())
                            }
                        }
                    }
                    Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = { if (page > 1) page-- }, enabled = page > 1) { Icon(Icons.Default.ChevronLeft, "Previous page") }
                        Text("Page $page" + if (pages > 0) " of $pages" else "", Modifier.weight(1f), textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                        IconButton(onClick = { if (page < pages) page++ }, enabled = page < pages) { Icon(Icons.Default.ChevronRight, "Next page") }
                    }
                }
                d.s("kind") == "html" -> AndroidView(modifier = Modifier.fillMaxSize(), factory = { ctx ->
                    WebView(ctx).apply {
                        settings.javaScriptEnabled = false
                        settings.domStorageEnabled = false
                        webViewClient = object : WebViewClient() {
                            override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
                                val url = request?.url ?: return null
                                if (url.host != "lastbook.local") return null
                                val r: WebResponse = LastbookCore.web.handle(url.encodedPath.orEmpty(), url.queryParameterNames.associate { it to url.getQueryParameter(it).orEmpty() })
                                return WebResourceResponse(r.mime.substringBefore(';'), null, r.status, "OK", r.headers, ByteArrayInputStream(r.bytes))
                            }
                        }
                        loadUrl("https://lastbook.local/" + d.s("path"))
                    }
                })
                d.s("kind") == "transcript" -> Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(18.dp)) {
                    Text(text ?: "Loading…", style = MaterialTheme.typography.bodyMedium)
                }
                else -> Text("This file type can't be shown in this preview.", Modifier.align(Alignment.Center).padding(24.dp))
            }
        }
    }
}
