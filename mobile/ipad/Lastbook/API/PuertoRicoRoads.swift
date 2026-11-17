import Foundation

/// Mirrors engine/pr_rural.py. All input and map coordinates stay on the device.
enum PuertoRicoRoads {
    struct Address {
        let route: Int, meters: Int, locality: String, postal: String, interior: Bool, sector: String, landmark: String
    }
    static let km = #"(?<![a-z])(?:kilometros?|kilometers?|kilometres?|kms?|k\s*\.\s*m)\.?\s*#?\s*(\d{1,3}(?:[.,]\d{1,3})?)(?![\d.,]\d|\d)"#
    static let hm = #"(?<![a-z])(?:hectometros?|hectometers?|h\s*\.?\s*m)\.?\s*(\d)(?!\d)"#
    static let road = #"(?<![a-z0-9])(?:(?:carreteras?|carret|carr?|crta|ctra|crr|ruta|rta|route|rte|ramal|state (?:road|highway)|road|rd|highway|hwy)\.?\s*(?:estatal\s+)?(?:p\.?\s*r\.?\s*)?|p\.?\s*r\.?\s*)[-#\s]*(\d{1,4})(?![a-z0-9])"#
    static let zip = #"(?<!\d)(\d{5})(?:-\d{4})?(?!\d)"#
    static let sector = #"\b(?:sector|sect|sec|comunidad|com)\.?\s+([^,;\n]+?)(?=[,;\n]|\b(?:barrio|municipio)\b|$)"#
    static let landmark = #"\b(?:frente a|al lado de|detras de|junto a|cerca de)\s+([^,;\n]+?)(?=[,;\n]|\b(?:barrio|municipio|sector)\b|$)"#
    private static func fold(_ text: String) -> String {
        text.folding(options: .diacriticInsensitive, locale: Locale(identifier: "en_US_POSIX"))
            .lowercased().allMatches("[a-z0-9]+").joined(separator: " ")
    }
    private static func values(_ text: String, _ pattern: String) -> [String] {
        guard let rx = try? NSRegularExpression(pattern: pattern) else { return [] }
        return rx.matches(in: text, range: NSRange(text.startIndex..., in: text)).compactMap { match in
            Range(match.range(at: 1), in: text).map { String(text[$0]) }
        }
    }
    static func looksRural(_ query: String) -> Bool {
        let words = query.folding(options: .diacriticInsensitive, locale: Locale(identifier: "en_US_POSIX")).lowercased()
        return words.firstMatch(#"(?<![a-z])(?:k\.?\s*m\.?s?|kilometr(?:os?|es?|ers?))(?=\W|\d|$)|\d[.,]\d+\s+(?:de la\s+)?(?:carr(?:etera)?|pr[- ])"#) != nil
    }
    static func parse(_ query: String) -> Address? {
        var text = query.folding(options: .diacriticInsensitive, locale: Locale(identifier: "en_US_POSIX")).lowercased()
        guard text.firstMatch(#"\b(?:casa|solar|lote|lot|apto|apt|apartamento|box)\s*#?\s*\d"#) == nil else { return nil }
        text = text.replacing(#"^\s*(\d{1,3}[.,]\d{1,3})(?=\s+(?:carr(?:etera)?\.?|pr[- ])\s*[-#]?\s*\d)"#, with: "km $1")
            .replacing(#"\b(\d{1,4})\s+(?:state road|rural street)\b"#, with: "pr-$1")
            .replacing(#"(?:^|,\s*)([^,;\d]+?)\s+sector(?=\s*,|$)"#, with: ", sector $1")
        let namedPattern = #"\b(?:esq(?:uina)?\.?\s+(?:carr(?:etera)?|pr)[.\s#-]*\d{1,4}|parque industrial)\b|(?:^|(?<=,))\s*[^,;\d]*?\bshopping cent(?:er|re)\b"#
        let named = text.firstMatch(namedPattern) ?? ""
        text = text.replacing(namedPattern, with: ",")
        text = text.replacing(#"\b(km|hm)\.?\s+o\b"#, with: "$1 0")
        let markers = values(text, km)
        guard markers.count == 1 else { return nil }
        let value = markers[0].replacingOccurrences(of: ",", with: ".").components(separatedBy: ".")
        guard let whole = Int(value[0]) else { return nil }
        var meters = whole * 1000 + (Int(((value.count == 2 ? value[1] : "") + "000").prefix(3)) ?? 0)
        text = text.replacing(km, with: ",")
        let hectos = values(text, hm)
        if !hectos.isEmpty {
            guard hectos.count == 1, value.count == 1, let digit = Int(hectos[0]) else { return nil }
            meters += digit * 100
            text = text.replacing(hm, with: ",")
        }
        guard text.firstMatch(#"\b(?:hm|hectometros?)\b"#) == nil else { return nil }
        let codes = values(text, zip)
        guard codes.count <= 1 else { return nil }
        text = text.replacing(zip, with: " ")
        let pattern = values(text, road).isEmpty ? #"(?<![a-z0-9])(\d{1,4})(?![a-z0-9])"# : road
        let routes = values(text, pattern)
        guard routes.count == 1, let route = Int(routes[0]) else { return nil }
        text = text.replacing(pattern, with: ",")
        let interior = text.firstMatch(#"\b(?:int|interior)\b"#) != nil
        text = text.replacing(#"\b(?:int|interior|puerto rico|pr|blvd|ward)\b"#, with: " ")
            .replacing(#"\bb[º°]|\b(?:bo|barr|brrio)\b\.?"#, with: " barrio ")
            .replacing(#"\b(?:mun|mpio|municipality)\.?\b"#, with: "municipio")
        let hint = text.firstMatch(landmark) ?? ""
        text = text.replacing(landmark, with: " ")
        let area = values(text, sector).first ?? ""
        text = text.replacing(sector, with: " ")
        return Address(route: route, meters: meters, locality: fold(text), postal: codes.first ?? "", interior: interior,
                       sector: fold(area), landmark: fold(named + " " + hint))
    }

    private static func matches(_ locality: String, _ barrio: String, _ town: String) -> Bool {
        if locality.isEmpty { return true }
        var aliases = [fold(barrio)]
        if barrio.hasSuffix(" barrio-pueblo") {
            aliases += ["pueblo", fold(String(barrio.dropLast(" barrio-pueblo".count))) + " pueblo"]
        }
        for b in [""] + aliases.flatMap({ [$0, "barrio " + $0] }) {
            for m in ["", fold(town), "municipio " + fold(town)] {
                if [[b, m], [m, b]].contains(where: { $0.filter { !$0.isEmpty }.joined(separator: " ") == locality }) { return true }
            }
        }
        return false
    }

    static func find(_ a: Address, _ db: SQLiteDB, _ limit: Int) -> [[String: Any]] {
        guard limit > 0, !db.query("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pr_road'").isEmpty else { return [] }
        let rows = db.query("""
            SELECT low,high,lat0,lon0,lat1,lon1,barrio,municipio,zip FROM pr_road r JOIN pr_area a ON a.id=r.area
            WHERE route=? AND bucket=? AND low<=? AND high>=? ORDER BY r.rowid
            """, [a.route, a.meters / 1000, a.meters, a.meters])
        let kmText = String(format: "%.3f", locale: Locale(identifier: "en_US_POSIX"), Double(a.meters) / 1000)
            .replacing("0+$", with: "").replacing(#"\.$"#, with: "")
        var results: [[String: Any]] = []
        for r in rows {
            let b = r["barrio"]?.text ?? "", town = r["municipio"]?.text ?? ""
            guard (a.postal.isEmpty || a.postal == r["zip"]?.text), matches(a.locality, b, town),
                  let low = r["low"]?.double, let high = r["high"]?.double, high > low,
                  let y0 = r["lat0"]?.double, let y1 = r["lat1"]?.double, let x0 = r["lon0"]?.double, let x1 = r["lon1"]?.double else { continue }
            let t = (Double(a.meters) - low) / (high - low), lat = y0 + t * (y1-y0), lon = x0 + t * (x1-x0)
            if results.contains(where: { abs(($0["lat"] as? Double ?? 0) - lat) < 0.0005 && abs(($0["lon"] as? Double ?? 0) - lon) < 0.0005 }) { continue }
            var detail = [b.isEmpty ? "" : "Bo. " + b, town, "PR"].filter { !$0.isEmpty }.joined(separator: ", ") + " · Approximate position on the road."
            if a.interior { detail += " Interior access is unverified." }
            if !a.sector.isEmpty { detail += " Sector directions are unverified." }
            if !a.landmark.isEmpty { detail += " Landmark directions are unverified." }
            results.append(["name": "PR-\(a.route) km \(kmText)", "kind": "Road kilometer", "detail": detail,
                            "lat": (lat * 1e6).rounded() / 1e6, "lon": (lon * 1e6).rounded() / 1e6, "source": "FHWA HPMS", "onMap": true])
            if results.count == limit { return results }
        }
        let schools = db.query("""
            SELECT name,street,lat,lon,barrio,municipio,postal,reported_city FROM pr_school s JOIN pr_area a ON a.id=s.area
            WHERE route=? AND meters=? ORDER BY name,s.rowid
            """, [a.route, a.meters])
        for r in schools {
            let street = r["street"]?.text ?? "", town = r["municipio"]?.text ?? ""
            let barrio = r["barrio"]?.text ?? "", city = r["reported_city"]?.text ?? "", recorded = parse(street)
            let words = " " + fold(street) + " "
            guard let lat = r["lat"]?.double, let lon = r["lon"]?.double,
                  (a.postal.isEmpty || a.postal == r["postal"]?.text),
                  matches(a.locality, barrio, town) || matches(a.locality, barrio, city) || (recorded.map { matches(a.locality, $0.locality.replacing("^barrio ", with: ""), city) } ?? false),
                  a.sector.isEmpty || words.contains(" " + a.sector + " "),
                  a.landmark.isEmpty || words.contains(" " + a.landmark + " "),
                  !a.interior || fold(street).firstMatch(#"\b(?:interior|int)\b"#) != nil else { continue }
            results.append(["name": r["name"]?.text ?? "", "kind": "Public school", "detail": street + ", " + town + ", PR",
                            "lat": lat, "lon": lon, "source": "NCES EDGE", "onMap": true])
            if results.count == limit { break }
        }
        return results
    }
}
