import Foundation

/// Saved web pages as the desktop serves them, byte for byte.
///
/// Desktop (server.py Handler, engine/library.py Handler.do_GET, engine/saved_pages.py):
///  - a library address ending in .html/.htm, not index.html, of at most 8 MB, is read as text (UTF-8, bad bytes replaced,
///    newlines made \n), parsed with BeautifulSoup(html.parser), its links to pages the library holds pointed at the library
///    copy, and written out again (str(soup)); then send_data runs saved_pages.rewrite on it (if at most 16 MB) and, under
///    /documents/lastbook/, own_look;
///  - any other .html/.htm (index.html, a folder's index, a larger page up to 64 MB) goes through saved_pages.rewrite only.
/// Both are ported here: Python's html.parser (3.11.18) and Beautiful Soup 4.15's tree builder and "minimal" output are
/// reproduced as far as these pages use them, so the bytes come out the same.
enum SavedPages {
    static let MAX_PAGE = 16 * 1024 * 1024
    static let MAX_READ = 64 * 1024 * 1024
    static let MAX_TRANSCRIPT = 4 * 1024 * 1024
    static let MAX_PARSED_PAGE = 8 * 1024 * 1024   // engine/library.py MAX_PARSED_PAGE
    static let MAX_TAG = 64 * 1024

    /// The answer for library address `p` (percent-decoded), or nil when it is not a saved page (then it is served as a file).
    static func answer(_ p: String, lib: URL) -> APIResponse? {
        let folder = p.hasSuffix("/")
        let rel = String(p.dropFirst()) + (folder ? "index.html" : "")
        guard case .file(let url) = Router.shared.staticFile(lib, rel).body else { return nil }
        let name = rel.split(separator: "/").last.map(String.init) ?? ""
        let lower = name.lowercased()
        guard lower.hasSuffix(".html") || lower.hasSuffix(".htm") else { return nil }
        let size = ((try? FileManager.default.attributesOfItem(atPath: url.path))?[.size] as? NSNumber)?.intValue ?? Int.max
        let readLocal: ([UInt8]) -> [UInt8]? = { src in part(p, String(decoding: src, as: UTF8.self), lib: lib) }
        if !folder && (p.hasSuffix(".html") || p.hasSuffix(".htm")) && name != "index.html" && size <= MAX_PARSED_PAGE,
           let raw = try? Data(contentsOf: url), let parsed = Soup.reparse(raw, links: links(lib)) {
            var out = [UInt8](parsed)
            if out.count <= MAX_PAGE {
                out = rewrite(out, readLocal)
                if p.contains("/documents/lastbook/") { out = ownLook(out) }
            }
            return APIResponse(status: 200, mime: "text/html; charset=utf-8", headers: [:], body: .data(Data(out)))
        }
        guard size <= MAX_READ, let raw = try? Data(contentsOf: url) else { return nil }
        return APIResponse(status: 200, mime: "text/html", headers: [:], body: .data(Data(rewrite([UInt8](raw), readLocal))))
    }

    // ------------------------------------------------------------ links ----
    private static var linkCache: (String, [String: String])?
    private static let linkLock = NSLock()
    /// engine/library.py: {source_url or final_url: path} from catalog.json, later records winning.
    static func links(_ lib: URL) -> [String: String] {
        linkLock.lock(); defer { linkLock.unlock() }
        if let c = linkCache, c.0 == lib.path { return c.1 }
        var m: [String: String] = [:]
        if let d = try? Data(contentsOf: lib.appendingPathComponent("catalog.json")),
           let recs = try? JSONSerialization.jsonObject(with: d) as? [[String: Any]] {
            for r in recs {
                for k in ["source_url", "final_url"] {
                    if let v = r[k] as? String, !v.isEmpty, let path = r["path"] as? String { m[v] = path }
                }
            }
        }
        linkCache = (lib.path, m)
        return m
    }

    // ------------------------------------------------- saved_page_part ----
    /// server.py saved_page_part: a transcript the page names, by the rules for asking for it directly.
    static func part(_ page: String, _ src: String, lib: URL) -> [UInt8]? {
        guard let target = urljoin(page, src), target.hasPrefix("/"), !target.hasPrefix("//") else { return nil }
        var path = target
        if let q = path.firstIndex(where: { $0 == "?" || $0 == "#" }) { path = String(path[..<q]) }
        path = path.removingPercentEncoding ?? path
        guard !path.contains("/.."), LibraryFiles.prefixes.contains(where: { path.hasPrefix($0) }),
              case .file(let url) = Router.shared.staticFile(lib, String(path.dropFirst())).body,
              let size = (try? FileManager.default.attributesOfItem(atPath: url.path))?[.size] as? NSNumber,
              size.intValue <= MAX_TRANSCRIPT, let d = try? Data(contentsOf: url) else { return nil }
        return [UInt8](d)
    }

    /// urllib.parse.urljoin for a path base (no scheme or host).
    static func urljoin(_ base: String, _ url: String) -> String? {
        if url.isEmpty { return base }
        if url.range(of: #"^[A-Za-z][A-Za-z0-9+.\-]*:"#, options: .regularExpression) != nil { return url }
        if url.hasPrefix("//") { return url }
        var path = url, tail = ""
        if let i = path.firstIndex(where: { $0 == "?" || $0 == "#" }) { tail = String(path[i...]); path = String(path[..<i]) }
        if path.isEmpty { return base + tail }
        var baseParts = base.components(separatedBy: "/")
        if baseParts.last != "" { baseParts.removeLast() }
        var segs: [String]
        if path.hasPrefix("/") { segs = path.components(separatedBy: "/") }
        else {
            segs = baseParts + path.components(separatedBy: "/")
            if segs.count > 2 { segs = [segs[0]] + segs[1..<(segs.count - 1)].filter { !$0.isEmpty } + [segs[segs.count - 1]] }
        }
        var out: [String] = []
        for s in segs {
            if s == ".." { if !out.isEmpty { out.removeLast() } } else if s == "." { continue } else { out.append(s) }
        }
        if let l = segs.last, l == "." || l == ".." { out.append("") }
        let joined = out.joined(separator: "/")
        return (joined.isEmpty ? "/" : joined) + tail
    }

    // ------------------------------------------------------------ rewrite ----
    static let CSS: [UInt8] = Array("""
<style>
:where(.collapse:not(.navbar-collapse),.collapsing,.tab-pane,.accordion-collapse){display:block!important;height:auto!important;visibility:visible!important}
:where(.partial-collapse){height:auto!important;overflow:visible!important}
:where(.partial-collapse-overlay){display:none!important}
:where(button)[data-toggle="collapse"]:not(:has(span)),:where(button)[data-bs-toggle="collapse"]:not(:has(span)){display:none!important}
:where(button[data-toggle],button[data-bs-toggle]){pointer-events:none}
:where(a[data-toggle="collapse"],a[data-bs-toggle="collapse"]){pointer-events:none;color:inherit;text-decoration:none}
.navbar-offcanvas:target{left:0!important;transform:none!important;opacity:1!important;box-shadow:0 0 20px #0000004d}
:where(.navbar-toggler){display:none!important}
#expanded-description{display:block!important}
#collapsed-description:has(~#expanded-description),#collapse-description{display:none!important}
:where(a.offcanvas-toggle,a[id^="close-mobile-"]){pointer-events:auto;cursor:pointer}
:where(.video-tab-download-popup){position:static!important;visibility:visible!important;width:auto!important;box-shadow:none!important;border:0!important}
:where(.download-menu-submenu){display:block!important}
:where(.video-download-icons,.download-transcript-submenu-btn,.download-submenu-back-btn,.video-tab-toggle-section .tab-toggle-button){display:none!important}
:where(.download-menu-main a[href^="http"]){display:none!important}
:where(.download-menu-submenu a)::before{content:"Transcript PDF: "}
.lb-transcript{margin:.8em 0;font:inherit;line-height:1.5}
.lb-transcript summary{cursor:pointer;font-weight:600}
</style>
""".utf8)

    static let OWN_LOOK: [UInt8] = Array("""
<style id="lb-own">
:root{color-scheme:light dark;--ink:#1d1d1f;--ink2:#55555a;--line:#e6e6e9;--link:#10805c}
@media (prefers-color-scheme:dark){:root{--ink:#f2f2f3;--ink2:#c2c2c7;--line:#313134;--link:#3cc690}}
html{background:transparent}
body{font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI Variable Text","Segoe UI",system-ui,sans-serif!important;color:var(--ink);background:transparent;max-width:46em;margin:4px 0 24px!important;padding:0 2px!important;-webkit-font-smoothing:antialiased}
body>h1:first-child{display:none}
h2{font:650 19px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI Variable Display","Segoe UI",system-ui,sans-serif;margin:1.5em 0 .3em}
p{margin:.4em 0}a{color:var(--link)}
details{border-bottom:1px solid var(--line);padding:4px 0 8px}
summary{list-style:none;color:var(--ink2);font-size:15px;padding:4px 0}summary::-webkit-details-marker{display:none}
summary::before{content:"";display:inline-block;width:7px;height:7px;margin:0 10px 0 2px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(-45deg);vertical-align:2px;transition:transform .15s}
details[open]>summary::before{transform:rotate(45deg)}
ul{color:var(--ink2);font-size:14.5px;overflow-wrap:anywhere;padding-left:22px}
</style>
""".utf8)

    // Python bytes patterns: \s, \w, \b and re.I are ASCII-only there, so they are spelled out (the text is Latin-1, one char per byte).
    private static let W = "A-Za-z0-9_", S = "[ \\t\\n\\r\\x{0C}\\x{0B}]"
    private static func nb(_ p: String) -> String { "(?<![\(W)])" + p }   // \b before a word character
    private static func ne(_ p: String) -> String { p + "(?![\(W)])" }    // \b after a word character
    static let HEAD = BRe("(?i)" + ne("<head") + "[^>]*>")
    static let DOCTYPE = BRe("(?i)" + ne("<!doctype") + "[^>]*>")
    static let ANCHOR = BRe("(?i)" + ne("<a") + "[^>]*>")
    static let LOCAL = BRe("(?i)" + nb("href") + S + "*=" + S + "*(?:[\"']|(?![\"']))(?![a-z][a-z0-9+.-]*:|//)")
    static let TARGET = BRe("(?i)" + S + "target" + S + "*=" + S + "*(?:\"[^\"]*\"|'[^']*'|[^ \\t\\n\\r\\x{0C}\\x{0B}>]+)")
    static let DOWNLOAD = BRe("(?i)" + S + "download(?:" + S + "*=" + S + "*(?:\"[^\"]*\"|'[^']*'|[^ \\t\\n\\r\\x{0C}\\x{0B}>]+))?(?=[ \\t\\n\\r\\x{0C}\\x{0B}>/])")
    static let BUTTON = BRe("(?i)" + ne("<button") + "([^>]*)>")
    static let OPENS = BRe("(?i)" + nb("data-target") + "=[\"'](#[\(W)-]+)[\"']")
    static let IS_OPENER = BRe("(?i)" + nb("data-toggle") + "=[\"']offcanvas[\"']")
    static let IS_CLOSER = BRe("(?i)" + nb("id") + "=[\"']close-mobile-[\(W)-]+[\"']")
    static let DIV = BRe("(?i)" + ne("<div") + "[^>]*>")
    static let IS_GALLERY = BRe("(?i)" + nb("class") + "=[\"'][^\"']*" + nb(ne("image-gallery")))
    static let BASE_URL = BRe("(?i)" + nb("data-base-url") + "=[\"']([^\"']*)[\"']")
    static let HREF = BRe("(?i)" + nb("href") + "=[\"']([^\"']+)[\"']")
    static let TRACK = BRe("(?i)" + ne("<track") + "[^>]*>")
    static let TRACK_SRC = BRe("(?i)" + nb("src") + "=[\"']([^\"'>]+\\.vtt)[\"']")
    static let BLANK_ROW = BRe("<tr>(?:<td><small>[A-Z]+[0-9]+</small>" + S + "*</td>)+</tr>")
    static let LINK = BRe("(?i)" + ne("<link") + "[^>]*>")
    static let HINT_REL = BRe("(?i)" + nb("rel") + S + "*=" + S + "*(?:\"[^\"]*|'[^']*|[^ \\t\\n\\r\\x{0C}\\x{0B}>]+)")
    static let HINT = BRe("(?i)preconnect|dns-prefetch|prefetch|prerender")

    static func upto(_ d: [UInt8]) -> Int { (d.lastIndex(of: UInt8(ascii: ">")) ?? -1) + 1 }

    /// pattern.sub(fn, data[:end]) + data[end:]
    static func subUpto(_ re: BRe, _ d: [UInt8], _ fn: (ArraySlice<UInt8>) -> [UInt8]) -> [UInt8] {
        let end = upto(d)
        let ms = re.all(d, 0, end)
        if ms.isEmpty { return d }
        var out: [UInt8] = []; out.reserveCapacity(d.count)
        var pos = 0
        for m in ms {
            out += d[pos..<m.range.location]
            out += fn(d[m.range.location..<NSMaxRange(m.range)])
            pos = NSMaxRange(m.range)
        }
        out += d[pos...]
        return out
    }

    static func noHints(_ d: [UInt8]) -> [UInt8] {
        subUpto(LINK, d) { tag in
            let t = Array(tag)
            if t.count <= MAX_TAG, let rel = HINT_REL.search(t, 0, t.count),
               HINT.search(Array(t[rel.range.location..<NSMaxRange(rel.range)]), 0, rel.range.length) != nil { return [] }
            return t
        }
    }

    static func ownLook(_ d: [UInt8]) -> [UInt8] {
        let end = upto(d)
        let at = find(asciiLower(d), Array("</head>".utf8), 0, end == 0 ? d.count : end)
        return at >= 0 ? Array(d[..<at]) + OWN_LOOK + Array(d[at...]) : d + OWN_LOOK
    }

    static func anchor(_ tag: ArraySlice<UInt8>) -> [UInt8] {
        let a = Array(tag)
        guard a.count <= MAX_TAG, LOCAL.search(a, 0, a.count) != nil else { return a }
        return DOWNLOAD.sub(TARGET.sub(a))
    }

    static func galleryLinks(_ base: [UInt8], _ inner: [UInt8]) -> [UInt8] {
        let low = asciiLower(inner)
        var out: [UInt8] = [], pos = 0
        let end = upto(inner)
        while true {
            let m = ANCHOR.search(inner, pos, end)
            let close = m.map { find(low, Array("</a>".utf8), NSMaxRange($0.range)) } ?? -1
            guard let m, close >= 0 else { break }
            let tag = Array(inner[m.range.location..<NSMaxRange(m.range)])
            if tag.count <= MAX_TAG, let h = HREF.search(tag, 0, tag.count) {
                out += inner[pos..<m.range.location]
                out += Array("<figure style=\"margin:1em 0\"><img style=\"max-width:100%\" alt=\"\" src=\"".utf8) + base
                out += tag[h.range(at: 1).location..<NSMaxRange(h.range(at: 1))]
                out += Array("\"><figcaption>".utf8) + inner[NSMaxRange(m.range)..<close] + Array("</figcaption></figure>".utf8)
                pos = close + 4
            } else {
                out += inner[pos..<NSMaxRange(m.range)]
                pos = NSMaxRange(m.range)
            }
        }
        out += inner[pos...]
        return out
    }

    static func galleries(_ d: [UInt8]) -> [UInt8] {
        let low = asciiLower(d)
        let key = Array("image-gallery".utf8)
        if find(low, key, 0) < 0 { return d }
        var out: [UInt8] = [], pos = 0, scan = 0
        let end = upto(d)
        while let m = DIV.search(d, scan, end) {
            scan = NSMaxRange(m.range)
            let tag = Array(d[m.range.location..<NSMaxRange(m.range)])
            if tag.count > MAX_TAG || find(asciiLower(tag), key, 0) < 0 || IS_GALLERY.search(tag, 0, tag.count) == nil { continue }
            guard let base = BASE_URL.search(tag, 0, tag.count) else { continue }
            let close = find(low, Array("</div>".utf8), NSMaxRange(m.range))
            if close < 0 { break }
            out += d[pos..<NSMaxRange(m.range)]
            out += galleryLinks(Array(tag[base.range(at: 1).location..<NSMaxRange(base.range(at: 1))]), Array(d[NSMaxRange(m.range)..<close]))
            pos = close; scan = close
        }
        out += d[pos...]
        return out
    }

    static func drawers(_ d: [UInt8]) -> [UInt8] {
        let low = asciiLower(d)
        var out: [UInt8] = [], pos = 0, scan = 0
        let end = upto(d)
        while true {
            let m = BUTTON.search(d, scan, end)
            let close = m.map { find(low, Array("</button>".utf8), NSMaxRange($0.range)) } ?? -1
            guard let m, close >= 0 else { break }
            scan = close + 9
            let attrs = Array(d[m.range(at: 1).location..<NSMaxRange(m.range(at: 1))])
            if attrs.count > MAX_TAG { continue }
            let opens = IS_OPENER.search(attrs, 0, attrs.count) != nil ? OPENS.search(attrs, 0, attrs.count) : nil
            if opens == nil && IS_CLOSER.search(attrs, 0, attrs.count) == nil { continue }
            out += d[pos..<m.range.location]
            out += Array("<a href=\"".utf8)
            if let o = opens { out += attrs[o.range(at: 1).location..<NSMaxRange(o.range(at: 1))] } else { out.append(UInt8(ascii: "#")) }
            out += Array("\"".utf8) + attrs + Array(">".utf8) + d[NSMaxRange(m.range)..<close] + Array("</a>".utf8)
            pos = scan
        }
        out += d[pos...]
        return out
    }

    static func transcriptText(_ vtt: [UInt8]) -> String {
        var out: [String] = [], last: String?
        for line in pySplitlines(String(decoding: vtt, as: UTF8.self)) {
            var s = pyStrip(line)
            if s.isEmpty || s.hasPrefix("WEBVTT") || s.hasPrefix("NOTE") || s.hasPrefix("Kind:") || s.hasPrefix("Language:")
                || s.contains("-->") || pyIsDigit(s) { continue }
            let sc = Array(s.unicodeScalars)
            let end = (sc.lastIndex(of: ">") ?? -1) + 1
            let head = String(String.UnicodeScalarView(sc[..<end])), tail = String(String.UnicodeScalarView(sc[end...]))
            s = head.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression) + tail
            if s != last { out.append(s) }
            last = s
        }
        return out.joined(separator: " ")
    }

    static func rewrite(_ data: [UInt8], _ readLocal: (([UInt8]) -> [UInt8]?)?) -> [UInt8] {
        if data.prefix(512).contains(0) { return data }
        var d = noHints(data)
        if d.count > MAX_PAGE {
            d = BLANK_ROW.sub(d)
            if d.count > MAX_PAGE { return d }
        }
        d = subUpto(ANCHOR, d, anchor)
        d = galleries(d)
        d = drawers(d)
        var track: [UInt8]?
        if find(asciiLower(d), Array("<track".utf8), 0) >= 0 {
            for t in TRACK.all(d, 0, upto(d)) {
                let tag = Array(d[t.range.location..<NSMaxRange(t.range)])
                if tag.count <= MAX_TAG, let m = TRACK_SRC.search(tag, 0, tag.count) {
                    track = Array(tag[m.range(at: 1).location..<NSMaxRange(m.range(at: 1))]); break
                }
            }
        }
        if let track, let readLocal, let vtt = readLocal(track), !vtt.isEmpty {
            let block = Array("<details class=\"lb-transcript\" open><summary>Transcript</summary><p>".utf8)
                + Array(htmlEscape(transcriptText(vtt)).utf8) + Array("</p></details>".utf8)
            var i = find(d, Array("video-tab-content-section".utf8), 0)
            i = i >= 0 ? find(d, Array(">".utf8), i) + 1 : find(d, Array("</video>".utf8), 0) + 8
            i = min(i, d.count)   // find gave -1: Python then inserts at 0 or 7, clamped to the page
            d = Array(d[..<i]) + block + Array(d[i...])
        }
        let end = upto(d)
        let m = HEAD.search(d, 0, end) ?? DOCTYPE.search(d, 0, end)
        let i = m.map { NSMaxRange($0.range) } ?? 0
        return Array(d[..<i]) + CSS + Array(d[i...])
    }

    /// html.escape(s, quote=True)
    static func htmlEscape(_ s: String) -> String {
        var o = ""
        o.reserveCapacity(s.utf8.count)
        for u in s.unicodeScalars {
            switch u {
            case "&": o += "&amp;"; case "<": o += "&lt;"; case ">": o += "&gt;"
            case "\"": o += "&quot;"; case "'": o += "&#x27;"
            default: o.unicodeScalars.append(u)
            }
        }
        return o
    }

    static func asciiLower(_ d: [UInt8]) -> [UInt8] { d.map { $0 >= 65 && $0 <= 90 ? $0 + 32 : $0 } }

    /// bytes.find(needle, start, end)
    static func find(_ hay: [UInt8], _ needle: [UInt8], _ start: Int, _ end: Int? = nil) -> Int {
        let e = min(end ?? hay.count, hay.count)
        guard start >= 0, e - start >= needle.count, !needle.isEmpty else { return needle.isEmpty && start <= e ? start : -1 }
        return hay.withUnsafeBytes { h in
            needle.withUnsafeBytes { n in
                guard let p = memmem(h.baseAddress! + start, e - start, n.baseAddress!, needle.count) else { return -1 }
                return h.baseAddress!.distance(to: UnsafeRawPointer(p))
            }
        }
    }
}

/// A Python bytes regular expression, run on the bytes read as Latin-1 (one UTF-16 unit per byte, so offsets are byte offsets).
final class BRe: @unchecked Sendable {
    let re: NSRegularExpression
    init(_ p: String) { re = try! NSRegularExpression(pattern: p) }
    static func ns(_ d: [UInt8]) -> NSString {
        if d.isEmpty { return "" }
        return d.withUnsafeBufferPointer { NSString(bytes: $0.baseAddress!, length: d.count, encoding: String.Encoding.isoLatin1.rawValue)! }
    }
    func search(_ d: [UInt8], _ from: Int, _ to: Int) -> NSTextCheckingResult? {
        guard from <= to else { return nil }
        return re.firstMatch(in: BRe.ns(d) as String, range: NSRange(location: from, length: to - from))
    }
    func all(_ d: [UInt8], _ from: Int, _ to: Int) -> [NSTextCheckingResult] {
        guard from <= to else { return [] }
        return re.matches(in: BRe.ns(d) as String, range: NSRange(location: from, length: to - from))
    }
    /// pattern.sub(b'', d)
    func sub(_ d: [UInt8]) -> [UInt8] {
        let ms = all(d, 0, d.count)
        if ms.isEmpty { return d }
        var out: [UInt8] = [], pos = 0
        for m in ms { out += d[pos..<m.range.location]; pos = NSMaxRange(m.range) }
        out += d[pos...]
        return out
    }
}

// MARK: - BeautifulSoup(text, 'html.parser') and str(soup)

/// One node of the parse tree.
final class SoupNode {
    enum Kind { case tag, text, comment, cdata, pi, declaration, doctype }
    enum Attr { case s(String), list([String]), charset, content(String) }
    let kind: Kind
    var name = ""
    var attrs: [(String, Attr)] = []
    var children: [SoupNode] = []
    var text = ""
    var rawText = false           // a string directly inside <script> or <style>: not escaped on output
    init(_ k: Kind) { kind = k }
}

enum Soup {
    static let VOID: Set<String> = ["area", "base", "br", "col", "embed", "hr", "img", "input", "keygen", "link", "menuitem", "meta", "param",
                                    "source", "track", "wbr", "basefont", "bgsound", "command", "frame", "image", "isindex", "nextid", "spacer"]
    static let LIST_ATTRS: [String: Set<String>] = ["*": ["class", "accesskey", "dropzone"], "a": ["rel", "rev"], "link": ["rel", "rev"],
        "td": ["headers"], "th": ["headers"], "form": ["accept-charset"], "object": ["archive"], "area": ["rel"], "icon": ["sizes"],
        "iframe": ["sandbox"], "output": ["for"]]

    /// engine/library.py: read_text, BeautifulSoup, rewrite <a href> to library copies, str(soup).encode(). nil if it would fail.
    static func reparse(_ raw: Data, links: [String: String]) -> Data? {
        let text = String(decoding: raw, as: UTF8.self).replacingOccurrences(of: "\r\n", with: "\n").replacingOccurrences(of: "\r", with: "\n")
        let b = SoupBuilder()
        let parser = PyHTMLParser(text, b)
        parser.goahead(false)
        parser.rest()
        parser.goahead(true)
        b.finish()
        // for a in soup.select('a[href]'): point a link at a page the library holds
        var stack = [b.root]
        while let n = stack.popLast() {
            if n.kind == .tag && n.name == "a", let i = n.attrs.firstIndex(where: { $0.0 == "href" }) {
                let href: String
                switch n.attrs[i].1 { case .s(let v): href = v; case .list(let l): href = l.joined(separator: " "); case .charset: href = "utf-8"; case .content(let c): href = c }
                let (base, frag) = urldefrag(href)
                if let t = links[base] { n.attrs[i].1 = .s("/" + t + (frag.isEmpty ? "" : "#" + frag)) }
            }
            stack += n.children
        }
        return serialize(b.root).data(using: .utf8)
    }

    /// urllib.parse.urldefrag (the common cases: an empty query or params left by the split go too).
    static func urldefrag(_ url: String) -> (String, String) {
        guard let i = url.firstIndex(of: "#") else { return (url, "") }
        var base = String(url[..<i])
        let frag = String(url[url.index(after: i)...])
        if base.hasSuffix("?") { base.removeLast() }
        return (base, frag)
    }

    // ------------------------------------------------------------ output ----
    static func serialize(_ root: SoupNode) -> String {
        var out = ""
        // iterative: unclosed tags in old pages can nest thousands deep
        var stack: [(SoupNode, Int)] = [(root, 0)]
        while !stack.isEmpty {
            let (n, i) = stack[stack.count - 1]
            if i < n.children.count {
                stack[stack.count - 1].1 += 1
                let c = n.children[i]
                switch c.kind {
                case .tag:
                    out += openTag(c)
                    if c.children.isEmpty && VOID.contains(c.name) { continue }
                    stack.append((c, 0))
                case .text: if c.rawText { out += c.text } else { escapeXML(c.text, &out) }
                case .comment: out += "<!--" + c.text + "-->"
                case .cdata: out += "<![CDATA[" + c.text + "]]>"
                case .pi: out += "<?" + c.text + ">"
                case .declaration: out += "<?" + c.text + "?>"
                case .doctype: out += "<!DOCTYPE " + c.text + ">\n"
                }
            } else {
                stack.removeLast()
                if n !== root { out += "</" + n.name + ">" }
            }
        }
        return out
    }

    static func openTag(_ t: SoupNode) -> String {
        var s = "<" + t.name
        for (k, v) in t.attrs.sorted(by: { pyLT($0.0, $1.0) }) {
            let val: String
            switch v {
            case .s(let x): val = x
            case .list(let l): val = l.joined(separator: " ")
            case .charset: val = "utf-8"
            case .content(let orig): val = contentCharset(orig)
            }
            var e = ""
            escapeXML(val, &e)
            s += " " + k + "=" + quoted(e)
        }
        if t.children.isEmpty && VOID.contains(t.name) { s += "/" }
        return s + ">"
    }

    /// ContentMetaAttributeValue.substitute_encoding('utf-8'): ((^|;)\s*charset=)([^;]*) -> \1utf-8
    static func contentCharset(_ v: String) -> String {
        let rx = try! NSRegularExpression(pattern: "(?m)((^|;)[\\s\\x{1C}-\\x{1F}]*charset=)([^;]*)")
        return rx.stringByReplacingMatches(in: v, range: NSRange(v.startIndex..., in: v), withTemplate: "$1utf-8")
    }

    static func quoted(_ v: String) -> String {
        if v.utf8.contains(34) {
            if v.utf8.contains(39) { return "\"" + v.replacingOccurrences(of: "\"", with: "&quot;") + "\"" }
            return "'" + v + "'"
        }
        return "\"" + v + "\""
    }

    /// EntitySubstitution.substitute_xml: & < > as entities. Worked on the UTF-8 bytes: pages carry megabytes of data: addresses.
    static func escapeXML(_ s: String, _ out: inout String) {
        let u = s.utf8
        if !u.contains(where: { $0 == 38 || $0 == 60 || $0 == 62 }) { out += s; return }
        var buf: [UInt8] = []
        buf.reserveCapacity(u.count + 32)
        for c in u {
            switch c {
            case 38: buf += [38, 97, 109, 112, 59]   // &amp;
            case 60: buf += [38, 108, 116, 59]       // &lt;
            case 62: buf += [38, 103, 116, 59]       // &gt;
            default: buf.append(c)
            }
        }
        out += String(decoding: buf, as: UTF8.self)
    }
}

/// Beautiful Soup's tree construction (bs4/__init__.py BeautifulSoup and builder/_htmlparser.py BeautifulSoupHTMLParser).
final class SoupBuilder {
    let root = SoupNode(.tag)
    private var tagStack: [SoupNode]
    private var counter: [String: Int] = [:]
    private var preserve: [SoupNode] = []
    private var current: [String] = []
    private var alreadyClosed: [String] = []
    private var currentTag: SoupNode { tagStack[tagStack.count - 1] }

    init() { root.name = "[document]"; tagStack = [root] }

    // BeautifulSoupHTMLParser callbacks
    func starttag(_ tag: String, _ attrs: [(String, String?)], emptyElement: Bool = true) {
        var dict: [(String, String)] = []
        var at: [String: Int] = [:]
        for (k, v) in attrs {
            if let i = at[k] { dict[i].1 = v ?? "" } else { at[k] = dict.count; dict.append((k, v ?? "")) }
        }
        endData()
        let t = SoupNode(.tag)
        t.name = tag
        let universal = Soup.LIST_ATTRS["*"]!, specific = Soup.LIST_ATTRS[tag.lowercased()] ?? []
        t.attrs = dict.map { (k, v) in
            (universal.contains(k) || specific.contains(k)) ? (k, .list(splitWS(v))) : (k, .s(v))
        }
        if tag == "meta" { substitutions(t) }
        currentTag.children.append(t)
        tagStack.append(t)
        counter[tag, default: 0] += 1
        if tag == "pre" || tag == "textarea" { preserve.append(t) }
        if emptyElement && Soup.VOID.contains(tag) {   // is_empty_element: no contents yet and a void name
            endtag(tag, checkAlreadyClosed: false)
            alreadyClosed.append(tag)
        }
    }

    func endtag(_ tag: String, checkAlreadyClosed: Bool = true) {
        if checkAlreadyClosed, let i = alreadyClosed.firstIndex(of: tag) { alreadyClosed.remove(at: i); return }
        endData()
        popTo(tag)
    }

    func startendtag(_ tag: String, _ attrs: [(String, String?)]) {
        starttag(tag, attrs, emptyElement: false)
        endtag(tag, checkAlreadyClosed: false)
    }

    func data(_ s: String) { current.append(s) }

    func charref(_ name0: String) {
        var name = name0, hex = false
        if name.hasPrefix("x") || name.hasPrefix("X") { name.removeFirst(); hex = true }
        var num: Int? = nil
        var extra = ""
        if let v = Self.bigInt(name, hex) { num = v }
        else if let m = name.range(of: hex ? "^[0-9a-f]+" : "^[0-9]+", options: .regularExpression) {
            num = Self.bigInt(String(name[m]), hex); extra = String(name[m.upperBound...])
        } else { extra = name }
        if let num { data(Self.numericReference(num)) }
        else { data("") }
        data(extra)
    }

    /// int(name, base) with Python's leniency (surrounding whitespace, underscores between digits); huge numbers become Int.max.
    static func bigInt(_ s0: String, _ hex: Bool) -> Int? {
        let s = pyStrip(s0)
        guard !s.isEmpty, !s.hasPrefix("_"), !s.hasSuffix("_"), !s.contains("__") else { return nil }
        let digits = s.replacingOccurrences(of: "_", with: "")
        guard digits.unicodeScalars.allSatisfy({ hex ? ("0"..."9").contains($0) || ("a"..."f").contains($0) || ("A"..."F").contains($0) : ("0"..."9").contains($0) })
        else { return nil }
        return Int(digits, radix: hex ? 16 : 10) ?? Int.max
    }

    static let CP1252: [Int: UInt32] = [0x80: 0x20AC, 0x82: 0x201A, 0x83: 0x0192, 0x84: 0x201E, 0x85: 0x2026, 0x86: 0x2020, 0x87: 0x2021,
        0x88: 0x02C6, 0x89: 0x2030, 0x8A: 0x0160, 0x8B: 0x2039, 0x8C: 0x0152, 0x8E: 0x017D, 0x91: 0x2018, 0x92: 0x2019, 0x93: 0x201C,
        0x94: 0x201D, 0x95: 0x2022, 0x96: 0x2013, 0x97: 0x2014, 0x98: 0x02DC, 0x99: 0x2122, 0x9A: 0x0161, 0x9B: 0x203A, 0x9C: 0x0153,
        0x9E: 0x017E, 0x9F: 0x0178]

    /// UnicodeDammit.numeric_character_reference
    static func numericReference(_ n: Int) -> String {
        if n == 0 || n > 0x10FFFF || (0xD800...0xDFFF).contains(n) { return "\u{FFFD}" }
        if (0x80...0x9F).contains(n), let c = CP1252[n] { return String(Unicode.Scalar(c)!) }
        return String(Unicode.Scalar(UInt32(n))!)
    }

    func entityref(_ name: String) {
        if let c = Entities.bs4[name] { data(c) } else { data("&" + name) }
    }

    func special(_ s: String, _ kind: SoupNode.Kind) {
        endData()
        data(s)
        endData(kind)
    }

    func comment(_ s: String) { special(s, .comment) }
    func decl(_ s: String) { special(String(String.UnicodeScalarView(s.unicodeScalars.dropFirst(8))), .doctype) }
    func unknownDecl(_ s: String) {
        let head = String(String.UnicodeScalarView(s.unicodeScalars.prefix(6))).uppercased()
        if head == "CDATA[" { special(String(String.UnicodeScalarView(s.unicodeScalars.dropFirst(6))), .cdata) }
        else { special(s, .declaration) }
    }
    func pi(_ s: String) { special(s, .pi) }

    // BeautifulSoup
    func endData(_ kind: SoupNode.Kind = .text) {
        guard !current.isEmpty else { return }
        var s = current.joined()
        current = []
        if preserve.isEmpty && s.utf8.allSatisfy({ $0 == 0x20 || $0 == 0x0A || $0 == 0x09 || $0 == 0x0C || $0 == 0x0D }) {
            s = s.contains("\n") ? "\n" : " "
        }
        let o = SoupNode(kind)
        o.text = s
        o.rawText = kind == .text && (currentTag.name == "script" || currentTag.name == "style") && currentTag !== root
        currentTag.children.append(o)
    }

    private func popTo(_ name: String) {
        if name == "[document]" { return }
        var i = tagStack.count - 1
        while i > 0 {
            if (counter[name] ?? 0) == 0 { break }
            let t = tagStack[i]
            if t.name == name { popTag(); break }
            popTag()
            i -= 1
        }
    }

    private func popTag() {
        guard tagStack.count > 1 else { return }
        let t = tagStack.removeLast()
        if let c = counter[t.name] { counter[t.name] = c - 1 }
        if let p = preserve.last, p === t { preserve.removeLast() }
    }

    func finish() {
        endData()
        while tagStack.count > 1 { popTag() }
    }

    private func substitutions(_ t: SoupNode) {
        func get(_ k: String) -> SoupNode.Attr? { t.attrs.first { $0.0 == k }?.1 }
        func set(_ k: String, _ v: SoupNode.Attr) { if let i = t.attrs.firstIndex(where: { $0.0 == k }) { t.attrs[i].1 = v } }
        if get("charset") != nil { set("charset", .charset); return }
        if case .s(let content)? = get("content") {
            var equiv: [String] = []
            switch get("http-equiv") { case .s(let v)?: equiv = [v]; case .list(let l)?: equiv = l; default: break }
            if equiv.contains(where: { $0.lowercased() == "content-type" }) { set("content", .content(content)) }
        }
    }

    /// re.findall(r'\S+', v) with Python's idea of whitespace
    private func splitWS(_ v: String) -> [String] {
        var out: [String] = [], cur = String.UnicodeScalarView()
        for u in v.unicodeScalars {
            if Entities.pyIsSpace(u) { if !cur.isEmpty { out.append(String(cur)); cur = String.UnicodeScalarView() } } else { cur.append(u) }
        }
        if !cur.isEmpty { out.append(String(cur)) }
        return out
    }
}

/// Python 3.11.18's html.parser.HTMLParser with convert_charrefs=False, as Beautiful Soup runs it.
final class PyHTMLParser {
    private var raw: NSString
    private var n: Int
    private var cdataElem: String?
    private var escapable = true
    private var interestingCdata: NSRegularExpression?
    private let b: SoupBuilder

    init(_ text: String, _ b: SoupBuilder) {
        let u = Array(text.utf16)
        raw = NSString(characters: u, length: u.count)
        n = u.count
        self.b = b
    }

    private static func rx(_ p: String) -> NSRegularExpression { try! NSRegularExpression(pattern: p) }
    private static let TAGFIND = rx(#"([a-zA-Z][^\t\n\r\x{0C} />]*)(?:[\t\n\r\x{0C} ]|/(?!>))*"#)
    private static let ATTRFIND = rx(#"((?<=['"\t\n\r\x{0C} /])[^\t\n\r\x{0C} />][^\t\n\r\x{0C} /=>]*)([\t\n\r\x{0C} ]*=[\t\n\r\x{0C} ]*('[^']*'|"[^"]*"|(?!['"])[^>\t\n\r\x{0C} ]*))?(?:[\t\n\r\x{0C} ]|/(?!>))*"#)
    private static let LOCATETAGEND = rx(#"[a-zA-Z][^\t\n\r\x{0C} />]*[\t\n\r\x{0C} /]*(?:(?<=['"\t\n\r\x{0C} /])[^\t\n\r\x{0C} />][^\t\n\r\x{0C} /=>]*(?:[\t\n\r\x{0C} ]*=[\t\n\r\x{0C} ]*(?:'[^']*'|"[^"]*"|(?!['"])[^>\t\n\r\x{0C} ]*))?[\t\n\r\x{0C} /]*)*>?"#)
    private static let CHARREF = rx(#"&#(?:[0-9]+|[xX][0-9a-fA-F]+)[^0-9a-fA-F]"#)
    private static let ENTITYREF = rx(#"&([a-zA-Z][-.a-zA-Z0-9]*)[^a-zA-Z0-9]"#)
    private static let INCOMPLETE = rx(#"&[a-zA-Z#]"#)
    private static let COMMENTCLOSE = rx(#"--!?>"#)
    private static let COMMENTABRUPT = rx(#"-?>"#)
    static let CDATA_CONTENT: Set<String> = ["script", "style", "xmp", "iframe", "noembed", "noframes"]
    static let RCDATA_CONTENT: Set<String> = ["textarea", "title"]

    // ------------------------------------------------------------ helpers --
    private func c(_ i: Int) -> UInt16 { i < n ? raw.character(at: i) : 0 }
    /// A native (UTF-8) Swift string: a bridged NSString would make every later byte scan slow.
    private func sub(_ i: Int, _ j: Int) -> String {
        guard j > i else { return "" }
        var s = raw.substring(with: NSRange(location: i, length: min(j, n) - i))
        s.makeContiguousUTF8()
        return s
    }
    private func starts(_ s: String, _ i: Int) -> Bool {
        var k = i
        for u in s.utf16 { if k >= n || raw.character(at: k) != u { return false }; k += 1 }
        return true
    }
    private func find(_ s: String, _ from: Int) -> Int {
        guard from <= n else { return -1 }
        let r = raw.range(of: s, options: .literal, range: NSRange(location: from, length: n - from))
        return r.location == NSNotFound ? -1 : r.location
    }
    /// re.match at i (lookbehind may see before i, as Python's does)
    private func match(_ re: NSRegularExpression, _ i: Int) -> NSTextCheckingResult? {
        guard i <= n else { return nil }
        return re.firstMatch(in: raw as String, options: [.anchored, .withTransparentBounds, .withoutAnchoringBounds], range: NSRange(location: i, length: n - i))
    }
    private func search(_ re: NSRegularExpression, _ i: Int) -> NSTextCheckingResult? {
        guard i <= n else { return nil }
        return re.firstMatch(in: raw as String, options: [.withTransparentBounds, .withoutAnchoringBounds], range: NSRange(location: i, length: n - i))
    }
    private func isAlpha(_ u: UInt16) -> Bool { (u >= 65 && u <= 90) || (u >= 97 && u <= 122) }
    private func starttagopen(_ i: Int) -> Bool { c(i) == 60 && isAlpha(c(i + 1)) }
    private func endtagopen(_ i: Int) -> Bool { c(i) == 60 && c(i + 1) == 47 && isAlpha(c(i + 2)) }

    /// self.rawdata = rawdata[i:] after the first pass
    private var consumed = 0
    func rest() {
        if consumed > 0 {
            let u = (0..<(n - consumed)).map { raw.character(at: consumed + $0) }
            raw = NSString(characters: u, length: u.count)
            n = u.count
            consumed = 0
        }
    }

    private func setCdata(_ elem: String, escapable e: Bool) {
        cdataElem = elem.lowercased()
        escapable = e
        if cdataElem == "plaintext" { interestingCdata = nil; return }
        let letters = cdataElem!.map { ch -> String in ch.isLetter && ch.isASCII ? "[\(ch.lowercased())\(ch.uppercased())]" : NSRegularExpression.escapedPattern(for: String(ch)) }.joined()
        let end = "</" + letters + "(?=[\\t\\n\\r\\x{0C} />])"
        interestingCdata = Self.rx(e ? "&|" + end : end)
    }
    private func clearCdata() { cdataElem = nil; escapable = true; interestingCdata = nil }

    // ------------------------------------------------------------ goahead --
    func goahead(_ end: Bool) {
        var i = 0
        loop: while i < n {
            var j: Int
            if cdataElem == nil {
                j = i
                while j < n { let u = raw.character(at: j); if u == 60 || u == 38 { break }; j += 1 }
            } else if cdataElem == "plaintext" {
                j = n   // \Z: matches only at the very end
            } else if let m = search(interestingCdata!, i) {
                j = m.range.location
            } else { break }
            if i < j { b.data(sub(i, j)) }
            i = j
            if i == n { break }
            if c(i) == 60 {   // <
                var k: Int
                if starttagopen(i) { k = parseStarttag(i) }
                else if starts("</", i) { k = parseEndtag(i) }
                else if starts("<!--", i) { k = parseComment(i) }
                else if starts("<?", i) { k = parsePI(i) }
                else if starts("<!", i) { k = parseHTMLDeclaration(i) }
                else if i + 1 < n || end { b.data("<"); k = i + 1 }
                else { break }
                if k < 0 {
                    if !end { break }
                    if starttagopen(i) {
                    } else if starts("</", i) {
                        if i + 2 == n { b.data("</") }
                        else if endtagopen(i) {}
                        else { b.comment(sub(i + 2, n)) }
                    } else if starts("<!--", i) {
                        var jj = n
                        let tail = sub(i + 4, n)
                        for s in ["--!", "--", "-"] where tail.hasSuffix(s) { jj -= s.utf16.count; break }
                        b.comment(sub(i + 4, jj))
                    } else if starts("<![CDATA[", i) {
                        b.unknownDecl(sub(i + 3, n))
                    } else if sub(i, i + 9).lowercased() == "<!doctype" {
                        b.decl(sub(i + 2, n))
                    } else if starts("<!", i) {
                        b.comment(sub(i + 2, n))
                    } else if starts("<?", i) {
                        b.pi(sub(i + 2, n))
                    }
                    k = n
                }
                i = k
            } else if starts("&#", i) {
                if let m = match(Self.CHARREF, i) {
                    let g = sub(i, NSMaxRange(m.range))
                    let name = String(String.UnicodeScalarView(g.unicodeScalars.dropFirst(2).dropLast()))
                    b.charref(name)
                    var k = NSMaxRange(m.range)
                    if c(k - 1) != 59 { k -= 1 }
                    i = k
                    continue
                } else {
                    if find(";", i) >= 0 { b.data(sub(i, i + 2)); i += 2 }
                    break
                }
            } else if c(i) == 38 {   // &
                if let m = match(Self.ENTITYREF, i) {
                    b.entityref(sub(m.range(at: 1).location, NSMaxRange(m.range(at: 1))))
                    var k = NSMaxRange(m.range)
                    if c(k - 1) != 59 { k -= 1 }
                    i = k
                    continue
                }
                if let m = match(Self.INCOMPLETE, i) {
                    if end && NSMaxRange(m.range) == n { i += 1 }
                    break
                } else if i + 1 < n {
                    b.data("&")
                    i += 1
                } else { break }
            } else {
                break loop
            }
        }
        if end && i < n {
            b.data(sub(i, n))
            i = n
        }
        consumed = i
    }

    // ------------------------------------------------------------ parsers --
    private func parseHTMLDeclaration(_ i: Int) -> Int {
        if starts("<!--", i) { return parseComment(i) }
        if starts("<![CDATA[", i) {
            let j = find("]]>", i + 9)
            if j < 0 { return -1 }
            b.unknownDecl(sub(i + 3, j))
            return j + 3
        }
        if sub(i, i + 9).lowercased() == "<!doctype" {
            let gt = find(">", i + 9)
            if gt < 0 { return -1 }
            b.decl(sub(i + 2, gt))
            return gt + 1
        }
        if starts("<![", i) {
            let j = find(">", i + 3)
            if j < 0 { return -1 }
            if c(j - 1) == 93 { b.unknownDecl(sub(i + 3, j - 1)) } else { b.comment(sub(i + 2, j)) }
            return j + 1
        }
        return parseBogusComment(i)
    }

    private func parseComment(_ i: Int) -> Int {
        var m = search(Self.COMMENTCLOSE, i + 4)
        if m == nil { m = match(Self.COMMENTABRUPT, i + 4) }
        guard let m else { return -1 }
        b.comment(sub(i + 4, m.range.location))
        return NSMaxRange(m.range)
    }

    private func parseBogusComment(_ i: Int) -> Int {
        let pos = find(">", i + 2)
        if pos < 0 { return -1 }
        b.comment(sub(i + 2, pos))
        return pos + 1
    }

    private func parsePI(_ i: Int) -> Int {
        let j = find(">", i + 2)
        if j < 0 { return -1 }
        b.pi(sub(i + 2, j))
        return j + 1
    }

    private func parseStarttag(_ i: Int) -> Int {
        guard let le = match(Self.LOCATETAGEND, i + 1) else { return -1 }
        let endpos = NSMaxRange(le.range)
        if c(endpos - 1) != 62 { return -1 }
        guard let tm = match(Self.TAGFIND, i + 1) else { return -1 }
        var k = NSMaxRange(tm.range)
        let tag = sub(tm.range(at: 1).location, NSMaxRange(tm.range(at: 1))).lowercased()
        var attrs: [(String, String?)] = []
        while k < endpos {
            guard let m = match(Self.ATTRFIND, k) else { break }
            let name = sub(m.range(at: 1).location, NSMaxRange(m.range(at: 1)))
            var value: String?
            if m.range(at: 2).location != NSNotFound {
                let r3 = m.range(at: 3)
                var v = ""
                if r3.location != NSNotFound && r3.length > 0 {
                    let f = c(r3.location), l = c(NSMaxRange(r3) - 1)
                    if (f == 39 || f == 34) && l == f {   // value[:1] == quote == value[-1:]
                        v = r3.length >= 2 ? sub(r3.location + 1, NSMaxRange(r3) - 1) : ""
                    } else { v = sub(r3.location, NSMaxRange(r3)) }
                }
                value = v.isEmpty ? v : Entities.unescape(v)
            }
            attrs.append((name.lowercased(), value))
            k = NSMaxRange(m.range)
        }
        let endText = pyStrip(sub(k, endpos))
        if endText != ">" && endText != "/>" {
            b.data(sub(i, endpos))
            return endpos
        }
        if endText.hasSuffix("/>") {
            b.startendtag(tag, attrs)
        } else {
            b.starttag(tag, attrs)
            if Self.CDATA_CONTENT.contains(tag) || tag == "plaintext" { setCdata(tag, escapable: false) }
            else if Self.RCDATA_CONTENT.contains(tag) { setCdata(tag, escapable: true) }
        }
        return endpos
    }

    private func parseEndtag(_ i: Int) -> Int {
        if find(">", i + 2) < 0 { return -1 }
        if !endtagopen(i) {
            if c(i + 2) == 62 && i + 2 < n { return i + 3 }
            return parseBogusComment(i)
        }
        guard let le = match(Self.LOCATETAGEND, i + 2) else { return -1 }
        let j = NSMaxRange(le.range)
        if c(j - 1) != 62 { return -1 }
        guard let tm = match(Self.TAGFIND, i + 2) else { return -1 }
        b.endtag(sub(tm.range(at: 1).location, NSMaxRange(tm.range(at: 1))).lowercased())
        clearCdata()
        return j
    }
}

/// HTML character references: Python's html.unescape and Beautiful Soup's entity table.
enum Entities {
    /// html.entities.html5 (Python 3.11): each name, U+0001, its text, U+0002.
    static let html5Source: String = "AElig\u{1}\u{C6}\u{2}AElig;\u{1}\u{C6}\u{2}AMP\u{1}&\u{2}AMP;\u{1}&\u{2}Aacute\u{1}\u{C1}\u{2}Aacute;\u{1}\u{C1}\u{2}Abreve;\u{1}\u{102}\u{2}Acirc\u{1}\u{C2}\u{2}Acirc;\u{1}\u{C2}\u{2}Acy;\u{1}\u{410}\u{2}Afr;\u{1}\u{1D504}\u{2}Agrave\u{1}\u{C0}\u{2}Agrave;\u{1}\u{C0}\u{2}Alpha;\u{1}\u{391}\u{2}Amacr;\u{1}\u{100}\u{2}And;\u{1}\u{2A53}\u{2}Aogon;\u{1}\u{104}\u{2}Aopf;\u{1}\u{1D538}\u{2}ApplyFunction;\u{1}\u{2061}\u{2}Aring\u{1}\u{C5}\u{2}Aring;\u{1}\u{C5}\u{2}Ascr;\u{1}\u{1D49C}\u{2}Assign;\u{1}\u{2254}\u{2}Atilde\u{1}\u{C3}\u{2}Atilde;\u{1}\u{C3}\u{2}Auml\u{1}\u{C4}\u{2}Auml;\u{1}\u{C4}\u{2}Backslash;\u{1}\u{2216}\u{2}Barv;\u{1}\u{2AE7}\u{2}Barwed;\u{1}\u{2306}\u{2}Bcy;\u{1}\u{411}\u{2}Because;\u{1}\u{2235}\u{2}Bernoullis;\u{1}\u{212C}\u{2}Beta;\u{1}\u{392}\u{2}Bfr;\u{1}\u{1D505}\u{2}Bopf;\u{1}\u{1D539}\u{2}Breve;\u{1}\u{2D8}\u{2}Bscr;\u{1}\u{212C}\u{2}Bumpeq;\u{1}\u{224E}\u{2}CHcy;\u{1}\u{427}\u{2}" +
        "COPY\u{1}\u{A9}\u{2}COPY;\u{1}\u{A9}\u{2}Cacute;\u{1}\u{106}\u{2}Cap;\u{1}\u{22D2}\u{2}CapitalDifferentialD;\u{1}\u{2145}\u{2}Cayleys;\u{1}\u{212D}\u{2}Ccaron;\u{1}\u{10C}\u{2}Ccedil\u{1}\u{C7}\u{2}Ccedil;\u{1}\u{C7}\u{2}Ccirc;\u{1}\u{108}\u{2}Cconint;\u{1}\u{2230}\u{2}Cdot;\u{1}\u{10A}\u{2}Cedilla;\u{1}\u{B8}\u{2}CenterDot;\u{1}\u{B7}\u{2}Cfr;\u{1}\u{212D}\u{2}Chi;\u{1}\u{3A7}\u{2}CircleDot;\u{1}\u{2299}\u{2}CircleMinus;\u{1}\u{2296}\u{2}CirclePlus;\u{1}\u{2295}\u{2}CircleTimes;\u{1}\u{2297}\u{2}ClockwiseContourIntegral;\u{1}\u{2232}\u{2}CloseCurlyDoubleQuote;\u{1}\u{201D}\u{2}CloseCurlyQuote;\u{1}\u{2019}\u{2}Colon;\u{1}\u{2237}\u{2}Colone;\u{1}\u{2A74}\u{2}Congruent;\u{1}\u{2261}\u{2}Conint;\u{1}\u{222F}\u{2}ContourIntegral;\u{1}\u{222E}\u{2}Copf;\u{1}\u{2102}\u{2}Coproduct;\u{1}\u{2210}\u{2}CounterClockwiseContourIntegral;\u{1}\u{2233}\u{2}Cross;\u{1}\u{2A2F}\u{2}Cscr;\u{1}\u{1D49E}\u{2}Cup;\u{1}\u{22D3}\u{2}CupCap;\u{1}\u{224D}\u{2}DD;\u{1}\u{2145}\u{2}DDotrahd;\u{1}\u{2911}\u{2}DJcy;\u{1}\u{402}\u{2}DScy;\u{1}\u{405}\u{2}DZcy;\u{1}\u{40F}\u{2}" +
        "Dagger;\u{1}\u{2021}\u{2}Darr;\u{1}\u{21A1}\u{2}Dashv;\u{1}\u{2AE4}\u{2}Dcaron;\u{1}\u{10E}\u{2}Dcy;\u{1}\u{414}\u{2}Del;\u{1}\u{2207}\u{2}Delta;\u{1}\u{394}\u{2}Dfr;\u{1}\u{1D507}\u{2}DiacriticalAcute;\u{1}\u{B4}\u{2}DiacriticalDot;\u{1}\u{2D9}\u{2}DiacriticalDoubleAcute;\u{1}\u{2DD}\u{2}DiacriticalGrave;\u{1}`\u{2}DiacriticalTilde;\u{1}\u{2DC}\u{2}Diamond;\u{1}\u{22C4}\u{2}DifferentialD;\u{1}\u{2146}\u{2}Dopf;\u{1}\u{1D53B}\u{2}Dot;\u{1}\u{A8}\u{2}DotDot;\u{1}\u{20DC}\u{2}DotEqual;\u{1}\u{2250}\u{2}DoubleContourIntegral;\u{1}\u{222F}\u{2}DoubleDot;\u{1}\u{A8}\u{2}DoubleDownArrow;\u{1}\u{21D3}\u{2}DoubleLeftArrow;\u{1}\u{21D0}\u{2}DoubleLeftRightArrow;\u{1}\u{21D4}\u{2}DoubleLeftTee;\u{1}\u{2AE4}\u{2}DoubleLongLeftArrow;\u{1}\u{27F8}\u{2}DoubleLongLeftRightArrow;\u{1}\u{27FA}\u{2}DoubleLongRightArrow;\u{1}\u{27F9}\u{2}DoubleRightArrow;\u{1}\u{21D2}\u{2}DoubleRightTee;\u{1}\u{22A8}\u{2}DoubleUpArrow;\u{1}\u{21D1}\u{2}DoubleUpDownArrow;\u{1}\u{21D5}\u{2}DoubleVerticalBar;\u{1}\u{2225}\u{2}DownArrow;\u{1}\u{2193}\u{2}DownArrowBar;\u{1}\u{2913}\u{2}DownArrowUpArrow;\u{1}\u{21F5}\u{2}DownBreve;\u{1}\u{311}\u{2}DownLeftRightVector;\u{1}\u{2950}\u{2}DownLeftTeeVector;\u{1}\u{295E}\u{2}DownLeftVector;\u{1}\u{21BD}\u{2}" +
        "DownLeftVectorBar;\u{1}\u{2956}\u{2}DownRightTeeVector;\u{1}\u{295F}\u{2}DownRightVector;\u{1}\u{21C1}\u{2}DownRightVectorBar;\u{1}\u{2957}\u{2}DownTee;\u{1}\u{22A4}\u{2}DownTeeArrow;\u{1}\u{21A7}\u{2}Downarrow;\u{1}\u{21D3}\u{2}Dscr;\u{1}\u{1D49F}\u{2}Dstrok;\u{1}\u{110}\u{2}ENG;\u{1}\u{14A}\u{2}ETH\u{1}\u{D0}\u{2}ETH;\u{1}\u{D0}\u{2}Eacute\u{1}\u{C9}\u{2}Eacute;\u{1}\u{C9}\u{2}Ecaron;\u{1}\u{11A}\u{2}Ecirc\u{1}\u{CA}\u{2}Ecirc;\u{1}\u{CA}\u{2}Ecy;\u{1}\u{42D}\u{2}Edot;\u{1}\u{116}\u{2}Efr;\u{1}\u{1D508}\u{2}Egrave\u{1}\u{C8}\u{2}Egrave;\u{1}\u{C8}\u{2}Element;\u{1}\u{2208}\u{2}Emacr;\u{1}\u{112}\u{2}EmptySmallSquare;\u{1}\u{25FB}\u{2}EmptyVerySmallSquare;\u{1}\u{25AB}\u{2}Eogon;\u{1}\u{118}\u{2}Eopf;\u{1}\u{1D53C}\u{2}Epsilon;\u{1}\u{395}\u{2}Equal;\u{1}\u{2A75}\u{2}EqualTilde;\u{1}\u{2242}\u{2}Equilibrium;\u{1}\u{21CC}\u{2}Escr;\u{1}\u{2130}\u{2}Esim;\u{1}\u{2A73}\u{2}Eta;\u{1}\u{397}\u{2}Euml\u{1}\u{CB}\u{2}Euml;\u{1}\u{CB}\u{2}Exists;\u{1}\u{2203}\u{2}ExponentialE;\u{1}\u{2147}\u{2}Fcy;\u{1}\u{424}\u{2}" +
        "Ffr;\u{1}\u{1D509}\u{2}FilledSmallSquare;\u{1}\u{25FC}\u{2}FilledVerySmallSquare;\u{1}\u{25AA}\u{2}Fopf;\u{1}\u{1D53D}\u{2}ForAll;\u{1}\u{2200}\u{2}Fouriertrf;\u{1}\u{2131}\u{2}Fscr;\u{1}\u{2131}\u{2}GJcy;\u{1}\u{403}\u{2}GT\u{1}>\u{2}GT;\u{1}>\u{2}Gamma;\u{1}\u{393}\u{2}Gammad;\u{1}\u{3DC}\u{2}Gbreve;\u{1}\u{11E}\u{2}Gcedil;\u{1}\u{122}\u{2}Gcirc;\u{1}\u{11C}\u{2}Gcy;\u{1}\u{413}\u{2}Gdot;\u{1}\u{120}\u{2}Gfr;\u{1}\u{1D50A}\u{2}Gg;\u{1}\u{22D9}\u{2}Gopf;\u{1}\u{1D53E}\u{2}GreaterEqual;\u{1}\u{2265}\u{2}GreaterEqualLess;\u{1}\u{22DB}\u{2}GreaterFullEqual;\u{1}\u{2267}\u{2}GreaterGreater;\u{1}\u{2AA2}\u{2}GreaterLess;\u{1}\u{2277}\u{2}GreaterSlantEqual;\u{1}\u{2A7E}\u{2}GreaterTilde;\u{1}\u{2273}\u{2}Gscr;\u{1}\u{1D4A2}\u{2}Gt;\u{1}\u{226B}\u{2}HARDcy;\u{1}\u{42A}\u{2}Hacek;\u{1}\u{2C7}\u{2}Hat;\u{1}^\u{2}Hcirc;\u{1}\u{124}\u{2}Hfr;\u{1}\u{210C}\u{2}HilbertSpace;\u{1}\u{210B}\u{2}Hopf;\u{1}\u{210D}\u{2}HorizontalLine;\u{1}\u{2500}\u{2}Hscr;\u{1}\u{210B}\u{2}Hstrok;\u{1}\u{126}\u{2}HumpDownHump;\u{1}\u{224E}\u{2}" +
        "HumpEqual;\u{1}\u{224F}\u{2}IEcy;\u{1}\u{415}\u{2}IJlig;\u{1}\u{132}\u{2}IOcy;\u{1}\u{401}\u{2}Iacute\u{1}\u{CD}\u{2}Iacute;\u{1}\u{CD}\u{2}Icirc\u{1}\u{CE}\u{2}Icirc;\u{1}\u{CE}\u{2}Icy;\u{1}\u{418}\u{2}Idot;\u{1}\u{130}\u{2}Ifr;\u{1}\u{2111}\u{2}Igrave\u{1}\u{CC}\u{2}Igrave;\u{1}\u{CC}\u{2}Im;\u{1}\u{2111}\u{2}Imacr;\u{1}\u{12A}\u{2}ImaginaryI;\u{1}\u{2148}\u{2}Implies;\u{1}\u{21D2}\u{2}Int;\u{1}\u{222C}\u{2}Integral;\u{1}\u{222B}\u{2}Intersection;\u{1}\u{22C2}\u{2}InvisibleComma;\u{1}\u{2063}\u{2}InvisibleTimes;\u{1}\u{2062}\u{2}Iogon;\u{1}\u{12E}\u{2}Iopf;\u{1}\u{1D540}\u{2}Iota;\u{1}\u{399}\u{2}Iscr;\u{1}\u{2110}\u{2}Itilde;\u{1}\u{128}\u{2}Iukcy;\u{1}\u{406}\u{2}Iuml\u{1}\u{CF}\u{2}Iuml;\u{1}\u{CF}\u{2}Jcirc;\u{1}\u{134}\u{2}Jcy;\u{1}\u{419}\u{2}Jfr;\u{1}\u{1D50D}\u{2}Jopf;\u{1}\u{1D541}\u{2}Jscr;\u{1}\u{1D4A5}\u{2}Jsercy;\u{1}\u{408}\u{2}Jukcy;\u{1}\u{404}\u{2}KHcy;\u{1}\u{425}\u{2}KJcy;\u{1}\u{40C}\u{2}Kappa;\u{1}\u{39A}\u{2}" +
        "Kcedil;\u{1}\u{136}\u{2}Kcy;\u{1}\u{41A}\u{2}Kfr;\u{1}\u{1D50E}\u{2}Kopf;\u{1}\u{1D542}\u{2}Kscr;\u{1}\u{1D4A6}\u{2}LJcy;\u{1}\u{409}\u{2}LT\u{1}<\u{2}LT;\u{1}<\u{2}Lacute;\u{1}\u{139}\u{2}Lambda;\u{1}\u{39B}\u{2}Lang;\u{1}\u{27EA}\u{2}Laplacetrf;\u{1}\u{2112}\u{2}Larr;\u{1}\u{219E}\u{2}Lcaron;\u{1}\u{13D}\u{2}Lcedil;\u{1}\u{13B}\u{2}Lcy;\u{1}\u{41B}\u{2}LeftAngleBracket;\u{1}\u{27E8}\u{2}LeftArrow;\u{1}\u{2190}\u{2}LeftArrowBar;\u{1}\u{21E4}\u{2}LeftArrowRightArrow;\u{1}\u{21C6}\u{2}LeftCeiling;\u{1}\u{2308}\u{2}LeftDoubleBracket;\u{1}\u{27E6}\u{2}LeftDownTeeVector;\u{1}\u{2961}\u{2}LeftDownVector;\u{1}\u{21C3}\u{2}LeftDownVectorBar;\u{1}\u{2959}\u{2}LeftFloor;\u{1}\u{230A}\u{2}LeftRightArrow;\u{1}\u{2194}\u{2}LeftRightVector;\u{1}\u{294E}\u{2}LeftTee;\u{1}\u{22A3}\u{2}LeftTeeArrow;\u{1}\u{21A4}\u{2}LeftTeeVector;\u{1}\u{295A}\u{2}LeftTriangle;\u{1}\u{22B2}\u{2}LeftTriangleBar;\u{1}\u{29CF}\u{2}LeftTriangleEqual;\u{1}\u{22B4}\u{2}LeftUpDownVector;\u{1}\u{2951}\u{2}LeftUpTeeVector;\u{1}\u{2960}\u{2}LeftUpVector;\u{1}\u{21BF}\u{2}LeftUpVectorBar;\u{1}\u{2958}\u{2}LeftVector;\u{1}\u{21BC}\u{2}LeftVectorBar;\u{1}\u{2952}\u{2}" +
        "Leftarrow;\u{1}\u{21D0}\u{2}Leftrightarrow;\u{1}\u{21D4}\u{2}LessEqualGreater;\u{1}\u{22DA}\u{2}LessFullEqual;\u{1}\u{2266}\u{2}LessGreater;\u{1}\u{2276}\u{2}LessLess;\u{1}\u{2AA1}\u{2}LessSlantEqual;\u{1}\u{2A7D}\u{2}LessTilde;\u{1}\u{2272}\u{2}Lfr;\u{1}\u{1D50F}\u{2}Ll;\u{1}\u{22D8}\u{2}Lleftarrow;\u{1}\u{21DA}\u{2}Lmidot;\u{1}\u{13F}\u{2}LongLeftArrow;\u{1}\u{27F5}\u{2}LongLeftRightArrow;\u{1}\u{27F7}\u{2}LongRightArrow;\u{1}\u{27F6}\u{2}Longleftarrow;\u{1}\u{27F8}\u{2}Longleftrightarrow;\u{1}\u{27FA}\u{2}Longrightarrow;\u{1}\u{27F9}\u{2}Lopf;\u{1}\u{1D543}\u{2}LowerLeftArrow;\u{1}\u{2199}\u{2}LowerRightArrow;\u{1}\u{2198}\u{2}Lscr;\u{1}\u{2112}\u{2}Lsh;\u{1}\u{21B0}\u{2}Lstrok;\u{1}\u{141}\u{2}Lt;\u{1}\u{226A}\u{2}Map;\u{1}\u{2905}\u{2}Mcy;\u{1}\u{41C}\u{2}MediumSpace;\u{1}\u{205F}\u{2}Mellintrf;\u{1}\u{2133}\u{2}Mfr;\u{1}\u{1D510}\u{2}MinusPlus;\u{1}\u{2213}\u{2}Mopf;\u{1}\u{1D544}\u{2}Mscr;\u{1}\u{2133}\u{2}Mu;\u{1}\u{39C}\u{2}NJcy;\u{1}\u{40A}\u{2}Nacute;\u{1}\u{143}\u{2}Ncaron;\u{1}\u{147}\u{2}Ncedil;\u{1}\u{145}\u{2}Ncy;\u{1}\u{41D}\u{2}NegativeMediumSpace;\u{1}\u{200B}\u{2}" +
        "NegativeThickSpace;\u{1}\u{200B}\u{2}NegativeThinSpace;\u{1}\u{200B}\u{2}NegativeVeryThinSpace;\u{1}\u{200B}\u{2}NestedGreaterGreater;\u{1}\u{226B}\u{2}NestedLessLess;\u{1}\u{226A}\u{2}NewLine;\u{1}\u{A}\u{2}Nfr;\u{1}\u{1D511}\u{2}NoBreak;\u{1}\u{2060}\u{2}NonBreakingSpace;\u{1}\u{A0}\u{2}Nopf;\u{1}\u{2115}\u{2}Not;\u{1}\u{2AEC}\u{2}NotCongruent;\u{1}\u{2262}\u{2}NotCupCap;\u{1}\u{226D}\u{2}NotDoubleVerticalBar;\u{1}\u{2226}\u{2}NotElement;\u{1}\u{2209}\u{2}NotEqual;\u{1}\u{2260}\u{2}NotEqualTilde;\u{1}\u{2242}\u{338}\u{2}NotExists;\u{1}\u{2204}\u{2}NotGreater;\u{1}\u{226F}\u{2}NotGreaterEqual;\u{1}\u{2271}\u{2}NotGreaterFullEqual;\u{1}\u{2267}\u{338}\u{2}NotGreaterGreater;\u{1}\u{226B}\u{338}\u{2}NotGreaterLess;\u{1}\u{2279}\u{2}NotGreaterSlantEqual;\u{1}\u{2A7E}\u{338}\u{2}NotGreaterTilde;\u{1}\u{2275}\u{2}NotHumpDownHump;\u{1}\u{224E}\u{338}\u{2}NotHumpEqual;\u{1}\u{224F}\u{338}\u{2}NotLeftTriangle;\u{1}\u{22EA}\u{2}NotLeftTriangleBar;\u{1}\u{29CF}\u{338}\u{2}NotLeftTriangleEqual;\u{1}\u{22EC}\u{2}NotLess;\u{1}\u{226E}\u{2}NotLessEqual;\u{1}\u{2270}\u{2}NotLessGreater;\u{1}\u{2278}\u{2}NotLessLess;\u{1}\u{226A}\u{338}\u{2}NotLessSlantEqual;\u{1}\u{2A7D}\u{338}\u{2}NotLessTilde;\u{1}\u{2274}\u{2}NotNestedGreaterGreater;\u{1}\u{2AA2}\u{338}\u{2}NotNestedLessLess;\u{1}\u{2AA1}\u{338}\u{2}NotPrecedes;\u{1}\u{2280}\u{2}NotPrecedesEqual;\u{1}\u{2AAF}\u{338}\u{2}" +
        "NotPrecedesSlantEqual;\u{1}\u{22E0}\u{2}NotReverseElement;\u{1}\u{220C}\u{2}NotRightTriangle;\u{1}\u{22EB}\u{2}NotRightTriangleBar;\u{1}\u{29D0}\u{338}\u{2}NotRightTriangleEqual;\u{1}\u{22ED}\u{2}NotSquareSubset;\u{1}\u{228F}\u{338}\u{2}NotSquareSubsetEqual;\u{1}\u{22E2}\u{2}NotSquareSuperset;\u{1}\u{2290}\u{338}\u{2}NotSquareSupersetEqual;\u{1}\u{22E3}\u{2}NotSubset;\u{1}\u{2282}\u{20D2}\u{2}NotSubsetEqual;\u{1}\u{2288}\u{2}NotSucceeds;\u{1}\u{2281}\u{2}NotSucceedsEqual;\u{1}\u{2AB0}\u{338}\u{2}NotSucceedsSlantEqual;\u{1}\u{22E1}\u{2}NotSucceedsTilde;\u{1}\u{227F}\u{338}\u{2}NotSuperset;\u{1}\u{2283}\u{20D2}\u{2}NotSupersetEqual;\u{1}\u{2289}\u{2}NotTilde;\u{1}\u{2241}\u{2}NotTildeEqual;\u{1}\u{2244}\u{2}NotTildeFullEqual;\u{1}\u{2247}\u{2}NotTildeTilde;\u{1}\u{2249}\u{2}NotVerticalBar;\u{1}\u{2224}\u{2}Nscr;\u{1}\u{1D4A9}\u{2}Ntilde\u{1}\u{D1}\u{2}Ntilde;\u{1}\u{D1}\u{2}Nu;\u{1}\u{39D}\u{2}OElig;\u{1}\u{152}\u{2}Oacute\u{1}\u{D3}\u{2}Oacute;\u{1}\u{D3}\u{2}Ocirc\u{1}\u{D4}\u{2}Ocirc;\u{1}\u{D4}\u{2}Ocy;\u{1}\u{41E}\u{2}Odblac;\u{1}\u{150}\u{2}Ofr;\u{1}\u{1D512}\u{2}Ograve\u{1}\u{D2}\u{2}Ograve;\u{1}\u{D2}\u{2}Omacr;\u{1}\u{14C}\u{2}Omega;\u{1}\u{3A9}\u{2}Omicron;\u{1}\u{39F}\u{2}Oopf;\u{1}\u{1D546}\u{2}" +
        "OpenCurlyDoubleQuote;\u{1}\u{201C}\u{2}OpenCurlyQuote;\u{1}\u{2018}\u{2}Or;\u{1}\u{2A54}\u{2}Oscr;\u{1}\u{1D4AA}\u{2}Oslash\u{1}\u{D8}\u{2}Oslash;\u{1}\u{D8}\u{2}Otilde\u{1}\u{D5}\u{2}Otilde;\u{1}\u{D5}\u{2}Otimes;\u{1}\u{2A37}\u{2}Ouml\u{1}\u{D6}\u{2}Ouml;\u{1}\u{D6}\u{2}OverBar;\u{1}\u{203E}\u{2}OverBrace;\u{1}\u{23DE}\u{2}OverBracket;\u{1}\u{23B4}\u{2}OverParenthesis;\u{1}\u{23DC}\u{2}PartialD;\u{1}\u{2202}\u{2}Pcy;\u{1}\u{41F}\u{2}Pfr;\u{1}\u{1D513}\u{2}Phi;\u{1}\u{3A6}\u{2}Pi;\u{1}\u{3A0}\u{2}PlusMinus;\u{1}\u{B1}\u{2}Poincareplane;\u{1}\u{210C}\u{2}Popf;\u{1}\u{2119}\u{2}Pr;\u{1}\u{2ABB}\u{2}Precedes;\u{1}\u{227A}\u{2}PrecedesEqual;\u{1}\u{2AAF}\u{2}PrecedesSlantEqual;\u{1}\u{227C}\u{2}PrecedesTilde;\u{1}\u{227E}\u{2}Prime;\u{1}\u{2033}\u{2}Product;\u{1}\u{220F}\u{2}Proportion;\u{1}\u{2237}\u{2}Proportional;\u{1}\u{221D}\u{2}Pscr;\u{1}\u{1D4AB}\u{2}Psi;\u{1}\u{3A8}\u{2}QUOT\u{1}\u{22}\u{2}QUOT;\u{1}\u{22}\u{2}Qfr;\u{1}\u{1D514}\u{2}Qopf;\u{1}\u{211A}\u{2}Qscr;\u{1}\u{1D4AC}\u{2}RBarr;\u{1}\u{2910}\u{2}" +
        "REG\u{1}\u{AE}\u{2}REG;\u{1}\u{AE}\u{2}Racute;\u{1}\u{154}\u{2}Rang;\u{1}\u{27EB}\u{2}Rarr;\u{1}\u{21A0}\u{2}Rarrtl;\u{1}\u{2916}\u{2}Rcaron;\u{1}\u{158}\u{2}Rcedil;\u{1}\u{156}\u{2}Rcy;\u{1}\u{420}\u{2}Re;\u{1}\u{211C}\u{2}ReverseElement;\u{1}\u{220B}\u{2}ReverseEquilibrium;\u{1}\u{21CB}\u{2}ReverseUpEquilibrium;\u{1}\u{296F}\u{2}Rfr;\u{1}\u{211C}\u{2}Rho;\u{1}\u{3A1}\u{2}RightAngleBracket;\u{1}\u{27E9}\u{2}RightArrow;\u{1}\u{2192}\u{2}RightArrowBar;\u{1}\u{21E5}\u{2}RightArrowLeftArrow;\u{1}\u{21C4}\u{2}RightCeiling;\u{1}\u{2309}\u{2}RightDoubleBracket;\u{1}\u{27E7}\u{2}RightDownTeeVector;\u{1}\u{295D}\u{2}RightDownVector;\u{1}\u{21C2}\u{2}RightDownVectorBar;\u{1}\u{2955}\u{2}RightFloor;\u{1}\u{230B}\u{2}RightTee;\u{1}\u{22A2}\u{2}RightTeeArrow;\u{1}\u{21A6}\u{2}RightTeeVector;\u{1}\u{295B}\u{2}RightTriangle;\u{1}\u{22B3}\u{2}RightTriangleBar;\u{1}\u{29D0}\u{2}RightTriangleEqual;\u{1}\u{22B5}\u{2}RightUpDownVector;\u{1}\u{294F}\u{2}RightUpTeeVector;\u{1}\u{295C}\u{2}RightUpVector;\u{1}\u{21BE}\u{2}RightUpVectorBar;\u{1}\u{2954}\u{2}RightVector;\u{1}\u{21C0}\u{2}RightVectorBar;\u{1}\u{2953}\u{2}Rightarrow;\u{1}\u{21D2}\u{2}Ropf;\u{1}\u{211D}\u{2}RoundImplies;\u{1}\u{2970}\u{2}" +
        "Rrightarrow;\u{1}\u{21DB}\u{2}Rscr;\u{1}\u{211B}\u{2}Rsh;\u{1}\u{21B1}\u{2}RuleDelayed;\u{1}\u{29F4}\u{2}SHCHcy;\u{1}\u{429}\u{2}SHcy;\u{1}\u{428}\u{2}SOFTcy;\u{1}\u{42C}\u{2}Sacute;\u{1}\u{15A}\u{2}Sc;\u{1}\u{2ABC}\u{2}Scaron;\u{1}\u{160}\u{2}Scedil;\u{1}\u{15E}\u{2}Scirc;\u{1}\u{15C}\u{2}Scy;\u{1}\u{421}\u{2}Sfr;\u{1}\u{1D516}\u{2}ShortDownArrow;\u{1}\u{2193}\u{2}ShortLeftArrow;\u{1}\u{2190}\u{2}ShortRightArrow;\u{1}\u{2192}\u{2}ShortUpArrow;\u{1}\u{2191}\u{2}Sigma;\u{1}\u{3A3}\u{2}SmallCircle;\u{1}\u{2218}\u{2}Sopf;\u{1}\u{1D54A}\u{2}Sqrt;\u{1}\u{221A}\u{2}Square;\u{1}\u{25A1}\u{2}SquareIntersection;\u{1}\u{2293}\u{2}SquareSubset;\u{1}\u{228F}\u{2}SquareSubsetEqual;\u{1}\u{2291}\u{2}SquareSuperset;\u{1}\u{2290}\u{2}SquareSupersetEqual;\u{1}\u{2292}\u{2}SquareUnion;\u{1}\u{2294}\u{2}Sscr;\u{1}\u{1D4AE}\u{2}Star;\u{1}\u{22C6}\u{2}Sub;\u{1}\u{22D0}\u{2}Subset;\u{1}\u{22D0}\u{2}SubsetEqual;\u{1}\u{2286}\u{2}Succeeds;\u{1}\u{227B}\u{2}SucceedsEqual;\u{1}\u{2AB0}\u{2}SucceedsSlantEqual;\u{1}\u{227D}\u{2}SucceedsTilde;\u{1}\u{227F}\u{2}SuchThat;\u{1}\u{220B}\u{2}Sum;\u{1}\u{2211}\u{2}" +
        "Sup;\u{1}\u{22D1}\u{2}Superset;\u{1}\u{2283}\u{2}SupersetEqual;\u{1}\u{2287}\u{2}Supset;\u{1}\u{22D1}\u{2}THORN\u{1}\u{DE}\u{2}THORN;\u{1}\u{DE}\u{2}TRADE;\u{1}\u{2122}\u{2}TSHcy;\u{1}\u{40B}\u{2}TScy;\u{1}\u{426}\u{2}Tab;\u{1}\u{9}\u{2}Tau;\u{1}\u{3A4}\u{2}Tcaron;\u{1}\u{164}\u{2}Tcedil;\u{1}\u{162}\u{2}Tcy;\u{1}\u{422}\u{2}Tfr;\u{1}\u{1D517}\u{2}Therefore;\u{1}\u{2234}\u{2}Theta;\u{1}\u{398}\u{2}ThickSpace;\u{1}\u{205F}\u{200A}\u{2}ThinSpace;\u{1}\u{2009}\u{2}Tilde;\u{1}\u{223C}\u{2}TildeEqual;\u{1}\u{2243}\u{2}TildeFullEqual;\u{1}\u{2245}\u{2}TildeTilde;\u{1}\u{2248}\u{2}Topf;\u{1}\u{1D54B}\u{2}TripleDot;\u{1}\u{20DB}\u{2}Tscr;\u{1}\u{1D4AF}\u{2}Tstrok;\u{1}\u{166}\u{2}Uacute\u{1}\u{DA}\u{2}Uacute;\u{1}\u{DA}\u{2}Uarr;\u{1}\u{219F}\u{2}Uarrocir;\u{1}\u{2949}\u{2}Ubrcy;\u{1}\u{40E}\u{2}Ubreve;\u{1}\u{16C}\u{2}Ucirc\u{1}\u{DB}\u{2}Ucirc;\u{1}\u{DB}\u{2}Ucy;\u{1}\u{423}\u{2}Udblac;\u{1}\u{170}\u{2}Ufr;\u{1}\u{1D518}\u{2}Ugrave\u{1}\u{D9}\u{2}Ugrave;\u{1}\u{D9}\u{2}" +
        "Umacr;\u{1}\u{16A}\u{2}UnderBar;\u{1}_\u{2}UnderBrace;\u{1}\u{23DF}\u{2}UnderBracket;\u{1}\u{23B5}\u{2}UnderParenthesis;\u{1}\u{23DD}\u{2}Union;\u{1}\u{22C3}\u{2}UnionPlus;\u{1}\u{228E}\u{2}Uogon;\u{1}\u{172}\u{2}Uopf;\u{1}\u{1D54C}\u{2}UpArrow;\u{1}\u{2191}\u{2}UpArrowBar;\u{1}\u{2912}\u{2}UpArrowDownArrow;\u{1}\u{21C5}\u{2}UpDownArrow;\u{1}\u{2195}\u{2}UpEquilibrium;\u{1}\u{296E}\u{2}UpTee;\u{1}\u{22A5}\u{2}UpTeeArrow;\u{1}\u{21A5}\u{2}Uparrow;\u{1}\u{21D1}\u{2}Updownarrow;\u{1}\u{21D5}\u{2}UpperLeftArrow;\u{1}\u{2196}\u{2}UpperRightArrow;\u{1}\u{2197}\u{2}Upsi;\u{1}\u{3D2}\u{2}Upsilon;\u{1}\u{3A5}\u{2}Uring;\u{1}\u{16E}\u{2}Uscr;\u{1}\u{1D4B0}\u{2}Utilde;\u{1}\u{168}\u{2}Uuml\u{1}\u{DC}\u{2}Uuml;\u{1}\u{DC}\u{2}VDash;\u{1}\u{22AB}\u{2}Vbar;\u{1}\u{2AEB}\u{2}Vcy;\u{1}\u{412}\u{2}Vdash;\u{1}\u{22A9}\u{2}Vdashl;\u{1}\u{2AE6}\u{2}Vee;\u{1}\u{22C1}\u{2}Verbar;\u{1}\u{2016}\u{2}Vert;\u{1}\u{2016}\u{2}VerticalBar;\u{1}\u{2223}\u{2}VerticalLine;\u{1}|\u{2}VerticalSeparator;\u{1}\u{2758}\u{2}VerticalTilde;\u{1}\u{2240}\u{2}VeryThinSpace;\u{1}\u{200A}\u{2}" +
        "Vfr;\u{1}\u{1D519}\u{2}Vopf;\u{1}\u{1D54D}\u{2}Vscr;\u{1}\u{1D4B1}\u{2}Vvdash;\u{1}\u{22AA}\u{2}Wcirc;\u{1}\u{174}\u{2}Wedge;\u{1}\u{22C0}\u{2}Wfr;\u{1}\u{1D51A}\u{2}Wopf;\u{1}\u{1D54E}\u{2}Wscr;\u{1}\u{1D4B2}\u{2}Xfr;\u{1}\u{1D51B}\u{2}Xi;\u{1}\u{39E}\u{2}Xopf;\u{1}\u{1D54F}\u{2}Xscr;\u{1}\u{1D4B3}\u{2}YAcy;\u{1}\u{42F}\u{2}YIcy;\u{1}\u{407}\u{2}YUcy;\u{1}\u{42E}\u{2}Yacute\u{1}\u{DD}\u{2}Yacute;\u{1}\u{DD}\u{2}Ycirc;\u{1}\u{176}\u{2}Ycy;\u{1}\u{42B}\u{2}Yfr;\u{1}\u{1D51C}\u{2}Yopf;\u{1}\u{1D550}\u{2}Yscr;\u{1}\u{1D4B4}\u{2}Yuml;\u{1}\u{178}\u{2}ZHcy;\u{1}\u{416}\u{2}Zacute;\u{1}\u{179}\u{2}Zcaron;\u{1}\u{17D}\u{2}Zcy;\u{1}\u{417}\u{2}Zdot;\u{1}\u{17B}\u{2}ZeroWidthSpace;\u{1}\u{200B}\u{2}Zeta;\u{1}\u{396}\u{2}Zfr;\u{1}\u{2128}\u{2}Zopf;\u{1}\u{2124}\u{2}Zscr;\u{1}\u{1D4B5}\u{2}aacute\u{1}\u{E1}\u{2}aacute;\u{1}\u{E1}\u{2}abreve;\u{1}\u{103}\u{2}ac;\u{1}\u{223E}\u{2}acE;\u{1}\u{223E}\u{333}\u{2}acd;\u{1}\u{223F}\u{2}" +
        "acirc\u{1}\u{E2}\u{2}acirc;\u{1}\u{E2}\u{2}acute\u{1}\u{B4}\u{2}acute;\u{1}\u{B4}\u{2}acy;\u{1}\u{430}\u{2}aelig\u{1}\u{E6}\u{2}aelig;\u{1}\u{E6}\u{2}af;\u{1}\u{2061}\u{2}afr;\u{1}\u{1D51E}\u{2}agrave\u{1}\u{E0}\u{2}agrave;\u{1}\u{E0}\u{2}alefsym;\u{1}\u{2135}\u{2}aleph;\u{1}\u{2135}\u{2}alpha;\u{1}\u{3B1}\u{2}amacr;\u{1}\u{101}\u{2}amalg;\u{1}\u{2A3F}\u{2}amp\u{1}&\u{2}amp;\u{1}&\u{2}and;\u{1}\u{2227}\u{2}andand;\u{1}\u{2A55}\u{2}andd;\u{1}\u{2A5C}\u{2}andslope;\u{1}\u{2A58}\u{2}andv;\u{1}\u{2A5A}\u{2}ang;\u{1}\u{2220}\u{2}ange;\u{1}\u{29A4}\u{2}angle;\u{1}\u{2220}\u{2}angmsd;\u{1}\u{2221}\u{2}angmsdaa;\u{1}\u{29A8}\u{2}angmsdab;\u{1}\u{29A9}\u{2}angmsdac;\u{1}\u{29AA}\u{2}angmsdad;\u{1}\u{29AB}\u{2}angmsdae;\u{1}\u{29AC}\u{2}angmsdaf;\u{1}\u{29AD}\u{2}angmsdag;\u{1}\u{29AE}\u{2}angmsdah;\u{1}\u{29AF}\u{2}angrt;\u{1}\u{221F}\u{2}angrtvb;\u{1}\u{22BE}\u{2}angrtvbd;\u{1}\u{299D}\u{2}angsph;\u{1}\u{2222}\u{2}angst;\u{1}\u{C5}\u{2}" +
        "angzarr;\u{1}\u{237C}\u{2}aogon;\u{1}\u{105}\u{2}aopf;\u{1}\u{1D552}\u{2}ap;\u{1}\u{2248}\u{2}apE;\u{1}\u{2A70}\u{2}apacir;\u{1}\u{2A6F}\u{2}ape;\u{1}\u{224A}\u{2}apid;\u{1}\u{224B}\u{2}apos;\u{1}'\u{2}approx;\u{1}\u{2248}\u{2}approxeq;\u{1}\u{224A}\u{2}aring\u{1}\u{E5}\u{2}aring;\u{1}\u{E5}\u{2}ascr;\u{1}\u{1D4B6}\u{2}ast;\u{1}*\u{2}asymp;\u{1}\u{2248}\u{2}asympeq;\u{1}\u{224D}\u{2}atilde\u{1}\u{E3}\u{2}atilde;\u{1}\u{E3}\u{2}auml\u{1}\u{E4}\u{2}auml;\u{1}\u{E4}\u{2}awconint;\u{1}\u{2233}\u{2}awint;\u{1}\u{2A11}\u{2}bNot;\u{1}\u{2AED}\u{2}backcong;\u{1}\u{224C}\u{2}backepsilon;\u{1}\u{3F6}\u{2}backprime;\u{1}\u{2035}\u{2}backsim;\u{1}\u{223D}\u{2}backsimeq;\u{1}\u{22CD}\u{2}barvee;\u{1}\u{22BD}\u{2}barwed;\u{1}\u{2305}\u{2}barwedge;\u{1}\u{2305}\u{2}bbrk;\u{1}\u{23B5}\u{2}bbrktbrk;\u{1}\u{23B6}\u{2}bcong;\u{1}\u{224C}\u{2}bcy;\u{1}\u{431}\u{2}bdquo;\u{1}\u{201E}\u{2}becaus;\u{1}\u{2235}\u{2}because;\u{1}\u{2235}\u{2}bemptyv;\u{1}\u{29B0}\u{2}" +
        "bepsi;\u{1}\u{3F6}\u{2}bernou;\u{1}\u{212C}\u{2}beta;\u{1}\u{3B2}\u{2}beth;\u{1}\u{2136}\u{2}between;\u{1}\u{226C}\u{2}bfr;\u{1}\u{1D51F}\u{2}bigcap;\u{1}\u{22C2}\u{2}bigcirc;\u{1}\u{25EF}\u{2}bigcup;\u{1}\u{22C3}\u{2}bigodot;\u{1}\u{2A00}\u{2}bigoplus;\u{1}\u{2A01}\u{2}bigotimes;\u{1}\u{2A02}\u{2}bigsqcup;\u{1}\u{2A06}\u{2}bigstar;\u{1}\u{2605}\u{2}bigtriangledown;\u{1}\u{25BD}\u{2}bigtriangleup;\u{1}\u{25B3}\u{2}biguplus;\u{1}\u{2A04}\u{2}bigvee;\u{1}\u{22C1}\u{2}bigwedge;\u{1}\u{22C0}\u{2}bkarow;\u{1}\u{290D}\u{2}blacklozenge;\u{1}\u{29EB}\u{2}blacksquare;\u{1}\u{25AA}\u{2}blacktriangle;\u{1}\u{25B4}\u{2}blacktriangledown;\u{1}\u{25BE}\u{2}blacktriangleleft;\u{1}\u{25C2}\u{2}blacktriangleright;\u{1}\u{25B8}\u{2}blank;\u{1}\u{2423}\u{2}blk12;\u{1}\u{2592}\u{2}blk14;\u{1}\u{2591}\u{2}blk34;\u{1}\u{2593}\u{2}block;\u{1}\u{2588}\u{2}bne;\u{1}=\u{20E5}\u{2}bnequiv;\u{1}\u{2261}\u{20E5}\u{2}bnot;\u{1}\u{2310}\u{2}bopf;\u{1}\u{1D553}\u{2}bot;\u{1}\u{22A5}\u{2}bottom;\u{1}\u{22A5}\u{2}bowtie;\u{1}\u{22C8}\u{2}boxDL;\u{1}\u{2557}\u{2}boxDR;\u{1}\u{2554}\u{2}" +
        "boxDl;\u{1}\u{2556}\u{2}boxDr;\u{1}\u{2553}\u{2}boxH;\u{1}\u{2550}\u{2}boxHD;\u{1}\u{2566}\u{2}boxHU;\u{1}\u{2569}\u{2}boxHd;\u{1}\u{2564}\u{2}boxHu;\u{1}\u{2567}\u{2}boxUL;\u{1}\u{255D}\u{2}boxUR;\u{1}\u{255A}\u{2}boxUl;\u{1}\u{255C}\u{2}boxUr;\u{1}\u{2559}\u{2}boxV;\u{1}\u{2551}\u{2}boxVH;\u{1}\u{256C}\u{2}boxVL;\u{1}\u{2563}\u{2}boxVR;\u{1}\u{2560}\u{2}boxVh;\u{1}\u{256B}\u{2}boxVl;\u{1}\u{2562}\u{2}boxVr;\u{1}\u{255F}\u{2}boxbox;\u{1}\u{29C9}\u{2}boxdL;\u{1}\u{2555}\u{2}boxdR;\u{1}\u{2552}\u{2}boxdl;\u{1}\u{2510}\u{2}boxdr;\u{1}\u{250C}\u{2}boxh;\u{1}\u{2500}\u{2}boxhD;\u{1}\u{2565}\u{2}boxhU;\u{1}\u{2568}\u{2}boxhd;\u{1}\u{252C}\u{2}boxhu;\u{1}\u{2534}\u{2}boxminus;\u{1}\u{229F}\u{2}boxplus;\u{1}\u{229E}\u{2}boxtimes;\u{1}\u{22A0}\u{2}boxuL;\u{1}\u{255B}\u{2}boxuR;\u{1}\u{2558}\u{2}boxul;\u{1}\u{2518}\u{2}boxur;\u{1}\u{2514}\u{2}boxv;\u{1}\u{2502}\u{2}boxvH;\u{1}\u{256A}\u{2}boxvL;\u{1}\u{2561}\u{2}boxvR;\u{1}\u{255E}\u{2}boxvh;\u{1}\u{253C}\u{2}" +
        "boxvl;\u{1}\u{2524}\u{2}boxvr;\u{1}\u{251C}\u{2}bprime;\u{1}\u{2035}\u{2}breve;\u{1}\u{2D8}\u{2}brvbar\u{1}\u{A6}\u{2}brvbar;\u{1}\u{A6}\u{2}bscr;\u{1}\u{1D4B7}\u{2}bsemi;\u{1}\u{204F}\u{2}bsim;\u{1}\u{223D}\u{2}bsime;\u{1}\u{22CD}\u{2}bsol;\u{1}\u{5C}\u{2}bsolb;\u{1}\u{29C5}\u{2}bsolhsub;\u{1}\u{27C8}\u{2}bull;\u{1}\u{2022}\u{2}bullet;\u{1}\u{2022}\u{2}bump;\u{1}\u{224E}\u{2}bumpE;\u{1}\u{2AAE}\u{2}bumpe;\u{1}\u{224F}\u{2}bumpeq;\u{1}\u{224F}\u{2}cacute;\u{1}\u{107}\u{2}cap;\u{1}\u{2229}\u{2}capand;\u{1}\u{2A44}\u{2}capbrcup;\u{1}\u{2A49}\u{2}capcap;\u{1}\u{2A4B}\u{2}capcup;\u{1}\u{2A47}\u{2}capdot;\u{1}\u{2A40}\u{2}caps;\u{1}\u{2229}\u{FE00}\u{2}caret;\u{1}\u{2041}\u{2}caron;\u{1}\u{2C7}\u{2}ccaps;\u{1}\u{2A4D}\u{2}ccaron;\u{1}\u{10D}\u{2}ccedil\u{1}\u{E7}\u{2}ccedil;\u{1}\u{E7}\u{2}ccirc;\u{1}\u{109}\u{2}ccups;\u{1}\u{2A4C}\u{2}ccupssm;\u{1}\u{2A50}\u{2}cdot;\u{1}\u{10B}\u{2}cedil\u{1}\u{B8}\u{2}cedil;\u{1}\u{B8}\u{2}cemptyv;\u{1}\u{29B2}\u{2}" +
        "cent\u{1}\u{A2}\u{2}cent;\u{1}\u{A2}\u{2}centerdot;\u{1}\u{B7}\u{2}cfr;\u{1}\u{1D520}\u{2}chcy;\u{1}\u{447}\u{2}check;\u{1}\u{2713}\u{2}checkmark;\u{1}\u{2713}\u{2}chi;\u{1}\u{3C7}\u{2}cir;\u{1}\u{25CB}\u{2}cirE;\u{1}\u{29C3}\u{2}circ;\u{1}\u{2C6}\u{2}circeq;\u{1}\u{2257}\u{2}circlearrowleft;\u{1}\u{21BA}\u{2}circlearrowright;\u{1}\u{21BB}\u{2}circledR;\u{1}\u{AE}\u{2}circledS;\u{1}\u{24C8}\u{2}circledast;\u{1}\u{229B}\u{2}circledcirc;\u{1}\u{229A}\u{2}circleddash;\u{1}\u{229D}\u{2}cire;\u{1}\u{2257}\u{2}cirfnint;\u{1}\u{2A10}\u{2}cirmid;\u{1}\u{2AEF}\u{2}cirscir;\u{1}\u{29C2}\u{2}clubs;\u{1}\u{2663}\u{2}clubsuit;\u{1}\u{2663}\u{2}colon;\u{1}:\u{2}colone;\u{1}\u{2254}\u{2}coloneq;\u{1}\u{2254}\u{2}comma;\u{1},\u{2}commat;\u{1}@\u{2}comp;\u{1}\u{2201}\u{2}compfn;\u{1}\u{2218}\u{2}complement;\u{1}\u{2201}\u{2}complexes;\u{1}\u{2102}\u{2}cong;\u{1}\u{2245}\u{2}congdot;\u{1}\u{2A6D}\u{2}conint;\u{1}\u{222E}\u{2}copf;\u{1}\u{1D554}\u{2}coprod;\u{1}\u{2210}\u{2}copy\u{1}\u{A9}\u{2}" +
        "copy;\u{1}\u{A9}\u{2}copysr;\u{1}\u{2117}\u{2}crarr;\u{1}\u{21B5}\u{2}cross;\u{1}\u{2717}\u{2}cscr;\u{1}\u{1D4B8}\u{2}csub;\u{1}\u{2ACF}\u{2}csube;\u{1}\u{2AD1}\u{2}csup;\u{1}\u{2AD0}\u{2}csupe;\u{1}\u{2AD2}\u{2}ctdot;\u{1}\u{22EF}\u{2}cudarrl;\u{1}\u{2938}\u{2}cudarrr;\u{1}\u{2935}\u{2}cuepr;\u{1}\u{22DE}\u{2}cuesc;\u{1}\u{22DF}\u{2}cularr;\u{1}\u{21B6}\u{2}cularrp;\u{1}\u{293D}\u{2}cup;\u{1}\u{222A}\u{2}cupbrcap;\u{1}\u{2A48}\u{2}cupcap;\u{1}\u{2A46}\u{2}cupcup;\u{1}\u{2A4A}\u{2}cupdot;\u{1}\u{228D}\u{2}cupor;\u{1}\u{2A45}\u{2}cups;\u{1}\u{222A}\u{FE00}\u{2}curarr;\u{1}\u{21B7}\u{2}curarrm;\u{1}\u{293C}\u{2}curlyeqprec;\u{1}\u{22DE}\u{2}curlyeqsucc;\u{1}\u{22DF}\u{2}curlyvee;\u{1}\u{22CE}\u{2}curlywedge;\u{1}\u{22CF}\u{2}curren\u{1}\u{A4}\u{2}curren;\u{1}\u{A4}\u{2}curvearrowleft;\u{1}\u{21B6}\u{2}curvearrowright;\u{1}\u{21B7}\u{2}cuvee;\u{1}\u{22CE}\u{2}cuwed;\u{1}\u{22CF}\u{2}cwconint;\u{1}\u{2232}\u{2}cwint;\u{1}\u{2231}\u{2}cylcty;\u{1}\u{232D}\u{2}dArr;\u{1}\u{21D3}\u{2}dHar;\u{1}\u{2965}\u{2}" +
        "dagger;\u{1}\u{2020}\u{2}daleth;\u{1}\u{2138}\u{2}darr;\u{1}\u{2193}\u{2}dash;\u{1}\u{2010}\u{2}dashv;\u{1}\u{22A3}\u{2}dbkarow;\u{1}\u{290F}\u{2}dblac;\u{1}\u{2DD}\u{2}dcaron;\u{1}\u{10F}\u{2}dcy;\u{1}\u{434}\u{2}dd;\u{1}\u{2146}\u{2}ddagger;\u{1}\u{2021}\u{2}ddarr;\u{1}\u{21CA}\u{2}ddotseq;\u{1}\u{2A77}\u{2}deg\u{1}\u{B0}\u{2}deg;\u{1}\u{B0}\u{2}delta;\u{1}\u{3B4}\u{2}demptyv;\u{1}\u{29B1}\u{2}dfisht;\u{1}\u{297F}\u{2}dfr;\u{1}\u{1D521}\u{2}dharl;\u{1}\u{21C3}\u{2}dharr;\u{1}\u{21C2}\u{2}diam;\u{1}\u{22C4}\u{2}diamond;\u{1}\u{22C4}\u{2}diamondsuit;\u{1}\u{2666}\u{2}diams;\u{1}\u{2666}\u{2}die;\u{1}\u{A8}\u{2}digamma;\u{1}\u{3DD}\u{2}disin;\u{1}\u{22F2}\u{2}div;\u{1}\u{F7}\u{2}divide\u{1}\u{F7}\u{2}divide;\u{1}\u{F7}\u{2}divideontimes;\u{1}\u{22C7}\u{2}divonx;\u{1}\u{22C7}\u{2}djcy;\u{1}\u{452}\u{2}dlcorn;\u{1}\u{231E}\u{2}dlcrop;\u{1}\u{230D}\u{2}dollar;\u{1}$\u{2}dopf;\u{1}\u{1D555}\u{2}dot;\u{1}\u{2D9}\u{2}doteq;\u{1}\u{2250}\u{2}" +
        "doteqdot;\u{1}\u{2251}\u{2}dotminus;\u{1}\u{2238}\u{2}dotplus;\u{1}\u{2214}\u{2}dotsquare;\u{1}\u{22A1}\u{2}doublebarwedge;\u{1}\u{2306}\u{2}downarrow;\u{1}\u{2193}\u{2}downdownarrows;\u{1}\u{21CA}\u{2}downharpoonleft;\u{1}\u{21C3}\u{2}downharpoonright;\u{1}\u{21C2}\u{2}drbkarow;\u{1}\u{2910}\u{2}drcorn;\u{1}\u{231F}\u{2}drcrop;\u{1}\u{230C}\u{2}dscr;\u{1}\u{1D4B9}\u{2}dscy;\u{1}\u{455}\u{2}dsol;\u{1}\u{29F6}\u{2}dstrok;\u{1}\u{111}\u{2}dtdot;\u{1}\u{22F1}\u{2}dtri;\u{1}\u{25BF}\u{2}dtrif;\u{1}\u{25BE}\u{2}duarr;\u{1}\u{21F5}\u{2}duhar;\u{1}\u{296F}\u{2}dwangle;\u{1}\u{29A6}\u{2}dzcy;\u{1}\u{45F}\u{2}dzigrarr;\u{1}\u{27FF}\u{2}eDDot;\u{1}\u{2A77}\u{2}eDot;\u{1}\u{2251}\u{2}eacute\u{1}\u{E9}\u{2}eacute;\u{1}\u{E9}\u{2}easter;\u{1}\u{2A6E}\u{2}ecaron;\u{1}\u{11B}\u{2}ecir;\u{1}\u{2256}\u{2}ecirc\u{1}\u{EA}\u{2}ecirc;\u{1}\u{EA}\u{2}ecolon;\u{1}\u{2255}\u{2}ecy;\u{1}\u{44D}\u{2}edot;\u{1}\u{117}\u{2}ee;\u{1}\u{2147}\u{2}efDot;\u{1}\u{2252}\u{2}efr;\u{1}\u{1D522}\u{2}eg;\u{1}\u{2A9A}\u{2}" +
        "egrave\u{1}\u{E8}\u{2}egrave;\u{1}\u{E8}\u{2}egs;\u{1}\u{2A96}\u{2}egsdot;\u{1}\u{2A98}\u{2}el;\u{1}\u{2A99}\u{2}elinters;\u{1}\u{23E7}\u{2}ell;\u{1}\u{2113}\u{2}els;\u{1}\u{2A95}\u{2}elsdot;\u{1}\u{2A97}\u{2}emacr;\u{1}\u{113}\u{2}empty;\u{1}\u{2205}\u{2}emptyset;\u{1}\u{2205}\u{2}emptyv;\u{1}\u{2205}\u{2}emsp13;\u{1}\u{2004}\u{2}emsp14;\u{1}\u{2005}\u{2}emsp;\u{1}\u{2003}\u{2}eng;\u{1}\u{14B}\u{2}ensp;\u{1}\u{2002}\u{2}eogon;\u{1}\u{119}\u{2}eopf;\u{1}\u{1D556}\u{2}epar;\u{1}\u{22D5}\u{2}eparsl;\u{1}\u{29E3}\u{2}eplus;\u{1}\u{2A71}\u{2}epsi;\u{1}\u{3B5}\u{2}epsilon;\u{1}\u{3B5}\u{2}epsiv;\u{1}\u{3F5}\u{2}eqcirc;\u{1}\u{2256}\u{2}eqcolon;\u{1}\u{2255}\u{2}eqsim;\u{1}\u{2242}\u{2}eqslantgtr;\u{1}\u{2A96}\u{2}eqslantless;\u{1}\u{2A95}\u{2}equals;\u{1}=\u{2}equest;\u{1}\u{225F}\u{2}equiv;\u{1}\u{2261}\u{2}equivDD;\u{1}\u{2A78}\u{2}eqvparsl;\u{1}\u{29E5}\u{2}erDot;\u{1}\u{2253}\u{2}erarr;\u{1}\u{2971}\u{2}escr;\u{1}\u{212F}\u{2}esdot;\u{1}\u{2250}\u{2}" +
        "esim;\u{1}\u{2242}\u{2}eta;\u{1}\u{3B7}\u{2}eth\u{1}\u{F0}\u{2}eth;\u{1}\u{F0}\u{2}euml\u{1}\u{EB}\u{2}euml;\u{1}\u{EB}\u{2}euro;\u{1}\u{20AC}\u{2}excl;\u{1}!\u{2}exist;\u{1}\u{2203}\u{2}expectation;\u{1}\u{2130}\u{2}exponentiale;\u{1}\u{2147}\u{2}fallingdotseq;\u{1}\u{2252}\u{2}fcy;\u{1}\u{444}\u{2}female;\u{1}\u{2640}\u{2}ffilig;\u{1}\u{FB03}\u{2}fflig;\u{1}\u{FB00}\u{2}ffllig;\u{1}\u{FB04}\u{2}ffr;\u{1}\u{1D523}\u{2}filig;\u{1}\u{FB01}\u{2}fjlig;\u{1}fj\u{2}flat;\u{1}\u{266D}\u{2}fllig;\u{1}\u{FB02}\u{2}fltns;\u{1}\u{25B1}\u{2}fnof;\u{1}\u{192}\u{2}fopf;\u{1}\u{1D557}\u{2}forall;\u{1}\u{2200}\u{2}fork;\u{1}\u{22D4}\u{2}forkv;\u{1}\u{2AD9}\u{2}fpartint;\u{1}\u{2A0D}\u{2}frac12\u{1}\u{BD}\u{2}frac12;\u{1}\u{BD}\u{2}frac13;\u{1}\u{2153}\u{2}frac14\u{1}\u{BC}\u{2}frac14;\u{1}\u{BC}\u{2}frac15;\u{1}\u{2155}\u{2}frac16;\u{1}\u{2159}\u{2}frac18;\u{1}\u{215B}\u{2}frac23;\u{1}\u{2154}\u{2}frac25;\u{1}\u{2156}\u{2}frac34\u{1}\u{BE}\u{2}" +
        "frac34;\u{1}\u{BE}\u{2}frac35;\u{1}\u{2157}\u{2}frac38;\u{1}\u{215C}\u{2}frac45;\u{1}\u{2158}\u{2}frac56;\u{1}\u{215A}\u{2}frac58;\u{1}\u{215D}\u{2}frac78;\u{1}\u{215E}\u{2}frasl;\u{1}\u{2044}\u{2}frown;\u{1}\u{2322}\u{2}fscr;\u{1}\u{1D4BB}\u{2}gE;\u{1}\u{2267}\u{2}gEl;\u{1}\u{2A8C}\u{2}gacute;\u{1}\u{1F5}\u{2}gamma;\u{1}\u{3B3}\u{2}gammad;\u{1}\u{3DD}\u{2}gap;\u{1}\u{2A86}\u{2}gbreve;\u{1}\u{11F}\u{2}gcirc;\u{1}\u{11D}\u{2}gcy;\u{1}\u{433}\u{2}gdot;\u{1}\u{121}\u{2}ge;\u{1}\u{2265}\u{2}gel;\u{1}\u{22DB}\u{2}geq;\u{1}\u{2265}\u{2}geqq;\u{1}\u{2267}\u{2}geqslant;\u{1}\u{2A7E}\u{2}ges;\u{1}\u{2A7E}\u{2}gescc;\u{1}\u{2AA9}\u{2}gesdot;\u{1}\u{2A80}\u{2}gesdoto;\u{1}\u{2A82}\u{2}gesdotol;\u{1}\u{2A84}\u{2}gesl;\u{1}\u{22DB}\u{FE00}\u{2}gesles;\u{1}\u{2A94}\u{2}gfr;\u{1}\u{1D524}\u{2}gg;\u{1}\u{226B}\u{2}ggg;\u{1}\u{22D9}\u{2}gimel;\u{1}\u{2137}\u{2}gjcy;\u{1}\u{453}\u{2}gl;\u{1}\u{2277}\u{2}glE;\u{1}\u{2A92}\u{2}gla;\u{1}\u{2AA5}\u{2}" +
        "glj;\u{1}\u{2AA4}\u{2}gnE;\u{1}\u{2269}\u{2}gnap;\u{1}\u{2A8A}\u{2}gnapprox;\u{1}\u{2A8A}\u{2}gne;\u{1}\u{2A88}\u{2}gneq;\u{1}\u{2A88}\u{2}gneqq;\u{1}\u{2269}\u{2}gnsim;\u{1}\u{22E7}\u{2}gopf;\u{1}\u{1D558}\u{2}grave;\u{1}`\u{2}gscr;\u{1}\u{210A}\u{2}gsim;\u{1}\u{2273}\u{2}gsime;\u{1}\u{2A8E}\u{2}gsiml;\u{1}\u{2A90}\u{2}gt\u{1}>\u{2}gt;\u{1}>\u{2}gtcc;\u{1}\u{2AA7}\u{2}gtcir;\u{1}\u{2A7A}\u{2}gtdot;\u{1}\u{22D7}\u{2}gtlPar;\u{1}\u{2995}\u{2}gtquest;\u{1}\u{2A7C}\u{2}gtrapprox;\u{1}\u{2A86}\u{2}gtrarr;\u{1}\u{2978}\u{2}gtrdot;\u{1}\u{22D7}\u{2}gtreqless;\u{1}\u{22DB}\u{2}gtreqqless;\u{1}\u{2A8C}\u{2}gtrless;\u{1}\u{2277}\u{2}gtrsim;\u{1}\u{2273}\u{2}gvertneqq;\u{1}\u{2269}\u{FE00}\u{2}gvnE;\u{1}\u{2269}\u{FE00}\u{2}hArr;\u{1}\u{21D4}\u{2}hairsp;\u{1}\u{200A}\u{2}half;\u{1}\u{BD}\u{2}hamilt;\u{1}\u{210B}\u{2}hardcy;\u{1}\u{44A}\u{2}harr;\u{1}\u{2194}\u{2}harrcir;\u{1}\u{2948}\u{2}harrw;\u{1}\u{21AD}\u{2}hbar;\u{1}\u{210F}\u{2}hcirc;\u{1}\u{125}\u{2}" +
        "hearts;\u{1}\u{2665}\u{2}heartsuit;\u{1}\u{2665}\u{2}hellip;\u{1}\u{2026}\u{2}hercon;\u{1}\u{22B9}\u{2}hfr;\u{1}\u{1D525}\u{2}hksearow;\u{1}\u{2925}\u{2}hkswarow;\u{1}\u{2926}\u{2}hoarr;\u{1}\u{21FF}\u{2}homtht;\u{1}\u{223B}\u{2}hookleftarrow;\u{1}\u{21A9}\u{2}hookrightarrow;\u{1}\u{21AA}\u{2}hopf;\u{1}\u{1D559}\u{2}horbar;\u{1}\u{2015}\u{2}hscr;\u{1}\u{1D4BD}\u{2}hslash;\u{1}\u{210F}\u{2}hstrok;\u{1}\u{127}\u{2}hybull;\u{1}\u{2043}\u{2}hyphen;\u{1}\u{2010}\u{2}iacute\u{1}\u{ED}\u{2}iacute;\u{1}\u{ED}\u{2}ic;\u{1}\u{2063}\u{2}icirc\u{1}\u{EE}\u{2}icirc;\u{1}\u{EE}\u{2}icy;\u{1}\u{438}\u{2}iecy;\u{1}\u{435}\u{2}iexcl\u{1}\u{A1}\u{2}iexcl;\u{1}\u{A1}\u{2}iff;\u{1}\u{21D4}\u{2}ifr;\u{1}\u{1D526}\u{2}igrave\u{1}\u{EC}\u{2}igrave;\u{1}\u{EC}\u{2}ii;\u{1}\u{2148}\u{2}iiiint;\u{1}\u{2A0C}\u{2}iiint;\u{1}\u{222D}\u{2}iinfin;\u{1}\u{29DC}\u{2}iiota;\u{1}\u{2129}\u{2}ijlig;\u{1}\u{133}\u{2}imacr;\u{1}\u{12B}\u{2}image;\u{1}\u{2111}\u{2}imagline;\u{1}\u{2110}\u{2}" +
        "imagpart;\u{1}\u{2111}\u{2}imath;\u{1}\u{131}\u{2}imof;\u{1}\u{22B7}\u{2}imped;\u{1}\u{1B5}\u{2}in;\u{1}\u{2208}\u{2}incare;\u{1}\u{2105}\u{2}infin;\u{1}\u{221E}\u{2}infintie;\u{1}\u{29DD}\u{2}inodot;\u{1}\u{131}\u{2}int;\u{1}\u{222B}\u{2}intcal;\u{1}\u{22BA}\u{2}integers;\u{1}\u{2124}\u{2}intercal;\u{1}\u{22BA}\u{2}intlarhk;\u{1}\u{2A17}\u{2}intprod;\u{1}\u{2A3C}\u{2}iocy;\u{1}\u{451}\u{2}iogon;\u{1}\u{12F}\u{2}iopf;\u{1}\u{1D55A}\u{2}iota;\u{1}\u{3B9}\u{2}iprod;\u{1}\u{2A3C}\u{2}iquest\u{1}\u{BF}\u{2}iquest;\u{1}\u{BF}\u{2}iscr;\u{1}\u{1D4BE}\u{2}isin;\u{1}\u{2208}\u{2}isinE;\u{1}\u{22F9}\u{2}isindot;\u{1}\u{22F5}\u{2}isins;\u{1}\u{22F4}\u{2}isinsv;\u{1}\u{22F3}\u{2}isinv;\u{1}\u{2208}\u{2}it;\u{1}\u{2062}\u{2}itilde;\u{1}\u{129}\u{2}iukcy;\u{1}\u{456}\u{2}iuml\u{1}\u{EF}\u{2}iuml;\u{1}\u{EF}\u{2}jcirc;\u{1}\u{135}\u{2}jcy;\u{1}\u{439}\u{2}jfr;\u{1}\u{1D527}\u{2}jmath;\u{1}\u{237}\u{2}jopf;\u{1}\u{1D55B}\u{2}jscr;\u{1}\u{1D4BF}\u{2}" +
        "jsercy;\u{1}\u{458}\u{2}jukcy;\u{1}\u{454}\u{2}kappa;\u{1}\u{3BA}\u{2}kappav;\u{1}\u{3F0}\u{2}kcedil;\u{1}\u{137}\u{2}kcy;\u{1}\u{43A}\u{2}kfr;\u{1}\u{1D528}\u{2}kgreen;\u{1}\u{138}\u{2}khcy;\u{1}\u{445}\u{2}kjcy;\u{1}\u{45C}\u{2}kopf;\u{1}\u{1D55C}\u{2}kscr;\u{1}\u{1D4C0}\u{2}lAarr;\u{1}\u{21DA}\u{2}lArr;\u{1}\u{21D0}\u{2}lAtail;\u{1}\u{291B}\u{2}lBarr;\u{1}\u{290E}\u{2}lE;\u{1}\u{2266}\u{2}lEg;\u{1}\u{2A8B}\u{2}lHar;\u{1}\u{2962}\u{2}lacute;\u{1}\u{13A}\u{2}laemptyv;\u{1}\u{29B4}\u{2}lagran;\u{1}\u{2112}\u{2}lambda;\u{1}\u{3BB}\u{2}lang;\u{1}\u{27E8}\u{2}langd;\u{1}\u{2991}\u{2}langle;\u{1}\u{27E8}\u{2}lap;\u{1}\u{2A85}\u{2}laquo\u{1}\u{AB}\u{2}laquo;\u{1}\u{AB}\u{2}larr;\u{1}\u{2190}\u{2}larrb;\u{1}\u{21E4}\u{2}larrbfs;\u{1}\u{291F}\u{2}larrfs;\u{1}\u{291D}\u{2}larrhk;\u{1}\u{21A9}\u{2}larrlp;\u{1}\u{21AB}\u{2}larrpl;\u{1}\u{2939}\u{2}larrsim;\u{1}\u{2973}\u{2}larrtl;\u{1}\u{21A2}\u{2}lat;\u{1}\u{2AAB}\u{2}latail;\u{1}\u{2919}\u{2}" +
        "late;\u{1}\u{2AAD}\u{2}lates;\u{1}\u{2AAD}\u{FE00}\u{2}lbarr;\u{1}\u{290C}\u{2}lbbrk;\u{1}\u{2772}\u{2}lbrace;\u{1}{\u{2}lbrack;\u{1}[\u{2}lbrke;\u{1}\u{298B}\u{2}lbrksld;\u{1}\u{298F}\u{2}lbrkslu;\u{1}\u{298D}\u{2}lcaron;\u{1}\u{13E}\u{2}lcedil;\u{1}\u{13C}\u{2}lceil;\u{1}\u{2308}\u{2}lcub;\u{1}{\u{2}lcy;\u{1}\u{43B}\u{2}ldca;\u{1}\u{2936}\u{2}ldquo;\u{1}\u{201C}\u{2}ldquor;\u{1}\u{201E}\u{2}ldrdhar;\u{1}\u{2967}\u{2}ldrushar;\u{1}\u{294B}\u{2}ldsh;\u{1}\u{21B2}\u{2}le;\u{1}\u{2264}\u{2}leftarrow;\u{1}\u{2190}\u{2}leftarrowtail;\u{1}\u{21A2}\u{2}leftharpoondown;\u{1}\u{21BD}\u{2}leftharpoonup;\u{1}\u{21BC}\u{2}leftleftarrows;\u{1}\u{21C7}\u{2}leftrightarrow;\u{1}\u{2194}\u{2}leftrightarrows;\u{1}\u{21C6}\u{2}leftrightharpoons;\u{1}\u{21CB}\u{2}leftrightsquigarrow;\u{1}\u{21AD}\u{2}leftthreetimes;\u{1}\u{22CB}\u{2}leg;\u{1}\u{22DA}\u{2}leq;\u{1}\u{2264}\u{2}leqq;\u{1}\u{2266}\u{2}leqslant;\u{1}\u{2A7D}\u{2}les;\u{1}\u{2A7D}\u{2}lescc;\u{1}\u{2AA8}\u{2}lesdot;\u{1}\u{2A7F}\u{2}lesdoto;\u{1}\u{2A81}\u{2}lesdotor;\u{1}\u{2A83}\u{2}" +
        "lesg;\u{1}\u{22DA}\u{FE00}\u{2}lesges;\u{1}\u{2A93}\u{2}lessapprox;\u{1}\u{2A85}\u{2}lessdot;\u{1}\u{22D6}\u{2}lesseqgtr;\u{1}\u{22DA}\u{2}lesseqqgtr;\u{1}\u{2A8B}\u{2}lessgtr;\u{1}\u{2276}\u{2}lesssim;\u{1}\u{2272}\u{2}lfisht;\u{1}\u{297C}\u{2}lfloor;\u{1}\u{230A}\u{2}lfr;\u{1}\u{1D529}\u{2}lg;\u{1}\u{2276}\u{2}lgE;\u{1}\u{2A91}\u{2}lhard;\u{1}\u{21BD}\u{2}lharu;\u{1}\u{21BC}\u{2}lharul;\u{1}\u{296A}\u{2}lhblk;\u{1}\u{2584}\u{2}ljcy;\u{1}\u{459}\u{2}ll;\u{1}\u{226A}\u{2}llarr;\u{1}\u{21C7}\u{2}llcorner;\u{1}\u{231E}\u{2}llhard;\u{1}\u{296B}\u{2}lltri;\u{1}\u{25FA}\u{2}lmidot;\u{1}\u{140}\u{2}lmoust;\u{1}\u{23B0}\u{2}lmoustache;\u{1}\u{23B0}\u{2}lnE;\u{1}\u{2268}\u{2}lnap;\u{1}\u{2A89}\u{2}lnapprox;\u{1}\u{2A89}\u{2}lne;\u{1}\u{2A87}\u{2}lneq;\u{1}\u{2A87}\u{2}lneqq;\u{1}\u{2268}\u{2}lnsim;\u{1}\u{22E6}\u{2}loang;\u{1}\u{27EC}\u{2}loarr;\u{1}\u{21FD}\u{2}lobrk;\u{1}\u{27E6}\u{2}longleftarrow;\u{1}\u{27F5}\u{2}longleftrightarrow;\u{1}\u{27F7}\u{2}longmapsto;\u{1}\u{27FC}\u{2}longrightarrow;\u{1}\u{27F6}\u{2}" +
        "looparrowleft;\u{1}\u{21AB}\u{2}looparrowright;\u{1}\u{21AC}\u{2}lopar;\u{1}\u{2985}\u{2}lopf;\u{1}\u{1D55D}\u{2}loplus;\u{1}\u{2A2D}\u{2}lotimes;\u{1}\u{2A34}\u{2}lowast;\u{1}\u{2217}\u{2}lowbar;\u{1}_\u{2}loz;\u{1}\u{25CA}\u{2}lozenge;\u{1}\u{25CA}\u{2}lozf;\u{1}\u{29EB}\u{2}lpar;\u{1}(\u{2}lparlt;\u{1}\u{2993}\u{2}lrarr;\u{1}\u{21C6}\u{2}lrcorner;\u{1}\u{231F}\u{2}lrhar;\u{1}\u{21CB}\u{2}lrhard;\u{1}\u{296D}\u{2}lrm;\u{1}\u{200E}\u{2}lrtri;\u{1}\u{22BF}\u{2}lsaquo;\u{1}\u{2039}\u{2}lscr;\u{1}\u{1D4C1}\u{2}lsh;\u{1}\u{21B0}\u{2}lsim;\u{1}\u{2272}\u{2}lsime;\u{1}\u{2A8D}\u{2}lsimg;\u{1}\u{2A8F}\u{2}lsqb;\u{1}[\u{2}lsquo;\u{1}\u{2018}\u{2}lsquor;\u{1}\u{201A}\u{2}lstrok;\u{1}\u{142}\u{2}lt\u{1}<\u{2}lt;\u{1}<\u{2}ltcc;\u{1}\u{2AA6}\u{2}ltcir;\u{1}\u{2A79}\u{2}ltdot;\u{1}\u{22D6}\u{2}lthree;\u{1}\u{22CB}\u{2}ltimes;\u{1}\u{22C9}\u{2}ltlarr;\u{1}\u{2976}\u{2}ltquest;\u{1}\u{2A7B}\u{2}ltrPar;\u{1}\u{2996}\u{2}ltri;\u{1}\u{25C3}\u{2}" +
        "ltrie;\u{1}\u{22B4}\u{2}ltrif;\u{1}\u{25C2}\u{2}lurdshar;\u{1}\u{294A}\u{2}luruhar;\u{1}\u{2966}\u{2}lvertneqq;\u{1}\u{2268}\u{FE00}\u{2}lvnE;\u{1}\u{2268}\u{FE00}\u{2}mDDot;\u{1}\u{223A}\u{2}macr\u{1}\u{AF}\u{2}macr;\u{1}\u{AF}\u{2}male;\u{1}\u{2642}\u{2}malt;\u{1}\u{2720}\u{2}maltese;\u{1}\u{2720}\u{2}map;\u{1}\u{21A6}\u{2}mapsto;\u{1}\u{21A6}\u{2}mapstodown;\u{1}\u{21A7}\u{2}mapstoleft;\u{1}\u{21A4}\u{2}mapstoup;\u{1}\u{21A5}\u{2}marker;\u{1}\u{25AE}\u{2}mcomma;\u{1}\u{2A29}\u{2}mcy;\u{1}\u{43C}\u{2}mdash;\u{1}\u{2014}\u{2}measuredangle;\u{1}\u{2221}\u{2}mfr;\u{1}\u{1D52A}\u{2}mho;\u{1}\u{2127}\u{2}micro\u{1}\u{B5}\u{2}micro;\u{1}\u{B5}\u{2}mid;\u{1}\u{2223}\u{2}midast;\u{1}*\u{2}midcir;\u{1}\u{2AF0}\u{2}middot\u{1}\u{B7}\u{2}middot;\u{1}\u{B7}\u{2}minus;\u{1}\u{2212}\u{2}minusb;\u{1}\u{229F}\u{2}minusd;\u{1}\u{2238}\u{2}minusdu;\u{1}\u{2A2A}\u{2}mlcp;\u{1}\u{2ADB}\u{2}mldr;\u{1}\u{2026}\u{2}mnplus;\u{1}\u{2213}\u{2}models;\u{1}\u{22A7}\u{2}mopf;\u{1}\u{1D55E}\u{2}" +
        "mp;\u{1}\u{2213}\u{2}mscr;\u{1}\u{1D4C2}\u{2}mstpos;\u{1}\u{223E}\u{2}mu;\u{1}\u{3BC}\u{2}multimap;\u{1}\u{22B8}\u{2}mumap;\u{1}\u{22B8}\u{2}nGg;\u{1}\u{22D9}\u{338}\u{2}nGt;\u{1}\u{226B}\u{20D2}\u{2}nGtv;\u{1}\u{226B}\u{338}\u{2}nLeftarrow;\u{1}\u{21CD}\u{2}nLeftrightarrow;\u{1}\u{21CE}\u{2}nLl;\u{1}\u{22D8}\u{338}\u{2}nLt;\u{1}\u{226A}\u{20D2}\u{2}nLtv;\u{1}\u{226A}\u{338}\u{2}nRightarrow;\u{1}\u{21CF}\u{2}nVDash;\u{1}\u{22AF}\u{2}nVdash;\u{1}\u{22AE}\u{2}nabla;\u{1}\u{2207}\u{2}nacute;\u{1}\u{144}\u{2}nang;\u{1}\u{2220}\u{20D2}\u{2}nap;\u{1}\u{2249}\u{2}napE;\u{1}\u{2A70}\u{338}\u{2}napid;\u{1}\u{224B}\u{338}\u{2}napos;\u{1}\u{149}\u{2}napprox;\u{1}\u{2249}\u{2}natur;\u{1}\u{266E}\u{2}natural;\u{1}\u{266E}\u{2}naturals;\u{1}\u{2115}\u{2}nbsp\u{1}\u{A0}\u{2}nbsp;\u{1}\u{A0}\u{2}nbump;\u{1}\u{224E}\u{338}\u{2}nbumpe;\u{1}\u{224F}\u{338}\u{2}ncap;\u{1}\u{2A43}\u{2}ncaron;\u{1}\u{148}\u{2}ncedil;\u{1}\u{146}\u{2}ncong;\u{1}\u{2247}\u{2}ncongdot;\u{1}\u{2A6D}\u{338}\u{2}ncup;\u{1}\u{2A42}\u{2}ncy;\u{1}\u{43D}\u{2}ndash;\u{1}\u{2013}\u{2}" +
        "ne;\u{1}\u{2260}\u{2}neArr;\u{1}\u{21D7}\u{2}nearhk;\u{1}\u{2924}\u{2}nearr;\u{1}\u{2197}\u{2}nearrow;\u{1}\u{2197}\u{2}nedot;\u{1}\u{2250}\u{338}\u{2}nequiv;\u{1}\u{2262}\u{2}nesear;\u{1}\u{2928}\u{2}nesim;\u{1}\u{2242}\u{338}\u{2}nexist;\u{1}\u{2204}\u{2}nexists;\u{1}\u{2204}\u{2}nfr;\u{1}\u{1D52B}\u{2}ngE;\u{1}\u{2267}\u{338}\u{2}nge;\u{1}\u{2271}\u{2}ngeq;\u{1}\u{2271}\u{2}ngeqq;\u{1}\u{2267}\u{338}\u{2}ngeqslant;\u{1}\u{2A7E}\u{338}\u{2}nges;\u{1}\u{2A7E}\u{338}\u{2}ngsim;\u{1}\u{2275}\u{2}ngt;\u{1}\u{226F}\u{2}ngtr;\u{1}\u{226F}\u{2}nhArr;\u{1}\u{21CE}\u{2}nharr;\u{1}\u{21AE}\u{2}nhpar;\u{1}\u{2AF2}\u{2}ni;\u{1}\u{220B}\u{2}nis;\u{1}\u{22FC}\u{2}nisd;\u{1}\u{22FA}\u{2}niv;\u{1}\u{220B}\u{2}njcy;\u{1}\u{45A}\u{2}nlArr;\u{1}\u{21CD}\u{2}nlE;\u{1}\u{2266}\u{338}\u{2}nlarr;\u{1}\u{219A}\u{2}nldr;\u{1}\u{2025}\u{2}nle;\u{1}\u{2270}\u{2}nleftarrow;\u{1}\u{219A}\u{2}nleftrightarrow;\u{1}\u{21AE}\u{2}nleq;\u{1}\u{2270}\u{2}nleqq;\u{1}\u{2266}\u{338}\u{2}nleqslant;\u{1}\u{2A7D}\u{338}\u{2}nles;\u{1}\u{2A7D}\u{338}\u{2}" +
        "nless;\u{1}\u{226E}\u{2}nlsim;\u{1}\u{2274}\u{2}nlt;\u{1}\u{226E}\u{2}nltri;\u{1}\u{22EA}\u{2}nltrie;\u{1}\u{22EC}\u{2}nmid;\u{1}\u{2224}\u{2}nopf;\u{1}\u{1D55F}\u{2}not\u{1}\u{AC}\u{2}not;\u{1}\u{AC}\u{2}notin;\u{1}\u{2209}\u{2}notinE;\u{1}\u{22F9}\u{338}\u{2}notindot;\u{1}\u{22F5}\u{338}\u{2}notinva;\u{1}\u{2209}\u{2}notinvb;\u{1}\u{22F7}\u{2}notinvc;\u{1}\u{22F6}\u{2}notni;\u{1}\u{220C}\u{2}notniva;\u{1}\u{220C}\u{2}notnivb;\u{1}\u{22FE}\u{2}notnivc;\u{1}\u{22FD}\u{2}npar;\u{1}\u{2226}\u{2}nparallel;\u{1}\u{2226}\u{2}nparsl;\u{1}\u{2AFD}\u{20E5}\u{2}npart;\u{1}\u{2202}\u{338}\u{2}npolint;\u{1}\u{2A14}\u{2}npr;\u{1}\u{2280}\u{2}nprcue;\u{1}\u{22E0}\u{2}npre;\u{1}\u{2AAF}\u{338}\u{2}nprec;\u{1}\u{2280}\u{2}npreceq;\u{1}\u{2AAF}\u{338}\u{2}nrArr;\u{1}\u{21CF}\u{2}nrarr;\u{1}\u{219B}\u{2}nrarrc;\u{1}\u{2933}\u{338}\u{2}nrarrw;\u{1}\u{219D}\u{338}\u{2}nrightarrow;\u{1}\u{219B}\u{2}nrtri;\u{1}\u{22EB}\u{2}nrtrie;\u{1}\u{22ED}\u{2}nsc;\u{1}\u{2281}\u{2}nsccue;\u{1}\u{22E1}\u{2}nsce;\u{1}\u{2AB0}\u{338}\u{2}nscr;\u{1}\u{1D4C3}\u{2}" +
        "nshortmid;\u{1}\u{2224}\u{2}nshortparallel;\u{1}\u{2226}\u{2}nsim;\u{1}\u{2241}\u{2}nsime;\u{1}\u{2244}\u{2}nsimeq;\u{1}\u{2244}\u{2}nsmid;\u{1}\u{2224}\u{2}nspar;\u{1}\u{2226}\u{2}nsqsube;\u{1}\u{22E2}\u{2}nsqsupe;\u{1}\u{22E3}\u{2}nsub;\u{1}\u{2284}\u{2}nsubE;\u{1}\u{2AC5}\u{338}\u{2}nsube;\u{1}\u{2288}\u{2}nsubset;\u{1}\u{2282}\u{20D2}\u{2}nsubseteq;\u{1}\u{2288}\u{2}nsubseteqq;\u{1}\u{2AC5}\u{338}\u{2}nsucc;\u{1}\u{2281}\u{2}nsucceq;\u{1}\u{2AB0}\u{338}\u{2}nsup;\u{1}\u{2285}\u{2}nsupE;\u{1}\u{2AC6}\u{338}\u{2}nsupe;\u{1}\u{2289}\u{2}nsupset;\u{1}\u{2283}\u{20D2}\u{2}nsupseteq;\u{1}\u{2289}\u{2}nsupseteqq;\u{1}\u{2AC6}\u{338}\u{2}ntgl;\u{1}\u{2279}\u{2}ntilde\u{1}\u{F1}\u{2}ntilde;\u{1}\u{F1}\u{2}ntlg;\u{1}\u{2278}\u{2}ntriangleleft;\u{1}\u{22EA}\u{2}ntrianglelefteq;\u{1}\u{22EC}\u{2}ntriangleright;\u{1}\u{22EB}\u{2}ntrianglerighteq;\u{1}\u{22ED}\u{2}nu;\u{1}\u{3BD}\u{2}num;\u{1}#\u{2}numero;\u{1}\u{2116}\u{2}numsp;\u{1}\u{2007}\u{2}nvDash;\u{1}\u{22AD}\u{2}nvHarr;\u{1}\u{2904}\u{2}nvap;\u{1}\u{224D}\u{20D2}\u{2}nvdash;\u{1}\u{22AC}\u{2}nvge;\u{1}\u{2265}\u{20D2}\u{2}" +
        "nvgt;\u{1}>\u{20D2}\u{2}nvinfin;\u{1}\u{29DE}\u{2}nvlArr;\u{1}\u{2902}\u{2}nvle;\u{1}\u{2264}\u{20D2}\u{2}nvlt;\u{1}<\u{20D2}\u{2}nvltrie;\u{1}\u{22B4}\u{20D2}\u{2}nvrArr;\u{1}\u{2903}\u{2}nvrtrie;\u{1}\u{22B5}\u{20D2}\u{2}nvsim;\u{1}\u{223C}\u{20D2}\u{2}nwArr;\u{1}\u{21D6}\u{2}nwarhk;\u{1}\u{2923}\u{2}nwarr;\u{1}\u{2196}\u{2}nwarrow;\u{1}\u{2196}\u{2}nwnear;\u{1}\u{2927}\u{2}oS;\u{1}\u{24C8}\u{2}oacute\u{1}\u{F3}\u{2}oacute;\u{1}\u{F3}\u{2}oast;\u{1}\u{229B}\u{2}ocir;\u{1}\u{229A}\u{2}ocirc\u{1}\u{F4}\u{2}ocirc;\u{1}\u{F4}\u{2}ocy;\u{1}\u{43E}\u{2}odash;\u{1}\u{229D}\u{2}odblac;\u{1}\u{151}\u{2}odiv;\u{1}\u{2A38}\u{2}odot;\u{1}\u{2299}\u{2}odsold;\u{1}\u{29BC}\u{2}oelig;\u{1}\u{153}\u{2}ofcir;\u{1}\u{29BF}\u{2}ofr;\u{1}\u{1D52C}\u{2}ogon;\u{1}\u{2DB}\u{2}ograve\u{1}\u{F2}\u{2}ograve;\u{1}\u{F2}\u{2}ogt;\u{1}\u{29C1}\u{2}ohbar;\u{1}\u{29B5}\u{2}ohm;\u{1}\u{3A9}\u{2}oint;\u{1}\u{222E}\u{2}olarr;\u{1}\u{21BA}\u{2}olcir;\u{1}\u{29BE}\u{2}olcross;\u{1}\u{29BB}\u{2}" +
        "oline;\u{1}\u{203E}\u{2}olt;\u{1}\u{29C0}\u{2}omacr;\u{1}\u{14D}\u{2}omega;\u{1}\u{3C9}\u{2}omicron;\u{1}\u{3BF}\u{2}omid;\u{1}\u{29B6}\u{2}ominus;\u{1}\u{2296}\u{2}oopf;\u{1}\u{1D560}\u{2}opar;\u{1}\u{29B7}\u{2}operp;\u{1}\u{29B9}\u{2}oplus;\u{1}\u{2295}\u{2}or;\u{1}\u{2228}\u{2}orarr;\u{1}\u{21BB}\u{2}ord;\u{1}\u{2A5D}\u{2}order;\u{1}\u{2134}\u{2}orderof;\u{1}\u{2134}\u{2}ordf\u{1}\u{AA}\u{2}ordf;\u{1}\u{AA}\u{2}ordm\u{1}\u{BA}\u{2}ordm;\u{1}\u{BA}\u{2}origof;\u{1}\u{22B6}\u{2}oror;\u{1}\u{2A56}\u{2}orslope;\u{1}\u{2A57}\u{2}orv;\u{1}\u{2A5B}\u{2}oscr;\u{1}\u{2134}\u{2}oslash\u{1}\u{F8}\u{2}oslash;\u{1}\u{F8}\u{2}osol;\u{1}\u{2298}\u{2}otilde\u{1}\u{F5}\u{2}otilde;\u{1}\u{F5}\u{2}otimes;\u{1}\u{2297}\u{2}otimesas;\u{1}\u{2A36}\u{2}ouml\u{1}\u{F6}\u{2}ouml;\u{1}\u{F6}\u{2}ovbar;\u{1}\u{233D}\u{2}par;\u{1}\u{2225}\u{2}para\u{1}\u{B6}\u{2}para;\u{1}\u{B6}\u{2}parallel;\u{1}\u{2225}\u{2}parsim;\u{1}\u{2AF3}\u{2}" +
        "parsl;\u{1}\u{2AFD}\u{2}part;\u{1}\u{2202}\u{2}pcy;\u{1}\u{43F}\u{2}percnt;\u{1}%\u{2}period;\u{1}.\u{2}permil;\u{1}\u{2030}\u{2}perp;\u{1}\u{22A5}\u{2}pertenk;\u{1}\u{2031}\u{2}pfr;\u{1}\u{1D52D}\u{2}phi;\u{1}\u{3C6}\u{2}phiv;\u{1}\u{3D5}\u{2}phmmat;\u{1}\u{2133}\u{2}phone;\u{1}\u{260E}\u{2}pi;\u{1}\u{3C0}\u{2}pitchfork;\u{1}\u{22D4}\u{2}piv;\u{1}\u{3D6}\u{2}planck;\u{1}\u{210F}\u{2}planckh;\u{1}\u{210E}\u{2}plankv;\u{1}\u{210F}\u{2}plus;\u{1}+\u{2}plusacir;\u{1}\u{2A23}\u{2}plusb;\u{1}\u{229E}\u{2}pluscir;\u{1}\u{2A22}\u{2}plusdo;\u{1}\u{2214}\u{2}plusdu;\u{1}\u{2A25}\u{2}pluse;\u{1}\u{2A72}\u{2}plusmn\u{1}\u{B1}\u{2}plusmn;\u{1}\u{B1}\u{2}plussim;\u{1}\u{2A26}\u{2}plustwo;\u{1}\u{2A27}\u{2}pm;\u{1}\u{B1}\u{2}pointint;\u{1}\u{2A15}\u{2}popf;\u{1}\u{1D561}\u{2}pound\u{1}\u{A3}\u{2}pound;\u{1}\u{A3}\u{2}pr;\u{1}\u{227A}\u{2}prE;\u{1}\u{2AB3}\u{2}prap;\u{1}\u{2AB7}\u{2}prcue;\u{1}\u{227C}\u{2}pre;\u{1}\u{2AAF}\u{2}" +
        "prec;\u{1}\u{227A}\u{2}precapprox;\u{1}\u{2AB7}\u{2}preccurlyeq;\u{1}\u{227C}\u{2}preceq;\u{1}\u{2AAF}\u{2}precnapprox;\u{1}\u{2AB9}\u{2}precneqq;\u{1}\u{2AB5}\u{2}precnsim;\u{1}\u{22E8}\u{2}precsim;\u{1}\u{227E}\u{2}prime;\u{1}\u{2032}\u{2}primes;\u{1}\u{2119}\u{2}prnE;\u{1}\u{2AB5}\u{2}prnap;\u{1}\u{2AB9}\u{2}prnsim;\u{1}\u{22E8}\u{2}prod;\u{1}\u{220F}\u{2}profalar;\u{1}\u{232E}\u{2}profline;\u{1}\u{2312}\u{2}profsurf;\u{1}\u{2313}\u{2}prop;\u{1}\u{221D}\u{2}propto;\u{1}\u{221D}\u{2}prsim;\u{1}\u{227E}\u{2}prurel;\u{1}\u{22B0}\u{2}pscr;\u{1}\u{1D4C5}\u{2}psi;\u{1}\u{3C8}\u{2}puncsp;\u{1}\u{2008}\u{2}qfr;\u{1}\u{1D52E}\u{2}qint;\u{1}\u{2A0C}\u{2}qopf;\u{1}\u{1D562}\u{2}qprime;\u{1}\u{2057}\u{2}qscr;\u{1}\u{1D4C6}\u{2}quaternions;\u{1}\u{210D}\u{2}quatint;\u{1}\u{2A16}\u{2}quest;\u{1}?\u{2}questeq;\u{1}\u{225F}\u{2}quot\u{1}\u{22}\u{2}quot;\u{1}\u{22}\u{2}rAarr;\u{1}\u{21DB}\u{2}rArr;\u{1}\u{21D2}\u{2}rAtail;\u{1}\u{291C}\u{2}rBarr;\u{1}\u{290F}\u{2}rHar;\u{1}\u{2964}\u{2}" +
        "race;\u{1}\u{223D}\u{331}\u{2}racute;\u{1}\u{155}\u{2}radic;\u{1}\u{221A}\u{2}raemptyv;\u{1}\u{29B3}\u{2}rang;\u{1}\u{27E9}\u{2}rangd;\u{1}\u{2992}\u{2}range;\u{1}\u{29A5}\u{2}rangle;\u{1}\u{27E9}\u{2}raquo\u{1}\u{BB}\u{2}raquo;\u{1}\u{BB}\u{2}rarr;\u{1}\u{2192}\u{2}rarrap;\u{1}\u{2975}\u{2}rarrb;\u{1}\u{21E5}\u{2}rarrbfs;\u{1}\u{2920}\u{2}rarrc;\u{1}\u{2933}\u{2}rarrfs;\u{1}\u{291E}\u{2}rarrhk;\u{1}\u{21AA}\u{2}rarrlp;\u{1}\u{21AC}\u{2}rarrpl;\u{1}\u{2945}\u{2}rarrsim;\u{1}\u{2974}\u{2}rarrtl;\u{1}\u{21A3}\u{2}rarrw;\u{1}\u{219D}\u{2}ratail;\u{1}\u{291A}\u{2}ratio;\u{1}\u{2236}\u{2}rationals;\u{1}\u{211A}\u{2}rbarr;\u{1}\u{290D}\u{2}rbbrk;\u{1}\u{2773}\u{2}rbrace;\u{1}}\u{2}rbrack;\u{1}]\u{2}rbrke;\u{1}\u{298C}\u{2}rbrksld;\u{1}\u{298E}\u{2}rbrkslu;\u{1}\u{2990}\u{2}rcaron;\u{1}\u{159}\u{2}rcedil;\u{1}\u{157}\u{2}rceil;\u{1}\u{2309}\u{2}rcub;\u{1}}\u{2}rcy;\u{1}\u{440}\u{2}rdca;\u{1}\u{2937}\u{2}rdldhar;\u{1}\u{2969}\u{2}rdquo;\u{1}\u{201D}\u{2}" +
        "rdquor;\u{1}\u{201D}\u{2}rdsh;\u{1}\u{21B3}\u{2}real;\u{1}\u{211C}\u{2}realine;\u{1}\u{211B}\u{2}realpart;\u{1}\u{211C}\u{2}reals;\u{1}\u{211D}\u{2}rect;\u{1}\u{25AD}\u{2}reg\u{1}\u{AE}\u{2}reg;\u{1}\u{AE}\u{2}rfisht;\u{1}\u{297D}\u{2}rfloor;\u{1}\u{230B}\u{2}rfr;\u{1}\u{1D52F}\u{2}rhard;\u{1}\u{21C1}\u{2}rharu;\u{1}\u{21C0}\u{2}rharul;\u{1}\u{296C}\u{2}rho;\u{1}\u{3C1}\u{2}rhov;\u{1}\u{3F1}\u{2}rightarrow;\u{1}\u{2192}\u{2}rightarrowtail;\u{1}\u{21A3}\u{2}rightharpoondown;\u{1}\u{21C1}\u{2}rightharpoonup;\u{1}\u{21C0}\u{2}rightleftarrows;\u{1}\u{21C4}\u{2}rightleftharpoons;\u{1}\u{21CC}\u{2}rightrightarrows;\u{1}\u{21C9}\u{2}rightsquigarrow;\u{1}\u{219D}\u{2}rightthreetimes;\u{1}\u{22CC}\u{2}ring;\u{1}\u{2DA}\u{2}risingdotseq;\u{1}\u{2253}\u{2}rlarr;\u{1}\u{21C4}\u{2}rlhar;\u{1}\u{21CC}\u{2}rlm;\u{1}\u{200F}\u{2}rmoust;\u{1}\u{23B1}\u{2}rmoustache;\u{1}\u{23B1}\u{2}rnmid;\u{1}\u{2AEE}\u{2}roang;\u{1}\u{27ED}\u{2}roarr;\u{1}\u{21FE}\u{2}robrk;\u{1}\u{27E7}\u{2}ropar;\u{1}\u{2986}\u{2}ropf;\u{1}\u{1D563}\u{2}roplus;\u{1}\u{2A2E}\u{2}" +
        "rotimes;\u{1}\u{2A35}\u{2}rpar;\u{1})\u{2}rpargt;\u{1}\u{2994}\u{2}rppolint;\u{1}\u{2A12}\u{2}rrarr;\u{1}\u{21C9}\u{2}rsaquo;\u{1}\u{203A}\u{2}rscr;\u{1}\u{1D4C7}\u{2}rsh;\u{1}\u{21B1}\u{2}rsqb;\u{1}]\u{2}rsquo;\u{1}\u{2019}\u{2}rsquor;\u{1}\u{2019}\u{2}rthree;\u{1}\u{22CC}\u{2}rtimes;\u{1}\u{22CA}\u{2}rtri;\u{1}\u{25B9}\u{2}rtrie;\u{1}\u{22B5}\u{2}rtrif;\u{1}\u{25B8}\u{2}rtriltri;\u{1}\u{29CE}\u{2}ruluhar;\u{1}\u{2968}\u{2}rx;\u{1}\u{211E}\u{2}sacute;\u{1}\u{15B}\u{2}sbquo;\u{1}\u{201A}\u{2}sc;\u{1}\u{227B}\u{2}scE;\u{1}\u{2AB4}\u{2}scap;\u{1}\u{2AB8}\u{2}scaron;\u{1}\u{161}\u{2}sccue;\u{1}\u{227D}\u{2}sce;\u{1}\u{2AB0}\u{2}scedil;\u{1}\u{15F}\u{2}scirc;\u{1}\u{15D}\u{2}scnE;\u{1}\u{2AB6}\u{2}scnap;\u{1}\u{2ABA}\u{2}scnsim;\u{1}\u{22E9}\u{2}scpolint;\u{1}\u{2A13}\u{2}scsim;\u{1}\u{227F}\u{2}scy;\u{1}\u{441}\u{2}sdot;\u{1}\u{22C5}\u{2}sdotb;\u{1}\u{22A1}\u{2}sdote;\u{1}\u{2A66}\u{2}seArr;\u{1}\u{21D8}\u{2}searhk;\u{1}\u{2925}\u{2}" +
        "searr;\u{1}\u{2198}\u{2}searrow;\u{1}\u{2198}\u{2}sect\u{1}\u{A7}\u{2}sect;\u{1}\u{A7}\u{2}semi;\u{1};\u{2}seswar;\u{1}\u{2929}\u{2}setminus;\u{1}\u{2216}\u{2}setmn;\u{1}\u{2216}\u{2}sext;\u{1}\u{2736}\u{2}sfr;\u{1}\u{1D530}\u{2}sfrown;\u{1}\u{2322}\u{2}sharp;\u{1}\u{266F}\u{2}shchcy;\u{1}\u{449}\u{2}shcy;\u{1}\u{448}\u{2}shortmid;\u{1}\u{2223}\u{2}shortparallel;\u{1}\u{2225}\u{2}shy\u{1}\u{AD}\u{2}shy;\u{1}\u{AD}\u{2}sigma;\u{1}\u{3C3}\u{2}sigmaf;\u{1}\u{3C2}\u{2}sigmav;\u{1}\u{3C2}\u{2}sim;\u{1}\u{223C}\u{2}simdot;\u{1}\u{2A6A}\u{2}sime;\u{1}\u{2243}\u{2}simeq;\u{1}\u{2243}\u{2}simg;\u{1}\u{2A9E}\u{2}simgE;\u{1}\u{2AA0}\u{2}siml;\u{1}\u{2A9D}\u{2}simlE;\u{1}\u{2A9F}\u{2}simne;\u{1}\u{2246}\u{2}simplus;\u{1}\u{2A24}\u{2}simrarr;\u{1}\u{2972}\u{2}slarr;\u{1}\u{2190}\u{2}smallsetminus;\u{1}\u{2216}\u{2}smashp;\u{1}\u{2A33}\u{2}smeparsl;\u{1}\u{29E4}\u{2}smid;\u{1}\u{2223}\u{2}smile;\u{1}\u{2323}\u{2}smt;\u{1}\u{2AAA}\u{2}smte;\u{1}\u{2AAC}\u{2}" +
        "smtes;\u{1}\u{2AAC}\u{FE00}\u{2}softcy;\u{1}\u{44C}\u{2}sol;\u{1}/\u{2}solb;\u{1}\u{29C4}\u{2}solbar;\u{1}\u{233F}\u{2}sopf;\u{1}\u{1D564}\u{2}spades;\u{1}\u{2660}\u{2}spadesuit;\u{1}\u{2660}\u{2}spar;\u{1}\u{2225}\u{2}sqcap;\u{1}\u{2293}\u{2}sqcaps;\u{1}\u{2293}\u{FE00}\u{2}sqcup;\u{1}\u{2294}\u{2}sqcups;\u{1}\u{2294}\u{FE00}\u{2}sqsub;\u{1}\u{228F}\u{2}sqsube;\u{1}\u{2291}\u{2}sqsubset;\u{1}\u{228F}\u{2}sqsubseteq;\u{1}\u{2291}\u{2}sqsup;\u{1}\u{2290}\u{2}sqsupe;\u{1}\u{2292}\u{2}sqsupset;\u{1}\u{2290}\u{2}sqsupseteq;\u{1}\u{2292}\u{2}squ;\u{1}\u{25A1}\u{2}square;\u{1}\u{25A1}\u{2}squarf;\u{1}\u{25AA}\u{2}squf;\u{1}\u{25AA}\u{2}srarr;\u{1}\u{2192}\u{2}sscr;\u{1}\u{1D4C8}\u{2}ssetmn;\u{1}\u{2216}\u{2}ssmile;\u{1}\u{2323}\u{2}sstarf;\u{1}\u{22C6}\u{2}star;\u{1}\u{2606}\u{2}starf;\u{1}\u{2605}\u{2}straightepsilon;\u{1}\u{3F5}\u{2}straightphi;\u{1}\u{3D5}\u{2}strns;\u{1}\u{AF}\u{2}sub;\u{1}\u{2282}\u{2}subE;\u{1}\u{2AC5}\u{2}subdot;\u{1}\u{2ABD}\u{2}sube;\u{1}\u{2286}\u{2}subedot;\u{1}\u{2AC3}\u{2}" +
        "submult;\u{1}\u{2AC1}\u{2}subnE;\u{1}\u{2ACB}\u{2}subne;\u{1}\u{228A}\u{2}subplus;\u{1}\u{2ABF}\u{2}subrarr;\u{1}\u{2979}\u{2}subset;\u{1}\u{2282}\u{2}subseteq;\u{1}\u{2286}\u{2}subseteqq;\u{1}\u{2AC5}\u{2}subsetneq;\u{1}\u{228A}\u{2}subsetneqq;\u{1}\u{2ACB}\u{2}subsim;\u{1}\u{2AC7}\u{2}subsub;\u{1}\u{2AD5}\u{2}subsup;\u{1}\u{2AD3}\u{2}succ;\u{1}\u{227B}\u{2}succapprox;\u{1}\u{2AB8}\u{2}succcurlyeq;\u{1}\u{227D}\u{2}succeq;\u{1}\u{2AB0}\u{2}succnapprox;\u{1}\u{2ABA}\u{2}succneqq;\u{1}\u{2AB6}\u{2}succnsim;\u{1}\u{22E9}\u{2}succsim;\u{1}\u{227F}\u{2}sum;\u{1}\u{2211}\u{2}sung;\u{1}\u{266A}\u{2}sup1\u{1}\u{B9}\u{2}sup1;\u{1}\u{B9}\u{2}sup2\u{1}\u{B2}\u{2}sup2;\u{1}\u{B2}\u{2}sup3\u{1}\u{B3}\u{2}sup3;\u{1}\u{B3}\u{2}sup;\u{1}\u{2283}\u{2}supE;\u{1}\u{2AC6}\u{2}supdot;\u{1}\u{2ABE}\u{2}supdsub;\u{1}\u{2AD8}\u{2}supe;\u{1}\u{2287}\u{2}supedot;\u{1}\u{2AC4}\u{2}suphsol;\u{1}\u{27C9}\u{2}suphsub;\u{1}\u{2AD7}\u{2}suplarr;\u{1}\u{297B}\u{2}supmult;\u{1}\u{2AC2}\u{2}supnE;\u{1}\u{2ACC}\u{2}" +
        "supne;\u{1}\u{228B}\u{2}supplus;\u{1}\u{2AC0}\u{2}supset;\u{1}\u{2283}\u{2}supseteq;\u{1}\u{2287}\u{2}supseteqq;\u{1}\u{2AC6}\u{2}supsetneq;\u{1}\u{228B}\u{2}supsetneqq;\u{1}\u{2ACC}\u{2}supsim;\u{1}\u{2AC8}\u{2}supsub;\u{1}\u{2AD4}\u{2}supsup;\u{1}\u{2AD6}\u{2}swArr;\u{1}\u{21D9}\u{2}swarhk;\u{1}\u{2926}\u{2}swarr;\u{1}\u{2199}\u{2}swarrow;\u{1}\u{2199}\u{2}swnwar;\u{1}\u{292A}\u{2}szlig\u{1}\u{DF}\u{2}szlig;\u{1}\u{DF}\u{2}target;\u{1}\u{2316}\u{2}tau;\u{1}\u{3C4}\u{2}tbrk;\u{1}\u{23B4}\u{2}tcaron;\u{1}\u{165}\u{2}tcedil;\u{1}\u{163}\u{2}tcy;\u{1}\u{442}\u{2}tdot;\u{1}\u{20DB}\u{2}telrec;\u{1}\u{2315}\u{2}tfr;\u{1}\u{1D531}\u{2}there4;\u{1}\u{2234}\u{2}therefore;\u{1}\u{2234}\u{2}theta;\u{1}\u{3B8}\u{2}thetasym;\u{1}\u{3D1}\u{2}thetav;\u{1}\u{3D1}\u{2}thickapprox;\u{1}\u{2248}\u{2}thicksim;\u{1}\u{223C}\u{2}thinsp;\u{1}\u{2009}\u{2}thkap;\u{1}\u{2248}\u{2}thksim;\u{1}\u{223C}\u{2}thorn\u{1}\u{FE}\u{2}thorn;\u{1}\u{FE}\u{2}tilde;\u{1}\u{2DC}\u{2}times\u{1}\u{D7}\u{2}" +
        "times;\u{1}\u{D7}\u{2}timesb;\u{1}\u{22A0}\u{2}timesbar;\u{1}\u{2A31}\u{2}timesd;\u{1}\u{2A30}\u{2}tint;\u{1}\u{222D}\u{2}toea;\u{1}\u{2928}\u{2}top;\u{1}\u{22A4}\u{2}topbot;\u{1}\u{2336}\u{2}topcir;\u{1}\u{2AF1}\u{2}topf;\u{1}\u{1D565}\u{2}topfork;\u{1}\u{2ADA}\u{2}tosa;\u{1}\u{2929}\u{2}tprime;\u{1}\u{2034}\u{2}trade;\u{1}\u{2122}\u{2}triangle;\u{1}\u{25B5}\u{2}triangledown;\u{1}\u{25BF}\u{2}triangleleft;\u{1}\u{25C3}\u{2}trianglelefteq;\u{1}\u{22B4}\u{2}triangleq;\u{1}\u{225C}\u{2}triangleright;\u{1}\u{25B9}\u{2}trianglerighteq;\u{1}\u{22B5}\u{2}tridot;\u{1}\u{25EC}\u{2}trie;\u{1}\u{225C}\u{2}triminus;\u{1}\u{2A3A}\u{2}triplus;\u{1}\u{2A39}\u{2}trisb;\u{1}\u{29CD}\u{2}tritime;\u{1}\u{2A3B}\u{2}trpezium;\u{1}\u{23E2}\u{2}tscr;\u{1}\u{1D4C9}\u{2}tscy;\u{1}\u{446}\u{2}tshcy;\u{1}\u{45B}\u{2}tstrok;\u{1}\u{167}\u{2}twixt;\u{1}\u{226C}\u{2}twoheadleftarrow;\u{1}\u{219E}\u{2}twoheadrightarrow;\u{1}\u{21A0}\u{2}uArr;\u{1}\u{21D1}\u{2}uHar;\u{1}\u{2963}\u{2}uacute\u{1}\u{FA}\u{2}uacute;\u{1}\u{FA}\u{2}uarr;\u{1}\u{2191}\u{2}" +
        "ubrcy;\u{1}\u{45E}\u{2}ubreve;\u{1}\u{16D}\u{2}ucirc\u{1}\u{FB}\u{2}ucirc;\u{1}\u{FB}\u{2}ucy;\u{1}\u{443}\u{2}udarr;\u{1}\u{21C5}\u{2}udblac;\u{1}\u{171}\u{2}udhar;\u{1}\u{296E}\u{2}ufisht;\u{1}\u{297E}\u{2}ufr;\u{1}\u{1D532}\u{2}ugrave\u{1}\u{F9}\u{2}ugrave;\u{1}\u{F9}\u{2}uharl;\u{1}\u{21BF}\u{2}uharr;\u{1}\u{21BE}\u{2}uhblk;\u{1}\u{2580}\u{2}ulcorn;\u{1}\u{231C}\u{2}ulcorner;\u{1}\u{231C}\u{2}ulcrop;\u{1}\u{230F}\u{2}ultri;\u{1}\u{25F8}\u{2}umacr;\u{1}\u{16B}\u{2}uml\u{1}\u{A8}\u{2}uml;\u{1}\u{A8}\u{2}uogon;\u{1}\u{173}\u{2}uopf;\u{1}\u{1D566}\u{2}uparrow;\u{1}\u{2191}\u{2}updownarrow;\u{1}\u{2195}\u{2}upharpoonleft;\u{1}\u{21BF}\u{2}upharpoonright;\u{1}\u{21BE}\u{2}uplus;\u{1}\u{228E}\u{2}upsi;\u{1}\u{3C5}\u{2}upsih;\u{1}\u{3D2}\u{2}upsilon;\u{1}\u{3C5}\u{2}upuparrows;\u{1}\u{21C8}\u{2}urcorn;\u{1}\u{231D}\u{2}urcorner;\u{1}\u{231D}\u{2}urcrop;\u{1}\u{230E}\u{2}uring;\u{1}\u{16F}\u{2}urtri;\u{1}\u{25F9}\u{2}uscr;\u{1}\u{1D4CA}\u{2}utdot;\u{1}\u{22F0}\u{2}" +
        "utilde;\u{1}\u{169}\u{2}utri;\u{1}\u{25B5}\u{2}utrif;\u{1}\u{25B4}\u{2}uuarr;\u{1}\u{21C8}\u{2}uuml\u{1}\u{FC}\u{2}uuml;\u{1}\u{FC}\u{2}uwangle;\u{1}\u{29A7}\u{2}vArr;\u{1}\u{21D5}\u{2}vBar;\u{1}\u{2AE8}\u{2}vBarv;\u{1}\u{2AE9}\u{2}vDash;\u{1}\u{22A8}\u{2}vangrt;\u{1}\u{299C}\u{2}varepsilon;\u{1}\u{3F5}\u{2}varkappa;\u{1}\u{3F0}\u{2}varnothing;\u{1}\u{2205}\u{2}varphi;\u{1}\u{3D5}\u{2}varpi;\u{1}\u{3D6}\u{2}varpropto;\u{1}\u{221D}\u{2}varr;\u{1}\u{2195}\u{2}varrho;\u{1}\u{3F1}\u{2}varsigma;\u{1}\u{3C2}\u{2}varsubsetneq;\u{1}\u{228A}\u{FE00}\u{2}varsubsetneqq;\u{1}\u{2ACB}\u{FE00}\u{2}varsupsetneq;\u{1}\u{228B}\u{FE00}\u{2}varsupsetneqq;\u{1}\u{2ACC}\u{FE00}\u{2}vartheta;\u{1}\u{3D1}\u{2}vartriangleleft;\u{1}\u{22B2}\u{2}vartriangleright;\u{1}\u{22B3}\u{2}vcy;\u{1}\u{432}\u{2}vdash;\u{1}\u{22A2}\u{2}vee;\u{1}\u{2228}\u{2}veebar;\u{1}\u{22BB}\u{2}veeeq;\u{1}\u{225A}\u{2}vellip;\u{1}\u{22EE}\u{2}verbar;\u{1}|\u{2}vert;\u{1}|\u{2}vfr;\u{1}\u{1D533}\u{2}vltri;\u{1}\u{22B2}\u{2}vnsub;\u{1}\u{2282}\u{20D2}\u{2}vnsup;\u{1}\u{2283}\u{20D2}\u{2}" +
        "vopf;\u{1}\u{1D567}\u{2}vprop;\u{1}\u{221D}\u{2}vrtri;\u{1}\u{22B3}\u{2}vscr;\u{1}\u{1D4CB}\u{2}vsubnE;\u{1}\u{2ACB}\u{FE00}\u{2}vsubne;\u{1}\u{228A}\u{FE00}\u{2}vsupnE;\u{1}\u{2ACC}\u{FE00}\u{2}vsupne;\u{1}\u{228B}\u{FE00}\u{2}vzigzag;\u{1}\u{299A}\u{2}wcirc;\u{1}\u{175}\u{2}wedbar;\u{1}\u{2A5F}\u{2}wedge;\u{1}\u{2227}\u{2}wedgeq;\u{1}\u{2259}\u{2}weierp;\u{1}\u{2118}\u{2}wfr;\u{1}\u{1D534}\u{2}wopf;\u{1}\u{1D568}\u{2}wp;\u{1}\u{2118}\u{2}wr;\u{1}\u{2240}\u{2}wreath;\u{1}\u{2240}\u{2}wscr;\u{1}\u{1D4CC}\u{2}xcap;\u{1}\u{22C2}\u{2}xcirc;\u{1}\u{25EF}\u{2}xcup;\u{1}\u{22C3}\u{2}xdtri;\u{1}\u{25BD}\u{2}xfr;\u{1}\u{1D535}\u{2}xhArr;\u{1}\u{27FA}\u{2}xharr;\u{1}\u{27F7}\u{2}xi;\u{1}\u{3BE}\u{2}xlArr;\u{1}\u{27F8}\u{2}xlarr;\u{1}\u{27F5}\u{2}xmap;\u{1}\u{27FC}\u{2}xnis;\u{1}\u{22FB}\u{2}xodot;\u{1}\u{2A00}\u{2}xopf;\u{1}\u{1D569}\u{2}xoplus;\u{1}\u{2A01}\u{2}xotime;\u{1}\u{2A02}\u{2}xrArr;\u{1}\u{27F9}\u{2}xrarr;\u{1}\u{27F6}\u{2}xscr;\u{1}\u{1D4CD}\u{2}xsqcup;\u{1}\u{2A06}\u{2}" +
        "xuplus;\u{1}\u{2A04}\u{2}xutri;\u{1}\u{25B3}\u{2}xvee;\u{1}\u{22C1}\u{2}xwedge;\u{1}\u{22C0}\u{2}yacute\u{1}\u{FD}\u{2}yacute;\u{1}\u{FD}\u{2}yacy;\u{1}\u{44F}\u{2}ycirc;\u{1}\u{177}\u{2}ycy;\u{1}\u{44B}\u{2}yen\u{1}\u{A5}\u{2}yen;\u{1}\u{A5}\u{2}yfr;\u{1}\u{1D536}\u{2}yicy;\u{1}\u{457}\u{2}yopf;\u{1}\u{1D56A}\u{2}yscr;\u{1}\u{1D4CE}\u{2}yucy;\u{1}\u{44E}\u{2}yuml\u{1}\u{FF}\u{2}yuml;\u{1}\u{FF}\u{2}zacute;\u{1}\u{17A}\u{2}zcaron;\u{1}\u{17E}\u{2}zcy;\u{1}\u{437}\u{2}zdot;\u{1}\u{17C}\u{2}zeetrf;\u{1}\u{2128}\u{2}zeta;\u{1}\u{3B6}\u{2}zfr;\u{1}\u{1D537}\u{2}zhcy;\u{1}\u{436}\u{2}zigrarr;\u{1}\u{21DD}\u{2}zopf;\u{1}\u{1D56B}\u{2}zscr;\u{1}\u{1D4CF}\u{2}zwj;\u{1}\u{200D}\u{2}zwnj;\u{1}\u{200C}\u{2}"
    static func pyIsSpace(_ u: Unicode.Scalar) -> Bool { u.properties.isWhitespace || (0x1C...0x1F).contains(u.value) }

    static let html5: [String: String] = {
        var d: [String: String] = [:]
        for e in html5Source.split(separator: "\u{2}") {
            let p = e.split(separator: "\u{1}", maxSplits: 1, omittingEmptySubsequences: false)
            if p.count == 2 { d[String(p[0])] = String(p[1]) }
        }
        return d
    }()

    /// bs4 EntitySubstitution.HTML_ENTITY_TO_CHARACTER: names without ';', the first in sorted order winning.
    static let bs4: [String: String] = {
        var d: [String: String] = [:]
        for k in html5.keys.sorted(by: pyLT) {
            let name = k.hasSuffix(";") ? String(k.dropLast()) : k
            if d[name] == nil { d[name] = html5[k] }
        }
        return d
    }()

    static let INVALID_CHARREFS: [Int: String] = [0x00: "\u{FFFD}", 0x0d: "\r", 0x80: "\u{20ac}", 0x81: "\u{81}", 0x82: "\u{201a}",
        0x83: "\u{0192}", 0x84: "\u{201e}", 0x85: "\u{2026}", 0x86: "\u{2020}", 0x87: "\u{2021}", 0x88: "\u{02c6}", 0x89: "\u{2030}",
        0x8a: "\u{0160}", 0x8b: "\u{2039}", 0x8c: "\u{0152}", 0x8d: "\u{8d}", 0x8e: "\u{017d}", 0x8f: "\u{8f}", 0x90: "\u{90}",
        0x91: "\u{2018}", 0x92: "\u{2019}", 0x93: "\u{201c}", 0x94: "\u{201d}", 0x95: "\u{2022}", 0x96: "\u{2013}", 0x97: "\u{2014}",
        0x98: "\u{02dc}", 0x99: "\u{2122}", 0x9a: "\u{0161}", 0x9b: "\u{203a}", 0x9c: "\u{0153}", 0x9d: "\u{9d}", 0x9e: "\u{017e}",
        0x9f: "\u{0178}"]

    static func invalidCodepoint(_ n: Int) -> Bool {
        (0x1...0x8).contains(n) || (0xe...0x1f).contains(n) || (0x7f...0x9f).contains(n) || (0xfdd0...0xfdef).contains(n)
            || n == 0xb || (n & 0xFFFE) == 0xFFFE && n <= 0x10FFFF
    }

    static let CHARREF = try! NSRegularExpression(pattern: #"&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\x{0C} <&#;]{1,32};?)"#)

    /// html.unescape
    static func unescape(_ s: String) -> String {
        guard s.utf8.contains(38) else { return s }   // '&'
        let ns = s as NSString
        var out = "", pos = 0
        for m in CHARREF.matches(in: s, range: NSRange(location: 0, length: ns.length)) {
            out += ns.substring(with: NSRange(location: pos, length: m.range.location - pos))
            out += replace(ns.substring(with: m.range(at: 1)))
            pos = NSMaxRange(m.range)
        }
        return out + ns.substring(from: pos)
    }

    private static func replace(_ s: String) -> String {
        let sc = Array(s.unicodeScalars)
        if sc[0] == "#" {
            let hex = sc.count > 1 && (sc[1] == "x" || sc[1] == "X")
            var digits = String(String.UnicodeScalarView(sc.dropFirst(hex ? 2 : 1)))
            while digits.hasSuffix(";") { digits.removeLast() }
            let num = Int(digits, radix: hex ? 16 : 10) ?? Int.max
            if let r = INVALID_CHARREFS[num] { return r }
            if (0xD800...0xDFFF).contains(num) || num > 0x10FFFF { return "\u{FFFD}" }
            if invalidCodepoint(num) { return "" }
            return String(Unicode.Scalar(UInt32(num))!)
        }
        if let v = html5[s] { return v }
        var x = sc.count - 1
        while x > 1 {
            let head = String(String.UnicodeScalarView(sc[..<x]))
            if let v = html5[head] { return v + String(String.UnicodeScalarView(sc[x...])) }
            x -= 1
        }
        return "&" + s
    }
}
