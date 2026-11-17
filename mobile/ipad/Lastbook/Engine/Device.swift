import Foundation
#if canImport(UIKit)
import UIKit
#endif

/// The word on-screen text uses for this device: "iPhone" or "iPad" (so "Files › On My iPhone › Lastbook" matches what the
/// Files app shows). The Mac test tools build the engine without UIKit and read "iPad", as before.
enum Device {
    static let name: String = {
        #if canImport(UIKit)
        return UIDevice.current.userInterfaceIdiom == .phone ? "iPhone" : "iPad"
        #else
        return "iPad"
        #endif
    }()
    /// The system's name, for text such as "iOS asked for memory back".
    static var os: String { name == "iPhone" ? "iOS" : "iPadOS" }
}
