import Foundation
import CryptoKit

// Mac parity tool: runs the iPad engine's routes (the same Swift files as the app) against a LastbookData folder and prints
// each answer, so it can be compared with the desktop server.py. Never part of the app.
//
//   apidump LASTBOOK_DATA DESKTOP_SOURCE 'GET /api/videos' ['GET /api/map/tile/12/702/1635?v=1' ...]
// Prints one line per request: the status, then the body (JSON as is; other bodies as "<mime> <bytes> bytes sha256=...").

let args = CommandLine.arguments
guard args.count >= 4 else {
    FileHandle.standardError.write(Data("usage: apidump LASTBOOK_DATA DESKTOP_SOURCE 'GET /path?query' ...\n".utf8))
    exit(2)
}
Resources.override = URL(fileURLWithPath: args[2])
Library.shared.useForTesting(URL(fileURLWithPath: args[1]))
Router.shared.install(Routes.all)

for spec in args[3...] {
    let parts = spec.split(separator: " ", maxSplits: 1).map(String.init)
    let method = parts.count == 2 ? parts[0] : "GET"
    let target = parts.last!
    let comps = URLComponents(string: "lastbook://app" + target)!
    let q = APIRequest.parseQuery(comps.percentEncodedQuery)
    let req = APIRequest(method: method, path: comps.percentEncodedPath.removingPercentEncoding ?? comps.path, query: q, headers: [:], body: nil)
    let t0 = Date()
    let r = Router.shared.route(req)
    let ms = Int(Date().timeIntervalSince(t0) * 1000)
    var body = Data()
    switch r.body {
    case .data(let d): body = d
    case .file(let u): body = (try? Data(contentsOf: u)) ?? Data()
    case .stream(let produce):
        let sem = DispatchSemaphore(value: 0)
        produce { chunk in if let chunk { body.append(chunk) } else { sem.signal() } }
        sem.wait()
    }
    if r.mime.hasPrefix("application/json") {   // one line; everything else (html and text included) as its sha256
        print("\(r.status) \(ms)ms \(target)\n" + (String(data: body, encoding: .utf8) ?? ""))
    } else {
        let h = SHA256.hash(data: body).map { String(format: "%02x", $0) }.joined()
        print("\(r.status) \(ms)ms \(target)\n\(r.mime) \(body.count) bytes sha256=\(h)")
    }
}
