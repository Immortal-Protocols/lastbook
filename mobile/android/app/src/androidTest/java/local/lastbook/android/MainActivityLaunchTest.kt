package local.lastbook.android

import android.content.Intent
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isSelectable
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import local.lastbook.android.data.Services
import local.lastbook.core.LastbookCore
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class MainActivityLaunchTest {

    @get:Rule
    val composeRule = createEmptyComposeRule()

    private lateinit var tempLibraryRoot: File
    private lateinit var libraryPathFile: File
    private var previousLibraryPath: String? = null
    private lateinit var chatsFile: File
    private var previousChatsJson: String? = null

    @Before
    fun setUp() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        libraryPathFile = File(LastbookCore.paths.settingsDir, "library-path.txt")
        previousLibraryPath = libraryPathFile.takeIf { it.isFile }?.readText()

        chatsFile = File(File(context.filesDir, "Chats"), "chats.json")
        previousChatsJson = chatsFile.takeIf { it.isFile }?.readText()

        tempLibraryRoot = File(context.cacheDir, "launch-test-library-${System.nanoTime()}").apply {
            File(this, "library-data").mkdirs()
            File(this, "library-data/catalog.json").writeText("[]")
        }
        LastbookCore.paths.root = tempLibraryRoot
        LastbookCore.reloadLibrary()
        Services.chat.deleteAll()
    }

    @After
    fun tearDown() {
        Services.chat.stop()
        Services.chat.deleteAll()
        if (previousChatsJson != null) {
            chatsFile.parentFile?.mkdirs()
            chatsFile.writeText(previousChatsJson!!)
        } else {
            chatsFile.delete()
        }

        if (previousLibraryPath != null) {
            libraryPathFile.parentFile?.mkdirs()
            libraryPathFile.writeText(previousLibraryPath!!)
        } else {
            libraryPathFile.delete()
        }
        tempLibraryRoot.deleteRecursively()
        LastbookCore.reloadLibrary()
    }

    private fun launcherIntent(configure: Intent.() -> Unit = {}): Intent {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        return Intent(context, MainActivity::class.java).apply {
            action = Intent.ACTION_MAIN
            addCategory(Intent.CATEGORY_LAUNCHER)
            configure()
        }
    }

    @Test
    fun normalLaunchOpensLastbookOnVideosTab() {
        ActivityScenario.launch<MainActivity>(launcherIntent()).use {
            composeRule.waitForIdle()
            composeRule.onNodeWithText("Watch it done — practical how-tos first").assertIsDisplayed()
            composeRule.onNode(hasText("Videos") and isSelectable()).assertIsDisplayed()
            composeRule.onNode(hasText("Map") and isSelectable()).assertIsDisplayed()
            composeRule.onNode(hasText("Chat") and isSelectable()).assertIsDisplayed()
            composeRule.onNode(hasText("Library") and isSelectable()).assertIsDisplayed()
            assertTrue(Services.chat.chats.isEmpty())
            assertNull(Services.chat.current)
        }
    }

    @Test
    fun unsupportedLaunchInputsCreateNoChatOrNavigationError() {
        val injectedQuestion = "Injected external question that must not auto-send"
        val intent = launcherIntent {
            putExtra("lb_tab", "library")
            putExtra("lb_route", "invalid/external/destination")
            putExtra("lb_ask", injectedQuestion)
        }
        ActivityScenario.launch<MainActivity>(intent).use {
            composeRule.waitForIdle()
            // Wait past the previous 500ms delayed auto-send window to verify nothing triggers.
            Thread.sleep(750)
            composeRule.waitForIdle()

            // Launcher stays on the normal default Videos destination with no navigation error.
            composeRule.onNodeWithText("Watch it done — practical how-tos first").assertIsDisplayed()
            assertTrue(Services.chat.chats.isEmpty())
            assertNull(Services.chat.current)
            val savedChats = chatsFile.takeIf { it.isFile }?.readText().orEmpty()
            assertFalse(savedChats.contains(injectedQuestion))
        }
    }

    @Test
    fun inAppNavigationAndDeliberateOfflineChatSendWork() {
        val deliberateQuestion = "How do I purify drinking water?"
        ActivityScenario.launch<MainActivity>(launcherIntent()).use {
            composeRule.waitForIdle()
            composeRule.onNodeWithText("Watch it done — practical how-tos first").assertIsDisplayed()

            // Navigate to Library via in-app bottom navigation.
            composeRule.onNode(hasText("Library") and isSelectable()).performClick()
            composeRule.onNodeWithText("On this phone").assertIsDisplayed()

            // Navigate to Chat via in-app bottom navigation.
            composeRule.onNode(hasText("Chat") and isSelectable()).performClick()
            composeRule.onNodeWithText("Ask the library").assertIsDisplayed()

            // Deliberately type and send a question offline.
            composeRule.onNodeWithText("Ask a question…").performTextInput(deliberateQuestion)
            composeRule.onNodeWithContentDescription("Send").performClick()

            composeRule.waitUntil(timeoutMillis = 10_000) {
                Services.chat.current?.messages?.lastOrNull()?.running == false
            }
            composeRule.waitForIdle()

            composeRule.onNodeWithText(deliberateQuestion).assertIsDisplayed()
            assertEquals(1, Services.chat.chats.size)
            assertEquals(deliberateQuestion, Services.chat.chats.first().title)

            // Wait for the soft keyboard to dismiss so the bottom bar returns, then navigate back to Videos.
            composeRule.waitUntil(timeoutMillis = 5_000) {
                composeRule.onAllNodes(hasText("Videos") and isSelectable()).fetchSemanticsNodes().isNotEmpty()
            }
            composeRule.onNode(hasText("Videos") and isSelectable()).performClick()
            composeRule.onNodeWithText("Watch it done — practical how-tos first").assertIsDisplayed()
        }
    }
}
