import SwiftUI
import Foundation
import WebKit

/// ZIM encyclopedias on iPhone through CoreKiwix.xcframework (libkiwix/libzim, GPL-3.0). Only the iPhone target links
/// this framework; the iPad target is unchanged.
final class PhoneZimArchives {
    static let shared = PhoneZimArchives()
    private let lock = NSLock()
    private var open: [String: UnsafeMutableRawPointer] = [:]

    func archive(_ name: String) -> UnsafeMutableRawPointer? {
        lock.lock(); defer { lock.unlock() }
        if let a = open[name] { return a }
        guard let lib = Library.shared.lib else { return nil }
        let file = lib.appendingPathComponent("collections/\(name)")
        guard FileManager.default.fileExists(atPath: file.path), let a = lb_zim_open(file.path) else { return nil }
        open[name] = a
        return a
    }

    deinit { for a in open.values { lb_zim_close(a) } }
}

struct PhoneZimAPI: RouteGroup {
    func handle(_ r: APIRequest) -> APIResponse? {
        if r.path == "/api/zim" {
            return .json(LibraryAPI.zimNames())
        }
        if r.path == "/api/zim/search" {
            let name = r.q("name"), q = r.q("q"), full = r.q("full") == "1"
            guard let a = PhoneZimArchives.shared.archive(name) else { return .json([Any]()) }
            guard let c = lb_zim_search(a, q, full, 30) else { return .json([Any]()) }
            defer { lb_zim_free(c) }
            let s = String(cString: c)
            let data = Data(s.utf8)
            let obj = (try? JSONSerialization.jsonObject(with: data)) ?? [Any]()
            return .json(obj)
        }
        guard r.path.hasPrefix("/zim/") else { return nil }
        let rest = String(r.path.dropFirst(5))
        let name = rest.split(separator: "/", maxSplits: 1).first.map(String.init) ?? ""
        let path = rest.split(separator: "/", maxSplits: 1).count > 1 ? String(rest.split(separator: "/", maxSplits: 1)[1]) : ""
        guard !name.isEmpty, let a = PhoneZimArchives.shared.archive(name) else { return .notFound() }
        var mime: UnsafeMutablePointer<CChar>? = nil
        var length = 0
        guard let bytes = lb_zim_item(a, path, &mime, &length), length >= 0 else { return .notFound() }
        defer { lb_zim_free(bytes) }
        let mimeString = mime.map { String(cString: $0) } ?? "application/octet-stream"
        lb_zim_free(mime)
        var data = Data(bytes: bytes, count: length)
        if mimeString.hasPrefix("text/html") {
            var html = String(decoding: data, as: UTF8.self)
            let prefix = "/zim/\(name)/"
            html = html.replacingOccurrences(of: "href=\"/", with: "href=\"\(prefix)")
                .replacingOccurrences(of: "src=\"/", with: "src=\"\(prefix)")
            if !html.lowercased().contains("<base ") {
                html = html.replacingOccurrences(of: "<head>", with: "<head><base href=\"\(prefix)\">", options: .caseInsensitive)
            }
            data = Data(html.utf8)
        }
        return APIResponse(status: 200, mime: mimeString, headers: ["Cache-Control": "max-age=86400"], body: .data(data))
    }
}

/// One WKWebView on lastbook://app/zim/<name>/, using the same in-process scheme handler as the rest of the app.
final class PhoneZimController: NSObject, ObservableObject, WKNavigationDelegate {
    let name: String
    private let scheme = SchemeHandler()
    private(set) var web: WKWebView?
    @Published private(set) var loading = true
    @Published private(set) var canGoBack = false
    @Published private(set) var canGoForward = false
    init(name: String) { self.name = name }

    func makeWeb() -> WKWebView {
        if let web { return web }
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(scheme, forURLScheme: "lastbook")
        cfg.websiteDataStore = .default()
        cfg.allowsInlineMediaPlayback = true
        cfg.defaultWebpagePreferences.preferredContentMode = .desktop
        cfg.userContentController.addUserScript(WKUserScript(source: scheme.topScript(), injectionTime: .atDocumentStart, forMainFrameOnly: true))
        let v = WKWebView(frame: .zero, configuration: cfg)
        v.navigationDelegate = self
        v.allowsBackForwardNavigationGestures = true
        #if DEBUG
        v.isInspectable = true
        #endif
        v.load(URLRequest(url: URL(string: SchemeHandler.origin + "/zim/\(name)/")!))
        web = v
        return v
    }

    func load(_ path: String) {
        let enc = path.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed.subtracting(CharacterSet(charactersIn: "/"))) ?? path
        web?.load(URLRequest(url: URL(string: SchemeHandler.origin + "/zim/\(name)/\(enc)")!))
    }

    func goBack() { web?.goBack() }
    func goForward() { web?.goForward() }
    func goHome() { web?.load(URLRequest(url: URL(string: SchemeHandler.origin + "/zim/\(name)/")!)) }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        loading = false
        canGoBack = webView.canGoBack
        canGoForward = webView.canGoForward
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }
}

struct PhoneZimCanvas: UIViewRepresentable {
    let controller: PhoneZimController
    func makeUIView(context: Context) -> WKWebView { controller.makeWeb() }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}
