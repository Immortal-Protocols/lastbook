import Foundation
import CoreGraphics
import ImageIO
import PDFKit

/// Port of the desktop's library and reading routes: server.py (topics, find, shelves, doc, page, transcript, retrieve,
/// library), engine/library.py (/api/search, /api/health, /api/download-status, /api/collection-search) and the keyword
/// half of assistant.hybrid. There is no semantic model on the iPad, so /api/retrieve answers as the desktop does with
/// no model in the library (retrieval.AVAILABLE False). There is no libzim either: encyclopedia search answers as the
/// desktop does when its ZIM files cannot be opened.
struct LibraryAPI: RouteGroup {
    func handle(_ r: APIRequest) -> APIResponse? {
        let p = r.path
        switch p {
        case "/api/library": return .json(Self.library())
        case "/api/topics": return .json(Self.topicsResolved())
        case "/api/find": return .json(Self.find(pyPrefix(r.q("q"), 200), kind: r.q("kind", "all")))
        case "/api/shelves": return .json(Self.shelves())
        case "/api/collection":
            guard let off = pyInt(r.query["offset"], 0) else { return Self.serverError("ValueError") }
            return .json(Self.collectionItems(r.q("name"), offset: off))
        case "/api/retrieve":
            guard let k = pyInt(r.query["k"], 8) else { return Self.serverError("ValueError") }
            let q = r.q("q")
            return .json(["q": q, "results": Self.hybrid(pyPrefix(q, 200), k: min(20, k), kind: r.q("kind", "any")),
                          "semantic": Self.semanticStatus])
        case "/api/health": return .json(["service": "survival-library", "offline": true])
        case "/api/download-status": return .json(Self.downloadStatus())
        case "/api/search": return .json(Self.search(r.q("q"), limit: 40))
        case "/api/collection-search":
            // Desktop: every ZIM failing to open (or libzim missing) is a 500; no ZIM at all is an empty list.
            return Self.zimNames().isEmpty ? .json([Any]()) : .error("Encyclopedia search failed.", status: 500)
        default: break
        }
        if p.hasPrefix("/api/shelf/") {
            guard let off = pyInt(r.query["offset"], 0) else { return Self.serverError("ValueError") }
            return .json(Self.shelf(String(p.dropFirst(11)), kind: r.q("kind", "all"), q: r.q("q"), offset: off))
        }
        if p.hasPrefix("/api/doc/") {
            if let rec = Catalog.shared.get(String(p.dropFirst(9))) { return .json(Catalog.shared.publicRec(rec, full: true)!) }
            return .error("This item is not in the library catalog.", status: 404)
        }
        if p.hasPrefix("/api/transcript/") {
            if let t = Self.transcript(String(p.dropFirst(16))) { return .json(t) }
            return .error("unknown video", status: 404)
        }
        if p.hasPrefix("/api/page/") { return Self.page(r) }
        return nil
    }

    static func serverError(_ name: String) -> APIResponse { .error("Server error (\(name)).", status: 500) }

    // ------------------------------------------------------------- library ----
    static let SOURCES_PAGE = "documents/lastbook/sources-and-permissions.html"

    static func zimNames() -> [String] {
        guard let lib = Library.shared.lib,
              let names = try? FileManager.default.contentsOfDirectory(atPath: lib.appendingPathComponent("collections").path) else { return [] }
        return names.filter { $0.hasSuffix(".zim") && !$0.hasPrefix(".") }.sorted(by: pyLT)
    }

    static func library() -> Rec {
        var out: Rec = [:]
        let s = Library.shared.lib.flatMap { try? Data(contentsOf: $0.appendingPathComponent("summary.json")) }
            .flatMap { try? JSONSerialization.jsonObject(with: $0) as? Rec } ?? [:]
        for k in ["resources", "pdfs", "pdf_pages", "web_pages", "videos", "collections", "document_bytes"] { out[k] = s[k] ?? NSNull() }
        out["zims"] = zimNames()
        Catalog.shared.ensure()
        out["sources"] = Catalog.shared.byPath[SOURCES_PAGE].map { $0.s("id") as Any } ?? NSNull()
        let pack = packInfo()
        out["pack"] = pyTruthy(pack)
        out["pins"] = pyTruthy(pack) ? !mapLayers().isEmpty : true
        return out
    }

    /// server.py pack_info(): LastbookData/pack.json, or None.
    static func packInfo() -> Any? {
        guard let root = Library.shared.root, let d = try? Data(contentsOf: root.appendingPathComponent("pack.json")) else { return nil }
        return try? JSONSerialization.jsonObject(with: d, options: [.fragmentsAllowed])
    }

    /// The pin kinds of server.py map_contents()['layers'] (only whether there are any is used here).
    static func mapLayers() -> Set<String> {
        var kinds = Set<String>()
        func distinct(_ db: SQLiteDB?, _ table: String, _ col: String) {
            guard let db, db.tables().contains(table) else { return }
            for row in db.query("SELECT DISTINCT \(col) FROM \(table)") { if let v = row[col]?.text { kinds.insert(v) } }
        }
        distinct(Library.shared.db("map.sqlite", geo: true), "poi", "cls")
        distinct(Library.shared.db("national.sqlite", geo: true), "poi", "cls")
        distinct(Library.shared.db("geography/resources/atlas.sqlite"), "resource", "kind")
        distinct(Library.shared.db("water.sqlite", geo: true), "resource", "kind")
        distinct(Library.shared.db("crops.sqlite", geo: true), "resource", "kind")
        return kinds
    }

    static func downloadStatus() -> Rec {
        var out: Rec = [:]
        guard let lib = Library.shared.lib else { return out }
        for (k, rel) in [("channels", "channel-archive-status.json"), ("collections", "manifests/kiwix-progress.json"),
                         ("transcripts", "transcript-status.json"), ("subjects", "subject-video-status.json")] {
            guard let d = try? Data(contentsOf: lib.appendingPathComponent(rel)),
                  var v = try? JSONSerialization.jsonObject(with: d, options: [.fragmentsAllowed]) else { continue }
            if k == "transcripts" {
                guard var o = v as? Rec else { continue }   // desktop: .pop on a non-dict raises, and the key is skipped
                o.removeValue(forKey: "videos"); v = o
            }
            out[k] = v
        }
        return out
    }

    // -------------------------------------------------------------- topics ----
    static func itemHere(_ i: Rec, _ zims: [String]) -> Bool {
        if i.truthy("zim") {
            let parts = i.s("zim").components(separatedBy: "/")
            return parts.count > 1 && zims.contains(parts[1])
        }
        return !i.truthy("doc") || Catalog.shared.get(i.s("doc")) != nil
    }

    static func resolveItem(_ i: Rec) -> Rec {
        var i = i
        if i.truthy("doc") {
            let r = Catalog.shared.get(i.s("doc"))
            if let r, var src = Catalog.shared.publicRec(r) {
                src["notes"] = r["notes"] ?? NSNull()
                i["src"] = src
            } else { i["src"] = NSNull() }
        }
        return i
    }

    static func topicsResolved() -> [Rec] {
        let gaps = (try? Data(contentsOf: Resources.url("content").appendingPathComponent("gaps.json")))
            .flatMap { try? JSONSerialization.jsonObject(with: $0) as? Rec } ?? [:]
        let zims = zimNames()
        func here(_ items: Any?) -> [Rec] { (items as? [Rec] ?? []).filter { itemHere($0, zims) }.map(resolveItem) }
        var res: [Rec] = []
        for t0 in Catalog.shared.topics {
            var t = t0
            t["gaps"] = gaps[t.s("id")] ?? Rec()
            for k in ["prepare", "learn"] { t[k] = here(t0[k]) }
            t["limits"] = (t0["limits"] as? [Rec] ?? []).map { i -> Rec in itemHere(i, zims) ? resolveItem(i) : ["text": i["text"] ?? NSNull()] }
            for k in ["choices", "route"] {
                var kept: [Rec] = []
                for c in t0[k] as? [Rec] ?? [] {
                    var c2 = c
                    let read = here(c["read"])
                    c2["read"] = read
                    if c.truthy("goto") || !read.isEmpty || !c.truthy("read") { kept.append(c2) }
                }
                t[k] = kept
            }
            res.append(t)
        }
        return res
    }

    // -------------------------------------------------------------- search ----
    static let STOP = Set(("a an and are as at be but by can do does for from get got have help how i if in into is it its me my need " +
        "no not of on or our please should so some that the their them then there these they this to up us was we " +
        "what when where which who why will with without you your").split(separator: " ").map(String.init))
    static let SYN: [String: [String]] = [
        "cut": ["wound", "wounds", "laceration", "bleeding"], "cuts": ["wound", "wounds", "laceration"],
        "bleed": ["bleeding", "haemorrhage", "hemorrhage"], "bleeding": ["haemorrhage", "hemorrhage", "blood loss"],
        "blood": ["bleeding"], "burn": ["burns", "scald"], "burned": ["burns"], "burnt": ["burns"],
        "broken": ["fracture", "fractures"], "bone": ["fracture", "bones"], "sprain": ["sprains", "strain", "twisted"],
        "poop": ["faeces", "feces", "excreta", "latrine"], "pee": ["urine"], "toilet": ["latrine", "toilets", "sanitation", "excreta"],
        "sewage": ["sewer", "wastewater", "excreta"], "trash": ["garbage", "refuse", "waste", "rubbish"], "garbage": ["refuse", "waste", "rubbish"],
        "purify": ["purification", "disinfect", "disinfection", "treatment"], "clean": ["disinfect", "safe"],
        "drinking": ["potable", "drinking"], "filter": ["filtration", "filters"], "bleach": ["chlorine", "hypochlorite"],
        "blackout": ["outage", "power outage"], "outage": ["blackout"], "electricity": ["electric", "power"],
        "power": ["electricity", "outage"], "light": ["lighting", "flashlight", "lantern"], "flashlight": ["torch", "lantern"],
        "generator": ["generators"], "solar": ["photovoltaic", "pv"], "battery": ["batteries"],
        "cook": ["cooking", "stove"], "cooking": ["stove", "cook"], "stove": ["stoves", "cooking"], "fridge": ["refrigerator", "refrigerated"],
        "spoiled": ["spoilage", "unsafe food"], "rotten": ["spoilage", "spoiled"],
        "canning": ["canned", "canner"], "pickle": ["pickling", "pickled"],
        "cold": ["hypothermia", "cold weather", "winter"], "freezing": ["hypothermia", "frostbite"], "hot": ["heat"],
        "heat": ["heat stroke", "heat exhaustion", "hyperthermia", "extreme heat"], "heatstroke": ["heat stroke"],
        "smoke": ["air quality", "wildfire smoke"], "quake": ["earthquake"], "earthquake": ["earthquakes", "seismic"],
        "flood": ["flooding", "floods"], "tsunami": ["tsunamis"], "fire": ["fires", "wildfire"], "wildfire": ["wildfires", "fire"],
        "baby": ["newborn", "infant", "babies"], "pregnant": ["pregnancy"], "birth": ["childbirth", "labor", "delivery"],
        "kid": ["child", "children"], "kids": ["children", "child"], "old": ["elderly", "older"],
        "fever": ["temperature", "fevers"], "diarrhea": ["diarrhoea", "dehydration"], "diarrhoea": ["diarrhea"],
        "vomit": ["vomiting"], "puke": ["vomiting"], "sick": ["illness", "disease"], "medicine": ["medicines", "drugs", "medication"],
        "pills": ["medicines", "tablets", "medication"], "painkiller": ["analgesic", "paracetamol", "pain"],
        "heart": ["cardiac", "heart attack"], "cpr": ["resuscitation", "chest compressions"], "choking": ["choke", "airway"],
        "unconscious": ["unresponsive", "recovery position"], "bite": ["bites"], "snake": ["snakebite", "snakes"],
        "sting": ["stings"], "allergic": ["allergy", "anaphylaxis"], "infection": ["infected", "infections"],
        "teeth": ["tooth", "dental"], "tooth": ["teeth", "dental"], "stress": ["anxiety", "mental health"], "depressed": ["depression"],
        "grow": ["growing", "planting", "garden"], "garden": ["gardening", "vegetable"], "seeds": ["seed", "seed saving"],
        "plant": ["planting", "sowing"], "soil": ["compost", "soils"], "potato": ["potatoes"], "potatoes": ["potato"],
        "chickens": ["poultry", "hens"], "chicken": ["poultry"], "goat": ["goats"], "bees": ["beekeeping", "honey bee"],
        "radio": ["radios", "amateur radio", "ham"], "ham": ["amateur radio"], "phone": ["telephone", "cell phone", "mobile"],
        "map": ["maps", "navigation"], "compass": ["navigation", "bearing"], "lost": ["navigation", "lost"],
        "shelter": ["shelters", "sheltering"], "tent": ["tents", "tarp", "shelter"], "warm": ["warmth", "heating", "insulation"],
        "fix": ["repair", "repairs"], "repair": ["repairs", "maintenance"], "engine": ["engines", "small engine"],
        "weld": ["welding"], "wood": ["woodworking", "timber", "lumber"], "knife": ["knives", "sharpening"], "sharpen": ["sharpening"],
        "knot": ["knots"], "rope": ["ropes", "knots"], "pump": ["pumps"], "well": ["wells", "borehole"],
        "rain": ["rainwater"], "gas": ["natural gas", "propane", "gas leak"], "leak": ["leaks", "leaking"],
        "carbon": ["monoxide"], "co": ["carbon monoxide"], "mold": ["mould"], "rats": ["rodents", "rodent"], "mosquito": ["mosquitoes"],
    ]
    static let CLINICAL = #"(?i)surg|clinical|district hospital|essential drugs|tuberculosis|obstetric|cholera epidemic|measles epidemic|anaesth|war surgery"#
    static let GENERAL = #"(?i)first aid|emergency|basic|household|home|beginner|guide|handbook|where there is no"#
    static let KIND_FILTERS: [String: [String]] = ["read": ["pdf", "html", "pptx"], "video": ["video", "transcript"]]
    /// (pattern, groups): everyday phrases -> one idea, checked before single words
    static let PHRASES: [(String, [[String]])] = [
        (#"power (cut|outage|failure)|no (power|electricity)|lights? (are )?out|blackout"#, [["outage", "blackout", "power outage"]]),
        (#"(phone|cell|mobile)( is| was)? (dead|flat|out of battery)|(dead|flat) (phone|battery)"#, [["phone", "phones", "cell phone"], ["charge", "charging", "charger", "power bank"]]),
        (#"(water|tap) (is )?(off|not working|stopped)|no (running )?water"#, [["water"]]),
        (#"toilet (is )?(not working|won'?t flush|broken)|can'?t flush"#, [["latrine", "toilet", "excreta"]]),
        (#"heart attack"#, [["heart attack", "chest pain"]]),
        (#"(passed|blacked) out|fainted"#, [["unconscious", "fainting", "unresponsive"]]),
        (#"food (went|gone|is) bad|spoiled food"#, [["spoilage", "food safety"]]),
        (#"can'?t breathe|not breathing|stopped breathing"#, [["breathing", "resuscitation", "airway"]]),
    ]

    static func ftsExpr(_ groups: [[String]]) -> String {
        groups.map { g in "(" + g.map { "\"" + $0.replacingOccurrences(of: "\"", with: "\"\"") + "\"" }.joined(separator: " OR ") + ")" }
            .joined(separator: " AND ")
    }

    static func queryGroups(_ q0: String) -> ([String], [[String]]) {
        var q = q0.lowercased().replacingOccurrences(of: "\u{2019}", with: "'")
        var phraseGroups: [[String]] = []
        for (rx, g) in PHRASES where Rx.search(rx, q) {
            phraseGroups += g
            q = Rx.sub(rx, " ", q)
        }
        var words = Rx.findall(#"[\w'-]+"#, q).map { $0.lowercased() }
        words = words.map { pyStrip($0, "'") }.filter { !$0.isEmpty }
        var content = words.filter { !STOP.contains($0) }
        if content.isEmpty { content = phraseGroups.isEmpty ? words : [] }
        var groups: [[String]] = []
        for w in content {
            var g = [w] + (SYN[w] ?? [])
            let stem = String(String.UnicodeScalarView(w.unicodeScalars.dropLast()))
            if w.hasSuffix("s") && w.unicodeScalars.count > 4 && !g.contains(stem) { g.append(stem) }
            groups.append(g)
        }
        return (phraseGroups.map { $0[0] } + content, phraseGroups + groups)
    }

    static func ftsRows(_ sql: String, _ args: [Any?]) -> [(String, Int?, String?, Double)] {
        guard let db = Library.shared.db("search.sqlite") else { return [] }
        return db.query(sql, args).map { ($0["doc_id"]?.text ?? "", $0["page"]?.int.map { Int($0) }, $0["snip"]?.text, $0["score"]?.double ?? 0) }
    }

    static func find(_ q: String, kind: String) -> Rec {
        let (content, groups) = queryGroups(q)
        if groups.isEmpty { return ["q": q, "results": [Any](), "expanded": [Any]()] }
        let sql = "SELECT doc_id,page,snippet(pages,6,'\u{01}','\u{02}',' … ',28) AS snip,bm25(pages,0,6,1,1,0,0,1) AS score " +
                  "FROM pages WHERE pages MATCH ? ORDER BY bm25(pages,0,6,1,1,0,0,1) LIMIT 600"
        var mode = "all words"
        var rows = ftsRows(sql, [ftsExpr(groups)])
        if rows.count < 8 && groups.count > 1 {
            mode = "some words"
            rows += ftsRows(sql, [groups.map { "(" + ftsExpr([$0]) + ")" }.joined(separator: " OR ")])
        }
        let cat = Catalog.shared
        cat.ensure()
        let allowed = KIND_FILTERS[kind]
        struct D { var r: Rec; var score = 0.0; var hits: [(Int?, String?)] = []; var n = 0 }
        var docs: [String: D] = [:], order: [String] = []
        for (docId, page0, snip, score) in rows {
            guard var r = cat.byId[docId], r.s("kind") != "metadata" else { continue }
            var page = page0
            if r.s("kind") == "transcript", let v = cat.byPath[r.s("video_path")] { r = v; page = nil }
            if let allowed, !allowed.contains(r.s("kind")) { continue }
            let id = r.s("id")
            if docs[id] == nil { docs[id] = D(r: r); order.append(id) }
            var d = docs[id]!
            if d.hits.count < 3 && !d.hits.contains(where: { $0.0 == page }) {
                d.hits.append((r.s("kind") == "pdf" ? page : nil, snip))
            }
            d.n += 1
            if d.n == 1 { d.score = -score } else if d.n <= 4 { d.score += -score * 0.1 }
            docs[id] = d
        }
        var out: [(Double, D)] = []
        for id in order {
            let d = docs[id]!, r = d.r
            let w = Catalog.trust(r).1
            let title = r.s("title").lowercased()
            let tb = Double(groups.filter { g in g.contains { title.contains($0) } }.count) / Double(groups.count)
            var s = d.score * w * (1 + tb)
            if Rx.search(#"(?i)Spanish|español|\bkit de\b"#, r.s("title") + r.s("notes")) { s *= 0.5 }
            if Rx.search(CLINICAL, r.s("title") + " " + r.s("collection")) && !Rx.search(CLINICAL, q) { s *= 0.6 }
            if Rx.search(#"(?i)^index$|front matter|table of contents|credits|^contents"#, Catalog.cleanTitle(r)) { s *= 0.3 }
            if Rx.search(GENERAL, r.s("title")) { s *= 1.25 }
            out.append((s, d))
        }
        out = stableSort(out) { $0.0 > $1.0 }
        let results: [Rec] = out.prefix(30).map { (_, d) in
            var p = cat.publicRec(d.r)!
            p["hits"] = d.hits.map { ["page": $0.0 as Any? ?? NSNull(), "snippet": cleanSnip($0.1)] as Rec }
            return p
        }
        let contentSet = Set(content)
        let expanded = Set(groups.flatMap { $0.dropFirst() }).subtracting(contentSet).sorted(by: pyLT)
        return ["q": q, "mode": mode, "expanded": expanded, "results": results]
    }

    static func cleanSnip(_ s: String?) -> String {
        Rx.sub(Rx.pyWS, " ", s ?? "")
            .replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;").replacingOccurrences(of: "\"", with: "&quot;")
            .replacingOccurrences(of: "'", with: "&#x27;")
            .replacingOccurrences(of: "\u{01}", with: "<mark>").replacingOccurrences(of: "\u{02}", with: "</mark>")
    }

    /// engine/library.py search(): the plain page search (/api/search).
    static func search(_ query: String, limit: Int) -> [Rec] {
        let terms = Rx.findall(#"[\w-]+"#, query)
        if terms.isEmpty { return [] }
        let expr = terms.map { "\"" + $0.replacingOccurrences(of: "\"", with: "\"\"") + "\"" }.joined(separator: " AND ")
        guard let db = Library.shared.db("search.sqlite") else { return [] }
        return db.query("SELECT doc_id,title,collection,category,path,page,snippet(pages,6,'[',']',' … ',42) AS excerpt," +
                        "bm25(pages,0,5,2,1,0,0,1) AS score FROM pages WHERE pages MATCH ? ORDER BY score LIMIT ?", [expr, limit])
            .map { row in
                var o: Rec = [:]
                for k in ["doc_id", "title", "collection", "category", "path", "page", "excerpt", "score"] { o[k] = row[k]?.json ?? NSNull() }
                return o
            }
    }

    // -------------------------------------------------------------- shelves ----
    static let SHELVES: [(String, String, String)] = [
        ("health", "Health & first aid", #"medic|first-aid|care|health|dent|mental|obstet|midwi|clinic|surg"#),
        ("water", "Water & sanitation", #"water|rain|sanit|wash|hygien"#),
        ("food", "Food: growing, keeping & cooking", #"agri|food|seed|crop|garden(?!-power)|livestock|dairy|ferment|bee|farm|soil|grow|irrigat|oil-crop|grain"#),
        ("safety", "Disasters, safety & outdoors", #"survival|shelter|disaster|prepar|safety|hazard|wildfire|knot|weather|polar|defen|radiolog|rescue|fire"#),
        ("power", "Power & energy", #"energy|power|solar|generator|offgrid|battery|inverter|charge-controller"#),
        ("comms", "Radio, communication & navigation", #"communic|radio|navigation"#),
        ("repair", "Tools, repair & equipment", #"engine|mower|tractor|vehicle|hvac|compressor|bicycle|aerial|backhoe|bearing|sharpen|weld|repair|equipment|seal|pump|snow|motorcycle|truck|car|marine|forklift|workshop|hand-tool"#),
        ("making", "Making things & materials", #"manufact|craft|glass|ceram|textil|wood|paper|metal|materials|machin|leather|amate|lime|refractor|typeset|mill|mineral|production|raw-material"#),
        ("build", "Building & infrastructure", #"civil|infrastructure|building"#),
        ("community", "Community, teaching & recovery", #"communit|educat|teach|accessib|recover|accountab|organiz|continuity|inventory"#),
        ("science", "Science, maths & engineering courses", #"math|physic|chemistr|biolog|astronom|earth|ecolog|science|engineer|control|metrolog|quality|thermo|electromag|circuit|microelec|comput|digital|space|aviation|aircraft|laborator|measurement"#),
        ("creators", "Bushcraft & primitive-skills videos", #"^creator-"#),
    ]

    static func shelfOf(_ r: Rec) -> String {
        let c = r.s("category").lowercased()
        if c.hasPrefix("creator-") { return "creators" }
        for (sid, _, rx) in SHELVES where sid != "creators" && Rx.search(rx, c) { return sid }
        return "other"
    }

    static func shelves() -> [Rec] {
        var counts: [String: (Int, Int)] = [:]
        for r in Catalog.shared.records where !["metadata", "transcript", "zim"].contains(r.s("kind")) {
            var c = counts[shelfOf(r)] ?? (0, 0)
            if r.s("kind") == "video" { c.1 += 1 } else { c.0 += 1 }
            counts[shelfOf(r)] = c
        }
        return (SHELVES.map { ($0.0, $0.1) } + [("other", "Other references")]).map { (s, t) in
            let c = counts[s] ?? (0, 0)
            return ["id": s, "title": t, "read": c.0, "video": c.1]
        }
    }

    static func shelf(_ sid: String, kind: String, q: String, offset: Int, limit: Int = 40) -> Rec {
        let allowed = KIND_FILTERS[kind]
        let ql = q.lowercased()
        var rs = Catalog.shared.records.filter { r in
            !["metadata", "transcript", "zim"].contains(r.s("kind")) && shelfOf(r) == sid
                && (allowed == nil || allowed!.contains(r.s("kind")))
                && (q.isEmpty || (r.s("title") + " " + r.s("collection") + " " + r.s("publisher")).lowercased().contains(ql))
        }
        rs = stableSort(rs) { a, b in
            let wa = -Catalog.trust(a).1, wb = -Catalog.trust(b).1
            if wa != wb { return wa < wb }
            if a.s("collection") != b.s("collection") { return pyLT(a.s("collection"), b.s("collection")) }
            return pyLT(a.s("title"), b.s("title"))
        }
        var groups: [String: [Rec]] = [:], order: [String] = []
        for r in rs {
            let c = r.truthy("collection") ? r.s("collection") : "Other"
            if groups[c] == nil { order.append(c) }
            groups[c, default: []].append(r)
        }
        let items: [Rec] = order.map { c in
            let v = groups[c]!
            return ["collection": c, "count": v.count, "trust": Catalog.trust(v[0]).0, "items": v.prefix(6).map { Catalog.shared.publicRec($0)! }]
        }
        return ["total": rs.count, "collections": pySlice(items, offset, offset + limit), "more": items.count > offset + limit]
    }

    static func collectionItems(_ name: String, offset: Int, limit: Int = 60) -> Rec {
        let rs = stableSort(Catalog.shared.records.filter { $0.str("collection") == name && $0.s("kind") != "metadata" }) { pyLT($0.s("title"), $1.s("title")) }
        return ["total": rs.count, "items": pySlice(rs, offset, offset + limit).map { Catalog.shared.publicRec($0)! }, "more": rs.count > offset + limit]
    }

    // ------------------------------------------------------- pages and text ----
    static func pageTexts(_ r: Rec) -> [String] {
        guard let lib = Library.shared.lib else { return [] }
        let rel = r.truthy("text_path") ? r.s("text_path") : "text/\(r.s("id")).txt"
        guard let t = readText(lib.appendingPathComponent(rel)) else { return [] }
        return t.contains("\n\u{0C}\n") ? t.components(separatedBy: "\n\u{0C}\n") : t.components(separatedBy: "\u{0C}")
    }

    static func page(_ req: APIRequest) -> APIResponse {
        guard let m = Rx.groups(#"^/api/page/([^/]+)/(\d+)(\.png)?$"#, req.path) else { return .error("not found", status: 404) }
        guard let r = Catalog.shared.get(m[0]!) else { return .error("unknown document", status: 404) }
        guard let n = Int(m[1]!) else { return serverError("ValueError") }
        if m[2] != nil {
            if r.s("kind") != "pdf" { return .error("not a PDF", status: 400) }
            guard let w = pyInt(req.query["w"], 1000) else { return serverError("ValueError") }
            guard let png = PageRenderer.shared.png(r, n, max(160, min(1600, w))) else { return serverError("PdfiumError") }
            return .bytes(png, mime: "image/png")
        }
        let ps = pageTexts(r)
        return .json(["page": n, "pages": ps.count, "text": (n > 0 && n <= ps.count) ? ps[n - 1] : ""])
    }

    // ----------------------------------------------------------- transcripts ----
    static func vttCues(_ url: URL) -> [Rec] {
        var cues: [(Int, String)] = []
        for line in pySplitlines(readText(url) ?? "") {
            if let g = Rx.groups(#"^(\d+):(\d\d):(\d\d)[.,](\d+)\s+-->"#, line) {
                cues.append((Int(g[0]!)! * 3600 + Int(g[1]!)! * 60 + Int(g[2]!)!, ""))
            } else if let g = Rx.groups(#"^(\d\d):(\d\d)[.,](\d+)\s+-->"#, line) {
                cues.append((Int(g[0]!)! * 60 + Int(g[1]!)!, ""))
            } else if !cues.isEmpty {
                let s = pyStrip(line)
                guard !s.isEmpty, !pyIsDigit(s) else { continue }
                let txt = pyStrip(htmlUnescape(Rx.sub(#"<[^>]+>"#, "", line)))
                if !txt.isEmpty && !scalarsHasSuffix(cues[cues.count - 1].1, txt) {
                    cues[cues.count - 1].1 = pyStrip(cues[cues.count - 1].1 + " " + txt)
                }
            }
        }
        var out: [(Int, String)] = [], last = ""
        for (ct, ctext) in cues {
            var t = ctext
            if !last.isEmpty && scalarsHasPrefix(t, last) { t = pyStrip(String(String.UnicodeScalarView(t.unicodeScalars.dropFirst(last.unicodeScalars.count)))) }
            if t.isEmpty { continue }
            last = ctext
            if let o = out.last, ct - o.0 < 12 && o.1.unicodeScalars.count < 220 { out[out.count - 1].1 += " " + t }
            else { out.append((ct, t)) }
        }
        return out.map { ["t": $0.0, "text": $0.1] }
    }

    static func transcript(_ videoId: String) -> Rec? {
        let cat = Catalog.shared
        cat.ensure()
        guard let v = cat.byId[videoId], let lib = Library.shared.lib else { return nil }
        let tx = cat.videoTx[v.s("path")]
        var vtts: [String] = []
        if let tx, tx.truthy("vtt_path") { vtts.append(tx.s("vtt_path")) }
        vtts += (v["captions"] as? [String] ?? []).filter { $0.hasSuffix(".vtt") }
        func isFile(_ rel: String) -> Bool {
            var d: ObjCBool = false
            return FileManager.default.fileExists(atPath: lib.appendingPathComponent(rel).path, isDirectory: &d) && !d.boolValue
        }
        for p in vtts where isFile(p) {
            let src: Any = (tx?.truthy("caption_type") ?? false) ? tx!["caption_type"]! : "captions"
            return ["source": src, "notes": tx?["notes"] ?? NSNull(), "cues": vttCues(lib.appendingPathComponent(p))]
        }
        if let tx, isFile(tx.s("path")) {
            let text = readText(lib.appendingPathComponent(tx.s("path"))) ?? ""
            return ["source": tx.truthy("caption_type") ? tx["caption_type"]! : "transcript", "notes": tx["notes"] ?? NSNull(),
                    "cues": text.components(separatedBy: "\n\n").filter { !pyStrip($0).isEmpty }.map { ["t": NSNull(), "text": $0] as Rec }]
        }
        return ["source": NSNull(), "cues": [Any]()]
    }

    // ------------------------------------------------------------- retrieve ----
    /// retrieval.Index.status when the library has no model (desktop: 'off'), which is always so on the iPad.
    static let semanticStatus: Rec = ["state": "off", "chunks": 0, "docs": 0, "pending": NSNull(), "rate": NSNull(),
                                      "note": "Meaning-based search is off: no model in this library. Keyword search still works."]

    /// assistant.hybrid with no meaning-based results: keyword passages ranked by reciprocal rank, trust and title match.
    static func hybrid(_ q: String, k: Int, kind: String) -> [Rec] {
        let cat = Catalog.shared
        cat.ensure()
        let ok: [String]? = ["manual": ["pdf", "html", "pptx"], "video": ["video", "transcript"]][kind.isEmpty ? "any" : kind]
        func allowed(_ d: String) -> Bool {
            guard let r = cat.byId[d], r.s("kind") != "metadata" else { return false }
            return ok == nil || ok!.contains(r.s("kind"))
        }
        // _fts(q, 120)
        var rows: [(String, Int?, String?, Double)] = []
        let (_, groups) = queryGroups(q)
        if !groups.isEmpty {
            let sql = "SELECT doc_id,page,snippet(pages,6,'','',' … ',40) AS snip FROM pages WHERE pages MATCH ? " +
                      "ORDER BY bm25(pages,0,6,1,1,0,0,1) LIMIT ?"
            rows = ftsRows(sql, [ftsExpr(groups), 120])
            if rows.count < 10 && groups.count > 1 {
                rows += ftsRows(sql, [groups.map { "(" + ftsExpr([$0]) + ")" }.joined(separator: " OR "), 120])
            }
        }
        struct Key: Hashable { let d: String; let p: Int? }
        var kw: [(Key, String?)] = []
        for (docId0, page0, snip, _) in rows {
            guard let r = cat.byId[docId0] else { continue }
            var docId = docId0, page = page0
            if r.s("kind") == "transcript" {
                guard let v = cat.byPath[r.s("video_path")] else { continue }
                docId = v.s("id"); page = nil
            }
            if !allowed(docId) { continue }
            kw.append((Key(d: docId, p: cat.byId[docId]!.s("kind") == "pdf" ? page : nil), snip))
        }
        let ql = q.lowercased()
        let qwords = Rx.findall(#"[a-z0-9-]{3,}"#, ql).filter { !STOP.contains($0) }
        let models = Rx.findall(#"[a-z0-9-]+"#, ql).filter { Rx.search(#"\d"#, $0) && Rx.search("[a-z]", $0) && $0.unicodeScalars.count >= 3 }
        // retrieval.rrf over the keyword list alone
        var fusedOrder: [Key] = [], fused: [Key: (Double, Int)] = [:], text: [Key: String?] = [:]
        for (key, snip) in kw {
            if text[key] == nil { text[key] = .some(snip) }
            if fused[key] == nil {
                let rank = fusedOrder.count
                fused[key] = (1.0 / Double(60 + rank + 1), rank + 1)
                fusedOrder.append(key)
            }
        }
        var out: [(Double, Key)] = []
        for key in fusedOrder {
            let r = cat.byId[key.d]!
            var score = fused[key]!.0 * (0.75 + 0.25 * Catalog.trust(r).1)
            if Rx.search(CLINICAL, r.s("title") + " " + r.s("collection")) && !Rx.search(CLINICAL, q) { score *= 0.55 }
            let title = (r.s("title") + " " + (r.truthy("model") ? r.s("model") : "")).lowercased()
            if !models.isEmpty && models.contains(where: { title.contains($0) }) { score *= 3 }
            else if qwords.filter({ title.contains($0) }).count >= max(2, qwords.count / 2) { score *= 1.3 }
            out.append((score, key))
        }
        out = stableSort(out) { $0.0 > $1.0 }
        var res: [Rec] = [], perDoc: [String: Int] = [:]
        for (score, key) in out {
            if perDoc[key.d, default: 0] >= 2 { continue }
            perDoc[key.d, default: 0] += 1
            let r = cat.byId[key.d]!
            let pub = cat.publicRec(r)!
            let excerpt = pyPrefix(Rx.sub(Rx.pyWS, " ", (text[key] ?? nil) ?? ""), 900)
            res.append(["doc_id": key.d, "title": pub["title"]!, "publisher": pub["publisher"]!, "year": pub["year"]!, "kind": r.s("kind"),
                        "trust": pub["trust"]!, "pages": pub["pages"]!, "page": key.p as Any? ?? NSNull(), "t": NSNull(),
                        "duration": pub["duration"] ?? NSNull(), "thumb": pub["thumb"] ?? NSNull(), "excerpt": excerpt,
                        "found_by": ["keyword": fused[key]!.1], "score": pyRound2(score * 1000),
                        "notes": pyPrefix(r.s("notes"), 300), "imageOnly": r.s("searchability").hasPrefix("image-only")])
            if res.count >= k { break }
        }
        return res
    }
}

// ------------------------------------------------------------ PDF pages ----
/// Draws PDF pages with PDFKit. Desktop draws them with PDFium (server.py render_page): the longer side is `width` pixels,
/// RGB on white, PNG. Same size and shape here; the pixels themselves differ (another renderer and PNG encoder).
final class PageRenderer: @unchecked Sendable {
    static let shared = PageRenderer()
    private let lock = NSLock()
    private var docs: [String: PDFDocument] = [:], docOrder: [String] = []
    private let cache = NSCache<NSString, NSData>()

    init() { cache.totalCostLimit = 48 * 1024 * 1024 }

    func png(_ r: Rec, _ n: Int, _ width: Int) -> Data? {
        let key = "\(r.s("id"))-\(n)-\(width)" as NSString
        if let d = cache.object(forKey: key) { return d as Data }
        lock.lock(); defer { lock.unlock() }
        guard let lib = Library.shared.lib else { return nil }
        let path = lib.appendingPathComponent(r.s("path")).path
        var doc = docs[path]
        if doc == nil {
            doc = PDFDocument(url: URL(fileURLWithPath: path))
            if let doc {
                docs[path] = doc; docOrder.append(path)
                if docOrder.count > 4 { docs.removeValue(forKey: docOrder.removeFirst()) }
            }
        }
        guard let doc, n >= 1, n <= doc.pageCount, let page = doc.page(at: n - 1), let data = Self.render(page, width) else { return nil }
        cache.setObject(data as NSData, forKey: key, cost: data.count)
        return data
    }

    static func render(_ page: PDFPage, _ width: Int) -> Data? {
        let box = page.bounds(for: .cropBox)
        // PDFium's sizes are 32-bit floats and pypdfium2 takes ceil(size * scale) in doubles; doing the same gives the same
        // pixel size, including its occasional extra pixel row.
        var w = Double(Float(box.width)), h = Double(Float(box.height))
        if abs(page.rotation) % 180 == 90 { swap(&w, &h) }
        guard w > 0, h > 0 else { return nil }
        let scale = Double(width) / max(w, h)
        let pw = Int(ceil(w * scale)), ph = Int(ceil(h * scale))
        guard pw > 0, ph > 0,
              let ctx = CGContext(data: nil, width: pw, height: ph, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return nil }
        ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
        ctx.fill(CGRect(x: 0, y: 0, width: pw, height: ph))
        ctx.interpolationQuality = .high
        ctx.scaleBy(x: scale, y: scale)
        page.draw(with: .cropBox, to: ctx)   // applies the page's rotation and box origin
        guard let img = ctx.makeImage() else { return nil }
        let out = NSMutableData()
        guard let dest = CGImageDestinationCreateWithData(out as CFMutableData, "public.png" as CFString, 1, nil) else { return nil }
        CGImageDestinationAddImage(dest, img, nil)
        return CGImageDestinationFinalize(dest) ? out as Data : nil
    }
}

// ------------------------------------------------------- Python helpers ----
/// Regular expressions as Python's re uses them here (search, sub, findall, match groups), compiled once.
enum Rx {
    /// Python's \s+ on str: ICU's \s plus the separators \x1c-\x1f, which Python counts as whitespace (some PDF text has them).
    static let pyWS = #"[\s\x{1c}-\x{1f}]+"#
    private static var cache: [String: NSRegularExpression] = [:]
    private static let lock = NSLock()
    static func re(_ p: String) -> NSRegularExpression {
        lock.lock(); defer { lock.unlock() }
        if let r = cache[p] { return r }
        let r = try! NSRegularExpression(pattern: p)
        cache[p] = r
        return r
    }
    static func search(_ p: String, _ s: String) -> Bool { re(p).firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil }
    static func sub(_ p: String, _ t: String, _ s: String) -> String {
        re(p).stringByReplacingMatches(in: s, range: NSRange(s.startIndex..., in: s), withTemplate: NSRegularExpression.escapedTemplate(for: t))
    }
    static func findall(_ p: String, _ s: String) -> [String] {
        re(p).matches(in: s, range: NSRange(s.startIndex..., in: s)).compactMap { Range($0.range, in: s).map { String(s[$0]) } }
    }
    /// The capture groups of the first match (nil for a group that took no part), or nil with no match.
    static func groups(_ p: String, _ s: String) -> [String?]? {
        guard let m = re(p).firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) else { return nil }
        return (1..<m.numberOfRanges).map { Range(m.range(at: $0), in: s).map { String(s[$0]) } }
    }
}

/// Python's str < str: code point order.
func pyLT(_ a: String, _ b: String) -> Bool { a.unicodeScalars.lexicographicallyPrecedes(b.unicodeScalars) }
/// s[:n] in code points.
func pyPrefix(_ s: String, _ n: Int) -> String { String(String.UnicodeScalarView(s.unicodeScalars.prefix(n))) }
func scalarsHasPrefix(_ s: String, _ p: String) -> Bool { s.unicodeScalars.starts(with: p.unicodeScalars) }
func scalarsHasSuffix(_ s: String, _ p: String) -> Bool { s.unicodeScalars.reversed().starts(with: p.unicodeScalars.reversed()) }

/// str.strip() (whitespace) or str.strip(chars).
func pyStrip(_ s: String, _ chars: String? = nil) -> String {
    let set: (Unicode.Scalar) -> Bool
    if let chars { let c = Set(chars.unicodeScalars); set = { c.contains($0) } }
    else { set = { $0.properties.isWhitespace || (0x1C...0x1F).contains($0.value) } }
    var v = Array(s.unicodeScalars)
    while let f = v.first, set(f) { v.removeFirst() }
    while let l = v.last, set(l) { v.removeLast() }
    return String(String.UnicodeScalarView(v))
}

func pyIsDigit(_ s: String) -> Bool { !s.isEmpty && s.unicodeScalars.allSatisfy { $0.properties.numericType == .decimal || $0.properties.numericType == .digit } }

/// str.splitlines() on text already read with universal newlines.
func pySplitlines(_ s: String) -> [String] {
    let breaks: Set<UInt32> = [0x0A, 0x0B, 0x0C, 0x0D, 0x1C, 0x1D, 0x1E, 0x85, 0x2028, 0x2029]
    var out: [String] = [], cur = String.UnicodeScalarView()
    for u in s.unicodeScalars {
        if breaks.contains(u.value) { out.append(String(cur)); cur = String.UnicodeScalarView() } else { cur.append(u) }
    }
    if !cur.isEmpty { out.append(String(cur)) }
    return out
}

/// int(qs.get(k, d)): nil when the value is not a whole number (desktop answers 500 ValueError).
func pyInt(_ v: String?, _ d: Int) -> Int? {
    guard let v else { return d }
    return Int(pyStrip(v).replacingOccurrences(of: "_", with: ""))
}

/// a[start:end] with Python's negative indices.
func pySlice<T>(_ a: [T], _ start: Int, _ end: Int) -> [T] {
    let n = a.count
    func clamp(_ i: Int) -> Int { i < 0 ? max(0, n + i) : min(n, i) }
    let s = clamp(start), e = clamp(end)
    return s < e ? Array(a[s..<e]) : []
}

/// round(x, 2) as Python does it (correctly rounded from the exact binary value).
func pyRound2(_ x: Double) -> Double { Double(String(format: "%.2f", x)) ?? x }

func pyTruthy(_ v: Any?) -> Bool {
    guard let v, !(v is NSNull) else { return false }
    if let d = v as? [String: Any] { return !d.isEmpty }
    if let a = v as? [Any] { return !a.isEmpty }
    if let s = v as? String { return !s.isEmpty }
    if let n = v as? NSNumber { return n != 0 }
    return true
}

/// Path.read_text(encoding='utf-8', errors='replace'): bad bytes become U+FFFD and \r\n, \r become \n.
func readText(_ u: URL) -> String? {
    var d: ObjCBool = false
    guard FileManager.default.fileExists(atPath: u.path, isDirectory: &d), !d.boolValue, let data = try? Data(contentsOf: u) else { return nil }
    return String(decoding: data, as: UTF8.self).replacingOccurrences(of: "\r\n", with: "\n").replacingOccurrences(of: "\r", with: "\n")
}

/// html.unescape for what captions carry: named basics and numeric references.
func htmlUnescape(_ s: String) -> String {
    guard s.contains("&") else { return s }
    let named = ["amp": "&", "lt": "<", "gt": ">", "quot": "\"", "apos": "'", "nbsp": "\u{A0}", "#39": "'"]
    let rx = Rx.re(#"&(#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z]+);"#)
    var out = "", last = s.startIndex
    for m in rx.matches(in: s, range: NSRange(s.startIndex..., in: s)) {
        guard let r = Range(m.range, in: s), let g = Range(m.range(at: 1), in: s) else { continue }
        let name = String(s[g])
        var rep: String?
        if name.hasPrefix("#x") || name.hasPrefix("#X") { rep = UInt32(name.dropFirst(2), radix: 16).flatMap(Unicode.Scalar.init).map { String(Character($0)) } }
        else if name.hasPrefix("#") { rep = UInt32(name.dropFirst()).flatMap(Unicode.Scalar.init).map { String(Character($0)) } }
        else { rep = named[name] }
        out += s[last..<r.lowerBound]
        out += rep ?? String(s[r])
        last = r.upperBound
    }
    return out + s[last...]
}
