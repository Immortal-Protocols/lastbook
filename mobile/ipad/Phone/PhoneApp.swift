import SwiftUI
import UniformTypeIdentifiers

/// The iPhone app. It shares the iPad's engine, router and detail screens; only the shell, the setup flow and the
/// Library destination are phone-shaped. The iPad target is untouched by this file.
@main
struct LastbookPhoneApp: App {
    init() {
        AppStatePhone.launchNotes = Installer.atLaunch()
        Library.shared.locate()
        Router.shared.install(Routes.all + [PhoneZimAPI()])
        _ = LocalAI.shared
        DispatchQueue.global(qos: .utility).async { VideoCompat.shared.decidesAV1() }
    }

    var body: some Scene {
        WindowGroup { PhoneRoot() }
    }
}

final class AppStatePhone: ObservableObject {
    static var launchNotes: [String] = []
    @Published var hasLibrary = Library.shared.locate()
    @Published var message: String? = AppStatePhone.launchNotes.isEmpty ? nil : AppStatePhone.launchNotes.joined(separator: " ")
    @Published var revision = 0
    func refresh() { hasLibrary = Library.shared.locate(); revision += 1 }
}

struct PhoneRoot: View {
    @StateObject private var state = AppStatePhone()
    @State private var installing = false

    var body: some View {
        Group {
            if state.hasLibrary {
                PhoneShell(manage: { installing = true })
                    .id(state.revision)
                    .onAppear { DispatchQueue.global(qos: .utility).async { Installer.afterOpen() } }
            } else {
                PhoneWelcome(message: state.message, install: { installing = true }, lookAgain: { state.refresh() })
            }
        }
        .sheet(isPresented: $installing) {
            PhoneSetupSheet(onDone: { installing = false; state.refresh() })
        }
        .onAppear {
            #if DEBUG
            if UserDefaults.standard.bool(forKey: "LBShowInstall") {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) { installing = true }
            }
            #endif
        }
    }
}

struct PhoneSetupSheet: View {
    var onDone: () -> Void
    @State private var selectedTierID: String = "auto"
    @State private var pickingCustomGGUF = false
    @State private var customNote: String?
    @State private var customIsError = false
    @State private var installedModels: [URL] = []
    private let ram = ProcessInfo.processInfo.physicalMemory

    private var recommendedTier: Gemma4.Tier { Gemma4.bestTier(forRAM: ram) }

    var body: some View {
        VStack(spacing: 0) {
            InstallView(onDone: onDone)
            Divider()
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Phone AI Tier & Storage").font(.subheadline.weight(.semibold))
                    Spacer()
                    Picker("AI Model Tier", selection: $selectedTierID) {
                        Text("Auto (\(recommendedTier.title))").tag("auto")
                        ForEach(Gemma4.tiers) { t in
                            let fits = UInt64(t.memoryBytes) <= ram
                            Text("\(t.title) (\(ByteCountFormatter.string(fromByteCount: t.size, countStyle: .file))\(fits ? "" : " · may exceed RAM"))")
                                .tag(t.id)
                        }
                        Text("Custom GGUF file…").tag("custom")
                        Text("No AI").tag("none")
                    }
                    .pickerStyle(.menu)
                    .onChange(of: selectedTierID) { _, v in
                        UserDefaults.standard.set(v, forKey: "LBPhoneModelTier")
                        if v != "custom" { UserDefaults.standard.removeObject(forKey: "LBPhoneCustomModel") }
                        if v == "custom" { pickingCustomGGUF = true }
                        else if v == "none" { LocalAI.shared.model?.setEnabled(false) }
                        else { LocalAI.shared.model?.setEnabled(true) }
                        NotificationCenter.default.post(name: .lastbookModelTierChanged, object: nil)
                    }
                }
                HStack(spacing: 12) {
                    Button {
                        pickingCustomGGUF = true
                    } label: {
                        Label("Import Custom .gguf…", systemImage: "doc.badge.plus").font(.caption)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    Text("Storage: \((Library.shared.root ?? Installer.packTarget).path)")
                        .font(.caption2).foregroundStyle(.secondary).lineLimit(1).truncationMode(.middle)
                }
                if !installedModels.isEmpty {
                    ForEach(installedModels, id: \.path) { u in
                        let isPinned = Gemma4.tier(forFile: u.lastPathComponent) != nil
                        HStack {
                            Text(u.lastPathComponent + (isPinned ? " (verified)" : " (unverified custom model)"))
                                .font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                            Spacer()
                            if !isPinned {
                                Button("Remove", role: .destructive) {
                                    try? FileManager.default.removeItem(at: u)
                                    if UserDefaults.standard.string(forKey: "LBPhoneCustomModel") == u.lastPathComponent {
                                        UserDefaults.standard.removeObject(forKey: "LBPhoneCustomModel")
                                        if UserDefaults.standard.string(forKey: "LBPhoneModelTier") == "custom" {
                                            UserDefaults.standard.set("auto", forKey: "LBPhoneModelTier")
                                            selectedTierID = "auto"
                                        }
                                    }
                                    refreshModels()
                                    LocalAI.shared.model?.discover()
                                }.font(.caption2)
                            }
                        }
                    }
                }
                if let customNote {
                    Text(customNote).font(.caption).foregroundStyle(customIsError ? .red : .green)
                }
            }
            .padding(.horizontal, 18).padding(.vertical, 10)
            .background(Color(.secondarySystemBackground))
        }
        .fileImporter(isPresented: $pickingCustomGGUF, allowedContentTypes: [.data, .item]) { result in
            if case .success(let url) = result { importCustomGGUF(url) }
        }
        .onAppear {
            selectedTierID = UserDefaults.standard.string(forKey: "LBPhoneModelTier") ?? "auto"
            UserDefaults.standard.set(selectedTierID, forKey: "LBPhoneModelTier")
            refreshModels()
        }
    }

    private func refreshModels() {
        let dir = (Library.shared.root ?? Installer.packTarget).appendingPathComponent("models")
        installedModels = ((try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.pathExtension.lowercased() == "gguf" }
    }

    private func importCustomGGUF(_ src: URL) {
        let scoped = src.startAccessingSecurityScopedResource()
        defer { if scoped { src.stopAccessingSecurityScopedResource() } }
        guard let fh = try? FileHandle(forReadingFrom: src),
              let head = try? fh.read(upToCount: 4),
              String(data: head, encoding: .ascii) == "GGUF" else {
            customIsError = true
            customNote = "That file is not a GGUF model (missing GGUF magic header)."
            return
        }
        try? fh.close()
        let dir = (Library.shared.root ?? Installer.packTarget).appendingPathComponent("models")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let name = src.lastPathComponent.lowercased().hasSuffix(".gguf") ? src.lastPathComponent : (src.lastPathComponent + ".gguf")
        let dst = dir.appendingPathComponent(name)
        do {
            if FileManager.default.fileExists(atPath: dst.path) { try FileManager.default.removeItem(at: dst) }
            try FileManager.default.copyItem(at: src, to: dst)
            UserDefaults.standard.set("custom", forKey: "LBPhoneModelTier")
            UserDefaults.standard.set(name, forKey: "LBPhoneCustomModel")
            customIsError = false
            customNote = "Imported \(name) (unverified custom model)."
            refreshModels()
            LocalAI.shared.model?.discover()
            NotificationCenter.default.post(name: .lastbookModelTierChanged, object: nil)
        } catch {
            customIsError = true
            customNote = "Could not copy model: \(error.localizedDescription)"
        }
    }
}

struct PhoneWelcome: View {
    var message: String?
    var install: () -> Void
    var lookAgain: () -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: 22) {
                Image("Book").resizable().scaledToFit().frame(width: 96, height: 96)
                    .background(Color(red: 248 / 255, green: 243 / 255, blue: 233 / 255),
                                in: RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .accessibilityHidden(true)
                Text("Lastbook").font(.largeTitle.bold())
                Text("Your offline survival library: videos, a map and a guide you can ask. Nothing is sent anywhere.")
                    .font(.body).multilineTextAlignment(.center).foregroundStyle(.secondary)
                if let message { Text(message).foregroundStyle(.red).multilineTextAlignment(.center) }
                Button("Install Lastbook", action: install)
                    .buttonStyle(.borderedProminent).controlSize(.large).font(.title3.bold())
                Button("Look again", action: lookAgain).buttonStyle(.bordered).controlSize(.large)
            }
            .padding(28).frame(maxWidth: 560).frame(maxWidth: .infinity)
        }
    }
}
