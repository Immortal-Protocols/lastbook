package local.lastbook.android.ui

import android.annotation.SuppressLint
import android.net.Uri
import android.webkit.WebView
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
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import local.lastbook.core.LastbookCore
import local.lastbook.core.Rec
import local.lastbook.core.d
import local.lastbook.core.s
import local.lastbook.core.toStringMap
import org.json.JSONArray
import org.json.JSONObject

private const val MAP_CSS = """
html.lb-embed .side,html.lb-embed header.top,html.lb-embed .tabbar,html.lb-embed .maphead,html.lb-embed .maptools,
html.lb-embed .capband,html.lb-embed #sideBtn,html.lb-embed .skip{display:none!important}
html.lb-embed body{padding:0!important;margin:0!important;background:var(--bg)}
html.lb-map,html.lb-map body{height:100%;overflow:hidden}
html.lb-map main.map-page{position:fixed;inset:0;padding:0!important;margin:0!important;max-width:none!important;min-height:0}
html.lb-map .mapgrid{display:block!important}
html.lb-map .mapwrap{position:fixed!important;inset:0!important;height:auto!important;min-height:0!important;border-radius:0!important;border:0!important;box-shadow:none!important}
html.lb-map #map-full,html.lb-map #gps{display:none!important}
html.lb-map .map-top{left:12px;top:12px;right:78px}
html.lb-map .map-search input,html.lb-map .map-layers-btn{height:46px;font-size:16px}
html.lb-map .mapctl{right:12px;top:12px}
html.lb-map .map-pop,html.lb-map .map-card{left:12px!important;right:12px!important;width:auto!important;top:auto!important;bottom:12px!important;max-height:62%!important}
html.lb-map .mapattr{display:none!important}
html.lb-map .map-status{left:50%;bottom:24px}
"""

@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun MapScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var webView by remember { mutableStateOf<WebView?>(null) }
    var showSheet by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(true) }
    var items by remember { mutableStateOf<List<Rec>>(emptyList()) }
    var sheetLoading by remember { mutableStateOf(false) }
    var center by remember { mutableStateOf(44.98 to -93.26) }
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = false)

    DisposableEffect(Unit) {
        onDispose { webView?.destroy(); webView = null }
    }

    Box(Modifier.fillMaxSize()) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                WebView(ctx).apply {
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.allowFileAccess = false
                    settings.allowContentAccess = false
                    settings.mediaPlaybackRequiresUserGesture = true
                    settings.setSupportZoom(false)
                    settings.builtInZoomControls = false
                    settings.useWideViewPort = true
                    settings.loadWithOverviewMode = true
                    webViewClient = object : LocalWebViewClient() {
                        override fun onPageFinished(view: WebView?, url: String?) {
                            super.onPageFinished(view, url)
                            loading = false
                            view?.evaluateJavascript("""
                                (()=>{document.documentElement.classList.add('plat-ipad','lb-embed','lb-map');
                                let s=document.getElementById('lb-embed-css'); if(!s){s=document.createElement('style');s.id='lb-embed-css';(document.head||document.documentElement).appendChild(s)}
                                s.textContent=${JSONObject.quote(MAP_CSS)};})()
                            """.trimIndent(), null)
                        }
                    }
                    val (lat0, lon0) = LastbookCore.map.homeCenter()
                    loadUrl("https://lastbook.local/#/map?lat=$lat0&lon=$lon0&z=7")
                    webView = this
                }
            },
        )
        if (loading) CircularProgressIndicator(Modifier.align(Alignment.Center))
        ExtendedFloatingActionButton(
            onClick = {
                scope.launch {
                    sheetLoading = true; showSheet = true
                    val js = "(function(){return location.hash})()"
                    webView?.evaluateJavascript(js) { v ->
                        val hash = v?.trim('"') ?: ""
                        val u = Uri.parse("https://x/$hash")
                        val lat = u.getQueryParameter("lat")?.toDoubleOrNull() ?: center.first
                        val lon = u.getQueryParameter("lon")?.toDoubleOrNull() ?: center.second
                        center = lat to lon
                        scope.launch {
                            val classes = listOf("hospital", "clinic", "doctors", "pharmacy", "fire_station", "police", "shelter",
                                "drinking_water", "reservoir", "lake", "dam", "spring", "supermarket", "hardware", "fuel", "camp_site")
                            items = withContext(Dispatchers.IO) {
                                val bytes = LastbookCore.map.near(lat, lon, classes, 24)
                                runCatching {
                                    val a = JSONArray(String(bytes))
                                    (0 until a.length()).mapNotNull { a.optJSONObject(it)?.toStringMap() }
                                }.getOrDefault(emptyList())
                            }
                            sheetLoading = false
                        }
                    }
                }
            },
            modifier = Modifier.align(Alignment.BottomEnd).padding(18.dp),
            icon = { Icon(Icons.Default.MyLocation, null) },
            text = { Text("Nearby") },
        )
    }

    if (showSheet) {
        ModalBottomSheet(onDismissRequest = { showSheet = false }, sheetState = sheetState) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 18.dp)) {
                Text("Nearest to the map center", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text("For the layers you have on. Straight-line distance, not by road.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (sheetLoading) Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            else LazyColumn(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                items(items, key = { it.s("cls") + it.d("lat").toString() + it.d("lon").toString() }) { r ->
                    Column(Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 10.dp).clickable {
                        val name = r.s("name").ifEmpty { r.s("label") }
                        val q = "lat=${r.d("lat")}&lon=${r.d("lon")}&z=16&pin=${Uri.encode(name)}"
                        webView?.evaluateJavascript("location.hash='#/map?$q'", null)
                        showSheet = false
                    }) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(r.s("label"), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                            Text("${r.d("km")} km ${r.s("dir")}", style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text(r.s("name").ifEmpty { "Unnamed ${r.s("label")}" }, fontWeight = FontWeight.SemiBold)
                        val detail = r.s("detail").ifEmpty { r.s("summary") }
                        if (detail.isNotEmpty()) Text(detail, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}
