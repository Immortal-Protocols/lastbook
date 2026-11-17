import AVFoundation
import VideoToolbox

// Does this machine decode VP9 (and AV1) in MP4 through AVFoundation? Prints VideoToolbox's hardware answer and whether one
// real frame comes out of each given file. Mac check for the VP9 videos in Medium and All; the iPad answer needs a device.
//   vp9probe FILE...
print("VT hardware VP9: \(VTIsHardwareDecodeSupported(kCMVideoCodecType_VP9))  AV1: \(VTIsHardwareDecodeSupported(kCMVideoCodecType_AV1))")
for p in CommandLine.arguments.dropFirst() {
    let asset = AVURLAsset(url: URL(fileURLWithPath: p))
    var frames = 0
    var note = ""
    do {
        guard let t = try await asset.loadTracks(withMediaType: .video).first else { print("no video  \(p)"); continue }
        let r = try AVAssetReader(asset: asset)
        let out = AVAssetReaderTrackOutput(track: t, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange])
        r.add(out)
        r.timeRange = CMTimeRange(start: .zero, duration: CMTime(seconds: 3, preferredTimescale: 600))
        if r.startReading() {
            while let s = out.copyNextSampleBuffer() { if CMSampleBufferGetImageBuffer(s) != nil { frames += 1 } }
        }
        if r.status == .failed { note = " reader failed: \(r.error?.localizedDescription ?? "")" }
        let playable = try await asset.load(.isPlayable)
        print("frames(3s) \(frames)  isPlayable \(playable)\(note)  \((p as NSString).lastPathComponent)")
    } catch { print("error \(error)  \(p)") }
}
