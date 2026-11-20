package local.lastbook.android.ui

import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.LocalLibrary
import androidx.compose.material.icons.outlined.Map
import androidx.compose.material.icons.outlined.PlayCircle
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import local.lastbook.android.data.Services

private data class Dest(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

private val destinations = listOf(
    Dest("videos", "Videos", Icons.Outlined.PlayCircle),
    Dest("map", "Map", Icons.Outlined.Map),
    Dest("chat", "Chat", Icons.Outlined.ChatBubbleOutline),
    Dest("library", "Library", Icons.Outlined.LocalLibrary),
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun MainShell(onManage: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val nav: NavHostController = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val route = backStack?.destination?.route ?: "videos"
    val top = destinations.any { it.route == route }
    val imeVisible = WindowInsets.isImeVisible

    androidx.compose.runtime.LaunchedEffect(Unit) {
        val act = context as? android.app.Activity ?: return@LaunchedEffect
        val tab = act.intent?.getStringExtra("lb_tab")
        val ask = act.intent?.getStringExtra("lb_ask")
        val openRoute = act.intent?.getStringExtra("lb_route")
        if (!tab.isNullOrEmpty() && destinations.any { it.route == tab }) {
            nav.navigate(tab) {
                popUpTo("videos") { saveState = true }
                launchSingleTop = true
            }
        }
        if (!openRoute.isNullOrEmpty()) {
            nav.navigate(openRoute)
        }
        if (!ask.isNullOrEmpty()) {
            nav.navigate("chat") {
                popUpTo("videos") { saveState = true }
                launchSingleTop = true
            }
            kotlinx.coroutines.delay(500)
            Services.chat.send(ask)
        }
    }

    Scaffold(bottomBar = {
        if (top && !imeVisible) NavigationBar(containerColor = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp) {
            destinations.forEach { d ->
                NavigationBarItem(
                    selected = route == d.route,
                    onClick = {
                        // Tapping Chat always returns to the main chat page, not the last conversation.
                        if (d.route == "chat") Services.chat.newChat()
                        // Always pop back to the tab root: saved-state restoration here used to leave the
                        // controller pointing at an old entry, so some tabs (Videos) stopped responding.
                        nav.navigate(d.route) {
                            popUpTo("videos")
                            launchSingleTop = true
                        }
                    },
                    icon = { Icon(d.icon, contentDescription = null) },
                    label = { Text(d.label) },
                )
            }
        }
    }) { pad ->
        NavHost(navController = nav, startDestination = "videos",
            modifier = Modifier.padding(pad).consumeWindowInsets(pad)) {
            composable("videos") {
                VideosScreen(
                    onOpen = { id -> nav.navigate("watch/${android.net.Uri.encode(id)}") },
                    onRow = { row -> nav.navigate("row/${android.net.Uri.encode(row)}") },
                )
            }
            composable("row/{row}") { e ->
                val row = e.arguments?.getString("row") ?: "all"
                CategoryScreen(android.net.Uri.decode(row), onOpen = { id -> nav.navigate("watch/${android.net.Uri.encode(id)}") },
                    onBack = { nav.popBackStack() })
            }
            composable("watch/{id}") { e ->
                val id = android.net.Uri.decode(e.arguments?.getString("id") ?: "")
                WatchScreen(id, onBack = { nav.popBackStack() }, onOpen = { v -> nav.navigate("watch/${android.net.Uri.encode(v)}") },
                    onAsk = { about, label ->
                        Services.chat.newChat()
                        Services.chat.pendingAbout = about
                        Services.chat.pendingAboutLabel = label
                        nav.navigate("chat") { launchSingleTop = true }
                    })
            }
            composable("map") { MapScreen() }
            composable("chat") {
                ChatScreen(
                    onOpenVideo = { id, t -> nav.navigate("watch/${android.net.Uri.encode(id)}") },
                    onOpenDoc = { id, page -> nav.navigate("read/${android.net.Uri.encode(id)}?page=${page ?: 0}") },
                    onManage = onManage,
                )
            }
            composable("library") {
                LibraryScreen(
                    onManage = onManage,
                    onOpen = { id, page -> nav.navigate("read/${android.net.Uri.encode(id)}?page=${page ?: 0}") },
                    onOpenVideo = { id -> nav.navigate("watch/${android.net.Uri.encode(id)}") },
                    onOpenZim = { name -> nav.navigate("zim/${android.net.Uri.encode(name)}") },
                )
            }
            composable("read/{id}?page={page}") { e ->
                val id = android.net.Uri.decode(e.arguments?.getString("id") ?: "")
                val page = e.arguments?.getString("page")?.toIntOrNull() ?: 0
                ReaderScreen(id, page, onBack = { nav.popBackStack() }, onAsk = { about, label ->
                    Services.chat.newChat()
                    Services.chat.pendingAbout = about
                    Services.chat.pendingAboutLabel = label
                    nav.navigate("chat") { launchSingleTop = true }
                })
            }
            composable("zim/{name}") { e ->
                ZimScreen(android.net.Uri.decode(e.arguments?.getString("name") ?: ""), onBack = { nav.popBackStack() })
            }
        }
    }
}
