import Foundation

// Mac test harness for the iPad app's local AI: the app's own engine, routes and AI files (Engine/AI, ChatAPI), linked to the
// same llama.cpp bridge built for macOS (build/llama/macosx). It drives the model through the same /api/assistant/status and
// /api/chat routes the web view uses, and the same lifecycle calls UIKit triggers (launch, foreground, background, memory
// warning). Never part of the app. Mac numbers say nothing about the iPad: device numbers come only from a physical iPad.
//
//   aiharness LASTBOOK_DATA DESKTOP_SOURCE MODEL_FOLDER STATE_FILE OUT_DIR SCENARIO ['question' ['follow-up']]
//
// Scenarios: ask (question, optional follow-up), prewarm, disabled, missing, background, memory, relaunch,
//            q-checking, q-measuring, q-loading, q-stop
// env AIH_STOP_AFTER_S / AIH_CANCEL_AFTER_S (ask): background stop / the person's Stop N s into the answer.
// env LASTBOOK_AI_TEST_SLOW_LOAD_MS: slows each load step, to act while it loads.

let a = CommandLine.arguments
guard a.count >= 7 else {
    FileHandle.standardError.write(Data("usage: aiharness LASTBOOK_DATA DESKTOP_SOURCE MODEL_FOLDER STATE_FILE OUT_DIR SCENARIO ['question' ['follow-up']]\n".utf8))
    exit(2)
}
setvbuf(stdout, nil, _IOLBF, 0)
Resources.override = URL(fileURLWithPath: a[2])
Library.shared.useForTesting(URL(fileURLWithPath: a[1]))
Router.shared.install(Routes.all)
let modelDir = URL(fileURLWithPath: a[3])
let model = LlamaLocal(stateFile: URL(fileURLWithPath: a[4]), places: { [modelDir] }, documents: nil)
LocalAI.shared.model = model
let out = URL(fileURLWithPath: a[5])
try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
let scenario = a[6]
let question = a.count > 7 ? a[7] : "The tap water is off. How do I make water safe to drink?"
let env = ProcessInfo.processInfo.environment
let T0 = Date()
func now() -> String { String(format: "%6.2fs", Date().timeIntervalSince(T0)) }
func log(_ s: String) { print("\(now()) \(s)") }
var failures: [String] = []
func expect(_ ok: Bool, _ what: String) { log((ok ? "PASS " : "FAIL ") + what); if !ok { failures.append(what) } }

func route(_ method: String, _ path: String, _ body: Any? = nil, quiet: Bool = false, alive: @escaping () -> Bool = { true }) -> (Int, Data) {
    let comps = URLComponents(string: "lastbook://app" + path)!
    let req = APIRequest(method: method, path: comps.path, query: APIRequest.parseQuery(comps.percentEncodedQuery), headers: [:],
                         body: body.flatMap { try? JSONSerialization.data(withJSONObject: $0) })
    let r = Router.shared.route(req)
    switch r.body {
    case .data(let d): return (r.status, d)
    case .file(let u): return (r.status, (try? Data(contentsOf: u)) ?? Data())
    case .stream(let produce):
        var all = Data()
        let sem = DispatchSemaphore(value: 0)
        let lock = NSLock()
        var lastLine = ""
        Thread.current.threadDictionary[ChatAPI.aliveKey] = alive
        produce { chunk in
            guard let chunk else { sem.signal(); return }
            lock.lock(); all.append(chunk); lock.unlock()
            if quiet { return }
            for line in String(decoding: chunk, as: UTF8.self).split(separator: "\n") where line.hasPrefix("data: ") {
                let ev = (try? JSONSerialization.jsonObject(with: Data(line.dropFirst(6).utf8))) as? Rec ?? [:]
                var l = ""
                switch ev.s("type") {
                case "delta": print(ev.s("text"), terminator: ""); continue
                case "state": l = "[state \(ev.s("state"))\(ev["pct"].map { $0 is NSNull ? "" : " \($0)" } ?? "") · model \(model.state)]"
                case "tool": l = "[tool \(ev.s("phase")) \(ev.s("name"))]"
                case "done": l = "[done: \((ev["sources"] as? [Rec])?.count ?? 0) cited, invalid \((ev["invalid"] as? [Any])?.count ?? 0)]"
                default: l = "[\(ev.s("type"))\(ev["count"].map { " \($0)" } ?? "")\(ev["text"].map { ": \($0)" } ?? "")]"
                }
                if l != lastLine { print(""); log(l); lastLine = l }
            }
        }
        Thread.current.threadDictionary.removeObject(forKey: ChatAPI.aliveKey)
        sem.wait()
        return (r.status, all)
    }
}

func status() -> Rec { (try? JSONSerialization.jsonObject(with: route("GET", "/api/assistant/status").1)) as? Rec ?? [:] }
func local() -> Rec { status()["local"] as? Rec ?? [:] }
func events(_ d: Data) -> [Rec] {
    String(decoding: d, as: UTF8.self).components(separatedBy: "\n\n").compactMap { c in
        c.hasPrefix("data: ") ? (try? JSONSerialization.jsonObject(with: Data(c.dropFirst(6).utf8))) as? Rec : nil
    }
}
/// Polls status until `until` or the timeout, printing each change. Returns the last `local`.
@discardableResult
func watch(_ secs: Double, until: (Rec) -> Bool) -> Rec {
    let t = Date()
    var last = "", l: Rec = [:]
    while Date().timeIntervalSince(t) < secs {
        let s = status()
        l = s["local"] as? Rec ?? [:]
        let line = "online=\(s["online"]!) state=\(l.s("state")) phase=\(l.s("phase")) pct=\(l["pct"] ?? "") \(l.s("message"))"
        if line != last { log(line); last = line }
        if until(l) { break }
        Thread.sleep(forTimeInterval: 0.1)
    }
    return l
}
func ask(_ q: String, history: [Rec] = [], alive: @escaping () -> Bool = { true }) -> [Rec] {
    let t = Date()
    let (code, body) = route("POST", "/api/chat", ["messages": history + [["role": "user", "content": q]], "about": NSNull()], alive: alive)
    print("")
    log("HTTP \(code), \(String(format: "%.1f", Date().timeIntervalSince(t))) s")
    return events(body)
}
/// The two kinds of request the web view makes while browsing (Videos and Map), timed.
func uiProbe() -> (Double, Double) {
    var t = Date(); _ = route("GET", "/api/videos"); let v = Date().timeIntervalSince(t) * 1000
    t = Date(); _ = route("GET", "/api/map/tile/11/351/817?v=1"); let m = Date().timeIntervalSince(t) * 1000
    return (v, m)
}
func done(_ evs: [Rec]) -> Rec? { evs.last { $0.s("type") == "done" } }

switch scenario {
case "ask":
    watch(900) { !["checking", "measuring", "absent"].contains($0.s("state")) }
    var gone = false
    if let s = env["AIH_STOP_AFTER_S"].flatMap(Double.init) {
        DispatchQueue.global().asyncAfter(deadline: .now() + s) { log("[harness: app goes to the background]"); model.didEnterBackground() }
    }
    if let s = env["AIH_CANCEL_AFTER_S"].flatMap(Double.init) {
        DispatchQueue.global().asyncAfter(deadline: .now() + s) { log("[harness: Stop pressed]"); gone = true }
    }
    let evs = ask(question, alive: { !gone })
    if let d = done(evs) {
        try? JSONSerialization.data(withJSONObject: d, options: [.prettyPrinted, .sortedKeys]).write(to: out.appendingPathComponent("done1.json"))
        log("CITED: " + ((d["sources"] as? [Rec]) ?? []).map { "[\($0.s("key"))] \($0.s("title")) p\($0["page"] ?? "")" }.joined(separator: "; "))
        if a.count > 8 {
            _ = ask(a[8], history: [["role": "user", "content": question], ["role": "assistant", "content": d.s("answer")]])
        }
    }

case "prewarm":
    // Launch prewarm reaches ready, a second prewarm is a no-op, and Videos/Map requests stay fast while it loads.
    var base: [(Double, Double)] = []
    for _ in 0..<5 { base.append(uiProbe()) }
    log("UI before load: videos \(base.map { Int($0.0) }) ms, map tile \(base.map { Int($0.1) }) ms")
    let t = Date()
    model.appLaunched()
    log("appLaunched returned in \(String(format: "%.1f", Date().timeIntervalSince(t) * 1000)) ms")
    var during: [(Double, Double)] = [], sawLoading = false
    while Date().timeIntervalSince(t) < 600 {
        let l = local()
        if l.s("state") == "loading" { sawLoading = true; during.append(uiProbe()); model.prewarm("again"); model.appLaunched() }
        if l.s("state") == "ready" { break }
        if ["checking", "measuring"].contains(l.s("state")) { during.append(uiProbe()) }
        Thread.sleep(forTimeInterval: 0.01)
    }
    let l = watch(1) { _ in true }
    log("UI while preparing/loading (\(during.count) samples): videos max \(Int(during.map { $0.0 }.max() ?? 0)) ms, median \(Int(during.map { $0.0 }.sorted()[safe: during.count / 2] ?? 0)) ms; map tile max \(Int(during.map { $0.1 }.max() ?? 0)) ms, median \(Int(during.map { $0.1 }.sorted()[safe: during.count / 2] ?? 0)) ms")
    expect(l.s("state") == "ready", "launch prewarm reaches ready (load_s \(l["load_s"] ?? ""))")
    expect(sawLoading, "the load was observed as `loading` with pct")

case "disabled":
    model.setEnabled(false)
    let t = Date()
    model.appLaunched()
    let l = watch(3) { _ in false }
    expect(l.s("state") == "off" && l.s("phase") == "unavailable", "disabled: state off, phase unavailable, no load")
    expect(((l["prewarm"] as? Rec)?["last"] as? Rec)?.s("skipped") == "off", "disabled: prewarm skipped (off)")
    _ = t
    model.setEnabled(true)   // leave it as found
    model.stop("asked")

case "missing":
    model.appLaunched()
    let l = watch(3) { _ in false }
    let s = status()
    expect(l.s("state") == "absent" && l.s("phase") == "unavailable" && l.s("message").isEmpty, "missing: absent, phase unavailable, no message, no error")
    expect((s["online"] as? Bool) == false, "missing: online false (chat.js falls back to library pages)")
    let evs = ask(question)
    expect(evs.first?.s("type") == "error" && evs.first?.s("error") == "model_unavailable", "missing: /api/chat answers model_unavailable with a plain reason: \(evs.first?.s("text") ?? "")")

case "background":
    // Background during a load cancels it and frees it; the next foreground loads again.
    model.appLaunched()
    watch(600) { $0.s("state") == "loading" && (($0["pct"] as? NSNumber)?.intValue ?? 0) > 0 }
    log("[harness: app goes to the background]")
    model.didEnterBackground()
    let l = local()
    expect(l.s("state") == "stopped", "background during load: state stopped at once (\(l.s("state")))")
    Thread.sleep(forTimeInterval: 3)
    let l2 = watch(1) { _ in true }
    expect(l2.s("state") == "stopped" && (l2["prewarm"] as? Rec)?["foreground"] as? Bool == false, "still stopped and not reloading while in the background")
    log("[harness: app comes to the front]")
    model.willEnterForeground()
    let l3 = watch(600) { $0.s("state") == "ready" }
    expect(l3.s("state") == "ready", "next foreground prewarms again to ready")

case "memory":
    model.appLaunched()
    watch(600) { $0.s("state") == "ready" }
    log("[harness: memory warning]")
    model.memoryWarning()
    model.prewarm("status poll")             // what a status poll, a library rescan or a stray call could do
    _ = route("POST", "/api/assistant/local", ["action": "rescan"])
    let l = watch(4) { _ in false }
    expect(l.s("state") == "stopped" && ((l["prewarm"] as? Rec)?["blocked"] as? String) == "memory", "memory warning: unloaded, no re-prewarm in this foreground session")
    log("[harness: app comes to the front]")
    model.willEnterForeground()
    let l2 = watch(600) { $0.s("state") == "ready" }
    expect(l2.s("state") == "ready", "next foreground prewarms again")

case "relaunch":
    // Run twice: the second process must not read the 17 GB again (the log says remembered; it is ready fast).
    let t = Date()
    model.appLaunched()
    let l = watch(900) { ["ready", "error", "too_big", "wrong", "absent"].contains($0.s("state")) }
    log("launch to \(l.s("state")): \(String(format: "%.2f", Date().timeIntervalSince(t))) s")

case "q-checking", "q-measuring":
    // A question while the file is being checked (or measured) waits through checking -> measuring -> loading and answers.
    model.appLaunched()
    let want = scenario == "q-checking" ? "checking" : "measuring"
    let l = watch(60) { $0.s("state") == want }
    expect(l.s("state") == want, "status shows \(want) (phase \(l.s("phase"))), online \(status()["online"]!)")
    let evs = ask(question)
    let stages = Set(evs.filter { $0.s("type") == "state" && $0.s("state") == "starting" }.compactMap { ($0["pct"] as? NSNumber)?.intValue })
    expect(done(evs) != nil, "question during \(want) waited and answered (\(stages.count) progress steps seen)")
    expect(!evs.contains { $0.s("type") == "error" }, "no error or unavailable event while preparing")

case "q-loading":
    model.appLaunched()
    watch(600) { $0.s("state") == "loading" }
    let evs = ask(question)
    expect(done(evs) != nil, "question during the prewarm load joined it and answered")
    expect(evs.contains { $0.s("type") == "state" && $0.s("state") == "starting" && $0["pct"] is NSNumber }, "it showed the load's pct")

case "q-stop":
    model.appLaunched()
    watch(600) { $0.s("state") == "loading" }
    var gone = false
    DispatchQueue.global().asyncAfter(deadline: .now() + 1.5) { log("[harness: Stop pressed]"); gone = true }
    let evs = ask(question, alive: { !gone })
    expect(!evs.contains { $0.s("type") == "error" } && done(evs) == nil, "Stop during preparation ends cleanly (no error, no answer)")
    let l = watch(600) { $0.s("state") == "ready" }
    expect(l.s("state") == "ready", "the prewarm load itself carries on to ready")

default:
    log("unknown scenario \(scenario)"); exit(2)
}

let fin = local()
log("final: state=\(fin.s("state")) phase=\(fin.s("phase")) load_s=\(fin["load_s"] ?? "")")
model.willTerminate()
log(failures.isEmpty ? "ALL PASS" : "FAILURES: \(failures)")
exit(failures.isEmpty ? 0 : 1)

extension Array { subscript(safe i: Int) -> Element? { indices.contains(i) ? self[i] : nil } }
