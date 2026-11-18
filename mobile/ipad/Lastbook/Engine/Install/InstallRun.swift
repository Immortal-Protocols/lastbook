import Foundation
import Combine
#if canImport(UIKit)
import UIKit
#endif

/// Runs a Plan: each item to download in order, each resumable (its part file stays on Cancel, a failure or a relaunch).
/// The run is complete only when the plan made afresh afterwards says so (library and required state map installed and
/// checked, and the state's addresses when published).
enum InstallRunner {
    enum Event {
        case started(item: PlanItem)
        /// phase: "Downloading", "Checking what was already downloaded", "Checking the download", "Unpacking",
        /// "Putting it in place", "Checking the local AI". overallDone/overallTotal: downloaded bytes across the run.
        case progress(item: PlanItem, phase: String, done: Int64, total: Int64, isDownload: Bool, overallDone: Int64, overallTotal: Int64)
        case finished(item: PlanItem, report: String)
    }

    /// After a library is switched in: point the app at it (the default) — the Mac test tool passes its own.
    static func useNewLibrary() {
        if Library.shared.root?.standardizedFileURL != Installer.packTarget.standardizedFileURL { Library.shared.forget() }
        else { Library.shared.locate() }
        Installer.afterOpen()
    }

    /// Runs every `toDownload` item of `plan`. Throws on the first failure (InstallError; .cancelled on Cancel); what is done
    /// stays done, and a new plan resumes at the first unfinished item.
    static func run(_ plan: Plan, control: DownloadControl, settings: URL = MapInstall.defaultSettings,
                    libraryChanged: @escaping () -> Void = useNewLibrary, events: @escaping (Event) -> Void) throws {
        if plan.state == nil { throw InstallError.refused("Choose your state first.") }
        if let free = plan.free, !plan.fits { throw InstallError.noSpace(need: plan.spaceNeeded, available: free) }
        let overallTotal = plan.downloadBytes
        var base: Int64 = 0
        for item in plan.toDo {
            try control.check()
            guard let e = item.entry else { continue }
            events(.started(item: item))
            let report: (String, Int64, Int64, Bool) -> Void = { phase, d, t, dl in
                let o = dl ? base + max(0, d - item.partialBytes) : base
                events(.progress(item: item, phase: phase, done: d, total: t, isDownload: dl, overallDone: min(o, overallTotal), overallTotal: overallTotal))
            }
            let step: (DownloadInstall.Step) -> Void = { s in
                switch s {
                case .downloading(let d, let n): report("Downloading", d, n, true)
                case .verifying(let d, let n): report("Checking what was already downloaded", d, n, false)
                case .installing(let p, let d, let n): report(p.rawValue, d, n, false)
                }
            }
            let text: String
            switch item.kind {
            case .pack:
                let r = try DownloadInstall.run(e, state: plan.state, target: Installer.packTarget, control: control, settings: settings, progress: step)
                libraryChanged()
                text = r.title
            case .map, .addresses, .videoCopies:
                guard let root = Library.shared.root else { throw InstallError.refused("Install a library first.") }
                text = try DownloadInstall.run(e, state: plan.state, target: root, control: control, settings: settings, progress: step).title
                if item.kind == .map { Installer.afterOpen(settings: settings) }
            case .model:
                guard let root = Library.shared.root else { throw InstallError.refused("Install a library first.") }
                text = try DownloadInstall.runModel(e, root: root, control: control, progress: step)
            }
            base += item.remainingDownload
            events(.finished(item: item, report: text))
        }
    }
}

extension DownloadInstall {
    /// Mac test tool only: fetch a small stand-in "model" from downloads.lastbook.org (never 17 GB on a test machine).
    nonisolated(unsafe) static var modelHostsOverride: Download.Hosts?

    /// The local AI model: from huggingface.co (desktop's model host and its download hosts), the SHA-256 checked as it
    /// arrives, then moved to <library>/models/, where LocalAI looks first, and LocalAI is asked to look again.
    static func runModel(_ e: CatalogEntry, root: URL, control: DownloadControl, progress: @escaping (Step) -> Void) throws -> String {
        let hosts = modelHostsOverride ?? .model
        guard e.available, let f = e.files.first, let url = URL(string: f.url), Download.urlAllowed(url, hosts) else {
            throw InstallError.network("Lastbook refused to download from an address it does not know.")
        }
        try checkSpace(e, f, target: root)
        let d = Download(url: url, dest: try dest(for: f, target: root), size: f.size, sha256: f.sha256, control: control, hosts: hosts) { done, total, ph in
            progress(ph == .downloading ? .downloading(done, total) : .verifying(done, total))
        }
        let file = try d.run()
        progress(.installing(.switching, 0, 0))
        let place = root.appendingPathComponent("models/\(f.name)")
        try? FileManager.default.removeItem(at: place)
        do { try ZipInstall.move(file, place) } catch { throw InstallError.folder("Lastbook could not put the local AI in place.") }
        // The SHA-256 was verified as the bytes arrived (Download.run): hand that to LocalAI so it doesn't read 17 GB again.
        LocalAI.shared.model?.markChecked(place, sha256: f.sha256)
        LocalAI.shared.model?.setEnabled(true)
        LocalAI.shared.model?.discover()
        return "Local AI downloaded"
    }
}

/// Progress reaches the screen at most five times a second.
final class Throttle: @unchecked Sendable {
    private let lock = NSLock(); private var last = Date.distantPast
    func due(final: Bool) -> Bool {
        lock.withLock { let now = Date(); if final || now.timeIntervalSince(last) > 0.2 { last = now; return true }; return false }
    }
}

/// The install screen's run: plan, start, progress, cancel, resume. Everything the view shows comes from here.
@MainActor
final class InstallRun: ObservableObject {
    @Published private(set) var plan: Plan?
    @Published private(set) var running = false
    @Published private(set) var current: PlanItem?
    @Published private(set) var phase = ""
    @Published private(set) var itemDone: Int64 = 0
    @Published private(set) var itemTotal: Int64 = 0
    @Published private(set) var overallDone: Int64 = 0
    @Published private(set) var overallTotal: Int64 = 0
    @Published private(set) var rateText: String?          // "12.3 MB/s · about 4 min left", only once measurable
    @Published private(set) var error: InstallError?
    @Published private(set) var finishedItems: [String] = []
    /// True while a plan is being made: the first plan on a big library opens every video once to see which need copies
    /// (All: 2,324). Show "Checking this iPad's videos…" meanwhile; it never runs on the main thread.
    @Published private(set) var planning = false
    /// The pack to install: the installed library's pack, else Small. Medium and All can be chosen.
    @Published var pack: String = UserDefaults.standard.string(forKey: InstallRun.packKey) ?? InstallPlan.packID {
        didSet { UserDefaults.standard.set(pack, forKey: Self.packKey); replan() }
    }
    static let packKey = "lastbook.install.pack"
    @Published var state: String? = UserDefaults.standard.string(forKey: InstallRun.stateKey) {
        didSet { UserDefaults.standard.set(state, forKey: InstallRun.stateKey); replan() }
    }
    static let stateKey = "lastbook.install.state"
    @Published var wantAI: Bool = UserDefaults.standard.object(forKey: InstallRun.aiKey) as? Bool ?? InstallPlan.defaultWantAI() {
        didSet { UserDefaults.standard.set(wantAI, forKey: Self.aiKey); replan() }
    }
    static let aiKey = "lastbook.install.ai"
    private let control = DownloadControl()
    private var samples: [(Date, Int64)] = []
    var onLibraryChanged: () -> Void = {}

    /// Complete: the library and the required state map (and addresses when published) are installed and checked.
    var complete: Bool { plan?.complete ?? false }

    private var planSerial = 0

    func replan() {
        let st = state, ai = wantAI, pk = pack
        planSerial += 1
        let serial = planSerial
        planning = true
        Task {
            let p = await Task.detached(priority: .userInitiated) { InstallPlan.make(pack: pk, state: st, wantAI: ai) }.value
            guard serial == planSerial else { return }
            planning = false
            if !running { plan = p }
        }
    }

    /// The first time: the installed library's pack (if no choice was saved), then a plan.
    func prepare() {
        planning = true
        Task {
            let d = await Task.detached(priority: .userInitiated) { InstallPlan.defaultPack() }.value
            if UserDefaults.standard.string(forKey: Self.packKey) == nil, d != pack { pack = d } else { replan() }
        }
    }

    #if canImport(UIKit)
    private var idleWas: Bool?
    #endif
    /// The screen stays on while a run is active (a download of hours must not stop for the screen lock), and goes back to
    /// what it was after a finish, Cancel or failure.
    private func keepAwake(_ on: Bool) {
        #if canImport(UIKit)
        if on { if idleWas == nil { idleWas = UIApplication.shared.isIdleTimerDisabled }; UIApplication.shared.isIdleTimerDisabled = true }
        else if let was = idleWas { UIApplication.shared.isIdleTimerDisabled = was; idleWas = nil }
        #endif
    }

    func cancel() { control.stop(); phase = "Stopping…" }

    /// Start, or resume after Cancel or a failure: a fresh plan, from the first unfinished item.
    func start() {
        guard !running else { return }
        error = nil; finishedItems = []; running = true; samples = []; rateText = nil
        control.reset()
        keepAwake(true)
        let st = state, ai = wantAI, pk = pack, control = self.control, throttle = Throttle()
        Task.detached(priority: .userInitiated) {
            let p = InstallPlan.make(pack: pk, state: st, wantAI: ai)
            await MainActor.run { self.plan = p; self.overallTotal = p.downloadBytes; self.overallDone = 0 }
            var failure: InstallError?
            do {
                try InstallRunner.run(p, control: control, libraryChanged: {
                    InstallRunner.useNewLibrary()
                    Task { @MainActor in self.onLibraryChanged() }
                }) { ev in
                    switch ev {
                    case .started(let i):
                        Task { @MainActor in self.current = i; self.phase = ""; self.itemDone = 0; self.itemTotal = 0; self.samples = [] }
                    case .progress(_, let ph, let d, let t, let dl, let od, let ot):
                        if throttle.due(final: d == t) {
                            Task { @MainActor in
                                self.phase = ph; self.itemDone = d; self.itemTotal = t; self.overallDone = od; self.overallTotal = ot
                                self.measure(od, ot, downloading: dl)
                            }
                        }
                    case .finished(let i, _):
                        Task { @MainActor in self.finishedItems.append(i.id) }
                    }
                }
            } catch let e as InstallError { failure = e } catch { failure = .network("\(error)") }
            let after = InstallPlan.make(pack: pk, state: st, wantAI: ai)
            let failed = failure
            await MainActor.run {
                self.keepAwake(false)
                self.plan = after; self.running = false; self.current = nil; self.rateText = nil
                self.error = failed
                if failed == nil && !after.complete {
                    self.error = .refused("Not finished yet: " + (after.blockers.first ?? after.items.filter { $0.required && $0.status != .installed }.map(\.title).joined(separator: ", ")))
                }
            }
        }
    }
    func resume() { start() }

    private func measure(_ d: Int64, _ t: Int64, downloading: Bool) {
        guard downloading else { rateText = nil; return }
        let now = Date()
        samples.append((now, d)); samples.removeAll { now.timeIntervalSince($0.0) > 10 }
        guard let first = samples.first, now.timeIntervalSince(first.0) >= 3, d - first.1 >= 1 << 20 else { rateText = nil; return }
        let rate = Double(d - first.1) / now.timeIntervalSince(first.0)
        let left = Double(t - d) / rate
        let f = DateComponentsFormatter(); f.allowedUnits = left >= 3600 ? [.hour, .minute] : [.minute, .second]; f.unitsStyle = .abbreviated
        rateText = "\(ByteCountFormatter.string(fromByteCount: Int64(rate), countStyle: .file))/s · about \(f.string(from: left) ?? "") left"
    }
}
