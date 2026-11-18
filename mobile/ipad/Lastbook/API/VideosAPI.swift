import Foundation

/// Port of server.py's videos section: /api/videos, /api/videos/<row>, /api/videos/related/<id>.
struct VideosAPI: RouteGroup {
    static let VROWS: [(String, String, String)] = [
        ("health", "First aid & health", "first-aid medical care-continuity"),
        ("water", "Water & sanitation", "water-safety-planning water-treatment rainwater water-sanitation water-sampling sanitary-inspection pumps"),
        ("food", "Growing & preserving food", "food-preservation agriculture food-growing seed-saving grain-mill-assembly grain-mill-maintenance grain-mill-operation"),
        ("power", "Power, generators & solar", "generator generators offgrid-power"),
        ("outdoors", "Shelter, fire & outdoor skills", "field-survival fire-and-shelter knots weather communications-navigation"),
        ("repair", "Tools, engines & repair", "small-engine-repair lawn-mower garden-power-equipment snow-blower woodworking welding welding-equipment sharpening workshop milling-layout-and-fit bearing-maintenance seals-installation road-vehicles marine heavy-ag-machinery machining-tool-geometry measurement"),
        ("making", "Making things by hand", "craft-manufacturing-including-ceramics-and-textiles glass-manufacturing-processes refractory-installation refractory-process-control typesetting-printing-binding bark-to-amate-paper"),
        ("coalcracker", "Coalcracker Bushcraft", "creator-coalcracker-bushcraft"),
        ("corporals", "Corporals Corner", "creator-corporals-corner"),
        ("canterbury", "Dave Canterbury", "creator-david-canterbury"),
        ("primitive", "Primitive Technology", "creator-primitive-technology"),
        ("courses", "Courses, lectures & more", ""),
    ]
    static let VROW_NOTE = ["coalcracker": "Hobbyist channel", "corporals": "Hobbyist channel", "canterbury": "Hobbyist channel",
                            "primitive": "Hobbyist channel — no narration", "courses": "University lectures (MIT and others)"]

    func handle(_ r: APIRequest) -> APIResponse? {
        let p = r.path
        if p == "/api/videos" { return .json(Self.home()) }
        if p.hasPrefix("/api/videos/related/") { return .json(Self.related(String(p.dropFirst(20)))) }
        if p.hasPrefix("/api/videos/") {
            return .json(Self.list(String(p.dropFirst(12)), q: r.q("q"), length: r.q("len"), sort: r.q("sort"), offset: r.qi("offset", 0)))
        }
        return nil
    }

    static func vrowOf(_ r: Rec) -> String {
        let c = r.s("category")
        for (vid, _, cats) in VROWS where cats.split(separator: " ").contains(Substring(c)) { return vid }
        return "courses"
    }

    static func vcard(_ r: Rec) -> Rec {
        let p = Catalog.shared.publicRec(r) ?? [:]
        var o: Rec = [:]
        for k in ["id", "title", "publisher", "duration", "thumb", "transcript", "trust", "year"] { o[k] = p[k] ?? NSNull() }
        return o
    }

    /// (-trust, no transcript, no thumb, title) like server.py vsort
    static func vless(_ a: Rec, _ b: Rec) -> Bool {
        let c = Catalog.shared
        func key(_ r: Rec) -> (Double, Int, Int, String) {
            (-Catalog.trust(r).1, (c.videoTx[r.s("path")] == nil && !r.truthy("captions")) ? 1 : 0, c.thumbs[r.s("path")] == nil ? 1 : 0, r.s("title"))
        }
        let x = key(a), y = key(b)
        if x.0 != y.0 { return x.0 < y.0 }; if x.1 != y.1 { return x.1 < y.1 }; if x.2 != y.2 { return x.2 < y.2 }
        return x.3 < y.3
    }

    static func guideVideos() -> [Rec] {
        var out: [Rec] = [], seen = Set<String>()
        for t in Catalog.shared.topics {
            var items: [Rec] = []
            for c in (t["choices"] as? [Rec] ?? []) { items += c["read"] as? [Rec] ?? [] }
            items += t["learn"] as? [Rec] ?? []
            items += t["prepare"] as? [Rec] ?? []
            for st in (t["route"] as? [Rec] ?? []) { items += st["read"] as? [Rec] ?? [] }
            for i in items {
                guard let r = Catalog.shared.get(i.s("doc")), r.s("kind") == "video", !seen.contains(r.s("id")) else { continue }
                seen.insert(r.s("id"))
                var c = vcard(r); c["guide"] = t.s("id"); c["guideTitle"] = t["title"] ?? NSNull()
                out.append(c)
            }
        }
        return out
    }

    static func home() -> [Rec] {
        var rows: [String: [Rec]] = [:]
        for r in Catalog.shared.records where r.s("kind") == "video" { rows[vrowOf(r), default: []].append(r) }
        let g = guideVideos()
        var res: [Rec] = [["id": "guides", "title": "Picked for the guides", "note": "Chosen to go with the survival guides", "count": g.count, "items": Array(g.prefix(16))]]
        for (vid, title, _) in VROWS {
            var rs = (rows[vid] ?? []).sorted(by: vless)
            if (VROW_NOTE[vid] ?? "").hasPrefix("Hobbyist") { rs = stableSort(rs) { $0.s("upload_date") > $1.s("upload_date") } }
            if !rs.isEmpty {
                res.append(["id": vid, "title": title, "note": VROW_NOTE[vid] ?? NSNull(), "count": rs.count, "items": rs.prefix(16).map(vcard)])
            }
        }
        return res
    }

    static func list(_ row: String, q: String, length: String, sort: String, offset: Int, limit: Int = 48) -> Rec {
        var rs: [Rec]
        if row == "guides" { rs = guideVideos().compactMap { Catalog.shared.get($0.s("id")) } }
        else { rs = Catalog.shared.records.filter { $0.s("kind") == "video" && (row == "" || row == "all" || vrowOf($0) == row) } }
        if !q.isEmpty {
            let words = q.lowercased().split(separator: " ").map(String.init)
            rs = rs.filter { r in let t = (r.s("title") + " " + r.s("publisher")).lowercased(); return words.allSatisfy(t.contains) }
        }
        let d: (Rec) -> Double = { $0.d("duration") }
        switch length {
        case "short": rs = rs.filter { d($0) > 0 && d($0) < 600 }
        case "medium": rs = rs.filter { 600 <= d($0) && d($0) < 1800 }
        case "long": rs = rs.filter { d($0) >= 1800 }
        default: break
        }
        switch sort {
        case "short": rs = stableSort(rs) { d($0) < d($1) }
        case "new": rs = stableSort(rs) { $0.s("upload_date") > $1.s("upload_date") }
        case "az": rs = stableSort(rs) { $0.s("title").lowercased() < $1.s("title").lowercased() }
        default: if row != "guides" { rs.sort(by: vless) }
        }
        let title = VROWS.first { $0.0 == row }?.1 ?? (row == "guides" ? "Picked for the guides" : "All videos")
        let page = rs.dropFirst(max(0, offset)).prefix(limit)
        return ["title": title, "note": VROW_NOTE[row] ?? NSNull(), "total": rs.count, "items": page.map(vcard), "more": rs.count > offset + limit]
    }

    static func related(_ vid: String, limit: Int = 12) -> [Rec] {
        guard let v = Catalog.shared.get(vid) else { return [] }
        let row = vrowOf(v)
        let vids = Catalog.shared.records.filter { $0.s("kind") == "video" && $0.s("id") != vid }
        let samePub = vids.filter { $0.s("publisher") == v.s("publisher") }
        let sameRow = vids.filter { vrowOf($0) == row && $0.s("publisher") != v.s("publisher") }
        let words = Set(v.s("title").lowercased().allMatches("[a-z]{4,}"))
        let score: (Rec) -> Int = { -words.intersection($0.s("title").lowercased().allMatches("[a-z]{4,}")).count }
        let a = stableSort(sameRow) { score($0) != score($1) ? score($0) < score($1) : vless($0, $1) }.prefix(limit / 2)
        let b = stableSort(samePub) { score($0) != score($1) ? score($0) < score($1) : $0.s("title") < $1.s("title") }.prefix(limit)
        return Array((Array(a) + Array(b)).prefix(limit)).map(vcard)
    }
}

/// Python's sort is stable; Swift's sort is not guaranteed to be.
func stableSort<T>(_ a: [T], by less: (T, T) -> Bool) -> [T] {
    a.enumerated().sorted { less($0.element, $1.element) || (!less($1.element, $0.element) && $0.offset < $1.offset) }.map(\.element)
}
