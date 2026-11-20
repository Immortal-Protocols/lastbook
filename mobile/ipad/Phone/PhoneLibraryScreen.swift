import SwiftUI

/// The phone's Library destination: what is ready, a searchable catalog, encyclopedias and the installer.
struct PhoneLibraryScreen: View {
    var manage: () -> Void
    @EnvironmentObject private var nav: AppNav
    @EnvironmentObject private var chats: ChatStore
    @State private var readiness: Readiness?
    @State private var query = ""
    @State private var kind = "all"
    @State private var hits: [Rec] = []
    @State private var searching = false
    @State private var opened: Opened?
    @State private var zimToOpen: String?

    private var zims: [String] { LibraryAPI.zimNames() }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    if let r = readiness {
                        ForEach(r.items, id: \.id) { i in
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: i.ok ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                                    .foregroundStyle(i.ok ? .green : .orange).font(.title3)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(i.title).font(.headline)
                                    Text(AIStatus.ipad(i.detail)).font(.subheadline).foregroundStyle(.secondary)
                                }
                            }
                        }
                    } else {
                        HStack { ProgressView(); Text("Checking this iPhone…") }
                    }
                } header: { Text("On this iPhone") } footer: {
                    if let r = readiness { Text(r.missing.isEmpty ? "Everything in this library is ready." : "Some things are not ready yet. The rest works now.") }
                }

                Section("Find something") {
                    HStack(spacing: 8) {
                        Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                        TextField("Search manuals, videos and pages", text: $query)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                    }
                    Picker("Kind", selection: $kind) {
                        Text("All").tag("all"); Text("Reading").tag("read"); Text("Videos").tag("video"); Text("Encyclopedias").tag("zim")
                    }.pickerStyle(.segmented)
                    if searching { HStack { ProgressView(); Text("Searching…") } }
                    ForEach(hits.prefix(60), id: \.idKey) { r in
                        Button {
                            if r.s("kind") == "video" { opened = .video(id: r.s("id"), t: nil) }
                            else { opened = .doc(id: r.s("id"), page: nil) }
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(r.s("title")).font(.body).foregroundStyle(.primary).lineLimit(2)
                                Text([Catalog.kindLabel(r), r.s("publisher")].filter { !$0.isEmpty }.joined(separator: " · "))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                if !zims.isEmpty {
                    Section("Encyclopedias") {
                        ForEach(zims, id: \.self) { z in
                            NavigationLink {
                                PhoneZimView(name: z)
                            } label: {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(z.replacingOccurrences(of: ".zim", with: "").replacingOccurrences(of: "_", with: " "))
                                    Text(zimSizeText(z)).font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }

                Section("Downloads") {
                    Button { manage() } label: { Label("Install or change library…", systemImage: "arrow.down.circle") }
                    if let root = Library.shared.root {
                        Text(root.path).font(.caption).foregroundStyle(.secondary)
                    }
                }

                Section("Chat") {
                    Toggle("Keep chat history on this iPhone", isOn: $chats.keep)
                    Button("Delete all chats", role: .destructive) { chats.deleteAll() }.disabled(chats.chats.isEmpty)
                }
            }
            .navigationTitle("Library")
            .searchable(text: $query, prompt: "Search manuals, videos and pages")
            .onChange(of: query) { _, q in
                Task { await search(q) }
            }
            .task { readiness = Readiness.check(); await chats.refreshStatus() }
            .onAppear {
                readiness = Readiness.check()
                #if DEBUG
                if let z = UserDefaults.standard.string(forKey: "LBZim"), !z.isEmpty { zimToOpen = z }
                #endif
            }
            .navigationDestination(isPresented: Binding(get: { zimToOpen != nil }, set: { if !$0 { zimToOpen = nil } })) {
                if let z = zimToOpen { PhoneZimView(name: z) }
            }
            .sheet(item: $opened) { o in
                OpenedSheet(opened: o).environmentObject(nav).environmentObject(chats)
            }
        }
    }

    @MainActor private func search(_ q: String) async {
        let text = q.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { hits = []; return }
        searching = true
        try? await Task.sleep(for: .milliseconds(180))
        if Task.isCancelled { return }
        hits = await LocalAPI.recs("/api/find", ["q": text, "kind": kind])
        searching = false
    }

    private func zimSizeText(_ name: String) -> String {
        guard let lib = Library.shared.lib,
              let size = (try? FileManager.default.attributesOfItem(atPath: lib.appendingPathComponent("collections/\(name)").path)[.size] as? NSNumber)?.int64Value else {
            return "Installed"
        }
        return ByteCountFormatter.string(fromByteCount: size, countStyle: .file) + " · Installed"
    }
}

struct PhoneZimView: View {
    let name: String
    @StateObject private var controller: PhoneZimController
    @State private var query = ""
    @State private var results: [Rec] = []
    @State private var searching = false
    @State private var showSearch = false
    @State private var fullTextMode = false

    init(name: String) {
        self.name = name
        _controller = StateObject(wrappedValue: PhoneZimController(name: name))
    }

    var body: some View {
        VStack(spacing: 0) {
            if showSearch {
                HStack(spacing: 8) {
                    Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                    TextField("Search this encyclopedia", text: $query)
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                        .onSubmit { Task { await runSearch(full: fullTextMode) } }
                    Button("Titles") { fullTextMode = false; Task { await runSearch(full: false) } }
                        .font(.caption.weight(fullTextMode ? .regular : .bold))
                    Button("Full text") { fullTextMode = true; Task { await runSearch(full: true) } }
                        .font(.caption.weight(fullTextMode ? .bold : .regular))
                }.padding(10)
                if searching { ProgressView().padding(8) }
                if !results.isEmpty {
                    List(results, id: \.idString) { r in
                        Button {
                            controller.load(r.s("path"))
                            showSearch = false; results = []
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(r.s("title")).font(.body).lineLimit(2)
                                let snippet = r.s("snippet").replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
                                if !snippet.isEmpty { Text(snippet).font(.caption).foregroundStyle(.secondary).lineLimit(3) }
                            }
                        }.buttonStyle(.plain)
                    }.frame(maxHeight: 260)
                }
            }
            PhoneZimCanvas(controller: controller)
                .overlay { if controller.loading { ProgressView() } }
        }
        .navigationTitle(name.replacingOccurrences(of: ".zim", with: "").replacingOccurrences(of: "_", with: " "))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button { controller.goBack() } label: { Image(systemName: "chevron.backward") }
                    .disabled(!controller.canGoBack)
                Button { controller.goForward() } label: { Image(systemName: "chevron.forward") }
                    .disabled(!controller.canGoForward)
                Button { showSearch = false; controller.goHome() } label: { Image(systemName: "house") }
                Button { showSearch.toggle() } label: { Image(systemName: "magnifyingglass") }
            }
        }
        .onChange(of: query) { _, q in
            guard showSearch else { return }
            Task {
                try? await Task.sleep(for: .milliseconds(160))
                if !Task.isCancelled { await runSearch(full: fullTextMode) }
            }
        }
        .onAppear { showSearch = false }
    }

    @MainActor private func runSearch(full: Bool) async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return }
        searching = true
        results = await LocalAPI.recs("/api/zim/search", ["name": name, "q": q, "full": full ? "1" : "0"])
        searching = false
    }
}

private extension Dictionary where Key == String, Value == Any {
    var idKey: String { (self["id"] as? String) ?? UUID().uuidString }
    var idString: String { (self["path"] as? String) ?? (self["title"] as? String) ?? UUID().uuidString }
}
