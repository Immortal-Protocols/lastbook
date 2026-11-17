import Foundation
#if canImport(VideoToolbox) && canImport(AVFoundation)
import AVFoundation
import VideoToolbox
#endif

/// Which video file to give the player: the original, or its H.264 sidecar copy.
///
/// Originals in AV1 (`av01`) or VP9 (`vp09`) may not play on a given iPad. A physical M1 iPad Pro reports AV1 as "playable"
/// and readyToPlay, yet decodes zero frames (physical test, November 2026). So each codec is decided
/// by the decoder itself: VideoToolbox hardware support for that codec, then one frame actually decoded from one of the
/// library's own files in that codec. Never a list of device names, never AVAsset.isPlayable, and no assumption about which
/// iPads have which decoder: AV1 and VP9 are each checked on this iPad.
///
/// Sidecar: LastbookData/derived/video-compat/h264-v1/manifest.json (built by tools/videocompat from the same library),
/// mapping each original's library path to its H.264 file, with the original's codec (`source_video`). The original's
/// address is answered with the copy, so the video keeps its id, row, captions, transcript links and seeking.
final class VideoCompat: @unchecked Sendable {
    static let shared = VideoCompat()
    static let version = "h264-v1"
    /// Codecs that get copies when this iPad can't decode them.
    static let handled = ["av01", "vp09"]

    struct Variant { let file: URL; let bytes: Int64; let sha256: String; let sourceBytes: Int64; let sourceCodec: String }

    private let lock = NSLock()
    private var loadedFor: String?
    private var variants: [String: Variant] = [:]          // library-data relative path -> variant

    /// Per codec, nil until decided; true when this iPad decodes that codec itself.
    private var decodes: [String: Bool] = [:]
    var av1Decodes: Bool? { decideLock.withLock { decodes["av01"] } }

    func reset() { lock.withLock { loadedFor = nil; variants = [:]; coverageFor = nil } }

    private func ensure() {
        lock.lock(); defer { lock.unlock() }
        guard let root = Library.shared.root else { variants = [:]; loadedFor = nil; return }
        if loadedFor == root.path { return }
        loadedFor = root.path
        variants = [:]
        let dir = root.appendingPathComponent("derived/video-compat/\(Self.version)")
        guard let d = try? Data(contentsOf: dir.appendingPathComponent("manifest.json")),
              let m = try? JSONSerialization.jsonObject(with: d) as? Rec, m.s("version") == Self.version,
              let items = m["items"] as? [String: Rec] else { return }
        for (src, it) in items {
            // Only a plain file name inside the sidecar folder; a manifest can never point elsewhere.
            let name = it.s("file"), codec = it.s("source_video")
            guard !name.isEmpty, !name.contains("/"), !name.hasPrefix("."), it.s("video") == "avc1", Self.handled.contains(codec) else { continue }
            let f = dir.appendingPathComponent(name)
            guard let size = (try? FileManager.default.attributesOfItem(atPath: f.path)[.size] as? NSNumber)?.int64Value,
                  size == Int64(it.d("bytes")) else { continue }   // a missing or partial copy is never served
            variants[src] = Variant(file: f, bytes: size, sha256: it.s("sha256"), sourceBytes: Int64(it.d("source_bytes")), sourceCodec: codec)
        }
    }

    /// The file to serve for a library video path, or nil to serve the original.
    func substitute(_ rel: String) -> URL? {
        ensure()
        guard let v = lock.withLock({ variants[rel] }) else { return nil }
        return decides(v.sourceCodec) ? nil : v.file
    }

    /// Whether this iPad needs H.264 copies for this library (for readiness, and so copies are never downloaded needlessly):
    /// it can't decode AV1, or the library has VP9 videos and it can't decode VP9.
    var needsH264: Bool {
        if !decides("av01") { return true }
        return codecsPresent().contains("vp09") && !decides("vp09")
    }

    func variantCount() -> (count: Int, bytes: Int64) {
        ensure()
        return lock.withLock { (variants.count, variants.values.reduce(0) { $0 + $1.bytes }) }
    }

    /// (videos this iPad can't play as they are, how many of those have no usable copy). Codecs are read from each video's
    /// own track, once per library. (Tuple labels kept from the AV1-only version; `av1` now counts AV1 and VP9 alike.)
    private var coverageFor: String?, coverageCache = (0, 0), codecCache: [String: String] = [:]
    func coverage() -> (av1: Int, missing: Int) {
        ensure()
        guard let lib = Library.shared.lib else { return (0, 0) }
        if let c = lock.withLock({ coverageFor == lib.path ? coverageCache : nil }) { return c }
        let codecs = scanCodecs(lib)
        var need = 0, missing = 0
        for (rel, codec) in codecs where Self.handled.contains(codec) && !decides(codec) {
            need += 1
            if lock.withLock({ variants[rel] }) == nil { missing += 1 }
        }
        lock.withLock { coverageFor = lib.path; coverageCache = (need, missing) }
        return (need, missing)
    }

    /// Codecs of the library's local videos (AV1 / VP9 only matter here), from the sidecar manifest and the files themselves.
    func codecsPresent() -> Set<String> {
        ensure()
        var s = Set(lock.withLock { variants.values.map(\.sourceCodec) })
        if let lib = Library.shared.lib { s.formUnion(scanCodecs(lib).values) }
        return s
    }

    private var codecsFor: String?
    private func scanCodecs(_ lib: URL) -> [String: String] {
        if let c = lock.withLock({ codecsFor == lib.path ? codecCache : nil }) { return c }
        var out: [String: String] = [:]
        for r in Catalog.shared.records where r.s("kind") == "video" {
            let rel = r.s("path"), f = lib.appendingPathComponent(rel)
            guard FileManager.default.fileExists(atPath: f.path), let c = Self.codec(f) else { continue }
            out[rel] = c
        }
        lock.withLock { codecsFor = lib.path; codecCache = out }
        return out
    }

    static func codec(_ url: URL) -> String? {
        #if canImport(AVFoundation)
        let sem = DispatchSemaphore(value: 0)
        var code: String?
        Task.detached {
            defer { sem.signal() }
            if let t = try? await AVURLAsset(url: url).loadTracks(withMediaType: .video).first,
               let fd = try? await t.load(.formatDescriptions).first {
                switch CMFormatDescriptionGetMediaSubType(fd) {
                case kCMVideoCodecType_AV1: code = "av01"
                case kCMVideoCodecType_VP9: code = "vp09"
                case kCMVideoCodecType_H264: code = "avc1"
                case kCMVideoCodecType_HEVC: code = "hvc1"
                default: code = "other"
                }
            }
        }
        _ = sem.wait(timeout: .now() + 10)
        return code
        #else
        return nil
        #endif
    }

    static func isAV1(_ url: URL) -> Bool { codec(url) == "av01" }

    // ------------------------------------------------------------ capability --
    private let decideLock = NSLock()
    private static func cacheKey(_ codec: String) -> String { codec == "av01" ? "lastbook.av1.decodes" : "lastbook.\(codec).decodes" }

    /// AV1 decision, kept for callers from the AV1-only version (launch warm-up).
    @discardableResult
    func decidesAV1() -> Bool { decides("av01") }

    /// Decided once per OS build per codec (a system update can add a decoder), then remembered.
    @discardableResult
    func decides(_ codec: String) -> Bool {
        guard Self.handled.contains(codec) else { return true }
        decideLock.lock(); defer { decideLock.unlock() }
        if let v = decodes[codec] { return v }
        let build = Self.osBuild()
        if let c = UserDefaults.standard.dictionary(forKey: Self.cacheKey(codec)), c["build"] as? String == build, let ok = c["ok"] as? Bool {
            decodes[codec] = ok
            return ok
        }
        let ok = Self.probe(codec, sample: firstOriginal(codec))
        decodes[codec] = ok
        UserDefaults.standard.set(["build": build, "ok": ok], forKey: Self.cacheKey(codec))
        NSLog("Lastbook: %@ decode on this device: %@", codec == "av01" ? "AV1" : "VP9", ok ? "yes" : "no (H.264 copies used)")
        return ok
    }

    private func firstOriginal(_ codec: String) -> URL? {
        ensure()
        guard let lib = Library.shared.lib else { return nil }
        if let src = lock.withLock({ variants.filter { $0.value.sourceCodec == codec }.keys.sorted().first }) {
            return lib.appendingPathComponent(src)
        }
        return lock.withLock({ codecsFor == lib.path ? codecCache : nil })?.filter { $0.value == codec }.keys.sorted().first
            .map { lib.appendingPathComponent($0) }
    }

    static func osBuild() -> String {
        var size = 0
        sysctlbyname("kern.osversion", nil, &size, nil, 0)
        var b = [CChar](repeating: 0, count: max(size, 1))
        sysctlbyname("kern.osversion", &b, &size, nil, 0)
        return String(cString: b)
    }

    /// True only if the system has a hardware decoder for the codec AND it hands back a real picture from one of the library's
    /// own files in that codec. With no such file in the library there is nothing to substitute, so the answer doesn't matter.
    static func probe(_ codec: String, sample: URL?) -> Bool {
        #if canImport(VideoToolbox) && canImport(AVFoundation)
        let type: CMVideoCodecType = codec == "vp09" ? kCMVideoCodecType_VP9 : kCMVideoCodecType_AV1
        guard VTIsHardwareDecodeSupported(type) else { return false }
        guard let sample else { return true }
        return decodesOneFrame(sample)
        #else
        return false
        #endif
    }

    static func probeAV1(sample: URL?) -> Bool { probe("av01", sample: sample) }

    #if canImport(AVFoundation)
    static func decodesOneFrame(_ url: URL) -> Bool {
        let sem = DispatchSemaphore(value: 0)
        var ok = false
        Task.detached {
            defer { sem.signal() }
            let asset = AVURLAsset(url: url)
            guard let t = try? await asset.loadTracks(withMediaType: .video).first, let r = try? AVAssetReader(asset: asset) else { return }
            let out = AVAssetReaderTrackOutput(track: t, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange])
            r.add(out)
            r.timeRange = CMTimeRange(start: .zero, duration: CMTime(seconds: 2, preferredTimescale: 600))
            guard r.startReading() else { return }
            for _ in 0..<60 {   // the first decoded picture, not just a sample
                guard let s = out.copyNextSampleBuffer() else { break }
                if let px = CMSampleBufferGetImageBuffer(s), CVPixelBufferGetWidth(px) > 0 { ok = true; break }
            }
            r.cancelReading()
        }
        _ = sem.wait(timeout: .now() + 10)
        return ok
    }
    #endif
}
