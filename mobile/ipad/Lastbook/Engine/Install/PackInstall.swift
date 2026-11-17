import Foundation

/// Installing a library pack from its zip (desktop engine/setup/install.py unpack/switch/apply_pending, api.py _do_pack):
///
///   <parent>/LastbookData.setup/unpack/LastbookData    the new library, built here from the zip (stage)
///   <parent>/LastbookData                              the library (on iPad: Documents/LastbookData)
///   <parent>/LastbookData.old-<date>                   the library it replaced, kept until the person deletes it
///
/// The zip must hold everything under a LastbookData/ top folder. Switching is two renames on one disk; if the new
/// library does not open (no catalog) the old one is put back. What belongs to the person, not the pack, moves to the
/// new library: models, address indexes, the AI's on/off state.
enum PackInstall {
    struct Staged {
        let target: URL         // the library's place (Documents/LastbookData)
        let work: URL
        let newLib: URL         // LastbookData.setup/unpack/LastbookData
        let pack: String        // pack.json name
        let bytes: Int64
        let skippedVideoCopies: Bool
    }

    static let videoCopiesPrefix = "derived/video-compat/"
    static func pendingFile(_ settings: URL) -> URL { settings.appendingPathComponent("pack-pending.json") }

    nonisolated(unsafe) static var testFailAfterMoveAside = false   // Mac test tool only: fail between the two renames

    // ------------------------------------------------------------------ stage ----
    /// Checks every member, then unpacks. `includeVideoCopies`: the H.264 copies under derived/video-compat/ are written only
    /// when this iPad needs them (VideoCompat.needsH264). `entry` (from the download list) gives the size limit and revision.
    static func stage(zip: URL, target: URL, entry: CatalogEntry?, includeVideoCopies: Bool,
                      progress: (Int64, Int64) -> Void = { _, _ in }, isCancelled: () -> Bool = { false }) throws -> Staged {
        let z = try ZipInstall.open(zip, what: "pack")
        let (members, total) = try ZipInstall.checkZip(z, installedBytes: entry?.installedBytes)
        guard let pj = members.first(where: { $0.parts == [ZipInstall.dataName, "pack.json"] })?.entry,
              let pack = try? JSONSerialization.jsonObject(with: ZipInstall.readSmall(z, pj)) as? [String: Any] else {
            throw InstallError.refused("This zip is not a Lastbook pack (it has no LastbookData/pack.json).")
        }
        if let rev = entry?.revision, (pack["content_revision"] as? String) != rev {
            throw InstallError.refused("The library content version does not match this download.")
        }
        guard members.contains(where: { $0.parts == [ZipInstall.dataName, "library-data", "catalog.json"] }) else {
            throw InstallError.refused("The unpacked pack has no library catalog in it.")
        }
        try FileManager.default.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
        let work = try ZipInstall.ensureWorkFolder(target)
        let skip: (String) -> Bool = { !includeVideoCopies && ($0 + "/").hasPrefix(videoCopiesPrefix) }
        let lib = try ZipInstall.unpack(z, members, total: total, into: work.appendingPathComponent("unpack"), margin: 512 << 20, what: "pack",
                                        skip: skip, progress: progress, isCancelled: isCancelled)
        guard MapInstall.isLibrary(lib) else { throw InstallError.refused("The unpacked pack has no library catalog in it.") }
        let name = (pack["name"] as? String) ?? entry?.id ?? "custom"
        // Refreshing the same pack keeps an installed state map (install.copy_map; clones on APFS, so no extra room).
        if let cur = ZipInstall.readJSON(target.appendingPathComponent("pack.json")), cur["name"] as? String == name,
           MapInstall.mapName(target) != "base" {
            try copyMap(from: target, to: lib)
        }
        try? ZipInstall.writeJSON(lib.appendingPathComponent("setup-pack.json"),
                                  ["pack": name, "installed": ISO8601DateFormatter().string(from: Date()), "files": [zip.lastPathComponent]])
        return Staged(target: target, work: work, newLib: lib, pack: name, bytes: total, skippedVideoCopies: !includeVideoCopies)
    }

    static func copyMap(from old: URL, to new: URL) throws {
        let fm = FileManager.default
        for rel in MapInstall.mapFiles(new) { try? fm.removeItem(at: new.appendingPathComponent(rel)) }
        for rel in MapInstall.mapFiles(old) {
            let d = new.appendingPathComponent(rel)
            try fm.createDirectory(at: d.deletingLastPathComponent(), withIntermediateDirectories: true)
            try fm.copyItem(at: old.appendingPathComponent(rel), to: d)
        }
    }

    /// A pack installed together with a state map: the map's files replace the pack's own map set inside the staged library.
    static func replaceMap(in s: Staged, with map: MapInstall.Staged) throws {
        try MapInstall.checkMap(map.newLib)
        for rel in MapInstall.mapFiles(s.newLib) { try? FileManager.default.removeItem(at: s.newLib.appendingPathComponent(rel)) }
        for rel in MapInstall.mapFiles(map.newLib) { try ZipInstall.move(map.newLib.appendingPathComponent(rel), s.newLib.appendingPathComponent(rel)) }
    }

    // ------------------------------------------------------------------ switching ----
    static func oldName(_ target: URL) -> URL {
        let f = DateFormatter(); f.dateFormat = "yyyyMMdd"; f.locale = Locale(identifier: "en_US_POSIX")
        let base = target.deletingLastPathComponent().appendingPathComponent("\(target.lastPathComponent).old-\(f.string(from: Date()))")
        var p = base, i = 2
        while FileManager.default.fileExists(atPath: p.path) { p = base.deletingLastPathComponent().appendingPathComponent("\(base.lastPathComponent)-\(i)"); i += 1 }
        return p
    }

    /// install.carry_over: the model files, address indexes, the AI's setting and (iPad) the H.264 video copies go with the person.
    static func carryOver(_ old: URL, _ new: URL) {
        let fm = FileManager.default
        let models = old.appendingPathComponent("models")
        for n in (try? fm.contentsOfDirectory(atPath: models.path)) ?? [] {
            let s = models.appendingPathComponent(n), d = new.appendingPathComponent("models/\(n)")
            if ZipInstall.isFile(s) && !fm.fileExists(atPath: d.path) { try? ZipInstall.move(s, d) }
        }
        let addr = old.appendingPathComponent("derived/geo/addresses")
        for n in (try? fm.contentsOfDirectory(atPath: addr.path)) ?? [] {
            let ok = n.count == 9 || n.count == 7   // XX.sqlite / XX.json
            let st = n.prefix(2)
            guard ok, st.unicodeScalars.allSatisfy({ CharacterSet.uppercaseLetters.contains($0) && $0.isASCII }),
                  [".sqlite", ".json"].contains(String(n.dropFirst(2))) else { continue }
            let s = addr.appendingPathComponent(n), d = new.appendingPathComponent("derived/geo/addresses/\(n)")
            if ZipInstall.isFile(s) && !fm.fileExists(atPath: d.path) { try? ZipInstall.move(s, d) }
        }
        // The H.264 video copies (iPad only): kept when the new library brings none of its own. Copies whose original is
        // not in the new library are never served (VideoCompat matches each copy to its original's path).
        let vc = old.appendingPathComponent(VideoCopiesInstall.folder), nvc = new.appendingPathComponent(VideoCopiesInstall.folder)
        if fm.fileExists(atPath: vc.appendingPathComponent("manifest.json").path) && !fm.fileExists(atPath: nvc.path) { try? ZipInstall.move(vc, nvc) }
        let st = old.appendingPathComponent("derived/llm/state.json"), nd = new.appendingPathComponent("derived/llm/state.json")
        if ZipInstall.isFile(st) && !fm.fileExists(atPath: nd.path) {
            try? fm.createDirectory(at: nd.deletingLastPathComponent(), withIntermediateDirectories: true)
            try? fm.copyItem(at: st, to: nd)
        }
    }

    enum Outcome: Equatable { case switched(old: URL?), restored(String) }

    private static func changed() {
        DBCache.shared.reset()
        Catalog.shared.reset()
        VideoCompat.shared.reset()
        NotificationCenter.default.post(name: MapInstall.didChange, object: nil)
    }

    /// Puts the staged library in place now (the iPad closes its databases instead of restarting). install.switch +
    /// apply_pending: if the new library then does not open, the old one is put back. Throws InstallError.activate when a
    /// rename fails (what was there is back).
    @discardableResult
    static func activate(_ s: Staged, settings: URL = MapInstall.defaultSettings) throws -> Outcome {
        let fm = FileManager.default
        guard MapInstall.isLibrary(s.newLib) else { throw InstallError.activate("The new library is not complete.") }
        let pending = pendingFile(settings)
        var rec: [String: Any] = ["kind": "pack", "new": s.newLib.path, "target": s.target.path, "switched": false, "written": Date().timeIntervalSince1970]
        DBCache.shared.reset()
        var old: URL? = nil
        if fm.fileExists(atPath: s.target.path) {
            let o = oldName(s.target)
            old = o
            rec["old"] = o.path
            try? ZipInstall.writeJSON(pending, rec)
            if MapInstall.isLibrary(s.target) { carryOver(s.target, s.newLib) }
            do { try ZipInstall.move(s.target, o) } catch {
                try? fm.removeItem(at: pending)
                throw InstallError.activate("Lastbook could not move the old library aside. Close anything using it, then try again.")
            }
        } else {
            try? ZipInstall.writeJSON(pending, rec)
        }
        do {
            if testFailAfterMoveAside { throw CocoaError(.fileWriteUnknown) }
            try ZipInstall.move(s.newLib, s.target)
        } catch {
            if let old { try? ZipInstall.move(old, s.target); carryOver(s.newLib, s.target) }
            try? fm.removeItem(at: pending)
            changed()
            throw InstallError.activate("Lastbook could not put the new library in place.")
        }
        rec["switched"] = true
        try? ZipInstall.writeJSON(pending, rec)
        let outcome = verifyOrRestore(target: s.target, old: old)
        changed()
        return outcome
    }

    private static func verifyOrRestore(target: URL, old: URL?) -> Outcome {
        if MapInstall.isLibrary(target) { return .switched(old: old) }
        guard let old, FileManager.default.fileExists(atPath: old.path) else { return .restored("The new library did not open.") }
        let broken = target.deletingLastPathComponent().appendingPathComponent(target.lastPathComponent + ".failed")
        try? FileManager.default.removeItem(at: broken)
        try? ZipInstall.move(target, broken)
        try? ZipInstall.move(old, target)
        carryOver(broken, target)
        return .restored("The new library did not open, so Lastbook put the old one back.")
    }

    /// At launch, before the library opens: an interrupted switch is put right. A pending file that does not match what
    /// activate writes for this library is removed, not obeyed (install._pending_ok).
    @discardableResult
    static func recoverIfNeeded(target: URL, settings: URL = MapInstall.defaultSettings) -> Outcome? {
        let pending = pendingFile(settings)
        guard let d = ZipInstall.readJSON(pending) else { return nil }
        let work = ZipInstall.workFolder(target)
        let old = (d["old"] as? String).map { URL(fileURLWithPath: $0) }
        guard d["kind"] as? String == "pack", let t = d["target"] as? String, let n = d["new"] as? String,
              ZipInstall.realPath(t) == ZipInstall.realPath(target.path),
              ZipInstall.realPath(n) == ZipInstall.realPath(work.appendingPathComponent("unpack/\(ZipInstall.dataName)").path),
              old == nil || (ZipInstall.realPath(old!.deletingLastPathComponent().path) == ZipInstall.realPath(target.deletingLastPathComponent().path)
                             && old!.lastPathComponent.hasPrefix(target.lastPathComponent + ".old-")) else {
            try? FileManager.default.removeItem(at: pending)
            return nil
        }
        let outcome: Outcome
        if d["switched"] as? Bool == true {
            outcome = verifyOrRestore(target: target, old: old)
        } else {
            // stopped between the renames: the old library is aside and the new one never arrived
            if !FileManager.default.fileExists(atPath: target.path), let old, FileManager.default.fileExists(atPath: old.path) {
                try? ZipInstall.move(old, target)
                carryOver(URL(fileURLWithPath: n), target)
            }
            try? FileManager.default.removeItem(at: pending)
            outcome = .restored("The library switch was interrupted, so Lastbook kept the library you had.")
        }
        changed()
        return outcome
    }

    /// The library opened: the pending file and the work folder go. The old library stays until the person deletes it.
    static func cleanupAfterOpen(target: URL, settings: URL = MapInstall.defaultSettings) {
        let pending = pendingFile(settings)
        guard FileManager.default.fileExists(atPath: pending.path) else { return }
        try? FileManager.default.removeItem(at: pending)
        let work = ZipInstall.workFolder(target)
        for sub in ["downloads", "unpack"] { try? FileManager.default.removeItem(at: work.appendingPathComponent(sub)) }
        if let rest = try? FileManager.default.contentsOfDirectory(atPath: work.path), rest.isEmpty { try? FileManager.default.removeItem(at: work) }
    }

    /// Earlier libraries kept beside this one (LastbookData.old-<date>), with their size.
    static func oldLibraries(_ target: URL) -> [(url: URL, bytes: Int64)] {
        let parent = target.deletingLastPathComponent()
        return ((try? FileManager.default.contentsOfDirectory(atPath: parent.path)) ?? [])
            .filter { $0.hasPrefix(target.lastPathComponent + ".old-") || $0 == target.lastPathComponent + ".failed" }.sorted()
            .map { (parent.appendingPathComponent($0), ZipInstall.treeSize(parent.appendingPathComponent($0))) }
    }

    static func deleteOld(_ u: URL, target: URL) throws {
        guard oldLibraries(target).contains(where: { $0.url.standardizedFileURL == u.standardizedFileURL }) else {
            throw InstallError.refused("That is not an old library Lastbook kept.")
        }
        try FileManager.default.removeItem(at: u)
    }
}
