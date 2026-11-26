import Foundation
import SQLite3

/// Thin read-only SQLite wrapper. Library databases are never written (as on desktop: engine/paths.py ro_uri).
final class SQLiteDB: @unchecked Sendable {
    private var db: OpaquePointer?
    private let lock = NSLock()
    let path: String

    init?(readOnly url: URL) {
        path = url.path
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        // immutable=1: the file never changes while open, so SQLite takes no locks and writes no -wal/-shm next to it.
        var comps = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        comps.scheme = "file"
        comps.queryItems = [URLQueryItem(name: "mode", value: "ro"), URLQueryItem(name: "immutable", value: "1")]
        let uri = comps.string ?? "file:\(url.path)?mode=ro"
        if sqlite3_open_v2(uri, &db, SQLITE_OPEN_READONLY | SQLITE_OPEN_URI | SQLITE_OPEN_FULLMUTEX, nil) != SQLITE_OK {
            sqlite3_close(db)
            return nil
        }
    }

    deinit { sqlite3_close(db) }

    enum Value { case int(Int64), double(Double), text(String), blob(Data), null
        var int: Int64? { if case .int(let v) = self { return v }; if case .double(let d) = self { return Int64(d) }; return nil }
        var double: Double? { if case .double(let v) = self { return v }; if case .int(let i) = self { return Double(i) }; return nil }
        var text: String? { if case .text(let v) = self { return v }; return nil }
        var blob: Data? { if case .blob(let v) = self { return v }; if case .text(let s) = self { return Data(s.utf8) }; return nil }
        var json: Any { switch self { case .int(let v): return v; case .double(let v): return v; case .text(let v): return v
                        case .blob(let v): return v.base64EncodedString(); case .null: return NSNull() } }
    }

    typealias Row = [String: Value]

    /// Runs a query with bound arguments (Int, Double, String, Data, nil). Returns rows keyed by column name.
    func query(_ sql: String, _ args: [Any?] = []) -> [Row] {
        var out: [Row] = []
        each(sql, args) { out.append($0) }
        return out
    }

    func each(_ sql: String, _ args: [Any?] = [], _ body: (Row) -> Void) {
        lock.lock(); defer { lock.unlock() }
        var st: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &st, nil) == SQLITE_OK else {
            NSLog("Lastbook SQLite prepare failed: %@ — %@", String(cString: sqlite3_errmsg(db)), sql)
            return
        }
        defer { sqlite3_finalize(st) }
        let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
        for (i, a) in args.enumerated() {
            let idx = Int32(i + 1)
            switch a {
            case nil: sqlite3_bind_null(st, idx)
            case let v as Int: sqlite3_bind_int64(st, idx, Int64(v))
            case let v as Int64: sqlite3_bind_int64(st, idx, v)
            case let v as Double: sqlite3_bind_double(st, idx, v)
            case let v as Float: sqlite3_bind_double(st, idx, Double(v))
            case let v as Bool: sqlite3_bind_int64(st, idx, v ? 1 : 0)
            case let v as String: sqlite3_bind_text(st, idx, v, -1, transient)
            case let v as Data: _ = v.withUnsafeBytes { sqlite3_bind_blob(st, idx, $0.baseAddress, Int32(v.count), transient) }
            default: sqlite3_bind_null(st, idx)
            }
        }
        let n = sqlite3_column_count(st)
        let names = (0..<n).map { String(cString: sqlite3_column_name(st, $0)) }
        while sqlite3_step(st) == SQLITE_ROW {
            var row: Row = [:]
            for c in 0..<n {
                switch sqlite3_column_type(st, c) {
                case SQLITE_INTEGER: row[names[Int(c)]] = .int(sqlite3_column_int64(st, c))
                case SQLITE_FLOAT: row[names[Int(c)]] = .double(sqlite3_column_double(st, c))
                case SQLITE_TEXT: row[names[Int(c)]] = .text(String(cString: sqlite3_column_text(st, c)))
                case SQLITE_BLOB:
                    let len = Int(sqlite3_column_bytes(st, c))
                    row[names[Int(c)]] = .blob(len > 0 ? Data(bytes: sqlite3_column_blob(st, c), count: len) : Data())
                default: row[names[Int(c)]] = .null
                }
            }
            body(row)
        }
    }

    func one(_ sql: String, _ args: [Any?] = []) -> Row? { query(sql, args).first }

    func tables() -> Set<String> {
        Set(query("select name from sqlite_master where type in ('table','view')").compactMap { $0["name"]?.text })
    }
}
