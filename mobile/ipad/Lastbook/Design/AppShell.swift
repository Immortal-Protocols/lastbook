import SwiftUI

/// The three destinations, in the product's order. Nothing else is a destination.
enum AppTab: Hashable { case videos, map, chat }

/// Something opened over the current tab: a library page at an exact page, or a video at an exact moment.
enum Opened: Identifiable, Hashable {
    case doc(id: String, page: Int?)
    case video(id: String, t: Double?)
    var id: String {
        switch self {
        case .doc(let i, let p): return "d:\(i):\(p ?? 0)"
        case .video(let i, let t): return "v:\(i):\(t ?? -1)"
        }
    }
}

/// Context a chat starts with ("Ask about this video"), as the desktop's ?about=kind:id:n.
struct ChatAbout: Equatable {
    var about: String       // "video:<id>:<seconds>" or "doc:<id>:<page>"
    var label: String
    var sub: String
}

/// Shell-wide navigation state. Each tab keeps its own stack; this only carries cross-tab requests.
@MainActor final class AppNav: ObservableObject {
    @Published var tab: AppTab = .videos
    @Published var showLibrary = false
    @Published var opened: Opened?
    @Published var chatAbout: ChatAbout?
    @Published var mapFocus: String?          // a #/map?... route for the map tab to show
    @Published var readiness: Readiness?
    @Published var searchFocus = 0            // ⌘F: bumps; the visible tab focuses its search

    func refreshReadiness() {
        Task {
            let r = await Task.detached(priority: .utility) { Readiness.check() }.value
            readiness = r
        }
    }

    /// A desktop-style route (from a web page's link or a chat source) opened the native way.
    func open(route: String) {
        guard let c = URLComponents(string: "lastbook://app/" + route.drop(while: { $0 == "#" || $0 == "/" })) else { return }
        let q = Dictionary((c.queryItems ?? []).map { ($0.name, $0.value ?? "") }, uniquingKeysWith: { a, _ in a })
        let parts = c.path.split(separator: "/").map { String($0).removingPercentEncoding ?? String($0) }
        switch parts.first {
        case "watch" where parts.count > 1: opened = .video(id: parts[1], t: q["t"].flatMap(Double.init))
        case "read" where parts.count > 1: opened = .doc(id: parts[1], page: q["p"].flatMap(Int.init))
        case "ask":
            if let a = q["about"], !a.isEmpty { chatAbout = ChatAbout(about: a, label: "This item", sub: "") }
            tab = .chat
        case "map": mapFocus = "#" + route.drop(while: { $0 == "#" }); tab = .map
        default: tab = .videos
        }
    }
}

/// The iPad app: a system tab view (the iPad top tab bar; three destinations need no sidebar) with Videos, Map and Chat.
struct AppShell: View {
    var manage: () -> Void
    var chooseFolder: () -> Void
    @StateObject private var nav = AppNav()
    @StateObject private var chats = ChatStore()
    @Environment(\.scenePhase) private var phase

    var body: some View {
        TabView(selection: $nav.tab) {
            Tab("Videos", systemImage: "play.rectangle", value: AppTab.videos) { VideosScreen() }
            Tab("Map", systemImage: "map", value: AppTab.map) { MapScreen() }
            Tab("Chat", systemImage: "bubble.left.and.text.bubble.right", value: AppTab.chat) { ChatScreen() }
        }
        .tabViewStyle(.tabBarOnly)
        .tint(Brand.accent)
        .environmentObject(nav)
        .environmentObject(chats)
        .sheet(isPresented: $nav.showLibrary) {
            LibrarySheet(manage: { nav.showLibrary = false; manage() }, chooseFolder: { nav.showLibrary = false; chooseFolder() })
                .environmentObject(nav).environmentObject(chats)
        }
        .sheet(item: $nav.opened) { o in
            OpenedSheet(opened: o).environmentObject(nav).environmentObject(chats)
                .presentationSizing(.page)
        }
        .background { KeyboardCommands(nav: nav, chats: chats) }
        .onAppear { nav.refreshReadiness(); debugLaunch() }
        .onChange(of: phase) { _, p in if p == .active { nav.refreshReadiness() } }
    }
}

#if DEBUG
/// Simulator review only (never in a release build): -LBTab chat|map|videos, -LBOrient landscape|portrait,
/// -LBOpen '#/watch/<id>?t=30', -LBLibrary YES, -LBNarrow 420 (a narrow window width, compact size class).
extension AppShell {
    func debugLaunch() {
        let d = UserDefaults.standard
        switch d.string(forKey: "LBTab") { case "map": nav.tab = .map; case "chat": nav.tab = .chat; default: break }
        if let o = d.string(forKey: "LBOrient") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                for case let scene as UIWindowScene in UIApplication.shared.connectedScenes {
                    scene.requestGeometryUpdate(.iOS(interfaceOrientations: o == "landscape" ? .landscapeRight : .portrait)) { e in NSLog("LBOrient: %@", "\(e)") }
                }
            }
        }
        if let r = d.string(forKey: "LBOpen") { DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { nav.open(route: r) } }
        if d.bool(forKey: "LBLibrary") { DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { nav.showLibrary = true } }
    }
}
#else
extension AppShell { func debugLaunch() {} }
#endif

/// Hardware-keyboard shortcuts (shown in the ⌘ overlay through their titles).
private struct KeyboardCommands: View {
    @ObservedObject var nav: AppNav
    @ObservedObject var chats: ChatStore
    var body: some View {
        ZStack {
            Button("Videos") { nav.tab = .videos }.keyboardShortcut("1", modifiers: .command).accessibilityHidden(true)
            Button("Map") { nav.tab = .map }.keyboardShortcut("2", modifiers: .command).accessibilityHidden(true)
            Button("Chat") { nav.tab = .chat }.keyboardShortcut("3", modifiers: .command).accessibilityHidden(true)
            Button("Search") { nav.searchFocus += 1 }.keyboardShortcut("f", modifiers: .command).accessibilityHidden(true)
            Button("New Chat") { nav.tab = .chat; chats.newChat() }.keyboardShortcut("n", modifiers: .command).accessibilityHidden(true)
            Button("Library") { nav.showLibrary = true }.keyboardShortcut(",", modifiers: .command).accessibilityHidden(true)
        }
        .frame(width: 0, height: 0).clipped()
        .opacity(0).allowsHitTesting(false)
        .accessibilityElement(children: .ignore).accessibilityHidden(true)
    }
}

/// The toolbar button every tab carries: Library (what's on this iPad, downloads, settings). A dot when something isn't ready.
struct LibraryToolbarButton: View {
    @EnvironmentObject var nav: AppNav
    var body: some View {
        Button { nav.showLibrary = true } label: {
            Label("Library", systemImage: "books.vertical")
                .overlay(alignment: .topTrailing) {
                    if let r = nav.readiness, !r.missing.isEmpty {
                        Circle().fill(.orange).frame(width: 9, height: 9).offset(x: 4, y: -2).accessibilityHidden(true)
                    }
                }
        }
        .accessibilityLabel(nav.readiness.map { $0.missing.isEmpty ? "Library, everything ready" : "Library, \($0.missing.count) not ready" } ?? "Library")
        .help("Library and downloads (⌘,)")
    }
}

/// A page or video opened from a chat source, the map or a reading page: over the current tab, so closing it returns there.
struct OpenedSheet: View {
    let opened: Opened
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            Group {
                switch opened {
                case .doc(let id, let page): ReaderView(docId: id, page: page)
                case .video(let id, let t): VideoWatchView(videoId: id, startAt: t)
                }
            }
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Done") { dismiss() }.keyboardShortcut(.cancelAction) } }
        }
    }
}

/// Lastbook's restrained identity: the book mark and its green (the desktop's --accent, light and dark).
enum Brand {
    static let accent = Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 0.235, green: 0.776, blue: 0.565, alpha: 1) : UIColor(red: 0.063, green: 0.502, blue: 0.361, alpha: 1) })
}

extension View {
    /// DEBUG only: -LBNarrow <points> lays the app out in a narrow column, as a narrow Stage Manager window would.
    @ViewBuilder func debugNarrow() -> some View {
        #if DEBUG
        let w = UserDefaults.standard.double(forKey: "LBNarrow")
        if w > 0 {
            self.frame(width: w).environment(\.horizontalSizeClass, .compact)
                .overlay(Rectangle().stroke(Color.gray, lineWidth: 1))
                .frame(maxWidth: .infinity).background(Color.gray.opacity(0.3))
        } else { self }
        #else
        self
        #endif
    }
}
