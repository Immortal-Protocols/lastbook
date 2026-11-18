import Foundation

/// Offline Puerto Rico land boundaries and recorded address candidates.
enum PuertoRicoParcels {
    static func number(_ text: String) -> String? {
        let value = PuertoRicoModel.plain(text).trimmingCharacters(in: .whitespacesAndNewlines)
            .replacing(#"^(?:(?:n(?:umero|um|o)\.?\s*(?:de\s+)?)?(?:catastro|crim|parcel(?:a)?(?:\s+(?:id|number))?)\s*[:#]?\s*)"#, with: "")
        if value.fullMatch(#"[0-9]{11}(?:[0-9]{3})?"#) { return value }
        guard value.fullMatch(#"[0-9]{3}-[0-9]{3}-[0-9]{3}-[0-9]{2}(?:-(?:[0-9]{3}|0{1,2}))?"#) else { return nil }
        var groups = value.components(separatedBy: "-")
        if groups.count == 5 && groups[4].count < 3 { groups[4] = "000" }
        return groups.joined()
    }
    static func display(_ key: String) -> String {
        key.replacing(#"^(\d{3})(\d{3})(\d{3})(\d{2})(\d{3})?$"#, with: "$1-$2-$3-$4-$5")
            .trimmingCharacters(in: CharacterSet(charactersIn: "-"))
    }
    static func outline(_ db: SQLiteDB, _ base: String) -> Rec? {
        let rows = db.query("SELECT barrio,municipio,lat,lon,rings FROM pr_parcel WHERE base=? ORDER BY area DESC,id", [base])
        guard let first = rows.first, let lat = first["lat"]?.double, let lon = first["lon"]?.double else { return nil }
        var rings: [[[Double]]] = []
        for row in rows {
            guard let s = row["rings"]?.text, let part = try? JSONDecoder().decode([[[Double]]].self, from: Data(s.utf8)) else { return nil }
            rings.append(contentsOf: part)
        }
        let barrio = first["barrio"]?.text ?? "", muni = first["municipio"]?.text ?? ""
        let detail = [barrio.isEmpty ? "" : "Bo. " + barrio, muni, "PR"].filter { !$0.isEmpty }.joined(separator: ", ")
        return ["name":display(base), "parcelNumber":display(base), "kind":"CRIM parcel", "lat":lat, "lon":lon,
                "detail":detail, "rings":rings, "source":"CRIM / Junta de Planificación", "onMap":true]
    }
    static func byNumber(_ db: SQLiteDB, _ key: String) -> [Rec] {
        let account = key.count == 14 && !key.hasSuffix("000")
        if account && db.one("SELECT 1 FROM pr_account WHERE number=?", [key]) == nil { return [] }
        guard var item = outline(db, String(key.prefix(11))) else { return [] }
        item["name"] = display(key)
        if account { item["detail"] = (item["detail"] as? String ?? "") + " · Recorded account on this land parcel." }
        return [item]
    }
    static func find(_ a: PuertoRicoRoads.Address, _ db: SQLiteDB, limit: Int, offset: Int) -> [Rec] {
        let rows = db.query("""
            SELECT DISTINCT a.base,a.meters,a.lot,a.sector,a.interior,a.access,a.source,p.barrio,p.municipio
            FROM pr_parcel_address a JOIN pr_parcel p ON p.base=a.base
            WHERE a.route=? AND (a.meters=? OR (a.meters IS NULL AND ?) OR ? IS NULL)
            AND (?='' OR a.lot=?) AND (?='' OR a.sector=?) AND (?=0 OR a.interior=1)
            AND (?='' OR a.access=?) AND (?='' OR COALESCE(NULLIF(a.postal,''),p.zip)=?)
            AND (?='' OR instr(' ' || a.landmark || ' ', ' ' || ? || ' ')>0)
            ORDER BY a.meters IS NULL,a.source!='CRIM',
              ((a.lot!='')+(a.sector!='')+a.interior+(a.access!='')) DESC,a.source,a.meters,a.lot,a.sector,a.interior,a.access
            """, [a.route,a.meters,!a.locality.isEmpty || !a.lot.isEmpty || !a.sector.isEmpty,a.meters,a.lot,a.lot,
                  a.sector,a.sector,a.interior,a.access,a.access,a.postal,a.postal,a.landmark,a.landmark])
        var best = [String:SQLiteDB.Row]()
        for row in rows {
            guard let base = row["base"]?.text, best[base] == nil,
                  PuertoRicoRoads.matches(a.locality,row["barrio"]?.text ?? "",row["municipio"]?.text ?? "") else { continue }
            best[base] = row
        }
        let keys = best.keys.sorted {
            let x = best[$0]?["meters"]?.int != nil, y = best[$1]?["meters"]?.int != nil
            return x == y ? $0 < $1 : x
        }
        return keys.dropFirst(min(keys.count, max(0,offset))).prefix(limit).compactMap { base in
            guard let r = best[base], var item = outline(db,base) else { return nil }
            let km = r["meters"]?.int.map { PuertoRicoModel.kilometer(Int($0)) }
            let lot = r["lot"]?.text ?? "", sector = r["sector"]?.text ?? "", access = r["access"]?.text ?? ""
            let road = "PR-\(a.route)" + (km.map { " km " + $0 } ?? "")
            let qualifiers = [lot.isEmpty ? "" : "Solar " + lot.uppercased(), sector.isEmpty ? "" : "Sector " + sector,
                              r["interior"]?.int == 1 ? ("Interior " + access).trimmingCharacters(in: .whitespaces) : ""]
                .filter { !$0.isEmpty }
            item["name"] = (qualifiers.first.map { $0 + " · " } ?? "") + road
            item["kind"] = "Possible parcel"
            item["parcelCount"] = keys.count
            let detail = [qualifiers.dropFirst().joined(separator: ", "), item["detail"] as? String ?? "",
                          km == nil ? "km unrecorded" : "", r["source"]?.text ?? ""]
            item["detail"] = detail.filter { !$0.isEmpty }.joined(separator: " · ")
            return item
        }
    }
}
