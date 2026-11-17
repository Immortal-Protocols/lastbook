import AVFoundation

// Prints the video and audio sample-entry codes AVFoundation reports for each file (a check on tools/videocompat).
func fourcc(_ f: FourCharCode) -> String {
    String(bytes: [UInt8((f >> 24) & 255), UInt8((f >> 16) & 255), UInt8((f >> 8) & 255), UInt8(f & 255)], encoding: .ascii) ?? "?"
}
for p in CommandLine.arguments.dropFirst() {
    let a = AVURLAsset(url: URL(fileURLWithPath: p))
    var out: [String] = []
    for kind in [AVMediaType.video, .audio] {
        if let t = try await a.loadTracks(withMediaType: kind).first, let fd = try await t.load(.formatDescriptions).first {
            out.append("\(kind.rawValue)=[\(fourcc(CMFormatDescriptionGetMediaSubType(fd)))]")
        }
    }
    print(out.joined(separator: " "), (p as NSString).lastPathComponent)
}
