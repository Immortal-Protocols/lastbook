import Foundation
import CoreFoundation

/// Read free-form directions only after the index misses. Mirrors engine/pr_rural_model.py.
enum PuertoRicoModel {
    typealias Address = PuertoRicoRoads.Address
    struct Numbers: Decodable { let small: [String], tens: [String], hundreds: [String]? }
    struct Language: Decodable { let prompt: String, preamble: String, grammar: [String], es: Numbers, en: Numbers }
    static let language: Language? = {
        guard let bytes = try? Data(contentsOf: Resources.url("web").appendingPathComponent("pr-rural-language.json")) else { return nil }
        return try? JSONDecoder().decode(Language.self, from: bytes)
    }()
    static let capacity = DispatchSemaphore(value: 1)
    static let unsafe = #"\b(?:entre|between|despues|antes|before|after|about|aproximadamente|salida|exit|box|casa|apt|apto|apartamento)\b"#
    static let hint = #"\b(?:frente|lado|detras|junto|cerca|esq|esquina|shopping center|parque industrial)\b"#
    static let tokens = #"\d+(?:[.,]\d+)?|[a-z]+"#

    static func eligible(_ q: String, _ parsed: Address?) -> Bool {
        let raw = plain(q), markers = raw.allMatches(PuertoRicoRoads.km)
        return q.count <= 400 && (PuertoRicoRoads.looksRural(q) || PuertoRicoRoads.parcelDirection(q)) && raw.firstMatch(unsafe) == nil && markers.count <= 1
            && !(markers.first?.firstMatch(#"\d[.,]\d"#) != nil && raw.firstMatch(PuertoRicoRoads.hm) != nil)
            && (parsed != nil || raw.allMatches(PuertoRicoRoads.road).count <= 1)
    }
    static func plain(_ q: String) -> String {
        q.folding(options: .diacriticInsensitive, locale: Locale(identifier: "en_US_POSIX")).lowercased()
            .replacingOccurrences(of: "º", with: "o").replacingOccurrences(of: "°", with: "o")
    }
    static func fold(_ q: String) -> String { plain(q).allMatches("[a-z0-9]+").joined(separator: " ") }
    static func kilometer(_ meters: Int) -> String {
        String(format: "%.3f", locale: Locale(identifier: "en_US_POSIX"), Double(meters) / 1000)
            .replacing("0+$", with: "").replacing(#"\.$"#, with: "")
    }
    static func extract(_ answer: String) -> Address? {
        let text = answer.trimmingCharacters(in: .whitespacesAndNewlines)
            .replacing(#"(?is)^\x60\x60\x60(?:json)?\s*(.*?)\s*\x60\x60\x60$"#, with: "$1")
        guard let a = (try? JSONSerialization.jsonObject(with: Data(text.utf8), options: [.fragmentsAllowed])) as? [Any], [7, 9].contains(a.count),
              let road = a[0] as? NSNumber, CFGetTypeID(road) != CFBooleanGetTypeID(), road.stringValue.firstMatch(#"^[1-9]\d{0,3}$"#) != nil,
              let area = a[2] as? String, let zip = a[3] as? String, zip.isEmpty || zip.firstMatch(#"^\d{5}$"#) != nil,
              let inside = a[4] as? NSNumber, CFGetTypeID(inside) == CFBooleanGetTypeID(),
              let sect = a[5] as? String, let land = a[6] as? String, [area, sect, land].allSatisfy({ $0.count <= 250 }) else { return nil }
        let lot = a.count == 9 ? a[7] as? String : "", access = a.count == 9 ? a[8] as? String : ""
        guard let lot, let access, max(lot.count, access.count) <= 250 else { return nil }
        let km = (a[1] as? String) ?? ((a[1] as? NSNumber).flatMap { CFGetTypeID($0) == CFBooleanGetTypeID() ? nil : $0.stringValue } ?? "")
        var meters: Int?
        if !(a[1] is NSNull) {
            guard km.firstMatch(#"^\d{1,3}(?:\.\d{1,3})?$"#) != nil, let n = Double(km) else { return nil }
            meters = Int((n*1000).rounded())
        }
        return Address(route: road.intValue, meters: meters, locality: fold(area), postal: zip,
                       interior: inside.boolValue, sector: fold(sect), landmark: fold(land), lot: PuertoRicoRoads.lotKey(plain(lot)), access: fold(access))
    }

    static func spelled(_ n: Int, _ spanish: Bool, _ l: Language) -> String {
        let w = spanish ? l.es : l.en
        if n < w.small.count { return w.small[n] }
        if n < 100 {
            let tens = w.tens[n/10 - w.small.count/10]
            return tens + (n%10 == 0 ? "" : (spanish ? " y " : " ") + spelled(n%10, spanish, l))
        }
        let base: String, rem: Int
        if n < 1000 {
            if spanish {
                guard let hundreds = w.hundreds else { return "" }
                base = n == 100 ? "cien" : hundreds[n/100-1]
            } else { base = spelled(n/100, false, l) + " hundred" }
            rem = n%100
        } else {
            base = spanish ? (n < 2000 ? "mil" : spelled(n/1000, true, l) + " mil") : spelled(n/1000, false, l) + " thousand"
            rem = n%1000
        }
        return base + (rem == 0 ? "" : " " + spelled(rem, spanish, l))
    }
    static func forms(_ value: String, _ l: Language) -> [String] {
        let pieces = value.components(separatedBy: ".")
        guard let n = Int(pieces[0]) else { return [] }
        var options: Set<String> = [value]
        for spanish in [true, false] {
            let whole = spelled(n, spanish, l)
            if pieces.count == 1 { options.insert(whole); continue }
            let frac = pieces[1]
            var endings = [frac, frac.compactMap { $0.wholeNumberValue }.map { spelled($0, spanish, l) }.joined(separator: " ")]
            if !frac.hasPrefix("0"), let f = Int(frac) { endings.append(spelled(f, spanish, l)) }
            for glue in spanish ? ["punto","con"] : ["point"] {
                for a in [pieces[0],whole] { for b in endings { options.insert([a,glue,b].joined(separator: " ")) } }
            }
        }
        return options.sorted { $0.count == $1.count ? $0 < $1 : $0.count > $1.count }
    }

    static func grounded(_ q: String, _ a: Address, _ parsed: Address?) -> Bool {
        guard let l = language, eligible(q, parsed) else { return false }
        var raw = plain(q)
        let zips = raw.allMatches(PuertoRicoRoads.zip).map { String($0.prefix(5)) }
        guard zips == (a.postal.isEmpty ? [] : [a.postal]),
              (raw.firstMatch(#"\b(?:int|interior)\b"#) != nil) == a.interior,
              (raw.firstMatch(#"\b(?:sector|sect|sec|comunidad|com)\b"#) != nil) == !a.sector.isEmpty,
              (raw.firstMatch(hint) != nil) == !a.landmark.isEmpty else { return false }
        if a.meters == nil && (!PuertoRicoRoads.parcelDirection(q) || raw.firstMatch(#"\b(?:km|kms|hm|kilometros?|kilometers?|kilometres?|hectometros?)\b"#) != nil) { return false }
        let qualified = raw.replacing(PuertoRicoRoads.zip, with: ",")
        guard let details = PuertoRicoRoads.qualifiers(qualified), details.lot == a.lot, details.access == a.access else { return false }
        if let p = parsed, p.route != a.route || p.meters != a.meters { return false }
        if !a.sector.isEmpty {
            let label = "(?:sector|sect|sec|comunidad|com)", name = NSRegularExpression.escapedPattern(for: a.sector)
            guard fold(raw).firstMatch("\\b(?:" + label + " " + name + "|" + name + " " + label + ")\\b") != nil else { return false }
        }
        raw = qualified.replacing(PuertoRicoRoads.lotPattern, with: " ").replacing(PuertoRicoRoads.accessPattern, with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines).replacing(l.preamble, with: "")
        var values = [String(a.route)]
        if let meters = a.meters { values.append(kilometer(meters)) }
        if parsed != nil, raw.firstMatch(PuertoRicoRoads.km) != nil {
            raw = raw.replacing(PuertoRicoRoads.km, with: " ").replacing(PuertoRicoRoads.hm, with: " ")
            values.removeLast()
        }
        var source = " " + raw.allMatches(tokens).joined(separator: " ").replacingOccurrences(of: ",", with: ".") + " "
        for value in values {
            guard let span = forms(value,l).compactMap({ source.range(of: " " + $0 + " ") }).first else { return false }
            source.replaceSubrange(span, with: " ")
        }
        let ignore = Set(l.grammar)
        func words(_ s: String) -> [String] { s.allMatches(tokens).filter { !ignore.contains($0) }.sorted() }
        return words(source) == words([a.locality, a.sector, a.landmark].joined(separator: " "))
    }

    static func validated(_ q: String, _ original: Address, _ parsed: Address?) -> Address? {
        var a = original
        if !a.landmark.isEmpty && !a.locality.isEmpty && plain(q).firstMatch(hint) == nil,
           fold(q).firstMatch("\\b(?:por|en) " + NSRegularExpression.escapedPattern(for: a.landmark) + "\\b") != nil {
            a = Address(route: a.route, meters: a.meters, locality: a.locality + " " + a.landmark, postal: a.postal,
                        interior: a.interior, sector: a.sector, landmark: "", lot: a.lot, access: a.access)
        }
        return grounded(q, a, parsed) ? a : nil
    }

    static func interpret(_ query: String, _ parsed: Address?) -> Address? {
        guard eligible(query, parsed), let l = language, let m = LocalAI.shared.model, m.available,
              ["ready","loading","stopped"].contains(m.status()["state"] as? String ?? ""),
              capacity.wait(timeout: .now()) == .success else { return nil }
        let end = DispatchTime.now() + 60, done = DispatchSemaphore(value: 0)
        let result = Locked<Address?>(nil)
        DispatchQueue.global(qos: .userInitiated).async {
            defer { capacity.signal(); done.signal() }
            let expired = { DispatchTime.now() >= end }
            guard m.ensureRunning(onWait: { _ in }, cancelled: expired) == nil, !expired() else { return }
            let msgs: [Rec] = [["role":"system","content":l.prompt],["role":"user","content":query]]
            var text = ""
            guard (try? m.generate(segments: GemmaPrompt.render(msgs, tools: []), maxTokens: 144, onlyIfIdle: true,
                                         cancelled: expired, piece: { text += $0 })) != nil,
                  let a = extract(GemmaPrompt.stripThinking(text)) else { return }
            result.value = validated(query, a, parsed)
        }
        guard done.wait(timeout: end) == .success else { return nil }
        return result.value
    }
    static func description(_ a: Address) -> String {
        ["PR-\(a.route)" + (a.meters.map { " km " + kilometer($0) } ?? ""), a.locality, a.postal,
         a.interior ? ("interior " + a.access).trimmingCharacters(in: .whitespaces) : "", a.lot.isEmpty ? "" : "lot " + a.lot,
         a.sector.isEmpty ? "" : "sector " + a.sector, a.landmark].filter { !$0.isEmpty }.joined(separator: ", ")
    }
}
