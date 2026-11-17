import SwiftUI
import WebKit

/// One page of the bundled library UI (the offline map, or a reading page) inside a native screen.
/// Security is the 0.1 shell's, unchanged: the same in-process scheme handler (no port), launch key, script-free frames
/// for saved pages, and the "Open on the internet?" confirmation, all from WebHost.Coordinator. The desktop's own
/// header, sidebar and tab bar are hidden by an iPad-only stylesheet injected here; the shared web/ source is untouched.
/// Links that would leave this page's kind (to a video, chat or another destination) come back to Swift and open natively.
struct LibraryWebView: UIViewRepresentable {
    enum Kind { case map, reader }
    let kind: Kind
    let route: String
    var command: String? = nil              // a route to switch to (map focus from a chat source)
    var onLink: (String) -> Void
    var onChangeLibrary: () -> Void
    @Environment(\.dynamicTypeSize) private var dts

    func makeCoordinator() -> Coord { Coord(onLink: onLink, host: WebHost.Coordinator(onChangeLibrary: onChangeLibrary)) }

    func makeUIView(context: Context) -> WKWebView {
        let c = context.coordinator
        let h = c.host
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(h.scheme, forURLScheme: "lastbook")
        cfg.websiteDataStore = .default()
        cfg.allowsInlineMediaPlayback = true
        cfg.allowsPictureInPictureMediaPlayback = true
        cfg.defaultWebpagePreferences.preferredContentMode = .desktop
        cfg.dataDetectorTypes = []
        let ucc = cfg.userContentController
        ucc.addUserScript(WKUserScript(source: h.scheme.topScript(), injectionTime: .atDocumentStart, forMainFrameOnly: true))
        ucc.addUserScript(WKUserScript(source: "document.documentElement.classList.add('plat-ipad','lb-embed','lb-\(kind == .map ? "map" : "reader")')", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        ucc.addUserScript(WKUserScript(source: Self.styleScript(kind == .map ? EmbedCSS.common + EmbedCSS.map : EmbedCSS.common + EmbedCSS.reader), injectionTime: .atDocumentStart, forMainFrameOnly: true))
        ucc.addUserScript(WKUserScript(source: Self.linkGuard(kind), injectionTime: .atDocumentStart, forMainFrameOnly: true))
        if let u = Bundle.main.url(forResource: "ipad-copy", withExtension: "js"), let js = try? String(contentsOf: u, encoding: .utf8) {
            ucc.addUserScript(WKUserScript(source: js, injectionTime: .atDocumentEnd, forMainFrameOnly: true))   // engine 0.3: iPad wording, as WebHost
        }
        ucc.add(h, name: "lastbook")
        ucc.add(c, name: "lbnative")
        let v = WKWebView(frame: .zero, configuration: cfg)
        v.navigationDelegate = h
        v.uiDelegate = h
        v.allowsBackForwardNavigationGestures = false
        v.isOpaque = false
        v.backgroundColor = .systemBackground
        v.pageZoom = Self.zoom(dts)
        #if DEBUG
        v.isInspectable = true
        #endif
        h.view = v
        c.lastCommand = command
        #if DEBUG
        if kind == .map, let js = UserDefaults.standard.string(forKey: "LBMapEval") {   // simulator review: e.g. open a place
            DispatchQueue.main.asyncAfter(deadline: .now() + 5) { v.evaluateJavaScript(js) { r, e in NSLog("LBMapEval %@ %@", String(describing: r), String(describing: e)) } }
        }
        #endif
        v.load(URLRequest(url: URL(string: SchemeHandler.origin + "/" + route)!))
        return v
    }

    func updateUIView(_ v: WKWebView, context: Context) {
        let z = Self.zoom(dts)
        if abs(v.pageZoom - z) > 0.01 { v.pageZoom = z }
        if let cmd = command, cmd != context.coordinator.lastCommand {
            context.coordinator.lastCommand = cmd
            v.evaluateJavaScript("location.hash=" + jsString(cmd))
        }
    }

    static func dismantleUIView(_ v: WKWebView, coordinator: Coord) {
        v.configuration.userContentController.removeScriptMessageHandler(forName: "lastbook")
        v.configuration.userContentController.removeScriptMessageHandler(forName: "lbnative")
    }

    /// Dynamic Type for the web page: the page (panels, labels) scales with the person's text size.
    static func zoom(_ d: DynamicTypeSize) -> CGFloat {
        switch d {
        case .xSmall, .small: return 0.9
        case .medium, .large: return 1
        case .xLarge: return 1.08
        case .xxLarge: return 1.16
        case .xxxLarge: return 1.24
        case .accessibility1: return 1.36
        case .accessibility2: return 1.48
        default: return 1.6
        }
    }

    static func styleScript(_ css: String) -> String {
        "(()=>{const s=document.createElement('style');s.id='lb-embed-css';s.textContent=\(jsString(css));(document.head||document.documentElement).appendChild(s)})()"
    }

    /// Catches in-page links before the page's router follows them. Map: anything not #/map. Reader: anything not #/read.
    static func linkGuard(_ k: Kind) -> String {
        let keep = k == .map ? "#/map" : "#/read/"
        return """
        (()=>{const keep=\(jsString(keep));
        const out=h=>h&&h.startsWith('#/')&&!h.startsWith(keep);
        document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[href^="#/"]');if(!a)return;const h=a.getAttribute('href');
          if(out(h)){e.preventDefault();e.stopImmediatePropagation();window.webkit.messageHandlers.lbnative.postMessage({open:h})}},true);
        addEventListener('hashchange',e=>{if(out(location.hash)){const h=location.hash;history.back();window.webkit.messageHandlers.lbnative.postMessage({open:h})}});
        })()
        """
    }

    final class Coord: NSObject, WKScriptMessageHandler {
        let onLink: (String) -> Void
        let host: WebHost.Coordinator
        var lastCommand: String?
        init(onLink: @escaping (String) -> Void, host: WebHost.Coordinator) { self.onLink = onLink; self.host = host }
        func userContentController(_ ucc: WKUserContentController, didReceive m: WKScriptMessage) {
            guard m.frameInfo.isMainFrame, let d = m.body as? [String: Any], let h = d["open"] as? String, h.hasPrefix("#/") else { return }
            onLink(h)
        }
    }
}

/// iPad-only styling of the bundled web pages. Hides the desktop chrome; the native tab bar and toolbar replace it.
enum EmbedCSS {
    static let common = """
    html.lb-embed .side,html.lb-embed header.top,html.lb-embed .tabbar,html.lb-embed .capband,html.lb-embed #sideBtn,html.lb-embed .skip{display:none!important}
    html.lb-embed body{padding:0!important;margin:0!important;background:var(--bg)}
    html.lb-embed{--top-h:0px;--bar-h:0px;scroll-padding-top:16px}
    """

    /// Apple Maps on iPad: the map fills the screen; a floating panel on the leading edge holds search, results and the
    /// selected place (the place card covers the results; closing it returns to them with the map unchanged).
    static let map = """
    html.lb-map,html.lb-map body{height:100%;overflow:hidden}
    html.lb-map main.map-page{position:fixed;inset:0;padding:0!important;margin:0!important;max-width:none!important;min-height:0}
    html.lb-map .maphead{display:none!important}
    html.lb-map .mapgrid{display:block!important}
    html.lb-map .mapwrap{position:fixed!important;inset:0!important;height:auto!important;min-height:0!important;border-radius:0!important;border:0!important;box-shadow:none!important}
    html.lb-map #map-full,html.lb-map #gps{display:none!important}
    html.lb-map .map-top{left:16px;top:16px;right:auto;width:360px;flex-wrap:nowrap}
    html.lb-map .map-search{flex:1 1 auto;border-radius:14px;box-shadow:0 2px 14px rgba(0,0,0,.18)}
    html.lb-map .map-search input,html.lb-map .map-layers-btn{height:48px;font-size:17px}
    html.lb-map .map-layers-btn{position:fixed;right:76px;top:16px;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.16)}
    html.lb-map .map-pop,html.lb-map .map-card,html.lb-map .maptools{left:16px!important;width:360px!important;border-radius:16px!important;box-shadow:0 6px 30px rgba(0,0,0,.22)!important}
    html.lb-map .map-pop,html.lb-map .map-card{top:76px!important;max-height:calc(100% - 92px)!important}
    html.lb-map .maptools{position:fixed!important;top:76px;bottom:16px;max-height:none!important;margin:0!important;overflow:auto;z-index:3;background:var(--bg);padding:6px;display:grid;gap:0;align-content:start}
    html.lb-map .maptools .panel{border:0!important;box-shadow:none!important;background:transparent!important;padding:12px 12px 14px!important;border-bottom:1px solid var(--line2)!important;border-radius:0!important}
    html.lb-map .maptools .panel:last-child{border-bottom:0!important}
    html.lb-map .mapgrid:has(#card:not([hidden])) .maptools,html.lb-map .mapgrid:has(#pres:not([hidden])) .maptools,html.lb-map .mapgrid:has(#layers:not([hidden])) .maptools{visibility:hidden}
    html.lb-map .maptools h2{font-size:19px;margin:0 0 4px}
    html.lb-map .mapctl{right:16px;top:16px}
    html.lb-map .mapctl button{width:48px;height:48px;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.16)}
    html.lb-map .mapattr{left:392px;bottom:8px;max-width:calc(100% - 560px)}
    html.lb-map .map-status{left:calc(50% + 188px)}
    html.lb-map .map-card{bottom:auto!important}
    html.lb-map .map-card:not([hidden])~.map-tip{display:none}
    html.lb-map .nearres button,html.lb-map .map-pop>button{min-height:44px}
    @media (max-width:760px){
      html.lb-map .map-top{width:auto;right:180px}
      html.lb-map .maptools{top:auto!important;left:12px!important;right:12px!important;width:auto!important;bottom:12px;max-height:38%!important}
      html.lb-map .map-pop,html.lb-map .map-card{left:12px!important;right:12px!important;width:auto!important;top:auto!important;bottom:12px!important;max-height:62%!important}
      html.lb-map .mapattr{display:none}
      html.lb-map .map-status{left:50%;bottom:calc(38% + 24px)}
    }
    """

    /// A reading page in a sheet: the page itself, at a readable width, without the desktop's back bar.
    static let reader = """
    html.lb-reader main{padding:20px 24px 40px!important}
    html.lb-reader .rtop{display:none!important}
    """
}

/// The Map destination: the offline map, edge to edge, with the native toolbar.
struct MapScreen: View {
    @EnvironmentObject var nav: AppNav
    @Environment(\.horizontalSizeClass) private var hsc
    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                LibraryWebView(kind: .map, route: "#/map", command: nav.mapFocus,
                               onLink: { nav.open(route: $0) }, onChangeLibrary: { nav.showLibrary = true })
                    .ignoresSafeArea(edges: hsc == .compact ? [] : [.bottom, .horizontal])   // narrow: the tab bar is at the bottom
                if let r = nav.readiness, let miss = r.items.first(where: { $0.id == "map" && !$0.ok }) {
                    Button { nav.showLibrary = true } label: {
                        Label(miss.title + ": only main roads and towns. Add your state’s map in Library.", systemImage: "map")
                            .font(.subheadline.weight(.medium)).padding(.horizontal, 16).padding(.vertical, 10)
                            .background(.regularMaterial, in: Capsule())
                    }
                    .buttonStyle(.plain).padding(.bottom, 54)
                }
            }
            .navigationTitle("Map")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { LibraryToolbarButton() } }
        }
    }
}

/// A library page at an exact page (chat sources, map links), drawn by the engine's reader.
struct ReaderView: View {
    @EnvironmentObject var nav: AppNav
    let docId: String
    let page: Int?
    @State private var title = ""
    var body: some View {
        let enc = docId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed.subtracting(CharacterSet(charactersIn: "/"))) ?? docId
        LibraryWebView(kind: .reader, route: "#/read/\(enc)" + (page.map { "?p=\($0)" } ?? ""),
                       onLink: { r in nav.opened = nil; DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { nav.open(route: r) } },
                       onChangeLibrary: { nav.opened = nil; nav.showLibrary = true })
            .ignoresSafeArea(edges: .bottom)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .task { title = (await LocalAPI.rec("/api/doc/\(docId)"))?.s("title") ?? "" }
    }
}
