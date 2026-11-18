import SwiftUI
import WebKit

/// The desktop UI (web/) in one WKWebView at lastbook://app/. No network: the custom scheme answers everything,
/// and any other address is refused unless the person taps a web link and agrees to leave the app.
struct WebHost: UIViewRepresentable {
    var onChangeLibrary: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onChangeLibrary: onChangeLibrary) }

    func makeUIView(context: Context) -> WKWebView {
        let c = context.coordinator
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(c.scheme, forURLScheme: "lastbook")
        cfg.websiteDataStore = .default()   // on this iPad only: keeps chats (if the person keeps them), bookmarks and view settings, as desktop
        cfg.allowsInlineMediaPlayback = true
        cfg.mediaTypesRequiringUserActionForPlayback = []
        cfg.allowsPictureInPictureMediaPlayback = true
        cfg.defaultWebpagePreferences.preferredContentMode = .desktop
        cfg.dataDetectorTypes = []
        cfg.userContentController.addUserScript(WKUserScript(source: c.scheme.topScript(), injectionTime: .atDocumentStart, forMainFrameOnly: true))
        cfg.userContentController.addUserScript(WKUserScript(source: "document.documentElement.classList.add('plat-ipad')", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        if let u = Bundle.main.url(forResource: "ipad-copy", withExtension: "js"), let js = try? String(contentsOf: u, encoding: .utf8) {
            // iPad wording for a few desktop sentences ("this computer", desktop folders); the shared web/ files stay as they are
            cfg.userContentController.addUserScript(WKUserScript(source: js, injectionTime: .atDocumentEnd, forMainFrameOnly: true))
        }
        cfg.userContentController.add(c, name: "lastbook")
        let v = WKWebView(frame: .zero, configuration: cfg)
        v.navigationDelegate = c
        v.uiDelegate = c
        v.allowsBackForwardNavigationGestures = true
        #if DEBUG
        v.isInspectable = true
        #endif
        c.view = v
        // Tests open a page directly: simctl launch ... -LBRoute '#/map' (launch arguments land in UserDefaults).
        let route = UserDefaults.standard.string(forKey: "LBRoute").flatMap { $0.hasPrefix("#") ? $0 : nil } ?? ""
        v.load(URLRequest(url: URL(string: SchemeHandler.origin + "/" + route)!))
        return v
    }

    func updateUIView(_ v: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
        let scheme = SchemeHandler()
        weak var view: WKWebView?
        let onChangeLibrary: () -> Void
        init(onChangeLibrary: @escaping () -> Void) { self.onChangeLibrary = onChangeLibrary }

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, preferences: WKWebpagePreferences) async -> (WKNavigationActionPolicy, WKWebpagePreferences) {
            let url = action.request.url
            let own = url?.scheme == "lastbook" && url?.host == "app"
            if own, url?.path == "/ui/setup.html" {   // desktop's "Library and local AI" page: on iPad, the native library picker
                await MainActor.run { onChangeLibrary() }
                return (.cancel, preferences)
            }
            if own || url?.scheme == "about" || url?.scheme == "blob" {
                if let t = action.targetFrame, !t.isMainFrame { preferences.allowsContentJavaScript = false }   // saved pages run no scripts
                if action.targetFrame == nil, own, let u = url {   // target=_blank on our own page: show it in the one window
                    let route = u.fragment.map { "#" + $0 } ?? "#/"
                    if u.path == "/" || u.path.isEmpty { _ = try? await webView.evaluateJavaScript("location.hash=" + jsString(route)) }
                    return (.cancel, preferences)
                }
                return (.allow, preferences)
            }
            if let u = url, ["http", "https"].contains(u.scheme ?? ""), action.navigationType == .linkActivated || action.targetFrame == nil {
                await MainActor.run { self.offerToLeave(u) }
            }
            return (.cancel, preferences)
        }

        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let u = action.request.url, ["http", "https"].contains(u.scheme ?? "") { offerToLeave(u) }
            else if let u = action.request.url, u.scheme == "lastbook" {
                webView.evaluateJavaScript("location.hash=" + jsString(u.fragment.map { "#" + $0 } ?? "#/"))
            }
            return nil
        }

        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }

        #if DEBUG
        /// Simulator tests only (never in a release build): simctl launch ... -LBEval 'js' runs once, 3 s after the first page loads.
        private var evaluated = false
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            guard !evaluated, let js = UserDefaults.standard.string(forKey: "LBEval") else { return }
            evaluated = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                webView.evaluateJavaScript(js) { r, e in NSLog("LBEval result: %@ %@", String(describing: r), String(describing: e)) }
            }
        }
        #endif

        func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
            if (message.body as? String) == "change-library" { onChangeLibrary() }
        }

        /// The only way out to the internet: a web link the person tapped, and only after they agree.
        @MainActor func offerToLeave(_ u: URL) {
            guard let top = view?.window?.rootViewController else { return }
            let a = UIAlertController(title: "Open on the internet?", message: "\(u.host ?? u.absoluteString) is a web page, not part of your offline library. Safari will open it if this iPad is online.", preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "Stay here", style: .cancel))
            a.addAction(UIAlertAction(title: "Open in Safari", style: .default) { _ in UIApplication.shared.open(u) })
            (top.presentedViewController ?? top).present(a, animated: true)
        }

        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo) async {
            await withCheckedContinuation { (k: CheckedContinuation<Void, Never>) in
                Task { @MainActor in
                    guard let top = webView.window?.rootViewController else { k.resume(); return }
                    let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
                    a.addAction(UIAlertAction(title: "OK", style: .default) { _ in k.resume() })
                    top.present(a, animated: true)
                }
            }
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo) async -> Bool {
            await withCheckedContinuation { (k: CheckedContinuation<Bool, Never>) in
                Task { @MainActor in
                    guard let top = webView.window?.rootViewController else { k.resume(returning: false); return }
                    let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
                    a.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in k.resume(returning: false) })
                    a.addAction(UIAlertAction(title: "OK", style: .default) { _ in k.resume(returning: true) })
                    top.present(a, animated: true)
                }
            }
        }
    }
}

func jsString(_ s: String) -> String {
    let d = try? JSONSerialization.data(withJSONObject: [s])
    return d.flatMap { String(data: $0, encoding: .utf8) }.map { String($0.dropFirst().dropLast()) } ?? "''"
}
