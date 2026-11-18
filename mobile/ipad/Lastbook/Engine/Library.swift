import Foundation

/// Where the person's library lives. The iPad sandbox means the app never scans the disk: either the library sits in the
/// app's own Documents folder (imported, or copied in through Files/Finder), or the person picked a LastbookData folder in
/// Files and the app keeps a security-scoped bookmark to it.
///
/// Layout is the desktop's (a LastbookData folder): library-data/ and derived/geo/.
final class Library: @unchecked Sendable {
    static let shared = Library()

    private(set) var root: URL?          // the LastbookData folder
    var lib: URL? { root?.appendingPathComponent("library-data") }
    var geo: URL? { root?.appendingPathComponent("derived/geo") }
    private var scoped: URL?
    private let bookmarkKey = "lastbook.library.bookmark"

    static var documents: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0] }
    /// The library inside the app's own container (Files: On My iPad › Lastbook › LastbookData).
    static var inApp: URL { documents.appendingPathComponent("LastbookData") }

    static func looksLikeLibrary(_ u: URL) -> Bool {
        FileManager.default.fileExists(atPath: u.appendingPathComponent("library-data/catalog.json").path)
    }

    /// Finds the library: the picked folder (bookmark) first, then the one inside the app.
    @discardableResult
    func locate() -> Bool {
        stopAccess()
        if let data = UserDefaults.standard.data(forKey: bookmarkKey) {
            var stale = false
            if let u = try? URL(resolvingBookmarkData: data, options: [], relativeTo: nil, bookmarkDataIsStale: &stale) {
                let ok = u.startAccessingSecurityScopedResource()
                if Self.looksLikeLibrary(u) {
                    if ok { scoped = u }
                    if stale, let fresh = try? u.bookmarkData() { UserDefaults.standard.set(fresh, forKey: bookmarkKey) }
                    return use(u)
                }
                if ok { u.stopAccessingSecurityScopedResource() }
            }
        }
        if Self.looksLikeLibrary(Self.inApp) { return use(Self.inApp) }
        root = nil
        return false
    }

    /// The person picked a folder in Files. Accepts LastbookData itself or a folder holding it.
    func choose(_ picked: URL) -> Bool {
        let ok = picked.startAccessingSecurityScopedResource()
        defer { if ok { picked.stopAccessingSecurityScopedResource() } }
        let cands = [picked, picked.appendingPathComponent("LastbookData")]
        guard let u = cands.first(where: Self.looksLikeLibrary) else { return false }
        guard let data = try? u.bookmarkData() else { return false }
        UserDefaults.standard.set(data, forKey: bookmarkKey)
        return locate()
    }

    func forget() {
        UserDefaults.standard.removeObject(forKey: bookmarkKey)
        locate()
    }

    private func use(_ u: URL) -> Bool {
        root = u
        Catalog.shared.reset()
        VideoCompat.shared.reset()
        return true
    }

    private func stopAccess() {
        scoped?.stopAccessingSecurityScopedResource()
        scoped = nil
    }

    func db(_ rel: String, geo inGeo: Bool = false) -> SQLiteDB? {
        guard let base = inGeo ? geo : lib else { return nil }
        return DBCache.shared.get(base.appendingPathComponent(rel))
    }
}

/// The app's bundled read-only files (web/, content/). The Mac parity tool (tools/apidump) points this at the desktop tree.
enum Resources {
    static var override: URL?
    static func url(_ name: String) -> URL {
        if let o = override { return o.appendingPathComponent(name) }
        return Bundle.main.url(forResource: name, withExtension: nil) ?? Bundle.main.bundleURL.appendingPathComponent(name)
    }
}

extension Library {
    /// For the Mac parity tool only: use this LastbookData folder directly.
    func useForTesting(_ u: URL) { _ = use(u) }
}

/// Open databases are reused; they are read-only and immutable.
final class DBCache: @unchecked Sendable {
    static let shared = DBCache()
    private var dbs: [String: SQLiteDB] = [:]
    private var missing: Set<String> = []
    private let lock = NSLock()
    func get(_ u: URL) -> SQLiteDB? {
        lock.lock(); defer { lock.unlock() }
        if let d = dbs[u.path] { return d }
        if missing.contains(u.path) { return nil }
        guard let d = SQLiteDB(readOnly: u) else { missing.insert(u.path); return nil }
        dbs[u.path] = d
        return d
    }
    func reset() { lock.lock(); dbs = [:]; missing = []; lock.unlock() }
}
