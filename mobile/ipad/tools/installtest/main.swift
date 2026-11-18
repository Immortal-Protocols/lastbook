import Foundation

// Mac test tool for the iPad map installer (Engine/Install). Never part of the app. Run it only on a COPY of a library
// (tools/build_installtest.sh makes build/install-test/LastbookData as an APFS clone of build/LastbookData).
//
//   installtest stage   ZIP ROOT ID SETTINGS            check + unpack into ROOT.setup/unpack-map, nothing switched
//   installtest install ZIP ROOT ID SETTINGS            stage, then activate
//   installtest fail    ZIP ROOT ID SETTINGS PHASE N    stage, activate with a failure after N renames in PHASE (out|in)
//   installtest crash   ZIP ROOT ID SETTINGS PHASE N    same, but the swap stops dead (app killed); then recoverIfNeeded
//   installtest recover ROOT SETTINGS                   recoverIfNeeded
//   installtest cleanup ROOT SETTINGS                   cleanupAfterOpen
//   installtest import  FILE TARGET STATE SETTINGS [unlisted] [h264|no-h264]   the install screen's path (Installer.install)
//   installtest download KIND ID DIR [stop-after N] [pins-none]   a REAL download (downloads.lastbook.org)
//   installtest dlinstall KIND ID TARGET STATE SETTINGS              download + install, as the screen does
//   installtest unzip   ZIP OUTDIR                      extract every member with ZipReader (CRC checked), print each
// ID may be '-' for no expected state. Prints one line per step; exit 1 on an install error.

let a = CommandLine.arguments
func usage() -> Never { FileHandle.standardError.write(Data("see tools/installtest/main.swift for usage\n".utf8)); exit(2) }
guard a.count >= 3 else { usage() }
let cmd = a[1]

func say(_ s: String) { print(s); fflush(stdout) }

func stage(_ zip: String, _ root: String, _ id: String) throws -> MapInstall.Staged {
    let t0 = Date()
    var last = 0.0
    let s = try MapInstall.stage(zip: URL(fileURLWithPath: zip), root: URL(fileURLWithPath: root), expectedID: id == "-" ? nil : id,
                                 progress: { d, t in
                                     let f = t > 0 ? Double(d) / Double(t) : 1
                                     if f - last >= 0.25 || d == t { last = f; say(String(format: "progress %.0f%% (%lld / %lld)", f * 100, d, t)) }
                                 })
    say(String(format: "staged %@ %lld bytes in %.1fs at %@", s.name, s.bytes, Date().timeIntervalSince(t0), s.newLib.path))
    return s
}

do {
    switch cmd {
    case "stage":
        guard a.count >= 6 else { usage() }
        _ = try stage(a[2], a[3], a[4])
    case "install", "fail", "crash":
        guard a.count >= (cmd == "install" ? 6 : 8) else { usage() }
        let settings = URL(fileURLWithPath: a[5])
        let s = try stage(a[2], a[3], a[4])
        if cmd != "install" { MapInstall.testFailPoint = .init(phase: a[6], after: Int(a[7]) ?? 0, crash: cmd == "crash") }
        let t0 = Date()
        do {
            let o = try MapInstall.activate(s, settings: settings)
            say(String(format: "activate %@ in %.2fs; map is now %@", "\(o)", Date().timeIntervalSince(t0), MapInstall.mapName(s.root)))
        } catch is MapInstall.SimulatedCrash {
            say("crashed mid-swap (simulated); pending file left: \(FileManager.default.fileExists(atPath: MapInstall.pendingFile(settings).path))")
            MapInstall.testFailPoint = nil
            let o = MapInstall.recoverIfNeeded(root: s.root, settings: settings)
            say("recover \(o.map { "\($0)" } ?? "nothing"); map is now \(MapInstall.mapName(s.root))")
        }
    case "recover":
        guard a.count >= 4 else { usage() }
        let o = MapInstall.recoverIfNeeded(root: URL(fileURLWithPath: a[2]), settings: URL(fileURLWithPath: a[3]))
        say("recover \(o.map { "\($0)" } ?? "nothing"); map is \(MapInstall.mapName(URL(fileURLWithPath: a[2])))")
    case "cleanup":
        guard a.count >= 4 else { usage() }
        MapInstall.cleanupAfterOpen(root: URL(fileURLWithPath: a[2]), settings: URL(fileURLWithPath: a[3]))
        say("cleaned")
    case "import":
        // import FILE TARGET STATE SETTINGS [unlisted] [h264|no-h264]: Installer.install as the install screen calls it.
        // TARGET is the LastbookData a pack becomes (never ~/Documents); STATE may be '-'.
        guard a.count >= 6 else { usage() }
        Installer.packTargetOverride = URL(fileURLWithPath: a[3])
        if a.contains("h264") { Installer.needsH264Override = true }
        if a.contains("no-h264") { Installer.needsH264Override = false }
        if FileManager.default.fileExists(atPath: a[3]) { Library.shared.useForTesting(URL(fileURLWithPath: a[3])) }
        let t0 = Date()
        var last = -1
        let r = try Installer.install(file: URL(fileURLWithPath: a[2]), state: a[4] == "-" ? nil : a[4], allowUnlisted: a.contains("unlisted"),
                                      settings: URL(fileURLWithPath: a[5]), progress: { p, d, t in
                                          let pct = t > 0 ? Int(d * 4 / t) : 0
                                          if pct != last { last = pct; say("\(p.rawValue) \(pct * 25)%") }
                                      })
        if FileManager.default.fileExists(atPath: a[3]) { Library.shared.useForTesting(URL(fileURLWithPath: a[3])) }
        Installer.afterOpen(settings: URL(fileURLWithPath: a[5]))
        say(String(format: "installed in %.1fs: %@ — %@", Date().timeIntervalSince(t0), r.title, r.detail))
        let st = Installer.status()
        say("status: library \(st.library ?? "none"), map \(st.map), addresses \(st.addresses) checked \(st.addressesChecked), video copies \(st.videoCopies), old \(st.oldLibraries.map { $0.url.lastPathComponent })")
    case "packfail":
        // packfail ZIP TARGET SETTINGS: stage a pack, then fail between the two renames; the old library must come back.
        guard a.count >= 5 else { usage() }
        let s = try PackInstall.stage(zip: URL(fileURLWithPath: a[2]), target: URL(fileURLWithPath: a[3]), entry: nil, includeVideoCopies: false)
        PackInstall.testFailAfterMoveAside = true
        do { try PackInstall.activate(s, settings: URL(fileURLWithPath: a[4])) } catch { say("activate failed as asked: \(error)") }
    case "recover-pack":
        guard a.count >= 4 else { usage() }
        let o = PackInstall.recoverIfNeeded(target: URL(fileURLWithPath: a[2]), settings: URL(fileURLWithPath: a[3]))
        say("recover-pack \(o.map { "\($0)" } ?? "nothing")")
    case "download":
        // download KIND ID DIR [stop-after N] [pins-none]: one REAL download of a listed file from downloads.lastbook.org.
        guard a.count >= 5, let kind = CatalogEntry.Kind(rawValue: a[2]), let e = InstallCatalog.entry(kind, a[3]), let f = e.files.first,
              let url = URL(string: f.url) else { usage() }
        if a.contains("pins-none") { Download.pinsOverride = [] }
        if let i = a.firstIndex(of: "hash-state-from"), let n = Int64(a[i + 1]) { Download.hashStateFrom = n }
        let stopAt = a.firstIndex(of: "stop-after").flatMap { Int64(a[$0 + 1]) }
        let control = DownloadControl()
        let dest = URL(fileURLWithPath: a[4]).appendingPathComponent(f.name)
        var lastPct = -1, lastPhase = ""
        let t0 = Date()
        let d = Download(url: url, dest: dest, size: f.size, sha256: f.sha256, control: control) { done, total, ph in
            let pct = total > 0 ? Int(done * 4 / total) * 25 : 0
            if pct != lastPct || ph.rawValue != lastPhase { lastPct = pct; lastPhase = ph.rawValue; say("\(ph.rawValue) \(done) / \(total) (\(pct)%)") }
            if let s = stopAt, done >= s, ph == .downloading { control.stop() }
        }
        say("start: \(f.name) \(f.size) bytes; already on disk \(d.doneBytes()) bytes")
        do {
            let out = try d.run()
            say(String(format: "done in %.1fs: %@ %lld bytes, sha256 %@", Date().timeIntervalSince(t0), out.lastPathComponent, ZipInstall.size(out) ?? -1,
                       try ZipInstall.sha256(out)))
        } catch let e as InstallError {
            say("stopped: \(e.code): \(e) — partial on disk \(d.doneBytes()) bytes")
            exit(1)
        }
    case "dlinstall":
        // dlinstall KIND ID TARGET STATE SETTINGS: the install screen's download path (space check, download, check, install).
        guard a.count >= 7, let kind = CatalogEntry.Kind(rawValue: a[2]), let e = InstallCatalog.entry(kind, a[3]) else { usage() }
        let target = URL(fileURLWithPath: a[4])
        Installer.packTargetOverride = target
        Library.shared.useForTesting(target)
        let t0 = Date()
        let r = try DownloadInstall.run(e, state: a[5] == "-" ? nil : a[5], target: target, control: DownloadControl(),
                                        settings: URL(fileURLWithPath: a[6])) { _ in }
        say(String(format: "installed in %.1fs: %@ — %@", Date().timeIntervalSince(t0), r.title, r.detail))
        say("checked address indexes: \(AddressInstall.installed(root: target)); downloads left: \((try? FileManager.default.contentsOfDirectory(atPath: ZipInstall.workFolder(target).appendingPathComponent("downloads").path)) ?? [])")
    case "spacecheck":
        // spacecheck DIR GB: DownloadInstall.checkSpace for a made-up entry of GB download + GB installed. No network.
        guard a.count >= 4, let gb = Int64(a[3]) else { usage() }
        let f = CatalogFile(name: "Test.zip", url: "https://downloads.lastbook.org/Test.zip", size: gb << 30, sha256: String(repeating: "0", count: 64))
        let e = CatalogEntry(kind: .pack, id: "test", title: "Test", installedBytes: gb << 30, revision: nil, files: [f], available: true)
        do { try DownloadInstall.checkSpace(e, f, target: URL(fileURLWithPath: a[2]).appendingPathComponent("LastbookData")); say("fits") }
        catch let e as InstallError { say("\(e.code): \(e)") }
    case "plan", "runplan":
        // plan TARGET STATE [flags]: InstallPlan.make with this Mac standing in for an iPad.
        // runplan TARGET STATE SETTINGS [flags] [stop-at BYTES]: InstallRunner.run on that plan (REAL downloads: only use it
        //   when every item to download is small; `only K1,K2` keeps just those kinds, `fake-model` swaps the model entry for
        //   a small published file).
        // flags: h264 | no-h264, ai | no-ai, ram GB, runtime, free GB
        guard a.count >= 4 else { usage() }
        let target = URL(fileURLWithPath: a[2])
        func arg(_ k: String) -> String? { a.firstIndex(of: k).flatMap { $0 + 1 < a.count ? a[$0 + 1] : nil } }
        Installer.packTargetOverride = target
        Installer.needsH264Override = a.contains("h264") ? true : false
        let isLib = MapInstall.isLibrary(target)
        if isLib { Library.shared.useForTesting(target) }
        let env = InstallPlan.Env(root: isLib ? target : nil, packTarget: target, needsH264: Installer.needsH264Override!,
                                  // `missing N` stands in for an iPad's own decoder check (this Mac decodes AV1, so coverage() finds none)
                                  av1Missing: arg("missing").flatMap { Int($0) } ?? (isLib && Installer.needsH264Override! ? VideoCompat.shared.coverage().missing : 0),
                                  ram: arg("ram").flatMap { UInt64($0) }.map { $0 << 30 } ?? ProcessInfo.processInfo.physicalMemory,
                                  aiRuntime: a.contains("runtime"),
                                  free: arg("free").flatMap { Int64($0) }.map { $0 << 30 } ?? ZipInstall.freeSpace(target.deletingLastPathComponent()))
        let wantAI = a.contains("ai") ? true : a.contains("no-ai") ? false : InstallPlan.defaultWantAI(env)
        var plan = InstallPlan.make(pack: arg("pack") ?? InstallPlan.packID, state: a[3] == "-" ? nil : a[3], wantAI: wantAI, env: env)
        if let only = arg("only") {
            let kinds = Set(only.split(separator: ",").map(String.init))
            plan.items = plan.items.filter { kinds.contains($0.kind.rawValue) }
        }
        if a.contains("fake-model"), let i = plan.items.firstIndex(where: { $0.kind == .model }), let ak = InstallCatalog.entry(.addresses, "AK") {
            // a stand-in model: the published 12 MB AK address zip, fetched by the model path (host override for the test only)
            let f = ak.files[0]
            let fake = CatalogEntry(kind: .model, id: "test-model", title: "Test model", installedBytes: f.size, revision: nil,
                                    files: [f], available: true, memoryBytes: 1)
            var it = plan.items[i]
            it = PlanItem(id: "model:test", kind: .model, title: "Test model", downloadBytes: f.size, installedBytes: f.size,
                          partialBytes: DownloadInstall.partial(f, target: target), status: it.status == .installed ? .toDownload : it.status,
                          required: false, note: it.note, entry: fake)
            plan.items[i] = it
            DownloadInstall.modelHostsOverride = .library
        }
        func show(_ p: Plan) {
            say("plan for \(p.state ?? "no state"): complete=\(p.complete) fits=\(p.fits) download=\(p.downloadBytes) need=\(p.spaceNeeded) free=\(p.free ?? -1)")
            for i in p.items {
                say("  \(i.id) [\(i.required ? "required" : "optional")] \(i.status) download=\(i.downloadBytes) installed=\(i.installedBytes) partial=\(i.partialBytes)\(i.note.map { " note: \($0)" } ?? "")")
            }
            for b in p.blockers { say("  blocker: \(b)") }
        }
        show(plan)
        if cmd == "runplan" {
            guard a.count >= 5 else { usage() }
            let control = DownloadControl()
            let stopAt = arg("stop-at").flatMap(Int64.init)
            do {
                try InstallRunner.run(plan, control: control, settings: URL(fileURLWithPath: a[4]), libraryChanged: {
                    Library.shared.useForTesting(target); Installer.afterOpen(settings: URL(fileURLWithPath: a[4]))
                }) { ev in
                    switch ev {
                    case .started(let i): say("started \(i.id) (resuming from \(i.partialBytes))")
                    case .progress(let i, let ph, let d, _, let dl, let od, let ot):
                        if let s = stopAt, dl, od >= s { control.stop() }
                        _ = (i, ph, d)
                        if dl && d == i.downloadBytes { say("  \(i.id) downloaded; overall \(od) of \(ot)") }
                    case .finished(let i, let r): say("finished \(i.id): \(r)")
                    }
                }
                say("run ended")
            } catch let e as InstallError { say("run stopped: \(e.code): \(e)") }
            let after = InstallPlan.make(pack: plan.pack, state: plan.state, wantAI: wantAI, env: InstallPlan.Env(root: MapInstall.isLibrary(target) ? target : nil,
                packTarget: target, needsH264: env.needsH264, av1Missing: env.av1Missing, ram: env.ram, aiRuntime: env.aiRuntime, free: env.free))
            say("after:"); show(after)
        }
    case "unzip":
        guard a.count >= 4 else { usage() }
        let z = try ZipReader(url: URL(fileURLWithPath: a[2]))
        let out = URL(fileURLWithPath: a[3])
        for e in z.entries where !e.isDirectory {
            let t0 = Date()
            let dest = out.appendingPathComponent(e.name.replacingOccurrences(of: "/", with: "_"))
            FileManager.default.createFile(atPath: dest.path, contents: nil)
            let h = try FileHandle(forWritingTo: dest)
            let n = try z.extract(e, to: h)
            try h.close()
            say(String(format: "ok %@ %llu bytes (method %d, crc %08x) %.1fs", e.name, n, e.method, e.crc32, Date().timeIntervalSince(t0)))
        }
    default: usage()
    }
} catch let e as InstallError {
    say("error \(e.code): \(e)")
    exit(1)
} catch {
    say("error: \(error)")
    exit(1)
}
