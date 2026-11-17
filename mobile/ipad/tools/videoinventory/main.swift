import AVFoundation
import Foundation

// Read-only inventory of a library's catalog videos, with AVFoundation (as tools/videocompat decides AV1):
//   videoinventory LIBRARY_DATA > out.tsv
// Columns: id, path, bytes, video fourcc, audio fourcc, duration s, width, height, video data rate b/s.
// Order follows the catalog after a sort (sort the TSV if order matters).
func fourcc(_ f: FourCharCode) -> String {
    let b = [UInt8((f >> 24) & 255), UInt8((f >> 16) & 255), UInt8((f >> 8) & 255), UInt8(f & 255)]
    return String(bytes: b, encoding: .ascii)?.trimmingCharacters(in: .whitespaces) ?? "\(f)"
}
let lib = URL(fileURLWithPath: CommandLine.arguments[1])
let cat = try JSONSerialization.jsonObject(with: Data(contentsOf: lib.appendingPathComponent("catalog.json"))) as! [[String: Any]]
let vids = cat.filter { ($0["kind"] as? String) == "video" }.compactMap { r -> (String, String)? in
    guard let id = r["id"] as? String, let p = r["path"] as? String else { return nil }
    return (id, p)
}

func row(_ id: String, _ rel: String) async -> String {
    let u = lib.appendingPathComponent(rel)
    guard let attrs = try? FileManager.default.attributesOfItem(atPath: u.path) else { return "\(id)\t\(rel)\t-1\tMISSING\t-\t0\t0\t0\t0" }
    let bytes = (attrs[.size] as? Int64) ?? -1
    let a = AVURLAsset(url: u)
    var vc = "-", ac = "-", w = 0, h = 0, rate: Float = 0, d = 0.0
    do {
        if let v = try await a.loadTracks(withMediaType: .video).first {
            vc = (try await v.load(.formatDescriptions)).first.map { fourcc(CMFormatDescriptionGetMediaSubType($0)) } ?? "?"
            let s = try await v.load(.naturalSize); w = Int(s.width); h = Int(s.height)
            rate = try await v.load(.estimatedDataRate)
        }
        if let t = try await a.loadTracks(withMediaType: .audio).first {
            ac = (try await t.load(.formatDescriptions)).first.map { fourcc(CMFormatDescriptionGetMediaSubType($0)) } ?? "?"
        }
        d = try await a.load(.duration).seconds
    } catch { vc = "ERROR:\(error.localizedDescription)" }
    return "\(id)\t\(rel)\t\(bytes)\t\(vc)\t\(ac)\t\(String(format: "%.3f", d))\t\(w)\t\(h)\t\(Int(rate))"
}

print(["id", "path", "bytes", "video", "audio", "duration", "width", "height", "video_rate"].joined(separator: "\t"))
await withTaskGroup(of: String.self) { g in
    var running = 0
    for (id, rel) in vids {
        if running >= 16, let s = await g.next() { print(s); running -= 1 }
        running += 1
        g.addTask { await row(id, rel) }
    }
    for await s in g { print(s) }
}
