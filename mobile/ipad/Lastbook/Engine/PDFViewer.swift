import Foundation
import PDFKit
import CryptoKit

/// Desktop app/bridge.py _answer_pdf: a PDF file is never handed to the web view. A library address ending in .pdf answers
/// with a page of pictures the app drew (no script, a policy allowing none), and `?pdf-page=N` is one page as a PNG.
enum PDFViewer {
    static let width = 1400            // bridge.py PDF_WIDTH: the longer side of a drawn page
    static let maxPages = 20000
    static let notice = Data("This PDF could not be shown here.".utf8)

    /// server.py Handler.NO_CODE_CSP and friends, so saved pages and PDFs run nothing.
    static let noCodeCSP = "default-src 'none'; script-src 'none'; connect-src 'none'; worker-src 'none'; object-src 'none'; manifest-src 'none'; base-uri 'none'; form-action 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; media-src 'self'; frame-src 'self'"
    static let savedPageCSP = "sandbox; " + noCodeCSP
    static let viewerCSP = "sandbox allow-scripts; " + noCodeCSP   // lazy images need scripting on; no script may run

    static func answer(_ rel: String, _ file: URL, _ query: [String: String]) -> APIResponse {
        var rec = Catalog.shared.byPathRec(rel) ?? [:]
        if rec.s("kind") != "pdf" {   // a file a course page links to, with no entry of its own
            let h = SHA256.hash(data: Data(("/" + rel).utf8)).map { String(format: "%02x", $0) }.joined()
            rec = ["id": "file-" + h.prefix(32), "path": rel, "kind": "pdf"]
        }
        if let n = query["pdf-page"].flatMap(Int.init) {
            guard let png = PageRenderer.shared.png(rec, n, width) else { return refusal() }
            return APIResponse(status: 200, mime: "image/png", headers: ["Cache-Control": "max-age=86400", "Content-Security-Policy": savedPageCSP], body: .data(png))
        }
        guard let doc = PDFDocument(url: file), doc.pageCount > 0 else { return refusal() }
        let title = esc(rec.str("title") ?? file.lastPathComponent)
        var rows = ""
        for i in 0..<min(doc.pageCount, maxPages) {
            guard let p = doc.page(at: i) else { continue }
            var b = p.bounds(for: .cropBox).size
            if abs(p.rotation) % 180 == 90 { b = CGSize(width: b.height, height: b.width) }
            rows += "<div class=\"p\" id=\"page=\(i + 1)\"><img loading=\"lazy\" decoding=\"async\" alt=\"Page \(i + 1)\" width=\"\(max(Int(b.width.rounded()), 1))\" height=\"\(max(Int(b.height.rounded()), 1))\" src=\"?pdf-page=\(i + 1)\"></div>"
        }
        let html = "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>\(title)</title><style>html{background:#525659}body{margin:0;padding:8px}.p{max-width:1000px;margin:0 auto 8px}.p img{display:block;width:100%;height:auto;background:#fff}</style></head><body>\(rows)</body></html>"
        return APIResponse(status: 200, mime: "text/html; charset=utf-8", headers: ["Content-Security-Policy": viewerCSP, "Cache-Control": "no-store"], body: .data(Data(html.utf8)))
    }

    static func refusal() -> APIResponse {
        APIResponse(status: 404, mime: "text/html; charset=utf-8", headers: ["Content-Security-Policy": savedPageCSP], body: .data(notice))
    }

    static func esc(_ s: String) -> String {
        s.replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;").replacingOccurrences(of: ">", with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;").replacingOccurrences(of: "'", with: "&#x27;")
    }
}

extension Catalog {
    func byPathRec(_ rel: String) -> Rec? { ensure(); return byPath[rel] }
}
