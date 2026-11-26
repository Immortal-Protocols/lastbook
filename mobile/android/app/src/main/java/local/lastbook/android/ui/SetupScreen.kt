package local.lastbook.android.ui

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import local.lastbook.android.install.InstallService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import local.lastbook.core.LastbookCore
import local.lastbook.core.install.CatalogEntry
import local.lastbook.core.install.InstallProgress
import local.lastbook.core.install.ItemState
import local.lastbook.core.install.Plan
import local.lastbook.core.install.PlanItem
import org.json.JSONObject
import java.io.File

private fun bytes(n: Long): String = android.text.format.Formatter.formatFileSize(
    LastbookCore.context, n
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SetupScreen(manage: Boolean = false, onDone: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val catalog = LastbookCore.installCatalog
    val packs = remember { catalog.packs }
    var packId by remember { mutableStateOf(packs.firstOrNull { it.id == "small" }?.id ?: packs.firstOrNull()?.id ?: "small") }
    var stateId by remember { mutableStateOf<String?>(null) }
    var wantAI by remember { mutableStateOf(LastbookCore.chat.aiEnabled()) }
    val totalRam = remember {
        runCatching { File("/proc/meminfo").readLines().first { it.startsWith("MemTotal:") }.split(Regex("\\s+"))[1].toLong() * 1024 }
            .getOrDefault(8L * 1024 * 1024 * 1024)
    }
    val best = remember { catalog.bestModelFor(totalRam) }
    var modelId by remember { mutableStateOf(best?.id) }
    var customUri by remember { mutableStateOf<Uri?>(null) }
    var customName by remember { mutableStateOf<String?>(null) }
    var showStatePicker by remember { mutableStateOf(false) }
    var showModelMenu by remember { mutableStateOf(false) }
    var rootPath by remember { mutableStateOf(LastbookCore.paths.root.absolutePath) }
    var plan by remember { mutableStateOf<Plan?>(null) }
    var running by remember { mutableStateOf(false) }
    var paused by remember { mutableStateOf(false) }
    var progress by remember { mutableStateOf<InstallProgress?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var done by remember { mutableStateOf(false) }
    var confirmFolder by remember { mutableStateOf(false) }

    val maps = remember { catalog.maps.sortedBy { it.title } }
    val stateTitle = maps.firstOrNull { it.id == stateId }?.title ?: "Choose your state"

    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            val f = treeToFile(context, uri)
            if (f != null) {
                LastbookCore.paths.root = f
                rootPath = f.absolutePath
            } else {
                error = "That folder can't be used directly. Choose a folder on this phone's internal storage."
            }
        }
    }
    val notifyPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    val modelPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            customUri = uri
            customName = queryName(context, uri) ?: "custom-model.gguf"
            modelId = null
        }
    }

    fun buildPlan(): Plan {
        val p = LastbookCore.installer.plan(packId, stateId, wantAI, if (customUri != null) null else modelId)
        plan = p
        return p
    }

    fun startInstall() {
        error = null; done = false; paused = false
        val p = buildPlan()
        if (stateId == null) { error = "Choose your state first."; return }
        if (!p.fits) { error = "There is not enough room: this needs ${bytes(p.peakBytes)} free and there is ${bytes(p.freeBytes)}."; return }
        running = true
        LastbookCore.chat.setAiEnabled(wantAI)
        if (wantAI) LastbookCore.chat.setSelectedModel(selectedModelFile(modelId, customName))
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            notifyPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        InstallService.start(context)
        LastbookCore.paths.installJobFile.writeText(JSONObject(mapOf(
            "pack" to packId, "state" to stateId, "model" to (modelId ?: ""), "ai" to wantAI
        )).toString())
        scope.launch {
            try {
                LastbookCore.installer.run(p, { pr ->
                    progress = pr
                    if (paused) throw kotlinx.coroutines.CancellationException("paused")
                }, isCancelled = { paused })
                if (customUri != null) {
                    withContext(Dispatchers.IO) { copyCustomModel(context, customUri!!, customName!!) }
                }
                LastbookCore.paths.installJobFile.delete()
                LastbookCore.reloadLibrary()
                InstallService.stop(context)
                running = false; done = true
            } catch (e: kotlinx.coroutines.CancellationException) {
                running = false
                InstallService.stop(context)
                if (!paused) error = "Install cancelled."
            } catch (e: Exception) {
                running = false
                InstallService.stop(context)
                error = e.message ?: "Install failed."
            }
        }
    }

    val hasPending = remember { LastbookCore.paths.installJobFile.isFile }

    if (running || (progress != null && !done)) {
        ProgressScreen(
            plan = plan, progress = progress, paused = paused,
            onPause = { paused = true },
            onResume = { paused = false; error = null; val p = plan ?: buildPlan(); running = true; scope.launch {
                try {
                    LastbookCore.installer.run(p, { progress = it; if (paused) throw kotlinx.coroutines.CancellationException("paused") }, isCancelled = { paused })
                    LastbookCore.paths.installJobFile.delete(); LastbookCore.reloadLibrary(); running = false; done = true
                } catch (e: kotlinx.coroutines.CancellationException) { running = false } catch (e: Exception) { running = false; error = e.message ?: "Install failed." }
            } },
            onCancel = { paused = true; running = false; progress = null },
            onDone = onDone,
            error = error,
        )
        return
    }

    if (done) {
        AlertDialog(
            onDismissRequest = { onDone() },
            title = { Text("Lastbook is ready") },
            text = { Text("Your library, map and local AI are installed. Everything works offline from here.") },
            confirmButton = { Button(onClick = onDone) { Text("Start") } },
        )
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text(if (manage) "Library and downloads" else "Set up Lastbook") })
    }) { pad ->
        Column(
            Modifier.fillMaxSize().padding(pad).verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Text(
                if (manage) "Change what is on this phone. Downloads are checked, then unpacked; an old library is kept until you delete it."
                else "Choose what to keep on this phone. Lastbook never looks up your location and works offline after this.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            if (hasPending && !manage) {
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("An install was interrupted", fontWeight = FontWeight.SemiBold)
                        Text("Your partial download is kept. Resume to carry on from where it stopped.", style = MaterialTheme.typography.bodySmall)
                        OutlinedButton(onClick = {
                            runCatching {
                                val o = JSONObject(LastbookCore.paths.installJobFile.readText())
                                packId = o.optString("pack", packId); stateId = o.optString("state").takeIf { it.isNotEmpty() }
                                wantAI = o.optBoolean("ai", true); modelId = o.optString("model").takeIf { it.isNotEmpty() }
                            }
                            startInstall()
                        }) { Text("Resume install") }
                    }
                }
            }

            Section("Your state") {
                Text("Lastbook installs your state's detailed map. It doesn't look up your location; you choose.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedButton(onClick = { showStatePicker = true }, modifier = Modifier.fillMaxWidth()) {
                    Text(stateTitle, modifier = Modifier.weight(1f)); Icon(Icons.Default.ExpandMore, null)
                }
            }

            Section("Library size") {
                for (p in packs) {
                    val item = LastbookCore.installer.plan(p.id, stateId, false, null).items.firstOrNull { it.key.startsWith("pack:") }
                    val peak = plan?.takeIf { it.packId == p.id }?.peakBytes ?: run {
                        val free = LastbookCore.paths.root.parentFile?.usableSpace ?: 0
                        (p.downloadBytes + p.installedBytes)
                    }
                    val free = LastbookCore.paths.root.parentFile?.usableSpace ?: 0
                    val fits = p.downloadBytes + 2_000_000_000L <= free || (LastbookCore.library.root != null && LastbookCore.installer.installedPack() == p.id)
                    Row(
                        Modifier.fillMaxWidth().clickable(enabled = fits) { packId = p.id }.padding(vertical = 8.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        RadioButton(selected = packId == p.id, onClick = { if (fits) packId = p.id }, enabled = fits)
                        Column(Modifier.weight(1f)) {
                            Text(p.title, fontWeight = FontWeight.SemiBold)
                            Text("${bytes(p.downloadBytes)} download · ${bytes(p.installedBytes)} installed · ${bytes(p.downloadBytes + p.installedBytes + 2_000_000_000L)} free while installing",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            if (!fits) Text("Not enough space on this phone for this size. Free some space or choose a smaller library.",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }

            Section("Local AI") {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Add local AI", fontWeight = FontWeight.SemiBold)
                        Text(if (wantAI) "Answers are written on this phone from the library only." else "Without it, Chat shows the library pages that match.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(checked = wantAI, onCheckedChange = {
                        wantAI = it
                        LastbookCore.chat.setAiEnabled(it)
                    })
                }
                if (wantAI) {
                    Box {
                        OutlinedButton(onClick = { showModelMenu = true }, modifier = Modifier.fillMaxWidth()) {
                            Text(modelLabel(catalog, modelId, customName) + " · " + bytes(catalog.model(modelId ?: "")?.downloadBytes ?: 0),
                                modifier = Modifier.weight(1f))
                            Icon(Icons.Default.ExpandMore, null)
                        }
                        DropdownMenu(expanded = showModelMenu, onDismissRequest = { showModelMenu = false }) {
                            DropdownMenuItem(text = { Text("Auto (best for this phone: ${best?.title ?: "none"})") }, onClick = {
                                modelId = best?.id; customUri = null; customName = null; showModelMenu = false
                            })
                            for (m in catalog.models.filter { it.available }) {
                                val fits = m.memoryBytes < totalRam
                                DropdownMenuItem(
                                    text = {
                                        Column {
                                            Text(m.title + if (m.id == best?.id) " · recommended" else "")
                                            Text("${bytes(m.downloadBytes)} · " + if (fits) "fits this phone" else "may not fit this phone's memory",
                                                style = MaterialTheme.typography.bodySmall)
                                        }
                                    },
                                    onClick = { modelId = m.id; customUri = null; customName = null; showModelMenu = false },
                                )
                            }
                            DropdownMenuItem(text = { Text("Use my own GGUF file…") }, onClick = {
                                showModelMenu = false
                                modelPicker.launch(arrayOf("application/octet-stream", "application/x-gguf", "*/*"))
                            })
                        }
                    }
                    val selectedModel = catalog.model(modelId ?: "")
                    if (customName == null && selectedModel != null && selectedModel.memoryBytes >= totalRam) {
                        Text(
                            "This phone may not have enough memory for ${selectedModel.title}; you can still install it and Lastbook will check the fit.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                    if (customName != null) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("Selected: $customName (unverified file you chose)", style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                            TextButton(onClick = { customUri = null; customName = null; modelId = best?.id }) { Text("Remove") }
                        }
                    }
                    val existingModels = File(rootPath, "models").listFiles()?.filter { it.isFile && it.name.endsWith(".gguf") }.orEmpty()
                    for (mf in existingModels) {
                        val isCatalog = catalog.models.any { it.files.any { f -> f.name == mf.name } }
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text(mf.name + (if (isCatalog) " (installed)" else " (unverified custom model)"),
                                style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                            TextButton(onClick = {
                                mf.delete()
                                if (LastbookCore.chat.selectedModelFile() == mf.name) LastbookCore.chat.setSelectedModel(null)
                                LastbookCore.chat.release()
                                rootPath = LastbookCore.paths.root.absolutePath
                            }) { Text("Delete") }
                        }
                    }
                }
            }

            Section("Where to save it") {
                Text(rootPath, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val buttonPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp)
                    OutlinedButton(
                        onClick = {
                            LastbookCore.paths.root = LastbookCore.paths.defaultRoot
                            rootPath = LastbookCore.paths.defaultRoot.absolutePath
                        },
                        modifier = Modifier.weight(1f),
                        contentPadding = buttonPadding
                    ) { Text("External app", maxLines = 1, overflow = TextOverflow.Ellipsis) }
                    OutlinedButton(
                        onClick = {
                            val internalRoot = File(context.filesDir, "LastbookData")
                            LastbookCore.paths.root = internalRoot
                            rootPath = internalRoot.absolutePath
                        },
                        modifier = Modifier.weight(1f),
                        contentPadding = buttonPadding
                    ) { Text("Internal app", maxLines = 1, overflow = TextOverflow.Ellipsis) }
                    OutlinedButton(
                        onClick = {
                            if (Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
                                error = "Allow all files access to choose a folder, or use app storage."
                                runCatching {
                                    context.startActivity(Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION, Uri.parse("package:${context.packageName}")))
                                }
                            } else folderPicker.launch(null)
                        },
                        modifier = Modifier.weight(1f),
                        contentPadding = buttonPadding
                    ) {
                        Icon(Icons.Default.Folder, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("Folder", maxLines = 1)
                    }
                }
            }

            val preview = LastbookCore.installer.plan(packId, stateId, wantAI, if (customUri != null) null else modelId)
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("What will be installed", fontWeight = FontWeight.SemiBold)
                    for (i in preview.items) if (i.state != ItemState.OPTED_OUT) {
                        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Text(i.title, modifier = Modifier.weight(1f))
                                Text(itemStateLabel(i.state, i), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            i.note?.let { note ->
                                Text(
                                    note,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (i.state == ItemState.UNAVAILABLE || i.kind == CatalogEntry.Kind.MODEL) {
                                        MaterialTheme.colorScheme.error
                                    } else {
                                        MaterialTheme.colorScheme.onSurfaceVariant
                                    },
                                )
                            }
                        }
                    }
                    if (customName != null && wantAI) {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text("Custom AI ($customName)", modifier = Modifier.weight(1f))
                            Text("Unverified GGUF", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    HorizontalDivider()
                    Text("To download: ${bytes(preview.downloadBytes)} · Room needed: ${bytes(preview.peakBytes)} · Free: ${bytes(preview.freeBytes)}",
                        style = MaterialTheme.typography.bodySmall)
                }
            }

            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(
                onClick = { startInstall() },
                enabled = stateId != null && (preview.items.any { it.state == ItemState.TO_DOWNLOAD } || (wantAI && customUri != null)),
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (manage) "Install or update" else "Install") }
            Spacer(Modifier.height(24.dp))
        }
    }

    if (showStatePicker) {
        StatePicker(maps, stateId) { stateId = it; showStatePicker = false }
    }
}

private fun selectedModelFile(id: String?, custom: String?): String? =
    if (custom != null) (if (custom.endsWith(".gguf", ignoreCase = true)) custom else "$custom.gguf")
    else LastbookCore.installCatalog.model(id ?: "")?.files?.firstOrNull()?.name

private fun modelLabel(catalog: local.lastbook.core.install.InstallCatalog, id: String?, custom: String?): String =
    when {
        custom != null -> "Custom model"
        id == null -> "No model"
        catalog.model(id) != null -> catalog.model(id)!!.title
        else -> "Auto"
    }

private fun itemStateLabel(state: ItemState, item: PlanItem): String = when (state) {
    ItemState.INSTALLED -> "Installed"
    ItemState.TO_DOWNLOAD -> if (item.downloadBytes > 0) "To download: ${bytes(item.downloadBytes)}" else "Included"
    ItemState.UNAVAILABLE -> "Not available"
    ItemState.OPTED_OUT -> "Off"
    ItemState.DOWNLOADING -> "Downloading"
    ItemState.CHECKING -> "Checking"
    ItemState.UNPACKING -> "Unpacking"
    ItemState.FINISHING -> "Finishing"
    ItemState.DONE -> "Done"
    ItemState.FAILED -> "Failed"
}

@Composable
private fun Section(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        content()
    }
}

@Composable
private fun StatePicker(maps: List<CatalogEntry>, selected: String?, onPick: (String) -> Unit) {
    var q by remember { mutableStateOf("") }
    val shown = maps.filter { q.isBlank() || it.title.contains(q, ignoreCase = true) || it.id.contains(q, ignoreCase = true) }
    AlertDialog(
        onDismissRequest = { },
        title = { Text("Choose your state") },
        text = {
            Column {
                OutlinedTextField(value = q, onValueChange = { q = it }, label = { Text("Search states") }, singleLine = true)
                Spacer(Modifier.height(8.dp))
                LazyColumn(Modifier.height(380.dp)) {
                    items(shown, key = { it.id }) { m ->
                        Row(
                            Modifier.fillMaxWidth().clickable { onPick(m.id) }.padding(vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            RadioButton(selected = m.id == selected, onClick = { onPick(m.id) })
                            Column(Modifier.weight(1f)) {
                                Text(m.title)
                                Text("${bytes(m.downloadBytes)} map", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = {}) { Text("") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProgressScreen(
    plan: Plan?, progress: InstallProgress?, paused: Boolean,
    onPause: () -> Unit, onResume: () -> Unit, onCancel: () -> Unit, onDone: () -> Unit,
    error: String?,
) {
    val items = plan?.items?.filter { it.state == ItemState.TO_DOWNLOAD } ?: emptyList()
    val active = progress
    Scaffold(topBar = { TopAppBar(title = { Text("Installing Lastbook") }) }) { pad ->
        Column(Modifier.fillMaxSize().padding(pad).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(if (paused) "Paused" else "Downloading and checking", style = MaterialTheme.typography.titleLarge)
            Text("The download continues while Lastbook is in the background. If the app stops, it carries on from where it stopped.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (active != null) {
                val now = active.overallDone + active.itemDone
                val fraction = if (active.overallTotal > 0) (now.toFloat() / active.overallTotal).coerceIn(0f, 1f) else 0f
                LinearProgressIndicator(progress = { fraction }, modifier = Modifier.fillMaxWidth())
                Text("${bytes(now)} of ${bytes(active.overallTotal)}", style = MaterialTheme.typography.bodySmall)
            } else CircularProgressIndicator()
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(items, key = { it.key }) { item ->
                    val state = if (active?.itemKey == item.key) active.state else item.state
                    Card {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(item.title, fontWeight = FontWeight.SemiBold)
                            Text(if (active?.itemKey == item.key) stateLabel(active) else itemStateLabel(state, item),
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            if (active?.itemKey == item.key && active.itemTotal > 0) {
                                LinearProgressIndicator(progress = { (active.itemDone.toFloat() / active.itemTotal).coerceIn(0f, 1f) },
                                    modifier = Modifier.fillMaxWidth())
                                Text("${bytes(active.itemDone)} of ${bytes(active.itemTotal)}", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                if (paused) Button(onClick = onResume, modifier = Modifier.weight(1f)) { Text("Resume") }
                else OutlinedButton(onClick = onPause, modifier = Modifier.weight(1f)) { Text("Pause") }
                OutlinedButton(onClick = onCancel) { Text("Cancel") }
            }
            if (active?.state == ItemState.DONE && !paused) Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("Open Lastbook") }
        }
    }
}

private fun stateLabel(p: InstallProgress): String = when (p.state) {
    ItemState.DOWNLOADING -> "Downloading ${bytes(p.itemDone)} of ${bytes(p.itemTotal)}"
    ItemState.CHECKING -> "Checking the file"
    ItemState.UNPACKING -> "Unpacking"
    ItemState.FINISHING -> "Finishing"
    ItemState.DONE -> "Done"
    ItemState.FAILED -> p.error ?: "Failed"
    else -> p.message
}

private fun treeToFile(context: android.content.Context, uri: Uri): File? {
    val docId = runCatching { android.provider.DocumentsContract.getTreeDocumentId(uri) }.getOrNull() ?: return null
    val parts = docId.split(':', limit = 2)
    val volume = parts.getOrNull(0) ?: return null
    val path = parts.getOrNull(1) ?: ""
    val base = when (volume) {
        "primary" -> Environment.getExternalStorageDirectory()
        else -> File("/storage/$volume")
    }
    return File(base, path)
}

private fun queryName(context: android.content.Context, uri: Uri): String? = runCatching {
    context.contentResolver.query(uri, null, null, null, null)?.use { c ->
        val i = c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
        if (i >= 0 && c.moveToFirst()) c.getString(i) else null
    }
}.getOrNull()

private fun copyCustomModel(context: android.content.Context, uri: Uri, name: String) {
    val dir = LastbookCore.paths.root.resolve("models").apply { mkdirs() }
    val safeName = if (name.endsWith(".gguf", ignoreCase = true)) name else "$name.gguf"
    val dst = File(dir, safeName)
    context.contentResolver.openInputStream(uri)?.use { input ->
        val header = ByteArray(4)
        val n = input.read(header)
        if (n < 4 || String(header, Charsets.US_ASCII) != "GGUF") {
            throw IllegalStateException("That file is not a GGUF model (missing GGUF header).")
        }
        dst.outputStream().use { out ->
            out.write(header, 0, 4)
            input.copyTo(out)
        }
    } ?: throw IllegalStateException("Could not open the selected model file.")
}
