package local.lastbook.android.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import local.lastbook.core.LastbookCore

@Composable
fun LastbookRoot() {
    var hasLibrary by remember { mutableStateOf(LastbookCore.reloadLibrary()) }
    var setup by remember { mutableStateOf(!hasLibrary) }
    var manage by remember { mutableStateOf(false) }

    if (setup) {
        SetupScreen(manage = manage, onDone = {
            hasLibrary = LastbookCore.reloadLibrary()
            setup = !hasLibrary
            manage = false
        })
    } else {
        MainShell(onManage = { manage = true; setup = true })
    }
}
