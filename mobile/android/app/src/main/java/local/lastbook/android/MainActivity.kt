package local.lastbook.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import local.lastbook.android.ui.LastbookRoot
import local.lastbook.android.ui.theme.LastbookTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            LastbookTheme {
                LastbookRoot()
            }
        }
    }
}
