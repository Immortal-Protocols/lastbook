import Foundation

/// A state's street-address index (desktop api.py _do_addresses and address_indexes): a zip holding only
/// derived/geo/addresses/<ST>.sqlite. It goes straight into the library (one rename) with a receipt <ST>.json naming the
/// zip and its SHA-256; the index counts as installed only when its size and receipt match the download list.
enum AddressInstall {
    static let dirs: Set<String> = ["", "derived", "derived/geo", "derived/geo/addresses"]

    static func rel(_ id: String) -> String { "derived/geo/addresses/\(id).sqlite" }

    /// Installs the index for state `id` from `zip`. `receipt` is {zip name: sha256} (from the download list); without one
    /// (an unlisted test file) no receipt is written. Returns the installed file.
    @discardableResult
    static func install(zip: URL, root: URL, id: String, installedBytes: Int64?, receipt: [String: String]?,
                        progress: (Int64, Int64) -> Void = { _, _ in }, isCancelled: () -> Bool = { false }) throws -> URL {
        guard id.count == 2, id == id.uppercased(), id.unicodeScalars.allSatisfy({ CharacterSet.uppercaseLetters.contains($0) }) else {
            throw InstallError.refused("That is not a state code (\(id)).")
        }
        let relative = rel(id)
        let z = try ZipInstall.open(zip, what: "address index")
        let (members, total) = try ZipInstall.checkZip(z, installedBytes: installedBytes, allowed: { $1 ? dirs.contains($0) : $0 == relative },
                                                       notAllowed: { InstallError.notAMap("The address download holds a file that is not \(id)’s address index (\($0)).") })
        guard members.contains(where: { $0.parts.dropFirst().joined(separator: "/") == relative }) else {
            throw InstallError.notAMap("The download has no address index for \(id) in it.")
        }
        let work = try ZipInstall.ensureWorkFolder(root)
        let lib = try ZipInstall.unpack(z, members, total: total, into: work.appendingPathComponent("unpack-addresses"), margin: 512 << 20,
                                        what: "address index", progress: progress, isCancelled: isCancelled)
        let staged = lib.appendingPathComponent(relative)
        guard let size = ZipInstall.size(staged), installedBytes == nil || size == installedBytes else {
            throw InstallError.damaged("The address index is missing or the wrong size.")
        }
        let dest = root.appendingPathComponent(relative)
        DBCache.shared.reset()
        for side in ["-wal", "-shm", "-journal"] { try? FileManager.default.removeItem(at: root.appendingPathComponent(relative + side)) }
        do { try ZipInstall.move(staged, dest) } catch { throw InstallError.folder("Lastbook could not put the address index in place.") }
        let rc = root.appendingPathComponent("derived/geo/addresses/\(id).json")
        if let receipt { try? ZipInstall.writeJSON(rc, ["files": receipt]) } else { try? FileManager.default.removeItem(at: rc) }
        try? FileManager.default.removeItem(at: work.appendingPathComponent("unpack-addresses"))
        DBCache.shared.reset()
        return dest
    }

    /// The states whose index is installed and checks out against the download list (desktop api.address_indexes).
    static func installed(root: URL) -> [String] {
        InstallCatalog.entries.filter { $0.kind == .addresses }.compactMap { e in
            let p = root.appendingPathComponent(rel(e.id))
            guard let size = ZipInstall.size(p), size == e.installedBytes,
                  let r = ZipInstall.readJSON(p.deletingPathExtension().appendingPathExtension("json"))?["files"] as? [String: String],
                  r == Dictionary(uniqueKeysWithValues: e.files.map { ($0.name, $0.sha256) }) else { return nil }
            return e.id
        }
    }

    /// Installed through the download list, or copied in by hand at exactly the published installed size (a library copied
    /// from a computer has no receipt; re-downloading an identical-size index would only waste the person's data).
    static func usable(root: URL, _ id: String) -> Bool {
        if installed(root: root).contains(id) { return true }
        guard let e = InstallCatalog.entry(.addresses, id), let size = ZipInstall.size(root.appendingPathComponent(rel(id))) else { return false }
        return size == e.installedBytes
    }

    /// Every index file present, checked or not (a library copied in from a computer may hold indexes without receipts).
    static func present(root: URL) -> [String] {
        ((try? FileManager.default.contentsOfDirectory(atPath: root.appendingPathComponent("derived/geo/addresses").path)) ?? [])
            .filter { $0.hasSuffix(".sqlite") }.map { String($0.dropLast(7)) }.sorted()
    }
}
