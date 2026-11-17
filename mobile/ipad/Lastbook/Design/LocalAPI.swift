import Foundation
import UIKit
import ImageIO

/// The native UI's only door into the engine: the same in-process router the web view uses (SchemeHandler), called
/// directly. No port, no network, no new engine API. Every answer is exactly what lastbook://app/<path> would return.
enum LocalAPI {
    /// GET an /api/ path. Runs off the main thread; returns parsed JSON or nil (with the status code for honest errors).
    static func get(_ path: String, _ query: [String: String] = [:]) async -> (Any?, Int) {
        await Task.detached(priority: .userInitiated) {
            let r = Router.shared.route(APIRequest(method: "GET", path: path, query: query, headers: [:], body: nil))
            guard case .data(let d) = r.body else { return (nil, r.status) }
            return (try? JSONSerialization.jsonObject(with: d, options: [.fragmentsAllowed]), r.status)
        }.value
    }

    static func rec(_ path: String, _ query: [String: String] = [:]) async -> Rec? { (await get(path, query)).0 as? Rec }
    static func recs(_ path: String, _ query: [String: String] = [:]) async -> [Rec] { ((await get(path, query)).0 as? [Rec]) ?? [] }

    /// A library file (video, thumbnail, transcript) as the router serves it: below library-data, allowed prefixes only,
    /// and with the H.264 copy substituted for an AV1 original on iPads that can't decode AV1 (VideoCompat).
    static func fileURL(_ libraryPath: String) -> URL? {
        guard !libraryPath.isEmpty else { return nil }
        let p = libraryPath.hasPrefix("/") ? libraryPath : "/" + libraryPath
        let r = Router.shared.route(APIRequest(method: "GET", path: p, query: [:], headers: [:], body: nil))
        if case .file(let u) = r.body { return u }
        return nil
    }

    /// A PDF page drawn by the engine (PDFKit), as the chat source cards show it.
    static func pageImage(doc: String, page: Int, width: Int = 300) async -> UIImage? {
        await Task.detached(priority: .utility) {
            let r = Router.shared.route(APIRequest(method: "GET", path: "/api/page/\(doc)/\(page).png", query: ["w": "\(width)"], headers: [:], body: nil))
            if case .data(let d) = r.body, r.status == 200 { return UIImage(data: d) }
            return nil
        }.value
    }

    /// POST (chat). Returns the response; the caller drives a stream body.
    static func post(_ path: String, json: Rec) -> APIResponse {
        let body = try? JSONSerialization.data(withJSONObject: json)
        return Router.shared.route(APIRequest(method: "POST", path: path, query: [:], headers: ["content-type": "application/json"], body: body))
    }
}

/// Downsampled thumbnails from library files, cached in memory.
final class Thumbs: @unchecked Sendable {
    static let shared = Thumbs()
    private let cache = NSCache<NSString, UIImage>()
    init() { cache.countLimit = 400 }

    func image(_ libraryPath: String, maxPixel: CGFloat = 640) async -> UIImage? {
        let key = "\(libraryPath)@\(Int(maxPixel))" as NSString
        if let i = cache.object(forKey: key) { return i }
        let img: UIImage? = await Task.detached(priority: .utility) {
            guard let u = LocalAPI.fileURL(libraryPath), let src = CGImageSourceCreateWithURL(u as CFURL, nil) else { return nil }
            let opts: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceThumbnailMaxPixelSize: maxPixel,
                                         kCGImageSourceCreateThumbnailWithTransform: true]
            guard let cg = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary) else { return nil }
            return UIImage(cgImage: cg)
        }.value
        if let img { cache.setObject(img, forKey: key) }
        return img
    }
}

enum Fmt {
    static func clock(_ s: Double) -> String {
        let t = Int(max(0, s.rounded(.down)))
        return t >= 3600 ? String(format: "%d:%02d:%02d", t / 3600, t / 60 % 60, t % 60) : String(format: "%d:%02d", t / 60, t % 60)
    }
    /// "12 min", "1 h 05 min"
    static func duration(_ s: Double) -> String {
        guard s > 0 else { return "" }
        let m = Int((s / 60).rounded())
        return m >= 60 ? "\(m / 60) h \(String(format: "%02d", m % 60)) min" : "\(max(1, m)) min"
    }
}
