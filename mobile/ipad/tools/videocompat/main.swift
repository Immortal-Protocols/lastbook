import AVFoundation
import CryptoKit
import Foundation
import VideoToolbox

// Builds H.264 MP4 versions of a library's AV1 videos for iPads that cannot decode AV1, with Apple's own decoder and
// encoder (no third-party binaries). Originals are only read. Output is a versioned sidecar, outside library-data:
//
//   videocompat LIBRARY_DATA OUT_DIR [--jobs N] [--only VIDEO_ID]
//
//   OUT_DIR/h264-v1/<video id>.mp4     one per AV1 original
//   OUT_DIR/h264-v1/manifest.json      source path -> variant, with sizes, sha256s, codecs and durations
//
// In a library the sidecar lives at LastbookData/derived/video-compat/h264-v1/. The app reads manifest.json and, on an
// iPad whose hardware cannot decode AV1, answers the original's address with the variant (same id, captions, seeking).

let VERSION = "h264-v1"

struct Item: Codable {
    var id: String
    var source: String            // path relative to library-data, as catalog.json
    var source_bytes: Int64
    var source_sha256: String
    var source_video: String      // codec four-character code
    var source_audio: String?
    var source_duration: Double
    var file: String              // relative to the manifest's folder
    var bytes: Int64
    var sha256: String
    var video: String
    var audio: String?
    var duration: Double
    var width: Int
    var height: Int
    var video_bitrate: Int
}

struct Manifest: Codable {
    var version: String
    var codec: String
    var note: String
    var source_count: Int          // videos in the catalog that are local files
    var av1_count: Int
    var items: [String: Item]      // keyed by source path
}

func fourcc(_ f: FourCharCode) -> String {
    let b = [UInt8((f >> 24) & 255), UInt8((f >> 16) & 255), UInt8((f >> 8) & 255), UInt8(f & 255)]
    return String(bytes: b, encoding: .ascii)?.trimmingCharacters(in: .whitespaces) ?? "\(f)"
}

func sha256(_ u: URL) throws -> String {
    let fh = try FileHandle(forReadingFrom: u); defer { try? fh.close() }
    var h = SHA256()
    while let d = try fh.read(upToCount: 8 << 20), !d.isEmpty { h.update(data: d) }
    return h.finalize().map { String(format: "%02x", $0) }.joined()
}

func codecs(_ asset: AVURLAsset) async throws -> (String?, String?, Double, CGSize, Float) {
    let v = try await asset.loadTracks(withMediaType: .video).first
    let a = try await asset.loadTracks(withMediaType: .audio).first
    var vc: String?, ac: String?, size = CGSize.zero, rate: Float = 0
    if let v {
        let fds = try await v.load(.formatDescriptions)
        vc = fds.first.map { fourcc(CMFormatDescriptionGetMediaSubType($0)) }
        size = try await v.load(.naturalSize)
        rate = try await v.load(.estimatedDataRate)
    }
    if let a { ac = try await a.load(.formatDescriptions).first.map { fourcc(CMFormatDescriptionGetMediaSubType($0)) } }
    let d = try await asset.load(.duration).seconds
    return (vc, ac, d, size, rate)
}

/// AV1 decode -> H.264 encode (VideoToolbox), audio passed through when it is already AAC.
func transcode(_ src: URL, _ dst: URL) async throws -> Int {
    let asset = AVURLAsset(url: src)
    guard let vt = try await asset.loadTracks(withMediaType: .video).first else { throw NSError(domain: "no video", code: 1) }
    let at = try await asset.loadTracks(withMediaType: .audio).first
    let size = try await vt.load(.naturalSize)
    let transform = try await vt.load(.preferredTransform)
    let srcRate = try await vt.load(.estimatedDataRate)
    let fps = try await vt.load(.nominalFrameRate)

    // Keep the picture size, at most 1920 on the long side; even dimensions for 4:2:0.
    let scale = min(1, 1920 / max(size.width, size.height))
    let w = Int((size.width * scale / 2).rounded()) * 2, h = Int((size.height * scale / 2).rounded()) * 2
    // H.264 needs roughly twice AV1's bits for the same look. Follow the original's own rate (many are very low), with a
    // floor so tiny ones stay watchable and a cap so large ones don't balloon.
    let bitrate = Int(min(6_000_000, max(200_000, Double(srcRate) * 2.0 * Double(scale * scale))))

    try? FileManager.default.removeItem(at: dst)
    let reader = try AVAssetReader(asset: asset)
    let writer = try AVAssetWriter(outputURL: dst, fileType: .mp4)
    writer.shouldOptimizeForNetworkUse = true   // moov first: the player can start and seek before the whole file is read

    let vOut = AVAssetReaderTrackOutput(track: vt, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange])
    vOut.alwaysCopiesSampleData = false
    reader.add(vOut)
    let keyEvery = max(1, Int((fps > 0 ? fps : 30) * 2))
    let vIn = AVAssetWriterInput(mediaType: .video, outputSettings: [
        AVVideoCodecKey: AVVideoCodecType.h264,
        AVVideoWidthKey: w, AVVideoHeightKey: h,
        AVVideoCompressionPropertiesKey: [
            AVVideoAverageBitRateKey: bitrate,
            AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
            AVVideoH264EntropyModeKey: AVVideoH264EntropyModeCABAC,
            AVVideoMaxKeyFrameIntervalKey: keyEvery,              // a keyframe at least every 2 s: seeking stays quick
            AVVideoMaxKeyFrameIntervalDurationKey: 2.0,
            AVVideoAllowFrameReorderingKey: true,
        ] as [String: Any],
    ])
    vIn.transform = transform
    vIn.expectsMediaDataInRealTime = false
    writer.add(vIn)

    var aOut: AVAssetReaderTrackOutput?, aIn: AVAssetWriterInput?
    if let at {
        let fd = try await at.load(.formatDescriptions).first
        let isAAC = fd.map { CMFormatDescriptionGetMediaSubType($0) == kAudioFormatMPEG4AAC } ?? false
        if isAAC {   // passthrough: the original sound, unchanged
            aOut = AVAssetReaderTrackOutput(track: at, outputSettings: nil)
            aIn = AVAssetWriterInput(mediaType: .audio, outputSettings: nil, sourceFormatHint: fd)
        } else {     // e.g. Opus: AAC-LC 160 kb/s stereo, which every iPad plays
            aOut = AVAssetReaderTrackOutput(track: at, outputSettings: [AVFormatIDKey: kAudioFormatLinearPCM])
            aIn = AVAssetWriterInput(mediaType: .audio, outputSettings: [AVFormatIDKey: kAudioFormatMPEG4AAC, AVNumberOfChannelsKey: 2,
                                                                         AVSampleRateKey: 48000, AVEncoderBitRateKey: 160_000])
        }
        aIn!.languageCode = try await at.load(.languageCode)            // keep the sound's language tag
        aIn!.extendedLanguageTag = try await at.load(.extendedLanguageTag)
        aOut!.alwaysCopiesSampleData = false
        reader.add(aOut!)
        aIn!.expectsMediaDataInRealTime = false
        writer.add(aIn!)
    }

    guard reader.startReading() else { throw reader.error ?? NSError(domain: "reader", code: 2) }
    guard writer.startWriting() else { throw writer.error ?? NSError(domain: "writer", code: 3) }
    writer.startSession(atSourceTime: .zero)

    func pump(_ out: AVAssetReaderTrackOutput, _ inp: AVAssetWriterInput, _ q: DispatchQueue) async {
        await withCheckedContinuation { (k: CheckedContinuation<Void, Never>) in
            inp.requestMediaDataWhenReady(on: q) {
                while inp.isReadyForMoreMediaData {
                    if let s = out.copyNextSampleBuffer() { if !inp.append(s) { inp.markAsFinished(); k.resume(); return } }
                    else { inp.markAsFinished(); k.resume(); return }
                }
            }
        }
    }
    async let v: Void = pump(vOut, vIn, DispatchQueue(label: "v"))
    if let aOut, let aIn { async let a: Void = pump(aOut, aIn, DispatchQueue(label: "a")); _ = await (v, a) } else { _ = await v }
    if reader.status == .failed { writer.cancelWriting(); throw reader.error! }
    await writer.finishWriting()
    if writer.status != .completed { throw writer.error ?? NSError(domain: "writer", code: 4) }
    return bitrate
}

/// VP9 sources: AVFoundation on this Mac cannot decode VP9 (VT VP9 = false, "Cannot Decode"),
/// so the trusted ffmpeg 7.1 decodes them and Apple's VideoToolbox H.264 encoder (h264_videotoolbox) encodes, with the same
/// rules as transcode(): same size (at most 1920), the same bitrate rule, a keyframe at least every 2 s, High profile,
/// fast start, AAC copied (its language tag kept) or AAC-LC 160 kb/s 48 kHz stereo. bitexact flags keep ffmpeg's own
/// version strings out of the file. The output is checked with AVFoundation exactly as AV1 copies are.
func transcodeFFmpeg(_ ff: String, _ src: URL, _ dst: URL, size: CGSize, srcRate: Float, fps: Float, aac: Bool, hasAudio: Bool) throws -> Int {
    let scale = min(1, 1920 / max(size.width, size.height))
    let w = Int((size.width * scale / 2).rounded()) * 2, h = Int((size.height * scale / 2).rounded()) * 2
    let bitrate = Int(min(6_000_000, max(200_000, Double(srcRate) * 2.0 * Double(scale * scale))))
    let keyEvery = max(1, Int((fps > 0 ? fps : 30) * 2))
    try? FileManager.default.removeItem(at: dst)
    var a = ["-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", src.path, "-map", "0:v:0"]
    if hasAudio { a += ["-map", "0:a:0"] }
    a += ["-c:v", "h264_videotoolbox", "-profile:v", "high", "-b:v", "\(bitrate)", "-g", "\(keyEvery)", "-pix_fmt", "nv12",
          "-vf", "scale=\(w):\(h)", "-allow_sw", "0"]
    if hasAudio { a += aac ? ["-c:a", "copy"] : ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"] }
    a += ["-map_metadata", "-1", "-map_chapters", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
          "-movflags", "+faststart", "-f", "mp4", dst.path]
    let p = Process(); p.executableURL = URL(fileURLWithPath: ff); p.arguments = a
    let err = Pipe(); p.standardError = err; p.standardOutput = FileHandle.nullDevice
    try p.run()
    let msg = err.fileHandleForReading.readDataToEndOfFile()
    p.waitUntilExit()
    guard p.terminationStatus == 0 else {
        throw NSError(domain: "ffmpeg \(p.terminationStatus): \(String(decoding: msg, as: UTF8.self).prefix(300))", code: 7)
    }
    return bitrate
}

// ------------------------------------------------------------------ main --
// Options for big libraries (Medium, All), added 2026-11-15; without them the tool behaves as before:
//   --reuse SIDECAR_DIR   (repeatable) an existing h264-v1 folder; an original whose sha256 equals one of its items'
//                         source_sha256 gets that copy cloned (APFS clone, no new data) after its file's sha256 is
//                         re-checked, instead of a new encode. The item is the same apart from this library's id/path.
//   --max-bytes N         stop starting new encodes once copies made in this run (plus those in flight, estimated from
//                         the bitrate rule) would pass N bytes. Clones from --reuse do not count.
//   --min-free N          stop starting new encodes if the output volume's free space would fall below N bytes.
// Videos are taken smallest file first, so a budget converts as many as it can. Outputs and manifest are unchanged in
// form; a stopped run leaves a valid, partial manifest and a re-run continues where it stopped.
let args = CommandLine.arguments
guard args.count >= 3 else {
    print("usage: videocompat LIBRARY_DATA OUT_DIR [--jobs N] [--only VIDEO_ID] [--reuse SIDECAR_DIR]... [--max-bytes N] [--min-free N]"); exit(2)
}
let lib = URL(fileURLWithPath: args[1]), outRoot = URL(fileURLWithPath: args[2]).appendingPathComponent(VERSION)
let jobs = args.firstIndex(of: "--jobs").map { Int(args[$0 + 1]) ?? 4 } ?? 4
let only = args.firstIndex(of: "--only").map { args[$0 + 1] }
let maxBytes = args.firstIndex(of: "--max-bytes").flatMap { Int64(args[$0 + 1]) }
let minFree = args.firstIndex(of: "--min-free").flatMap { Int64(args[$0 + 1]) }
// --ffmpeg PATH: also make copies of VP9 originals (source_video "vp09"), decoded by that ffmpeg (see transcodeFFmpeg).
// --codec av01|vp09: only that source codec in this run (default: AV1, plus VP9 when --ffmpeg is given).
let ffmpeg = args.firstIndex(of: "--ffmpeg").map { args[$0 + 1] }
let onlyCodec = args.firstIndex(of: "--codec").map { args[$0 + 1] }
let reuseDirs = args.indices.filter { args[$0] == "--reuse" }.map { URL(fileURLWithPath: args[$0 + 1]) }
try FileManager.default.createDirectory(at: outRoot, withIntermediateDirectories: true)

func fileSize(_ u: URL) -> Int64 { ((try? FileManager.default.attributesOfItem(atPath: u.path)[.size]) as? NSNumber)?.int64Value ?? -1 }
func freeBytes(_ u: URL) -> Int64 {
    ((try? u.resourceValues(forKeys: [.volumeAvailableCapacityKey]).volumeAvailableCapacity).flatMap { $0 }).map(Int64.init) ?? 0
}

// source sha256 -> (folder, item) from the reuse sidecars, only for copies present at their recorded size.
var reusable: [String: (URL, Item)] = [:]
for d in reuseDirs {
    guard let m = try? JSONDecoder().decode(Manifest.self, from: Data(contentsOf: d.appendingPathComponent("manifest.json"))) else {
        print("reuse: no manifest in \(d.path)"); exit(2)
    }
    for it in m.items.values where !it.file.contains("/") && fileSize(d.appendingPathComponent(it.file)) == it.bytes {
        reusable[it.source_sha256] = reusable[it.source_sha256] ?? (d, it)
    }
}
let reusableSizes = Set(reusable.values.map(\.1.source_bytes))

let cat = try JSONSerialization.jsonObject(with: Data(contentsOf: lib.appendingPathComponent("catalog.json"))) as! [[String: Any]]
let vids = cat.filter { ($0["kind"] as? String) == "video" }.compactMap { r -> (String, String, Int64)? in
    guard let id = r["id"] as? String, let p = r["path"] as? String,
          FileManager.default.fileExists(atPath: lib.appendingPathComponent(p).path) else { return nil }
    return (id, p, fileSize(lib.appendingPathComponent(p)))
}.filter { only == nil || $0.0 == only }.sorted { ($0.2, $0.1) < ($1.2, $1.1) }

let manifestURL = outRoot.appendingPathComponent("manifest.json")
var manifest = (try? JSONDecoder().decode(Manifest.self, from: Data(contentsOf: manifestURL)))
    ?? Manifest(version: VERSION, codec: "avc1+mp4a", note: "H.264 versions of AV1 originals, for iPads without AV1 decode. Originals unchanged.",
                source_count: 0, av1_count: 0, items: [:])
if only == nil { manifest.source_count = vids.count }
let lock = NSLock()
var failures: [String] = []
var made: Int64 = 0, inFlight: Int64 = 0, stopped: String?, skipped = 0, cloned = 0
let saveEncoder = JSONEncoder(); saveEncoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
/// Writes the manifest as it stands (under `lock`), so an interrupted run keeps what it made.
func saveManifest() {
    var m = manifest; m.av1_count = m.items.count
    try? saveEncoder.encode(m).write(to: manifestURL, options: .atomic)
}

await withTaskGroup(of: Void.self) { g in
    var running = 0
    for (id, rel, _) in vids {
        if running >= jobs { await g.next(); running -= 1 }
        running += 1
        g.addTask {
            let src = lib.appendingPathComponent(rel)
            var reserved: Int64 = 0, started = false
            defer { if reserved > 0 { lock.withLock { inFlight -= reserved } } }
            do {
                let (vc, ac, d, vsize, vrate) = try await codecs(AVURLAsset(url: src))
                guard vc == "av01" || (vc == "vp09" && ffmpeg != nil) else { return }
                if let onlyCodec, vc != onlyCodec { return }
                let file = id + ".mp4", dst = outRoot.appendingPathComponent(file)
                let srcBytes = fileSize(src)
                let srcSha = try sha256(src)
                let have = lock.withLock { manifest.items[rel] }
                if let have, have.source_sha256 == srcSha, FileManager.default.fileExists(atPath: dst.path),
                   (try? sha256(dst)) == have.sha256 { print("kept  \(id)"); return }   // re-runs are deterministic and cheap
                if reusableSizes.contains(srcBytes), let (dir, it) = reusable[srcSha].map({ ($0.0, $0.1) }),
                   (try? sha256(dir.appendingPathComponent(it.file))) == it.sha256 {
                    try? FileManager.default.removeItem(at: dst)
                    try FileManager.default.copyItem(at: dir.appendingPathComponent(it.file), to: dst)   // APFS clone
                    guard (try sha256(dst)) == it.sha256 else { throw NSError(domain: "reuse copy differs", code: 6) }
                    var item = it; item.id = id; item.source = rel; item.file = file
                    lock.withLock { manifest.items[rel] = item; cloned += 1; saveManifest() }
                    print("reuse \(id)  from \(dir.lastPathComponent == VERSION ? dir.deletingLastPathComponent().lastPathComponent : dir.path)")
                    return
                }
                // Budget: estimate this copy from the same bitrate rule transcode() uses, plus the audio it carries over.
                let scale = min(1, 1920 / max(vsize.width, vsize.height, 1))
                let estRate = min(6_000_000, max(200_000, Double(vrate) * 2.0 * Double(scale * scale)))
                let audio = max(0, Double(srcBytes) - Double(vrate) * d / 8)
                let est = Int64((estRate * d / 8 + audio) * 1.05) + 1_000_000
                let go: Bool = lock.withLock {
                    if stopped != nil { skipped += 1; return false }
                    if let maxBytes, made + inFlight + est > maxBytes {
                        stopped = "max-bytes \(maxBytes): made \(made), in flight \(inFlight), next \(id) ~\(est)"; skipped += 1; return false
                    }
                    if let minFree, freeBytes(outRoot) - inFlight - est < minFree {
                        stopped = "min-free \(minFree): free \(freeBytes(outRoot)), in flight \(inFlight), next \(id) ~\(est)"; skipped += 1; return false
                    }
                    inFlight += est; reserved = est
                    return true
                }
                guard go else { return }
                let t0 = Date()
                started = true
                let br: Int
                if vc == "vp09", let ffmpeg {
                    let vt = try await AVURLAsset(url: src).loadTracks(withMediaType: .video).first!
                    br = try transcodeFFmpeg(ffmpeg, src, dst, size: vsize, srcRate: vrate, fps: try await vt.load(.nominalFrameRate),
                                             aac: ac == "aac", hasAudio: ac != nil)
                } else {
                    br = try await transcode(src, dst)
                }
                let (ovc, oac, od, osize, _) = try await codecs(AVURLAsset(url: dst))
                // CoreMedia reports audio by its format ID: AAC is 'aac ' (kAudioFormatMPEG4AAC), trimmed "aac" (checked
                // directly, 2026-11-15). The MP4 sample-entry box name 'mp4a' is not what this API returns.
                guard ovc == "avc1", oac == (ac == nil ? nil : "aac"), abs(od - d) < 0.25 else {
                    throw NSError(domain: "check failed: \(ovc ?? "-") \(oac ?? "-") \(od) vs \(d)", code: 5)
                }
                let item = Item(id: id, source: rel, source_bytes: try FileManager.default.attributesOfItem(atPath: src.path)[.size] as! Int64,
                                source_sha256: srcSha, source_video: vc!, source_audio: ac, source_duration: d, file: file,
                                bytes: try FileManager.default.attributesOfItem(atPath: dst.path)[.size] as! Int64, sha256: try sha256(dst),
                                video: ovc!, audio: oac, duration: od, width: Int(osize.width), height: Int(osize.height), video_bitrate: br)
                lock.withLock { manifest.items[rel] = item; made += item.bytes; saveManifest() }
                print(String(format: "made  %@  %.0fs  %.1f MB -> %.1f MB  (est %.1f MB)", id, Date().timeIntervalSince(t0), Double(item.source_bytes) / 1e6,
                             Double(item.bytes) / 1e6, Double(est) / 1e6))
            } catch {
                if started {   // a failed encode leaves no partial file and no stale manifest entry
                    try? FileManager.default.removeItem(at: outRoot.appendingPathComponent(id + ".mp4"))
                    lock.withLock { manifest.items[rel] = nil; saveManifest() }
                }
                lock.withLock { failures.append("\(id): \(error)") }
                print("FAIL  \(id): \(error)")
            }
        }
    }
}
manifest.av1_count = manifest.items.count
let enc = JSONEncoder(); enc.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
try enc.encode(manifest).write(to: manifestURL)
let added = manifest.items.values.reduce(Int64(0)) { $0 + $1.bytes }, orig = manifest.items.values.reduce(Int64(0)) { $0 + $1.source_bytes }
print("sources \(manifest.source_count)  av1 \(manifest.av1_count)  fallbacks \(manifest.items.count)  added \(added) bytes (originals \(orig))  failures \(failures.count)")
if !reuseDirs.isEmpty || maxBytes != nil || minFree != nil {
    print("this run: made \(made) bytes new, reused (cloned) \(cloned), not started \(skipped)" + (stopped.map { "  STOPPED: \($0)" } ?? ""))
}
for f in failures { print("  " + f) }
exit(failures.isEmpty ? (stopped == nil ? 0 : 3) : 1)
