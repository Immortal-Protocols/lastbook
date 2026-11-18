import SwiftUI

/// One video as the engine's vcard describes it (/api/videos).
struct VCard: Identifiable, Hashable {
    let id: String, title: String, publisher: String, duration: Double, thumb: String?, hasTranscript: Bool
    init(_ r: Rec) {
        id = r.s("id"); title = r.s("title"); publisher = r.s("publisher"); duration = r.d("duration")
        thumb = r.str("thumb"); hasTranscript = r.truthy("transcript")
    }
    init(id: String, title: String, publisher: String, duration: Double, thumb: String?) {
        self.id = id; self.title = title; self.publisher = publisher; self.duration = duration; self.thumb = thumb; hasTranscript = false
    }
}

struct VRow: Identifiable { let id: String, title: String, note: String?, count: Int, items: [VCard] }

enum VideoRoute: Hashable {
    case row(id: String, title: String)
    case watch(id: String)
}

/// Where each video was left, on this iPad only (the resume point and "Continue watching").
final class VideoProgress: ObservableObject {
    static let shared = VideoProgress()
    struct Entry: Codable { var t: Double; var d: Double; var title: String; var publisher: String; var thumb: String?; var updated: Date }
    @Published private(set) var all: [String: Entry] = [:]
    private let key = "lb.design.videoProgress"
    init() {
        if let d = UserDefaults.standard.data(forKey: key), let v = try? JSONDecoder().decode([String: Entry].self, from: d) { all = v }
    }
    func save(_ id: String, _ e: Entry) {
        all[id] = e
        if let d = try? JSONEncoder().encode(all) { UserDefaults.standard.set(d, forKey: key) }
    }
    func forget(_ id: String) { all[id] = nil; if let d = try? JSONEncoder().encode(all) { UserDefaults.standard.set(d, forKey: key) } }
    /// Started, not finished: worth offering again.
    var continuing: [(String, Entry)] {
        all.filter { $0.value.t > 15 && ($0.value.d <= 0 || $0.value.t < $0.value.d - 20) }
            .sorted { $0.value.updated > $1.value.updated }.map { ($0.key, $0.value) }
    }
    func fraction(_ id: String) -> Double? {
        guard let e = all[id], e.d > 0, e.t > 15 else { return nil }
        return min(1, e.t / e.d)
    }
}

/// YouTube-style browse: a chip bar of categories on top filters one thumbnail grid in place; "All" is the home feed.
struct VideosScreen: View {
    @EnvironmentObject var nav: AppNav
    @State private var path = NavigationPath()
    @State private var rows: [VRow] = []
    @State private var loaded = false
    @State private var chip = "home"
    @State private var query = ""
    @State private var results: [VCard] = []
    @State private var searching = false
    @FocusState private var searchFocused: Bool
    @ObservedObject private var progress = VideoProgress.shared

    var body: some View {
        NavigationStack(path: $path) {
            VStack(spacing: 0) {
                if query.trimmingCharacters(in: .whitespaces).isEmpty && !rows.isEmpty {
                    ChipBar(rows: rows, chip: $chip)
                    Divider()
                }
                Group {
                    if !query.trimmingCharacters(in: .whitespaces).isEmpty {
                        VideoGrid(items: results, emptyText: searching ? nil : "No videos match “\(query)”. Try fewer or different words.")
                    } else if !loaded {
                        ProgressView("Opening videos…").frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if rows.isEmpty {
                        ContentUnavailableView("No videos in this library", systemImage: "play.rectangle",
                                               description: Text("Add a library with videos in Library."))
                    } else if chip == "home" {
                        home
                    } else {
                        VideoRowPage(rowId: chip).id(chip)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .navigationTitle("Videos")
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(for: VideoRoute.self) { r in
                switch r {
                case .row(let id, _): VideoRowPage(rowId: id)
                case .watch(let id): VideoWatchView(videoId: id, startAt: nil)
                }
            }
            .searchable(text: $query, placement: .toolbar, prompt: "Search videos")
            .searchFocused($searchFocused)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { BrandMark() }
                ToolbarItem(placement: .topBarTrailing) { LibraryToolbarButton() }
            }
        }
        .task { if !loaded { rows = await Self.loadRows(); loaded = true } }
        .task(id: query) {
            let q = query.trimmingCharacters(in: .whitespaces)
            guard !q.isEmpty else { results = []; return }
            searching = true
            try? await Task.sleep(for: .milliseconds(200))
            if Task.isCancelled { return }
            let r = await LocalAPI.rec("/api/videos/all", ["q": q])
            results = ((r?["items"] as? [Rec]) ?? []).map(VCard.init)
            searching = false
        }
        .onChange(of: nav.searchFocus) { _, _ in if nav.tab == .videos { path = NavigationPath(); searchFocused = true } }
    }

    static func loadRows() async -> [VRow] {
        await LocalAPI.recs("/api/videos").map {
            VRow(id: $0.s("id"), title: $0.s("title"), note: $0.str("note"), count: Int($0.d("count")), items: (($0["items"] as? [Rec]) ?? []).map(VCard.init))
        }.filter { !$0.items.isEmpty }
    }

    /// Home feed: continue watching, then each category's best videos in the grid, with "See all" selecting its chip.
    private var home: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 34) {
                let cont = progress.continuing
                if !cont.isEmpty {
                    section("Continue watching", note: nil, more: nil) {
                        ForEach(cont.prefix(8), id: \.0) { id, e in
                            NavigationLink(value: VideoRoute.watch(id: id)) {
                                VideoCardView(v: VCard(id: id, title: e.title, publisher: e.publisher, duration: e.d, thumb: e.thumb))
                            }.buttonStyle(.plain)
                        }
                    }
                }
                ForEach(rows) { r in
                    section(r.title, note: r.note, more: r.count > 6 ? (r.id, r.count) : nil) {
                        ForEach(r.items.prefix(6)) { v in
                            NavigationLink(value: VideoRoute.watch(id: v.id)) { VideoCardView(v: v) }.buttonStyle(.plain)
                        }
                    }
                }
            }
            .padding(24)
        }
    }

    private func section<C: View>(_ title: String, note: String?, more: (String, Int)?, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.title2.bold()).accessibilityAddTraits(.isHeader)
                    if let note { Text(note).font(.subheadline).foregroundStyle(.secondary) }
                }
                Spacer()
                if let (id, n) = more {
                    Button("See all \(n)") { chip = id }.font(.body.weight(.medium)).frame(minHeight: 44)
                }
            }
            LazyVGrid(columns: VideoGrid.columns, alignment: .leading, spacing: 26) { content() }
        }
    }
}

/// The chip bar under the toolbar (YouTube): one tap filters the grid; the selected chip is filled.
private struct ChipBar: View {
    let rows: [VRow]
    @Binding var chip: String
    var body: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    c("home", "All")
                    ForEach(rows) { r in c(r.id, r.title) }
                    c("all", "Every video")
                }
                .padding(.horizontal, 24).padding(.vertical, 10)
            }
            .onChange(of: chip) { _, v in withAnimation { proxy.scrollTo(v, anchor: .center) } }
        }
    }
    func c(_ id: String, _ t: String) -> some View {
        let on = chip == id
        return Button { chip = id } label: {
            Text(t).font(.subheadline.weight(.semibold))
                .padding(.horizontal, 16).frame(minHeight: 40)
                .foregroundStyle(on ? Color(.systemBackground) : Color.primary)
                .background(on ? Color.primary : Color(.secondarySystemFill), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                .contentShape(.hoverEffect, RoundedRectangle(cornerRadius: 10, style: .continuous)).hoverEffect(.highlight)
        }
        .buttonStyle(.plain).id(id)
        .frame(minHeight: 44)
        .accessibilityAddTraits(on ? .isSelected : [])
    }
}

/// Lastbook's own mark in the toolbar's leading corner (the brand, as YouTube shows its logo there).
struct BrandMark: View {
    var body: some View {
        HStack(spacing: 8) {
            Image("Book").resizable().scaledToFit().frame(width: 28, height: 28).clipShape(RoundedRectangle(cornerRadius: 6))
            Text("Lastbook").font(.headline)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Lastbook")
    }
}

struct VideoCardView: View {
    let v: VCard
    var width: CGFloat? = nil
    @ObservedObject private var progress = VideoProgress.shared
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ThumbView(path: v.thumb)
                .aspectRatio(16 / 9, contentMode: .fit)
                .overlay(alignment: .bottomTrailing) {
                    if v.duration > 0 {
                        Text(Fmt.clock(v.duration)).font(.caption.weight(.semibold).monospacedDigit())
                            .padding(.horizontal, 6).padding(.vertical, 3)
                            .background(.black.opacity(0.75), in: RoundedRectangle(cornerRadius: 5)).foregroundStyle(.white)
                            .padding(8)
                    }
                }
                .overlay(alignment: .bottom) {
                    if let f = progress.fraction(v.id) {
                        GeometryReader { g in
                            ZStack(alignment: .leading) {
                                Rectangle().fill(.black.opacity(0.35))
                                Rectangle().fill(Color.accentColor).frame(width: g.size.width * f)
                            }
                        }.frame(height: 4)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .contentShape(.hoverEffect, RoundedRectangle(cornerRadius: 12, style: .continuous))
                .hoverEffect(.lift)
            Text(v.title).font(.headline).lineLimit(2).multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(v.publisher).font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
        }
        .frame(width: width)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(v.title), \(v.publisher), \(Fmt.duration(v.duration))\(progress.fraction(v.id) != nil ? ", started" : "")")
        .accessibilityAddTraits(.isButton)
    }
}

struct ThumbView: View {
    let path: String?
    var maxPixel: CGFloat = 640
    @State private var img: UIImage?
    var body: some View {
        Rectangle().fill(Color(.tertiarySystemFill))
            .overlay {
                if let img { Image(uiImage: img).resizable().scaledToFill() }
                else { Image(systemName: "play.rectangle").font(.largeTitle).foregroundStyle(.tertiary) }
            }
            .clipped()
            .task(id: path) { if let path { img = await Thumbs.shared.image(path, maxPixel: maxPixel) } }
    }
}

/// An adaptive grid of videos (category pages and search results).
struct VideoGrid: View {
    static let columns = [GridItem(.adaptive(minimum: 260, maximum: 420), spacing: 22, alignment: .top)]
    let items: [VCard]
    var emptyText: String?
    var onLast: (() -> Void)? = nil
    var body: some View {
        if items.isEmpty {
            if let emptyText { ContentUnavailableView("Nothing here", systemImage: "magnifyingglass", description: Text(emptyText)) }
            else { ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity) }
        } else {
            ScrollView {
                LazyVGrid(columns: Self.columns, spacing: 30) {
                    ForEach(items) { v in
                        NavigationLink(value: VideoRoute.watch(id: v.id)) { VideoCardView(v: v) }.buttonStyle(.plain)
                            .onAppear { if v.id == items.last?.id { onLast?() } }
                    }
                }
                .padding(24)
            }
        }
    }
}

/// One category (or all videos), with Length and Sort, as the engine filters them.
struct VideoRowPage: View {
    let rowId: String
    @State private var items: [VCard] = []
    @State private var total = 0
    @State private var more = false
    @State private var length = ""
    @State private var sort = ""
    @State private var loading = false

    var body: some View {
        VideoGrid(items: items, emptyText: loading ? nil : "No videos with this length. Choose Any length.", onLast: { if more { Task { await load(reset: false) } } })
            .safeAreaInset(edge: .top, spacing: 0) {
                HStack(spacing: 12) {
                    Text(total > 0 ? "\(total) videos" : " ").font(.subheadline).foregroundStyle(.secondary)
                    Spacer()
                    Menu {
                        Picker("Length", selection: $length) {
                            Text("Any length").tag(""); Text("Under 10 min").tag("short"); Text("10–30 min").tag("medium"); Text("Over 30 min").tag("long")
                        }
                    } label: { Label(length.isEmpty ? "Length" : lengthName, systemImage: "clock") .labelStyle(.titleAndIcon) }
                    Menu {
                        Picker("Sort", selection: $sort) {
                            Text("Recommended").tag(""); Text("Shortest first").tag("short"); Text("Newest").tag("new"); Text("A–Z").tag("az")
                        }
                    } label: { Label("Sort", systemImage: "arrow.up.arrow.down").labelStyle(.titleAndIcon) }
                }
                .menuStyle(.button).buttonStyle(.bordered)
                .padding(.horizontal, 24).padding(.top, 12)
            }
            .task(id: "\(length)|\(sort)") { await load(reset: true) }
    }
    var lengthName: String { ["short": "Under 10 min", "medium": "10–30 min", "long": "Over 30 min"][length] ?? "Length" }

    func load(reset: Bool) async {
        if loading { return }
        loading = true
        let off = reset ? 0 : items.count
        let r = await LocalAPI.rec("/api/videos/\(rowId)", ["len": length, "sort": sort, "offset": "\(off)"])
        let got = ((r?["items"] as? [Rec]) ?? []).map(VCard.init)
        items = reset ? got : items + got.filter { g in !items.contains { $0.id == g.id } }
        total = Int(r?.d("total") ?? 0); more = (r?["more"] as? Bool) ?? false
        loading = false
    }
}
