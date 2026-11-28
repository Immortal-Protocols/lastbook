import SwiftUI

enum PhoneTab: Hashable { case videos, map, chat, library }

/// Four phone destinations. The iPad keeps its three tabs and Library sheet; the shared detail screens are the same.
struct PhoneShell: View {
    var manage: () -> Void
    @StateObject private var nav = AppNav()
    @StateObject private var chats = ChatStore()
    @State private var tab: PhoneTab = .videos
    @Environment(\.scenePhase) private var phase

    var body: some View {
        TabView(selection: $tab) {
            Tab("Videos", systemImage: "play.rectangle", value: PhoneTab.videos) { VideosScreen() }
            Tab("Map", systemImage: "map", value: PhoneTab.map) { PhoneMapScreen() }
            Tab("Chat", systemImage: "bubble.left.and.text.bubble.right", value: PhoneTab.chat) { ChatScreen() }
            Tab("Library", systemImage: "books.vertical", value: PhoneTab.library) {
                PhoneLibraryScreen(manage: manage)
            }
        }
        .tint(Brand.accent)
        .environmentObject(nav)
        .environmentObject(chats)
        .onChange(of: nav.showLibrary) { _, show in
            if show { tab = .library; nav.showLibrary = false }
        }
        .sheet(item: $nav.opened) { o in
            OpenedSheet(opened: o).environmentObject(nav).environmentObject(chats)
        }
        .onChange(of: phase) { _, p in if p == .active { nav.refreshReadiness() } }
        .onAppear {
            nav.refreshReadiness()
            debugLaunch()
        }
    }

    /// Simulator review only (never in a release build): -LBTab map|chat|library|videos, -LBAutoAsk "question".
    private func debugLaunch() {
        #if DEBUG
        let d = UserDefaults.standard
        switch d.string(forKey: "LBTab") {
        case "map": tab = .map; case "chat": tab = .chat; case "library": tab = .library; default: break
        }
        if let r = d.string(forKey: "LBOpen"), r.hasPrefix("#") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { nav.open(route: r) }
        }
        if let q = d.string(forKey: "LBAutoAsk"), !q.isEmpty {
            tab = .chat
            let delay = d.object(forKey: "LBAutoAskDelay") == nil ? 1.2 : d.double(forKey: "LBAutoAskDelay")
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { chats.send(q, about: nil) }
        }
        #endif
    }
}

/// The iPhone Map screen: the offline map plus a native "Nearby" bottom sheet listing items near the map center.
struct PhoneMapScreen: View {
    @EnvironmentObject var nav: AppNav
    @State private var showNearby = false
    @State private var loadingNearby = false
    @State private var items: [Rec] = []
    @State private var center: (Double, Double) = (34.05, -118.24)
    @State private var homeRoute = "#/map"

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottomTrailing) {
                LibraryWebView(kind: .map, route: homeRoute, command: nav.mapFocus,
                               onLink: { nav.open(route: $0) }, onChangeLibrary: { nav.showLibrary = true })
                VStack(alignment: .trailing, spacing: 10) {
                    if let r = nav.readiness, let miss = r.items.first(where: { $0.id == "map" && !$0.ok }) {
                        Button { nav.showLibrary = true } label: {
                            Label(miss.title + ": only main roads and towns. Add your state’s map in Library.", systemImage: "map")
                                .font(.caption.weight(.medium)).padding(.horizontal, 12).padding(.vertical, 8)
                                .background(.regularMaterial, in: Capsule())
                        }
                        .buttonStyle(.plain)
                    }
                    Button {
                        showNearby = true
                        Task { await loadNearby() }
                    } label: {
                        Label("Nearby", systemImage: "location.magnifyingglass")
                            .font(.subheadline.weight(.semibold))
                            .padding(.horizontal, 16).padding(.vertical, 12)
                            .foregroundStyle(.white)
                            .background(Brand.accent, in: Capsule())
                            .shadow(color: .black.opacity(0.2), radius: 6, y: 2)
                    }
                    .buttonStyle(.plain)
                }
                .padding(.trailing, 16)
                .padding(.bottom, 16)
            }
            .navigationTitle("Map")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showNearby) {
                NavigationStack {
                    Group {
                        if loadingNearby {
                            VStack(spacing: 12) { ProgressView(); Text("Finding nearby places…").foregroundStyle(.secondary) }
                                .frame(maxWidth: .infinity, maxHeight: .infinity)
                        } else if items.isEmpty {
                            ContentUnavailableView("No nearby items", systemImage: "mappin.slash",
                                                   description: Text("No help points or resources found near the map center."))
                        } else {
                            List {
                                Section {
                                    ForEach(Array(items.enumerated()), id: \.offset) { _, r in
                                        Button {
                                            let lat = (r["lat"] as? NSNumber)?.doubleValue ?? center.0
                                            let lon = (r["lon"] as? NSNumber)?.doubleValue ?? center.1
                                            let name = r.s("name").isEmpty ? r.s("label") : r.s("name")
                                            let enc = name.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? name
                                            nav.mapFocus = "#/map?lat=\(lat)&lon=\(lon)&z=16&pin=\(enc)"
                                            showNearby = false
                                        } label: {
                                            VStack(alignment: .leading, spacing: 4) {
                                                HStack(spacing: 8) {
                                                    Text(r.s("label")).font(.caption.weight(.semibold)).foregroundStyle(Brand.accent)
                                                    if let km = (r["km"] as? NSNumber)?.doubleValue {
                                                        Text(String(format: "%.1f km %@", km, r.s("dir")))
                                                            .font(.caption).foregroundStyle(.secondary)
                                                    }
                                                }
                                                Text(r.s("name").isEmpty ? "Unnamed \(r.s("label"))" : r.s("name"))
                                                    .font(.body.weight(.semibold)).foregroundStyle(.primary)
                                                let detail = r.s("detail").isEmpty ? r.s("summary") : r.s("detail")
                                                if !detail.isEmpty {
                                                    Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                                                }
                                            }
                                            .padding(.vertical, 2)
                                        }
                                    }
                                } header: {
                                    Text("\(items.count) nearest to the map center · straight-line distance")
                                }
                            }
                        }
                    }
                    .navigationTitle("Nearby")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .confirmationAction) { Button("Done") { showNearby = false } }
                    }
                }
                .presentationDetents([.medium, .large])
            }
            .task {
                if let info = await LocalAPI.rec("/api/map/info"),
                   let b = info["bounds"] as? [NSNumber], b.count >= 4 {
                    let lat = (b[1].doubleValue + b[3].doubleValue) / 2
                    let lon = (b[0].doubleValue + b[2].doubleValue) / 2
                    homeRoute = "#/map?lat=\(lat)&lon=\(lon)&z=7"
                    center = (lat, lon)
                }
            }
            .onAppear {
                #if DEBUG
                if UserDefaults.standard.bool(forKey: "LBShowNearby") {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                        showNearby = true
                        Task { await loadNearby() }
                    }
                }
                #endif
            }
        }
    }

    @MainActor private func loadNearby() async {
        loadingNearby = true
        if let info = await LocalAPI.rec("/api/map/info"),
           let b = info["bounds"] as? [NSNumber], b.count >= 4 {
            center = ((b[1].doubleValue + b[3].doubleValue) / 2.0, (b[0].doubleValue + b[2].doubleValue) / 2.0)
        }
        if let focus = nav.mapFocus, let c = URLComponents(string: "lastbook://app/" + focus.drop(while: { $0 == "#" || $0 == "/" })) {
            let q = Dictionary((c.queryItems ?? []).map { ($0.name, $0.value ?? "") }, uniquingKeysWith: { a, _ in a })
            if let la = q["lat"].flatMap(Double.init), let lo = q["lon"].flatMap(Double.init) {
                center = (la, lo)
            }
        }
        items = await LocalAPI.recs("/api/map/near", ["lat": "\(center.0)", "lon": "\(center.1)", "limit": "5"])
        loadingNearby = false
    }
}
