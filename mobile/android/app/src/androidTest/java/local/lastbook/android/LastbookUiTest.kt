package local.lastbook.android

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import local.lastbook.android.ui.ChatScreen
import local.lastbook.android.ui.LibraryScreen
import local.lastbook.android.ui.SetupScreen
import local.lastbook.android.ui.theme.LastbookTheme
import local.lastbook.core.LastbookCore
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LastbookUiTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun setupInterruptedInstallResumeAndSelectionFlow() {
        val jobFile = LastbookCore.paths.installJobFile
        jobFile.parentFile?.mkdirs()
        jobFile.writeText(JSONObject(mapOf("pack" to "small", "state" to "RI", "model" to "gemma-4-e2b", "ai" to true)).toString())
        try {
            composeRule.setContent {
                LastbookTheme {
                    SetupScreen(manage = false, onDone = {})
                }
            }
            composeRule.onNodeWithText("An install was interrupted").assertIsDisplayed()
            composeRule.onNodeWithText("Resume install").assertIsDisplayed()
            composeRule.onNodeWithText("Choose your state").performScrollTo().assertIsDisplayed()
            composeRule.onNodeWithText("Small").performScrollTo().assertIsDisplayed()
            composeRule.onNodeWithText("Add local AI").performScrollTo().assertIsDisplayed()
        } finally {
            jobFile.delete()
        }
    }

    @Test
    fun libraryReadinessAndFilterFlow() {
        composeRule.setContent {
            LastbookTheme {
                LibraryScreen(onManage = {}, onOpen = { _, _ -> }, onOpenVideo = {}, onOpenZim = {})
            }
        }
        composeRule.onNodeWithText("On this phone").assertIsDisplayed()
        composeRule.onNodeWithText("Install or change library…").assertIsDisplayed()
        composeRule.onNodeWithText("Reading").assertIsDisplayed()
        composeRule.onNodeWithText("Videos").assertIsDisplayed()
        composeRule.onAllNodesWithText("Encyclopedias").onFirst().assertIsDisplayed()
    }

    @Test
    fun chatStartersAndHistoryFlow() {
        composeRule.setContent {
            LastbookTheme {
                ChatScreen(onOpenVideo = { _, _ -> }, onOpenDoc = { _, _ -> }, onManage = {})
            }
        }
        composeRule.onNodeWithText("Ask the library").assertIsDisplayed()
        composeRule.onNodeWithText("Try one of these").assertIsDisplayed()
    }
}
