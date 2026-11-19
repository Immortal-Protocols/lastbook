import Foundation

/// Compare one complete direction with one public permit in its verified municipio.
enum PuertoRicoPermits {
    struct Grammar: Decodable {
        let prefix: String, postal: String, literal: String
        let intro, aliases: [[String]]
    }
    static let grammar: Grammar? = {
        let url = Resources.url("web").appendingPathComponent("pr-permit-language.json")
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(Grammar.self, from: data)
    }()
    static let numbers: [String:String] = {
        guard let lang = PuertoRicoModel.language else { return [:] }
        return Dictionary(uniqueKeysWithValues: (0..<10000).map { (PuertoRicoModel.spelled($0,true,lang),String($0)) })
    }()
    static let spokenPattern: String = {
        var words = Set(numbers.keys.flatMap { $0.components(separatedBy:" ") })
        words.insert("punto")
        let token = "(?:" + words.sorted().joined(separator:"|") + #"|\d+)\b"#
        return #"\b(kilometros?|km|carretera|por la|solar|lote|parcela|calle|edificio) ("# + token + "(?: " + token + "){0,14})"
    }()
    static func numeral(_ phrase: String, grouped: Bool) -> String? {
        if phrase.fullMatch("[0-9]+") { return phrase }
        if let n = numbers[phrase] { return n }
        let words = phrase.split(separator:" ").map(String.init)
        let digits = words.compactMap { numbers[$0] }
        if !words.isEmpty && digits.count == words.count && digits.allSatisfy({ $0.count == 1 }) { return digits.joined() }
        guard grouped && words.count > 1 else { return nil }
        var forms = Set<String>()
        for i in 1..<words.count {
            if let a = numbers[words.prefix(i).joined(separator:" ")], let b = numbers[words.dropFirst(i).joined(separator:" ")] {
                forms.insert(a + b)
            }
        }
        return forms.count == 1 ? forms.first : nil
    }
    static let trim = CharacterSet(charactersIn: " ,;.")
    static let barrioLabel = #"^(?:bo|barr|barrio)\b\.?\s*"#
    static func plain(_ text: String) -> String {
        text.folding(options: .diacriticInsensitive, locale: Locale(identifier:"en_US_POSIX"))
            .lowercased().replacing(#"\s+"#, with:" ").trimmingCharacters(in:trim)
    }
    // Apply computed replacements to the original capture ranges, from the end.
    static func rewrite(_ text: String, _ pattern: String, _ replacement: ([String]) -> String) -> String {
        guard let rx = try? NSRegularExpression(pattern:pattern) else { return text }
        let input = text as NSString, out = NSMutableString(string:text)
        for match in rx.matches(in:text, range:NSRange(location:0,length:input.length)).reversed() {
            let groups = (0..<match.numberOfRanges).map { i in
                match.range(at:i).location == NSNotFound ? "" : input.substring(with:match.range(at:i))
            }
            out.replaceCharacters(in:match.range, with:replacement(groups))
        }
        return out as String
    }
    static func townField(_ town: String) -> String {
        #"(?:^|[,;]\s*|\ben (?:el municipio de )?)(?:municipio de )?"#
            + NSRegularExpression.escapedPattern(for:town) + #"(?=\s*(?:[,;.]|$))"#
    }
    static func signature(_ text: String, _ town: String, locality: Bool = false) -> (String,String)? {
        guard let g = grammar else { return nil }
        var raw = plain(text).replacing(g.prefix,with:"")
        let zips = raw.allMatches(g.postal)
        guard zips.count <= 1 else { return nil }
        let postal = zips.first?.replacing("[^0-9]",with:"") ?? ""
        raw = raw.replacing(g.postal,with:",")
        guard let rx = try? NSRegularExpression(pattern:townField(town)),
              let m = rx.firstMatch(in:raw,range:NSRange(raw.startIndex...,in:raw)),
              let range = Range(m.range,in:raw) else { return nil }
        raw.replaceSubrange(range,with:",")
        raw = raw.trimmingCharacters(in:trim)
        guard !raw.isEmpty && !raw.contains("|") else { return nil }
        let literal = ("literal " + raw,postal)
        if raw.firstMatch(g.literal) != nil { return literal }
        for rule in g.intro { raw = raw.replacing(rule[0],with:rule[1]) }
        raw = rewrite(raw,spokenPattern) { m in
            let label = m[1] == "por la" ? "carretera" : m[1]
            let parts = m[2].components(separatedBy:" punto ")
            guard let n = numeral(parts[0],grouped:label == "carretera") else { return m[0] }
            if parts.count == 1 { return label + " " + n }
            guard parts.count == 2, ["km","kilometro","kilometros"].contains(label),
                  let decimal = numeral(parts[1],grouped:false) else { return m[0] }
            return label + " " + n + "." + decimal
        }
        for rule in g.aliases { raw = raw.replacing(rule[0],with:rule[1]) }
        raw = rewrite(raw,#"\|(km|road) (\d+)(?:[.,](\d+))?(?!\d)"#) { m in
            let frac = m[3].replacing("0+$",with:"")
            return "|" + m[1] + " " + m[2] + (frac.isEmpty ? "" : "." + frac) + "|"
        }
        let parts = raw.components(separatedBy:CharacterSet(charactersIn:"|,;"))
            .map { $0.split(whereSeparator:{ $0.isWhitespace }).joined(separator:" ") }.filter { !$0.isEmpty }
        let labels = parts.map { String($0.prefix(while:{ $0 != " " })) }
        let allowed = Set(["km","road","barrio","sector","interior","solar","parcela","urbanizacion","comunidad","calle","camino","edificio"])
        let fields = Set(labels)
        if locality, !fields.isDisjoint(with:["barrio","sector","urbanizacion","comunidad"]),
           !fields.contains("road"), !fields.contains("km"), fields.isSubset(of:allowed),
           fields.count == labels.count, parts.allSatisfy({ $0.contains(" ") }) {
            return ("locality " + parts.sorted().joined(separator:"|"),postal)
        }
        guard labels.contains("road"), labels.contains("km"), Set(labels).count == labels.count,
              Set(labels).isSubset(of:allowed) else { return literal }
        return ("parts " + parts.sorted().joined(separator:"|"),postal)
    }
    static func namesPlace(_ text: String, _ town: String, _ places: [[String: Any]]) -> Bool {
        var names = Set<String>()
        for place in places {
            let detail = plain(place["detail"] as? String ?? "")
            guard detail.firstMatch(#"(?<!\w)"# + NSRegularExpression.escapedPattern(for:town) + #"(?!\w)"#) != nil else { continue }
            let parts = detail.components(separatedBy:",")
            if parts.count > 1, !["puerto rico","pr"].contains(parts.last!.trimmingCharacters(in:.whitespaces)) { continue }
            let name = plain(place["name"] as? String ?? "")
            names.formUnion([name,name.replacing(barrioLabel,with:"")])
        }
        guard !names.isEmpty, let g = grammar else { return false }
        var raw = text.replacing(g.prefix,with:"").replacing(g.postal,with:",")
        guard let rx = try? NSRegularExpression(pattern:townField(town)),
              let m = rx.firstMatch(in:raw,range:NSRange(raw.startIndex...,in:raw)),
              let range = Range(m.range,in:raw) else { return false }
        raw.replaceSubrange(range,with:",")
        raw = raw.trimmingCharacters(in:trim).replacing(barrioLabel,with:"")
        return names.contains(raw)
    }
    typealias Evidence = (source:String, wording:String)
    static func fieldKey(_ signature: String) -> String {
        signature.trimmingCharacters(in:CharacterSet(charactersIn:" ."))
            .replacingOccurrences(of:" .|",with:"|").replacingOccurrences(of:".|",with:"|")
    }
    static func matches(_ query: String, _ db: SQLiteDB, namedPlaces: [[String: Any]] = []) -> [String:Evidence] {
        guard db.one("SELECT 1 FROM sqlite_master WHERE name='pr_permit_wording'") != nil else { return [:] }
        let text = plain(query)
        var result = [String:Evidence]()
        let verbatim = db.one("SELECT 1 FROM sqlite_master WHERE name='pr_local_verbatim'") != nil
        let fields = db.one("SELECT 1 FROM sqlite_master WHERE name='pr_permit_fields'") != nil
        for row in db.query("SELECT name FROM municipios ORDER BY name") {
            guard let name = row["name"]?.text else { continue }
            let town = plain(name)
            guard text.contains(town) else { continue }
            // Compare complete place names before interpreting words such as Camino as address labels.
            if namesPlace(text,town,namedPlaces) { continue }
            if verbatim {
                let raw = query.trimmingCharacters(in:.whitespacesAndNewlines)
                var withoutTown = raw
                if let delimiter = raw.lastIndex(where: { $0 == "," || $0 == ";" }),
                   plain(String(raw[raw.index(after:delimiter)...])) == town {
                    withoutTown = String(raw[..<delimiter]).trimmingCharacters(in:.whitespacesAndNewlines)
                }
                let exact = db.query("""
                    SELECT base,source,wording FROM pr_permit_wording WHERE town=? AND source IN ('CRIM','JP consulta')
                    AND wording COLLATE NOCASE IN (?,?) ORDER BY base,source,wording
                    """, [town,raw,withoutTown])
                for r in exact {
                    if let base = r["base"]?.text, result[base] == nil,
                       let source = r["source"]?.text, let wording = r["wording"]?.text {
                        result[base] = (source,wording)
                    }
                }
            }
            guard let (key,postal) = signature(text,town) else { continue }
            var keys = [key]
            if key.hasPrefix("literal "), let (other,_) = signature(text,town,locality:true), other != key {
                keys.append(other)
            }
            for key in keys {
                let rows = db.query("""
                    SELECT base,source,wording FROM pr_permit_wording
                    WHERE town=? AND signature=? AND (?='' OR substr(postal,1,length(?))=?)
                    ORDER BY base,source,wording
                    """, [town,key,postal,postal,postal])
                for r in rows {
                    if let base = r["base"]?.text, result[base] == nil,
                       let source = r["source"]?.text, let wording = r["wording"]?.text {
                        result[base] = (source,wording)
                    }
                }
                if fields && (key.hasPrefix("parts ") || key.hasPrefix("locality ")) {
                    let rows = db.query("""
                        SELECT base,source,wording FROM pr_permit_wording WHERE town=?
                        AND (signature GLOB 'parts *' OR signature GLOB 'locality *')
                        AND replace(replace(rtrim(signature,' .'),' .|','|'),'.|','|')=?
                        AND (?='' OR substr(postal,1,length(?))=?) ORDER BY base,source,wording
                        """, [town,fieldKey(key),postal,postal,postal])
                    for r in rows {
                        if let base = r["base"]?.text, result[base] == nil,
                           let source = r["source"]?.text, let wording = r["wording"]?.text {
                            result[base] = (source,wording)
                        }
                    }
                }
            }
        }
        return result
    }
}
