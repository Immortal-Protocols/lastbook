import XCTest

/// Small, targeted UI proof for the iPhone app: the four destinations, the phone Library screen, the setup sheet
/// (including the phone AI tier picker) and the ZIM reader. The heavy flows (downloads, AI generation) are proved by
/// the seeded-data screenshots and the Android engine tests; these catch navigation and shell regressions.
final class PhoneSmokeUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testFourDestinationsAndPhoneLibrary() throws {
        let app = XCUIApplication()
        app.launchArguments += ["-LBTab", "videos"]
        app.launch()
        let tabs = app.tabBars
        XCTAssertTrue(tabs.buttons["Videos"].waitForExistence(timeout: 20))
        XCTAssertTrue(tabs.buttons["Map"].exists)
        XCTAssertTrue(tabs.buttons["Chat"].exists)
        XCTAssertTrue(tabs.buttons["Library"].exists)

        tabs.buttons["Library"].tap()
        XCTAssertTrue(app.staticTexts["On this iPhone"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.navigationBars["Library"].waitForExistence(timeout: 10))

        tabs.buttons["Chat"].tap()
        XCTAssertTrue(app.textFields.firstMatch.waitForExistence(timeout: 10))
    }

    func testPhoneSetupSheetAndAITierPicker() throws {
        let app = XCUIApplication()
        app.launchArguments += ["-LBShowInstall", "YES"]
        app.launch()
        XCTAssertTrue(app.staticTexts["Install Lastbook"].waitForExistence(timeout: 20))
        XCTAssertTrue(app.staticTexts["Phone AI Tier & Storage"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["Import Custom .gguf…"].exists)
        XCTAssertTrue(app.buttons["Done"].exists)
    }

    func testZimReaderOpensAnArticle() throws {
        let app = XCUIApplication()
        app.launchArguments += ["-LBTab", "library", "-LBZim", "appropedia_en_all_maxi_2026-02.zim"]
        app.launch()
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 25))
    }
}
