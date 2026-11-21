# H.264 copies of videos some computers can't play

Many library videos are saved in AV1. Lastbook plays videos in the system's web view, and on a Mac that plays AV1 only with
a hardware decoder: Macs with an M3 or later have one, M1 and M2 Macs don't, and there the video won't play (#49). VP9 is
not played by every web view either. This page says how Lastbook plays those videos anyway, and how a library gets what it
needs for that.

## How playback works

Each AV1 or VP9 video can have an H.264 copy, which every supported computer decodes in hardware. The copies are the same
sidecar the iPad app already uses:

- `derived/video-compat/h264-v1/manifest.json` maps each original's library path to its copy, with the original's codec
  (`source_video`), and the copy's size, SHA-256, length and picture size.
- `derived/video-compat/h264-v1/<video id>.mp4` is the copy.

The originals are never changed, so a video keeps its id, catalog record, transcript, captions and watch progress.

On the desktop, `server.py` reads the manifest and tells the watch page, in `/api/doc/<id>`, that a copy exists and which
codec the original uses. The page asks the web view whether it can decode that codec. If not, it plays the copy, which the
server sends at the original's own address with `?copy=h264`. If the original fails anyway, or loads with no picture,
the page switches to the copy once, at the same moment. A copy counts only if it is a plain file name in that folder,
H.264, and the size the manifest gives, the same rules as on the iPad. Without a copy, nothing changes: the video plays as
before, or shows why it can't.

## Making the copies

`mobile/ipad/tools/videocompat` builds them with Apple's own decoder and encoder, so it needs a Mac that decodes AV1 (M3 or
later). VP9 originals also need an ffmpeg you supply. See [mobile/ipad/README.md](../mobile/ipad/README.md).

```bash
xcrun swiftc -O -o videocompat mobile/ipad/tools/videocompat/main.swift
./videocompat /path/to/LastbookData/library-data /path/to/LastbookData/derived/video-compat
```

The copy keeps the picture size (at most 1920 on the long side), puts a keyframe at least every 2 seconds so seeking stays
quick, writes the index first so playback starts before the whole file is read, and keeps AAC sound as it is.

## Checking a library

```bash
python3 tools/check_video_formats.py --data /path/to/LastbookData
```

It lists every AV1 or VP9 video and whether it has a usable copy, and exits 1 if any doesn't. It reads only each file's
index. Run it on a pack before release so a new AV1 video can't ship without its copy.

## What it costs: the Small pack

Measured on the Small pack of 13 November 2026, on an M5 Pro:

| | |
|---|---|
| Videos in the pack | 41 |
| In AV1 | 21 (3.1 hours), including 7 of the first-aid videos |
| In VP9 | none |
| Originals of those 21 | 1.13 GB |
| Their H.264 copies | 2.05 GB, about 1.8 times the originals |
| The pack, for comparison | 7.7 GB to download |
| Time to build all 21 | 10 minutes, four at a time |
| Failures | none; every copy's length is within 0.003 s of its original, and its sound is AAC |

The first-aid videos alone are 65 MB as AV1 and 108 MB as copies. On a computer that plays the copies, the originals are
not read at all, and the copies use the hardware H.264 decoder every supported Mac has, so playback costs no more than an
H.264 original. Medium and All have many more videos and were not measured.

## Still to decide

- **How existing installations get the copies.** The player code reaches people with an app update. The copies are data,
  so they need a download. The iPad README already plans a video-copies zip per pack; setup would list it, and offer it
  only on a computer that can't decode AV1. Until then, a copies folder built as above can be put in place by hand.
- **Copies or originals.** Shipping H.264 originals instead (downloading H.264 when the library is gathered, or
  re-encoding) would need no second file, but makes every pack larger for computers that play AV1 fine, and changes the
  files existing installations already have.
