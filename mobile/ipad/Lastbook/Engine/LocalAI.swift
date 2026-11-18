import Foundation
#if canImport(UIKit)
import UIKit
#endif

/// The in-process local AI boundary. Lastbook ships exactly one model, Gemma 4 26B A4B (Unsloth UD-Q4_K_M), run by
/// llama.cpp dde879bc (the desktop's pinned commit) linked into the app (Engine/AI/LlamaLocal.swift, llm/). There is no
/// cloud AI and no fallback model. The exact model loaded and answered on a physical M1 iPad Pro (16 GB) in testing.
protocol LocalModel: AnyObject {
    /// "absent", "wrong", "checking", "measuring", "too_big", "stopped", "loading", "ready", "error", "off" (desktop llm_local.Local).
    var state: String { get }
    /// Desktop Local.status(): what /api/assistant/status reports as `local`.
    func status() -> Rec
    /// True when a question can be answered: running, or ready to load.
    var available: Bool { get }
    /// Look for the file again (desktop "Look again").
    func discover()
    func setEnabled(_ on: Bool)
    /// The installer verified this file's SHA-256 while downloading it: record it as checked (desktop mark_checked).
    @discardableResult func markChecked(_ path: URL, sha256: String) -> Bool
    /// Loads the model when it is stopped and waits for it. nil when ready, "stopped" when the person stopped, else why not.
    func ensureRunning(onWait: (Int?) -> Void, cancelled: () -> Bool) -> String?
    /// Streams the visible text for an already-rendered Gemma 4 prompt (segments of text and special markup, so library text
    /// can never inject turn tokens). Returns the runner's done event; throws a plain sentence.
    func generate(segments: [Segment], maxTokens: Int, cancelled: @escaping () -> Bool, piece: @escaping (String) -> Void) throws -> Rec
    /// Free the model's memory (idle stop, background, memory warning, quit, or asked).
    func stop(_ why: String)
    /// Load in the background if installed, enabled, verified and fitting. Idempotent; never blocks.
    func prewarm(_ reason: String)
    func appLaunched()
    func willEnterForeground()
    func didEnterBackground()
    func memoryWarning()
    func willTerminate()
}

/// Pinned identity of the local AI models (26B desktop/iPad default, plus 12B flagship and E2B low/mid mobile tiers).
enum Gemma4 {
    static let file = "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
    static let size: Int64 = 16_947_541_728
    static let sha256 = "f2c28b3dc4776931ac6f879e11f203dec637ea0f14267a86ec8f6165f63f293f"

    struct Tier: Identifiable, Equatable {
        let id: String
        let title: String
        let file: String
        let size: Int64
        let sha256: String
        let memoryBytes: Int64
        let url: String
    }

    static let tiers: [Tier] = [
        Tier(id: "gemma-4-26b-a4b", title: "Gemma 4 26B A4B", file: file, size: size, sha256: sha256,
             memoryBytes: 19_027_384_256,
             url: "https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/c099eb48e663fd284577b04978a94ffccb261841/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf?download=true"),
        Tier(id: "gemma-4-12b", title: "Gemma 4 12B", file: "gemma-4-12b-it-UD-Q4_K_XL.gguf", size: 7_366_423_360,
             sha256: "90fd944d227e9d9b68e7e2c7d5b57b79d4c66ed521b0919fbbd932cf834f6f8e",
             memoryBytes: 10_100_000_000,
             url: "https://huggingface.co/unsloth/gemma-4-12b-it-GGUF/resolve/fc034cfff751157913579611efad8462ac1be606/gemma-4-12b-it-UD-Q4_K_XL.gguf?download=true"),
        Tier(id: "gemma-4-e2b", title: "Gemma 4 E2B", file: "gemma-4-E2B-it-UD-Q4_K_XL.gguf", size: 3_184_496_736,
             sha256: "b52f438017efaec5debf1c0d8be690571e212a07c312f1102bbce927258cfc32",
             memoryBytes: 5_368_709_120,
             url: "https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/0314792d7f1f7e229411f620751375812bb9faf2/gemma-4-E2B-it-UD-Q4_K_XL.gguf?download=true"),
    ]

    static func tier(forFile name: String) -> Tier? { tiers.first { $0.file == name } }
    static func bestTier(forRAM ram: UInt64) -> Tier {
        tiers.filter { UInt64($0.memoryBytes) <= ram }.max(by: { $0.memoryBytes < $1.memoryBytes }) ?? tiers.last!
    }
}

final class LocalAI: @unchecked Sendable {
    static let shared = LocalAI()
    /// The model. Where it is looked for: the library's LastbookData folder (and its models/ folder, as desktop), then the
    /// app's own Documents folder (Files › On My iPad › Lastbook). Nothing is downloaded.
    var model: LocalModel?

    init() {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        let docs = Library.documents
        model = LlamaLocal(stateFile: support.appendingPathComponent("Lastbook/local-ai.json"), places: {
            var out: [URL] = []
            if let root = Library.shared.root { out += [root.appendingPathComponent("models"), root] }
            out.append(docs)
            var seen = Set<String>()
            return out.filter { seen.insert($0.standardizedFileURL.path).inserted }
        }, documents: docs)
        watchLifecycle()
    }

    /// The `local` part of /api/assistant/status (desktop Local.status()); also read by Readiness.
    var status: Rec {
        model?.status() ?? ["state": "error", "file": Gemma4.file, "message": "This copy of Lastbook has no local AI runtime."]
    }

    /// Used by the Mac harness: other places and state file.
    init(model: LocalModel?) { self.model = model }

    /// Prewarm when Lastbook opens and each time it comes back to the front. Free the model when it goes to the background,
    /// when iPadOS warns about memory (then no prewarm until the next return to the front) and when Lastbook quits. None of
    /// it runs on the main thread: the model's own work is on a background thread of utility priority.
    private func watchLifecycle() {
        #if canImport(UIKit)
        let nc = NotificationCenter.default
        let q = DispatchQueue(label: "lastbook.local-ai.lifecycle", qos: .utility)
        // LocalAI.shared is made while the app starts (ChatAPI touches it when the routes are installed in LastbookApp.init):
        // prewarm once the app runs, unless it is starting in the background.
        DispatchQueue.main.async { [weak self] in
            guard UIApplication.shared.applicationState != .background else { return }
            q.async { self?.model?.appLaunched() }
        }
        nc.addObserver(forName: UIApplication.willEnterForegroundNotification, object: nil, queue: nil) { [weak self] _ in
            q.async { self?.model?.willEnterForeground() }
        }
        nc.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: nil) { [weak self] _ in
            guard let m = self?.model else { return }
            var task = UIBackgroundTaskIdentifier.invalid
            task = UIApplication.shared.beginBackgroundTask(withName: "Free the local AI") { UIApplication.shared.endBackgroundTask(task) }
            DispatchQueue.global(qos: .userInitiated).async {
                m.didEnterBackground()
                DispatchQueue.main.async { UIApplication.shared.endBackgroundTask(task) }
            }
        }
        nc.addObserver(forName: UIApplication.didReceiveMemoryWarningNotification, object: nil, queue: nil) { [weak self] _ in
            guard let m = self?.model else { return }
            DispatchQueue.global(qos: .userInitiated).async { m.memoryWarning() }
        }
        nc.addObserver(forName: UIApplication.willTerminateNotification, object: nil, queue: nil) { [weak self] _ in
            self?.model?.willTerminate()
        }
        #endif
    }
}
