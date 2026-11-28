import Foundation
#if canImport(UIKit)
import UIKit
#endif

/// The device the person is holding, for the few sentences the shared engine shows ("this iPhone" / "this iPad").
enum DeviceName {
    static var thisOne: String {
        #if canImport(UIKit)
        return UIDevice.current.userInterfaceIdiom == .pad ? "iPad" : "iPhone"
        #else
        return "iPad"
        #endif
    }
}
