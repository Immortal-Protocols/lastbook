import Foundation

// Mac test tool: does the iPad installer (Engine/Install, read-only here) handle Medium and All the way desktop setup does
// (docs/SETUP-API.md "State maps": Medium has California built in and choosing another state replaces it; All has the
// whole US and needs no state map; addresses are per state for every pack)? Small fixtures only, made under
// build/medium-all/test/ (sparse files for the big sizes); no download, no real pack, no simulator or device.
//
//   tools/build_mediumalltest.sh && build/mediumalltest
//
// Each check prints PASS, or GAP with what desktop does and what the iPad code does now. Exit 0 when every check that
// is not a known gap passes; exit 1 on any unexpected result.

let here = URL(fileURLWithPath: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "build/medium-all/test")
let fm = FileManager.default
try? fm.removeItem(at: here)
try fm.createDirectory(at: here, withIntermediateDirectories: true)

var passed = 0, gaps: [String] = [], unexpected: [String] = []
func check(_ name: String, _ ok: Bool, gap: Bool = false, _ detail: @autoclosure () -> String = "") {
    if ok { passed += 1; print("PASS  \(name)") }
    else if gap { gaps.append(name); print("GAP   \(name)  — \(detail())") }
    else { unexpected.append(name); print("FAIL  \(name)  — \(detail())") }
    fflush(stdout)
}

func write(_ u: URL, _ s: String) throws {
    try fm.createDirectory(at: u.deletingLastPathComponent(), withIntermediateDirectories: true)
    try Data(s.utf8).write(to: u)
}
func sparse(_ u: URL, _ n: Int64) throws {
    try fm.createDirectory(at: u.deletingLastPathComponent(), withIntermediateDirectories: true)
    fm.createFile(atPath: u.path, contents: nil)
    let h = try FileHandle(forWritingTo: u); try h.truncate(atOffset: UInt64(n)); try h.close()
}

/// A library folder shaped like a pack: pack.json, a catalog, a map file; optional state map-set.json.
func library(_ name: String, pack: String, map: String, stateMap: String? = nil, revision: String? = nil) throws -> URL {
    let root = here.appendingPathComponent(name).appendingPathComponent("LastbookData")
    var pj = "{\"name\": \"\(pack)\", \"size\": \"\(pack)\", \"map\": \"\(map)\""
    if let revision { pj += ", \"content_revision\": \"\(revision)\"" }
    try write(root.appendingPathComponent("pack.json"), pj + "}")
    try write(root.appendingPathComponent("library-data/catalog.json"), "[]")
    try write(root.appendingPathComponent("derived/geo/map.sqlite"), "map of \(map)")
    if let stateMap {
        let n = try fm.attributesOfItem(atPath: root.appendingPathComponent("derived/geo/map.sqlite").path)[.size] as! Int
        try write(root.appendingPathComponent("map-set.json"), "{\"name\": \"\(stateMap)\", \"files\": {\"derived/geo/map.sqlite\": \(n)}}")
    }
    return root
}

/// Street addresses for a state, as AddressInstall.installed accepts them (sparse file at the listed size + receipt).
func addAddresses(_ root: URL, _ st: String) throws {
    let e = InstallCatalog.entry(.addresses, st)!
    try sparse(root.appendingPathComponent("derived/geo/addresses/\(st).sqlite"), e.installedBytes!)
    let files = e.files.map { "\"\($0.name)\": \"\($0.sha256)\"" }.joined(separator: ", ")
    try write(root.appendingPathComponent("derived/geo/addresses/\(st).json"), "{\"files\": {\(files)}}")
}

func env(_ root: URL?, needsH264: Bool = false, av1Missing: Int = 0, free: Int64? = 1 << 40) -> InstallPlan.Env {
    InstallPlan.Env(root: root, packTarget: here.appendingPathComponent("target/LastbookData"), needsH264: needsH264,
                    av1Missing: av1Missing, ram: 16 << 30, aiRuntime: true, free: free)
}
func item(_ p: Plan, _ kind: PlanItem.Kind) -> PlanItem? { p.items.first { $0.kind == kind } }
func gb(_ n: Int64) -> String { String(format: "%.1f GB", Double(n) / 1e9) }

// ---------------------------------------------------------------- catalog --
print("== catalog (bundled manifest-v1)")
let med = InstallCatalog.entry(.pack, "medium"), all = InstallCatalog.entry(.pack, "all")
check("catalog lists Medium (available, 1 file)", med?.available == true && med?.files.count == 1, "\(String(describing: med))")
check("catalog lists All (available, 1 file)", all?.available == true && all?.files.count == 1, "\(String(describing: all))")
print("      Medium: download \(gb(med?.downloadBytes ?? 0)), installed \(gb(med?.installedBytes ?? 0))")
print("      All:    download \(gb(all?.downloadBytes ?? 0)), installed \(gb(all?.installedBytes ?? 0))")
check("video copies listed for Medium", InstallCatalog.entry(.videoCopies, "medium") != nil,
      "InstallCatalog.videoCopies has only \"small\"; Medium's sidecar is not built/published yet")
check("video copies listed for All", InstallCatalog.entry(.videoCopies, "all") != nil,
      "InstallCatalog.videoCopies has only \"small\"")

// ---------------------------------------------------------------- plans --
let medium = try library("medium", pack: "medium", map: "CA")
let allLib = try library("all", pack: "all", map: "us")
print("== Medium installed (built-in California map, no map-set.json, as the real pack)")
check("Medium's map reads as CA", MapInstall.mapName(medium) == "CA", "mapName = \(MapInstall.mapName(medium))")
do {
    let p = InstallPlan.make(state: "CA", wantAI: false, env: env(medium))
    check("library item: Medium kept (installed)", item(p, .pack)?.status == .installed, "\(String(describing: item(p, .pack)?.status))")
    check("state CA on Medium: no map download (desktop answers 'nothing')", item(p, .map)?.status == .installed,
          "map item is \(String(describing: item(p, .map)?.status)) for \(gb(item(p, .map)?.downloadBytes ?? 0)): InstallPlan needs checkMap (map-set.json), which a pack's own map has not")
    check("state CA on Medium: CA addresses to download", item(p, .addresses)?.status == .toDownload, "\(String(describing: item(p, .addresses)?.status))")
}
do {
    let p = InstallPlan.make(state: "TX", wantAI: false, env: env(medium))
    check("state TX on Medium: TX map to download, required (replaces CA)", item(p, .map)?.status == .toDownload && item(p, .map)?.required == true,
          "\(String(describing: item(p, .map)))")
    check("state TX on Medium: plan says the CA map goes", item(p, .map)?.note?.contains("California") == true,
          "no note; desktop shows the pack's own map and that choosing a state replaces it")
}
do {
    try addAddresses(medium, "CA")
    let p = InstallPlan.make(state: "CA", wantAI: false, env: env(medium))
    check("Medium + CA addresses installed: complete", p.complete,
          "complete = \(p.complete): the CA map item is never 'installed' (see above), so Medium can't finish without re-downloading CA")
}

print("== All installed (whole-US map)")
check("All's map reads as us", MapInstall.mapName(allLib) == "us")
do {
    let p = InstallPlan.make(state: "TX", wantAI: false, env: env(allLib))
    let m = item(p, .map)
    check("state TX on All: no state map needed (desktop: All needs no state map)", m == nil || m?.status == .installed || m?.required == false,
          "map item \(String(describing: m?.status)), required \(String(describing: m?.required)): installing it would REPLACE All's whole-US map with Texas only")
    check("state TX on All: TX addresses to download", item(p, .addresses)?.status == .toDownload, "\(String(describing: item(p, .addresses)?.status))")
    try addAddresses(allLib, "TX")
    let q = InstallPlan.make(state: "TX", wantAI: false, env: env(allLib))
    check("All + TX addresses installed: complete", q.complete, "complete = \(q.complete) (blocked by the TX map item)")
}

print("== A state map zip chosen in Files for All")
do {
    let src = here.appendingPathComponent("mapzip-src")
    try write(src.appendingPathComponent("map-set.json"), "{\"name\": \"TX\", \"files\": {\"derived/geo/socal-cells.json\": 2}}")
    try write(src.appendingPathComponent("derived/geo/socal-cells.json"), "[]")
    let zip = here.appendingPathComponent("Lastbook-Map-TX-tiny.zip")
    let pr = Process(); pr.executableURL = URL(fileURLWithPath: "/usr/bin/zip"); pr.currentDirectoryURL = src
    pr.arguments = ["-qr", zip.path, "map-set.json", "derived"]; try pr.run(); pr.waitUntilExit()
    Library.shared.useForTesting(allLib)
    let settings = here.appendingPathComponent("settings-all")
    var asked = false
    do { _ = try Installer.install(file: zip, state: "TX", allowUnlisted: true, settings: settings) }
    catch InstallError.needsConfirmation { asked = true } catch { print("      \(error)") }
    check("map zip onto All: asks before replacing the whole-US map (nothing changed)", asked && MapInstall.mapName(allLib) == "us",
          "asked \(asked), map \(MapInstall.mapName(allLib))")
}

print("== H.264 copies on Medium / All (iPad without AV1)")
do {
    let p = InstallPlan.make(state: "TX", wantAI: false, env: env(medium, needsH264: true, av1Missing: 279))
    let v = item(p, .videoCopies)
    var why = ""
    if case .unavailable(let w)? = v?.status { why = w }
    check("Medium copies: honest 'not available' naming the 279 videos, not required", why.contains("279") && v?.required == false,
          "\(String(describing: v))")
    check("Medium copies item is per pack (videoCopies:medium)", v?.id == "videoCopies:medium", "id is \(v?.id ?? "-"): with no catalog entry the id falls back to InstallPlan.packID")
}

print("== Choosing Medium or All for a new install")
do {
    let d = InstallPlan.make(state: "TX", wantAI: false, env: env(nil))
    check("a new install defaults to Small", item(d, .pack)?.id == "pack:small", "\(String(describing: item(d, .pack)?.id))")
    let p = InstallPlan.make(pack: "medium", state: "TX", wantAI: false, env: env(nil))
    check("a new install can choose Medium or All", item(p, .pack)?.id == "pack:medium" && item(p, .pack)?.status == .toDownload,
          "\(String(describing: item(p, .pack)))")
    let c = InstallPlan.make(pack: "medium", state: "CA", wantAI: false, env: env(nil))
    check("new Medium + CA: the CA map comes with Medium (nothing to fetch for it)", { if case .included? = item(c, .map)?.status { return true }; return false }(),
          "\(String(describing: item(c, .map)?.status))")
    let u = InstallPlan.make(pack: "all", state: "TX", wantAI: false, env: env(nil))
    check("new All + TX: whole-US map comes with All, TX addresses planned, no state map download",
          item(u, .map)?.id == "map:us" && item(u, .addresses)?.status == .toDownload && !u.toDo.contains { $0.kind == .map },
          "\(u.items.map { "\($0.id) \($0.status)" })")
    var tooBig = u; tooBig.capacity = 256_000_000_000
    check("All on a 256 GB iPad: says it can't fit even when empty", tooBig.tooBigForDevice && tooBig.blockers.contains { $0.contains("can’t fit on this iPad even if it were empty") },
          "\(tooBig.blockers)")
    var fine = u; fine.capacity = 2_000_000_000_000
    check("All on a 2 TB iPad: no capacity blocker", !fine.tooBigForDevice)
}

print("== Space for a Medium / All download (Plan.spaceNeeded arithmetic, real catalog sizes)")
for e in [med, all].compactMap({ $0 }) {
    let it = PlanItem(id: "pack:\(e.id)", kind: .pack, title: e.title, downloadBytes: e.downloadBytes, installedBytes: e.installedBytes ?? 0,
                      partialBytes: 0, status: .toDownload, required: true, note: nil, entry: e)
    let p = Plan(state: "TX", items: [it], free: nil, margin: 512 << 20)
    let want = e.downloadBytes + (e.installedBytes ?? 0) + (512 << 20)
    check("\(e.title): space needed = zip + unpacked + margin (\(gb(p.spaceNeeded)))", p.spaceNeeded == want, "\(p.spaceNeeded) vs \(want)")
    // Usable space after iPadOS (about 12 GB) and nothing else on the iPad.
    let fits = [256, 512, 1024, 2048].filter { Int64($0) * 1_000_000_000 - 12_000_000_000 >= p.spaceNeeded }
    print("      \(e.title) fits on an otherwise empty iPad of: \(fits.isEmpty ? "none" : fits.map { "\($0) GB" }.joined(separator: ", "))")
}

print("== Upgrading Small (with a TX state map, addresses, H.264 copies) to a tiny fake Medium zip")
do {
    let small = try library("upgrade", pack: "small", map: "base", stateMap: "TX", revision: "2026-11-13-small-v2")
    try addAddresses(small, "TX")
    try write(small.appendingPathComponent("derived/video-compat/h264-v1/manifest.json"), "{\"version\": \"h264-v1\", \"items\": {}}")
    let src = here.appendingPathComponent("zip-src")
    let fake = try library("zip-src-tmp", pack: "medium", map: "CA")
    try fm.createDirectory(at: src, withIntermediateDirectories: true)
    try fm.moveItem(at: fake, to: src.appendingPathComponent("LastbookData"))
    let zip = here.appendingPathComponent("Lastbook-Medium-fake.zip")
    let pr = Process(); pr.executableURL = URL(fileURLWithPath: "/usr/bin/zip"); pr.currentDirectoryURL = src
    pr.arguments = ["-qr", zip.path, "LastbookData"]; try pr.run(); pr.waitUntilExit()
    let settings = here.appendingPathComponent("settings"); try fm.createDirectory(at: settings, withIntermediateDirectories: true)
    let s = try PackInstall.stage(zip: zip, target: small, entry: med, includeVideoCopies: true)
    check("fake Medium zip stages (pack.json shape, catalog entry with no revision)", s.pack == "medium", "\(s.pack)")
    let out = try PackInstall.activate(s, settings: settings)
    if case .switched = out { check("switched to Medium", true) } else { check("switched to Medium", false, "\(out)") }
    check("after upgrade: map is Medium's CA (desktop also copies a state map only on a same-pack refresh)", MapInstall.mapName(small) == "CA",
          MapInstall.mapName(small))
    check("after upgrade: TX addresses carried over", AddressInstall.installed(root: small).contains("TX"), "\(AddressInstall.installed(root: small))")
    check("after upgrade: H.264 copies folder carried over (Small's 21 copies match Medium's paths)",
          fm.fileExists(atPath: small.appendingPathComponent("derived/video-compat/h264-v1/manifest.json").path))
    let p = InstallPlan.make(state: "TX", wantAI: false, env: env(small))
    check("after upgrade with state TX: the plan fetches the TX map again", item(p, .map)?.status == .toDownload, "\(String(describing: item(p, .map)?.status))")
    PackInstall.cleanupAfterOpen(target: small, settings: settings)
}

print("")
print("passed \(passed)  known gaps \(gaps.count)  unexpected \(unexpected.count)")
for u in unexpected { print("  unexpected: \(u)") }
exit(unexpected.isEmpty ? 0 : 1)
