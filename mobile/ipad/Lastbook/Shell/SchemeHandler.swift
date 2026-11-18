import Foundation
import WebKit

/// Answers every lastbook://app request in-process: no socket, no port (desktop: app/bridge.py, ORIGIN_MAC).
/// POSTs need the launch key, which only the app's top frame gets (TopScript below, as bridge.py TOP_SCRIPT).
final class SchemeHandler: NSObject, WKURLSchemeHandler {
    static let origin = "lastbook://app"
    let key = UUID().uuidString + UUID().uuidString
    private var live = Set<ObjectIdentifier>()
    private let liveLock = NSLock()
    private let queue = DispatchQueue(label: "lastbook.api", qos: .userInitiated, attributes: .concurrent)

    static let maxPiece: Int64 = 8 << 20   // most bytes one video Range answer holds; the player asks for the rest (bridge.py VIDEO_PIECE)

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        let id = ObjectIdentifier(task)
        liveLock.lock(); live.insert(id); liveLock.unlock()
        let req = task.request
        queue.async { [weak self] in
            guard let self else { return }
            let resp = self.answer(req)
            self.send(resp, req, task, id)
        }
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {
        liveLock.lock(); live.remove(ObjectIdentifier(task)); liveLock.unlock()
    }

    private func alive(_ id: ObjectIdentifier) -> Bool { liveLock.lock(); defer { liveLock.unlock() }; return live.contains(id) }
    private func done(_ id: ObjectIdentifier) { liveLock.lock(); live.remove(id); liveLock.unlock() }

    private func answer(_ req: URLRequest) -> APIResponse {
        guard let url = req.url, url.scheme == "lastbook", url.host == "app",
              let comps = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return .notFound() }
        let q = APIRequest.parseQuery(comps.percentEncodedQuery)
        var h: [String: String] = [:]
        for (k, v) in req.allHTTPHeaderFields ?? [:] { h[k.lowercased()] = v }
        let method = req.httpMethod ?? "GET"
        if method == "POST" {
            guard h["x-lastbook-key"] == key else { return .error("Forbidden.", status: 403) }
        }
        let path = comps.percentEncodedPath.removingPercentEncoding ?? comps.path
        let r = APIRequest(method: method, path: path.isEmpty ? "/" : path, query: q, headers: h, body: req.httpBody ?? req.httpBodyStream.map(Self.drain))
        return Router.shared.route(r)
    }

    private static func drain(_ s: InputStream) -> Data {
        s.open(); defer { s.close() }
        var d = Data(), buf = [UInt8](repeating: 0, count: 65536)
        while s.hasBytesAvailable { let n = s.read(&buf, maxLength: buf.count); if n <= 0 { break }; d.append(buf, count: n); if d.count > 256 * 1024 { break } }
        return d
    }

    private func headers(_ r: APIResponse, length: Int64?) -> [String: String] {
        var h = r.headers
        h["Content-Type"] = r.mime
        h["X-Content-Type-Options"] = "nosniff"
        if let length { h["Content-Length"] = String(length) }
        if h["Cache-Control"] == nil { h["Cache-Control"] = "no-store" }
        return h
    }

    private func send(_ r: APIResponse, _ req: URLRequest, _ task: WKURLSchemeTask, _ id: ObjectIdentifier) {
        let url = req.url!
        switch r.body {
        case .data(let d):
            let resp = HTTPURLResponse(url: url, statusCode: r.status, httpVersion: "HTTP/1.1", headerFields: headers(r, length: Int64(d.count)))!
            onMain(id) { task.didReceive(resp); task.didReceive(d); task.didFinish() }
        case .file(let f):
            sendFile(f, r, req, task, id)
        case .stream(let produce):
            let resp = HTTPURLResponse(url: url, statusCode: r.status, httpVersion: "HTTP/1.1", headerFields: headers(r, length: nil))!
            onMain(id, finish: false) { task.didReceive(resp) }
            // The producer (chat) learns here whether the web view still wants the stream: Stop or leaving ends it.
            Thread.current.threadDictionary[ChatAPI.aliveKey] = { [weak self] () -> Bool in self?.alive(id) ?? false }
            defer { Thread.current.threadDictionary.removeObject(forKey: ChatAPI.aliveKey) }
            produce { [weak self] chunk in
                guard let self else { return }
                if let chunk { self.onMain(id, finish: false) { task.didReceive(chunk) } }
                else { self.onMain(id) { task.didFinish() } }
            }
        }
    }

    private func sendFile(_ f: URL, _ r: APIResponse, _ req: URLRequest, _ task: WKURLSchemeTask, _ id: ObjectIdentifier) {
        let url = req.url!
        guard let fh = try? FileHandle(forReadingFrom: f),
              let size = (try? FileManager.default.attributesOfItem(atPath: f.path)[.size] as? NSNumber)?.int64Value else {
            let resp = HTTPURLResponse(url: url, statusCode: 404, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "text/plain"])!
            onMain(id) { task.didReceive(resp); task.didFinish() }
            return
        }
        defer { try? fh.close() }
        var h = headers(r, length: nil)
        h["Accept-Ranges"] = "bytes"
        if h["Cache-Control"] == "no-store" { h["Cache-Control"] = "max-age=3600" }
        var status = 200
        var start: Int64 = 0, end: Int64 = size - 1
        if let range = req.value(forHTTPHeaderField: "Range"), let m = Self.parseRange(range, size: size) {
            (start, end) = m
            if end - start + 1 > Self.maxPiece { end = start + Self.maxPiece - 1 }
            status = 206
            h["Content-Range"] = "bytes \(start)-\(end)/\(size)"
        } else if req.value(forHTTPHeaderField: "Range") != nil {
            h["Content-Range"] = "bytes */\(size)"
            let resp = HTTPURLResponse(url: url, statusCode: 416, httpVersion: "HTTP/1.1", headerFields: h)!
            onMain(id) { task.didReceive(resp); task.didFinish() }
            return
        }
        let length = max(0, end - start + 1)
        h["Content-Length"] = String(length)
        let resp = HTTPURLResponse(url: url, statusCode: status, httpVersion: "HTTP/1.1", headerFields: h)!
        onMain(id, finish: false) { task.didReceive(resp) }
        try? fh.seek(toOffset: UInt64(start))
        var left = length
        while left > 0, alive(id) {
            let n = Int(min(left, 1 << 20))
            guard let d = try? fh.read(upToCount: n), !d.isEmpty else { break }
            left -= Int64(d.count)
            onMain(id, finish: false) { task.didReceive(d) }
        }
        onMain(id) { task.didFinish() }
    }

    static func parseRange(_ h: String, size: Int64) -> (Int64, Int64)? {
        guard h.hasPrefix("bytes="), !h.contains(","), size > 0 else { return nil }
        let spec = h.dropFirst(6).split(separator: "-", omittingEmptySubsequences: false)
        guard spec.count == 2 else { return nil }
        if spec[0].isEmpty {   // suffix: the last N bytes
            guard let n = Int64(spec[1]), n > 0 else { return nil }
            return (max(0, size - n), size - 1)
        }
        guard let s = Int64(spec[0]), s < size else { return nil }
        let e = spec[1].isEmpty ? size - 1 : min(Int64(spec[1]) ?? size - 1, size - 1)
        return e >= s ? (s, e) : nil
    }

    /// WebKit wants task calls on the main thread, and none after stop.
    private func onMain(_ id: ObjectIdentifier, finish: Bool = true, _ body: @escaping () -> Void) {
        DispatchQueue.main.async { [weak self] in
            guard let self, self.alive(id) else { return }
            body()
            if finish { self.done(id) }
        }
    }

    /// Same as desktop TOP_SCRIPT (app/bridge.py), stream mode: the key on the top frame's own /api/ reads and POSTs,
    /// and no location service (it can ask the network).
    func topScript() -> String {
        #"""
        (() => {
          if (window.top !== window || window.origin === 'null') return;
          const none = { getCurrentPosition(ok, no) { if (no) setTimeout(no, 0, { code: 1, message: 'Lastbook stays offline and does not ask where you are.' }) }, watchPosition() { return 0 }, clearWatch() { } };
          try { Object.defineProperty(Navigator.prototype, 'geolocation', { get() { return none }, configurable: false }) } catch { }
          const KEY = '__KEY__', own = location.protocol + '//' + location.host;
          const real = window.fetch.bind(window);
          const mine = u => u.protocol + '//' + u.host === own;
          const keyed = (req) => { const headers = new Headers(req.headers); headers.set('X-Lastbook-Key', KEY); return real(new Request(req, { headers })) };
          window.fetch = async function (input, init) {
            const req = new Request(input, init);
            const u = new URL(req.url);
            if (!mine(u)) return real(req);
            if (req.method !== 'POST') return u.pathname.startsWith('/api/') ? keyed(req) : real(req);
            return keyed(req);
          };
        })();
        """#.replacingOccurrences(of: "__KEY__", with: key)
    }
}
