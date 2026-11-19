# Sharing downloads: mirrors and BitTorrent

The All library is one 388 GB zip, and `downloads.lastbook.org` gives about 1.2 MB/s per connection, so a download takes days.
Many people want exactly the same bytes. This lets them get those bytes from mirrors and from each other, without anyone along
the way being able to change one.

**Owner decisions this needs.** Two parts change rules in [SETUP-API.md](SETUP-API.md) and `CONTRIBUTING.md`, and are off or
empty until the owner chooses:
- **Mirrors** are hosts that are not Lastbook's. A mirror is used only for a file whose torrent is pinned, every piece from it is
  checked, and the package scan accepts a mirror address in the bundled manifest only beside such a pin. The bundled manifest
  lists none until the owner adds some, and people can add their own in setup.
- **BitTorrent** (downloading from other people and sharing with them) runs rqbit, a BitTorrent program, which listens for
  peers. Its control API listens on 127.0.0.1 only, behind a password made for each run. Lastbook's own code still opens no port:
  it starts and stops rqbit and reads its numbers through `download.local_api`. It is off unless the person turns it on, and the
  setting says that peers see this computer's address.

## The trust chain

1. The app's bundled manifest pins each file's SHA-256, as before. For a file with a torrent it also pins
   `torrent: {url, pieces_root, infohash_v2, piece_length}`, written by `packaging/make_torrent.py`.
2. The torrent is a hybrid BitTorrent v1 and v2 torrent of that one file, with the file's own address as its web seed. Setup
   fetches it from Lastbook's site only, and uses it only if the SHA-256 of its info is `infohash_v2` and its piece hashes add up
   to `pieces_root` (`engine/setup/torrent.py`). The info holds the v1 SHA-1 piece hashes too, so v1-only clients such as rqbit
   and aria2c check the same pinned file.
3. Each piece is then checked when it is read back from the disk (BEP 52: SHA-256 of 16 KiB blocks, built up to the piece's
   hash), whatever sent it. The downloader's pieces hold whole torrent pieces, and the run of finished pieces from byte 0 (the
   downloader from #125) takes one only once its torrent pieces match. A mirror that sends one wrong piece is not asked again.
   A piece that never matches from the file's own address stops the download after a few tries, with the file kept.
4. The whole file's SHA-256 is still the last check.

So a mirror or a peer can at most waste some bandwidth. It cannot get a changed byte into a library.

A fetched manifest can never add or change a pin on a file the app was built with (`manifest.merge`). It may change that
file's `mirrors`, but only when it pins the very same file and torrent.

## Mirrors

- A file entry may list `"mirrors": ["https://…/Lastbook-All.zip", …]`: https, no user name or password, port 443, at most 16.
  They are used only when the torrent pin checks out.
- A person can add their own (Library and local AI → Mirrors, or `POST /api/setup/mirrors {add}`): the address of a copy of
  the download site's tree. The file's path on the site is added to it.
- Each mirror gets as many connections as the file's own address (`CONNECTIONS`), so each mirror adds capacity.
- A mirror never stops the download, never moves the file's ETag and never spends the busy server's wait. One that sends a wrong
  piece, answers with another range, size or status, redirects elsewhere or keeps breaking is dropped, and the piece it had
  goes back to the others.
- With no mirror and BitTorrent off, a file comes through the downloader exactly as before, plus the torrent check where a
  torrent is pinned.
- TLS is checked against `roots.pem` as for every download: Let's Encrypt, Google Trust Services, Amazon and GlobalSign, which
  cover most hosts. A mirror whose certificate chains elsewhere fails and is dropped. Widening that is an owner decision.

## BitTorrent: downloading from other people

With BitTorrent on, a file with a pinned torrent of `PARALLEL_MIN` (512 MiB) or more also comes from other people while it
downloads (`Download._run_swarm`):

- `share.Swarm` starts an rqbit of its own (`server start --disable-persistence`, its control API on 127.0.0.1 behind a password
  made for it) and adds the torrent with its output in `downloads/swarm/`. That folder holds the very file Lastbook downloads into,
  so there is one copy on the disk, not two. Where the disk keeps gaps empty, the file is marked sparse first: on NTFS, a write
  at 8 GiB into a plain file took 17 s of zero-filling, and 0.02 s into a sparse one.
- rqbit fetches pieces in order, from the front. Lastbook's connections to the servers and mirrors take pieces from the back, so
  the two meet without doing the same work. A probe tells whether the disk really keeps gaps empty; on one that fills them
  anyway (a NAS share did: 1 MiB written at 4 GiB took 22 s), the connections take pieces from the far end of the window
  instead (`AHEAD` pieces past the first one not done), while rqbit takes its front.
- The connections are the downloader's own (the busy server's wait, the mirrors), but a server that stops sending pieces, or
  cannot be reached, is asked again later while rqbit goes on. Without rqbit that stops the download, with what is here kept.
- This way never cuts the file short. Its `.json` lists the pieces done (`"swarm"`), not a run from byte 0, and the last read
  checks them all. Paused with BitTorrent on and resumed with it off, the file goes on from the servers with those pieces kept.
- rqbit writes what a peer sends before it checks it, even over a piece Lastbook already has. So nothing rqbit says is taken on
  its word. A piece of its counts only when its bytes on the disk match the torrent's piece hash. Once every piece is in, rqbit's
  process is ended, and the whole file is read: every piece against its torrent hash, and the whole SHA-256. Any piece wrong in
  that read is fetched again from the servers alone, and the file read again.
- That last read is about an hour for 388 GB on a network share, and a few minutes on a fast local disk.
- Pause, cancel, a failure, or BitTorrent turned off end rqbit first. If rqbit cannot start, the download goes the usual way.
- The item shows how much came from people ("… from people sharing").

## BitTorrent: sharing (seeding)

- Off by default. When the person turns it on (the choose screen, or Library and local AI → Download and share with BitTorrent):
  - each downloaded file with a pinned torrent is kept with its `.torrent` in `<library>.share` beside the library, instead of
    being deleted once it is unpacked. The model is shared from the library itself.
  - while Lastbook is open, `engine/setup/share.py` seeds them with rqbit:
    `rqbit --disable-dht-persistence --disable-upnp-port-forward --http-api-listen-addr 127.0.0.1:<port> download --overwrite -o <folder> <torrents>`.
    That means a control API on this computer only, behind a password made for the run, no UPnP (the router is not changed) and no
    saved DHT state. Only torrents whose info matches the pin are seeded, and rqbit checks each file against its torrent before it
    uploads a byte.
  - Lastbook asks rqbit every 15 seconds how much it has uploaded, and adds that up across runs in
    `<settings>/setup/shared.json`. Library and local AI shows the total ("… shared with other people so far").
- rqbit ends with Lastbook: through a Windows job object however Lastbook ends, through the parent-death signal on Linux, and at
  exit on a Mac.
- Turning it off stops rqbit and keeps the files. **Delete kept files** removes them. The library is never touched.
- People with a torrent client (qBittorrent, Transmission, aria2c) can download or seed the same torrent. Setup's existing
  "Use the file you already have" checks a file got that way before using it.

## For the maintainers

```bash
python3 -I -B packaging/make_torrent.py derived/release/<release>/Lastbook-All.zip --url https://downloads.lastbook.org/Lastbook-All.zip --manifest derived/release/manifest-v1.json
```

This writes `Lastbook-All.zip.torrent` (upload it beside the zip) and pins it in the packs file, which
`packaging/release_manifest.py` then bundles. The default piece length is 16 MiB, the downloader's piece (`download.PIECE`),
which makes about 740 KB of piece hashes for 388 GB.

```bash
python3 -I -B packaging/share/fetch_rqbit.py win-x64
```

This fetches rqbit 9.1.0 into `derived/share/`, checked against GitHub's own digests pinned in `packaging/share/rqbit.json`. The
Windows build bundles it to `_internal/share` when it is there, and the package scan accepts only that exact file. The Mac and
Linux builds do not bundle it yet, so they do not offer sharing.

## Not done yet

- Telling rqbit which pieces Lastbook already has. Its API cannot, so once the two meet in the middle, rqbit may fetch some
  pieces again from peers until the download ends. That wastes some bandwidth, never a byte of the file.
- rqbit for the Mac and Linux packages.
- The iPad app's own downloader.
