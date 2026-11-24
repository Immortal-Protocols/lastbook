"""Text over radio: APRS, JS8Call, FT8, Meshtastic/LoRa, and how to stand up local offline apps. Email-over-radio lives in the email topic."""

ENTRIES = [
    {
        "id": "aprs",
        "title": "APRS (Automatic Packet Reporting System)",
        "publisher": "FCC Part 97 / widely published US APRS frequency practice",
        "section": "47 CFR 97.309, 97.221; US 2 m APRS channel 144.390 MHz as published in ARES field references and standard US VHF practice",
        "edition": "Part 97; ARES field references (in-library) for the US APRS frequency",
        "year": "2024",
        "license": "Part 97 is a US government work. 144.390 MHz is the published US 2-meter APRS channel used in ARES field material.",
        "trust": "official",
        "keywords": [
            "aprs", "packet", "144.390", "144.39", "beacon", "position", "digipeater",
            "direwolf", "ax.25", "gps", "tracker",
        ],
        "frequencies_mhz": [144.390, 145.825],
        "text": (
            "APRS carries short position, status, weather and text packets over AX.25 packet radio, usually 1200-baud AFSK on FM. "
            "In the US the standard 2-meter APRS channel is 144.390 MHz. (Other regions use a different VHF channel; do not assume 144.390 outside the US.) "
            "The amateur satellite / ISS APRS channel has commonly been 145.825 MHz.\n\n"
            "A typical station is a radio, a 1200-baud TNC or a sound-card TNC (Direwolf is a common local software TNC), and a source of position (a GPS receiver). "
            "A tracker can beacon a position automatically. A digipeater or I-gate relays packets; an I-gate also needs an internet path, which may be down. "
            "When the internet is down, APRS still works radio-to-radio and through RF digipeaters: positions and short messages hop as far as the RF path allows. That is the useful emergency mode.\n\n"
            "Keep beacons slow and low-power enough not to flood a busy channel. Identify under § 97.119. Packet emissions must stay within § 97.307 and § 97.309. "
            "This module does not include a live digipeater map."
        ),
    },
    {
        "id": "js8call-ft8",
        "title": "JS8Call messaging and FT8 weak-signal contacts",
        "publisher": "FCC Part 97 (digital emissions)",
        "section": "47 CFR 97.305, 97.307, 97.309",
        "edition": "eCFR Part 97. Application operating practice summarized without copying any application’s manual.",
        "year": "2024",
        "license": "Part 97 is a US government work. JS8Call and WSJT-X are separate applications; their names are used to identify the modes, not to ship their code.",
        "trust": "official",
        "keywords": [
            "js8", "js8call", "ft8", "wsjt", "weak signal", "hf data", "relay",
            "store and forward", "low power",
        ],
        "text": (
            "FT8 (typically used through the already-installed WSJT-X application) is a weak-signal HF/VHF mode for short, structured contacts. It will make a contact at very low signal-to-noise ratios. It is not a traffic or email system. Use it to get a signal through, confirm that a path exists, or exchange the brief fields the mode supports — not to pass a welfare message of any length.\n\n"
            "JS8Call is a related weak-signal mode built for keyboard messaging. Stations can send short free-text messages, request an acknowledgment, and relay or store-and-forward a message through other JS8 stations that are willing and in range. That relay function is the useful emergency property: a message can move across a chain of HF stations with no internet and very little power. It is not email, it is not Winlink, and messages are short.\n\n"
            "Both run locally on a computer already fitted with the application, a sound-card interface, and an HF (or VHF) radio. Once installed, neither needs the internet to transmit or receive. Tune to a published JS8 or FT8 frequency inside an amateur data segment you are licensed for, set the clock reasonably close (these modes are time-sensitive; a watch set from WWV or a pre-set clock is enough if GNSS is gone), and follow the in-app waterfall rather than a copied menu path — this module does not invent click-by-click setup.\n\n"
            "Identify as Part 97 requires. Stay inside the data segment and bandwidth for the band (§ 97.305, § 97.307)."
        ),
    },
    {
        "id": "meshtastic-lora",
        "title": "Meshtastic and LoRa mesh text",
        "publisher": "FCC Part 15 / Part 97 (depending on the radio and band)",
        "section": "47 CFR Part 15 (unlicensed ISM); Part 97 if the radio is operated in an amateur band under amateur rules",
        "edition": "eCFR. Meshtastic is a community firmware/project; no vendor manual is copied here.",
        "year": "2024",
        "license": "Rule citations are US government works. Product and project names identify the system.",
        "trust": "official",
        "keywords": [
            "meshtastic", "lora", "mesh", "868", "915", "433", "off-grid text",
            "ism", "long range",
        ],
        "frequencies_mhz": [433.0, 868.0, 915.0],
        "text": (
            "Meshtastic is firmware for small LoRa radios that form a mesh and pass short text, position and telemetry without a cellular network. Nodes forward other nodes’ messages so a phone or a stand-alone device at one edge of the mesh can reach a device at the other, as long as there are enough hops in between.\n\n"
            "In the US, most community Meshtastic devices run in the 915 MHz ISM band as unlicensed Part 15 radios. Other regions use 868 MHz or 433 MHz as their rules require. A LoRa radio can also be built or configured for an amateur band and operated under Part 97, but that is a different legal status (license, identification, no pecuniary interest, and the amateur technical rules). Do not assume a store-bought 915 MHz node is an amateur station.\n\n"
            "What it is good for: neighborhood or campus text when cell service is down; a trail group; a site with several nodes in line-of-sight or near it. What it is not: a long-haul HF system, an email system, or a substitute for a 406 MHz beacon. Range is modest (often a few kilometers in town, more with height and a clear path), and the mesh only exists where people have actually placed nodes.\n\n"
            "Stand it up locally: flash and configure the nodes before the emergency, set a channel/PSK the group shares, give each node a useful name, put at least one node high, and test a message hop. A phone talks to its local node over Bluetooth or USB; the RF path is node to node. This module does not ship firmware or a flashing guide."
        ),
    },
    {
        "id": "local-offline-apps",
        "title": "Standing up local offline radio applications",
        "publisher": "Lastbook comms reference (points at systems; does not bundle the applications)",
        "section": "Operational pattern for already-installed local clients used with Part 97 and Part 95 radios",
        "edition": "This module. Individual application licences and manuals are their authors’. Not bundled.",
        "year": "2026",
        "license": "This summary is original Lastbook reference text. It does not copy application manuals or ship third-party code.",
        "trust": "official",
        "keywords": [
            "direwolf", "pat", "winlink express", "js8call", "wsjt-x", "gpredict",
            "install", "offline app", "sound card", "interface", "setup local",
        ],
        "text": (
            "The applications that actually put text, email or images over radio are not inside Lastbook. Install and test them while you still have power, a computer, and (if they need it) one download. After that, the useful ones run locally and talk to a radio, not to a cloud.\n\n"
            "A working local stack looks like this:\n"
            "— A radio you are allowed to use, with a sound-card or TNC interface (or a built-in sound card / data port).\n"
            "— A software TNC if you need one (Direwolf is a common local AX.25 / packet TNC).\n"
            "— The client for the mode: JS8Call for JS8 messages and relays; WSJT-X for FT8; Pat or Winlink Express for radio email (see the email-over-radio entries); a Meshtastic flasher and the phone app for a LoRa mesh; Gpredict or Orbitron for satellite passes if you have a TLE file.\n"
            "— Your call sign, a local clock you trust, and a saved frequency or gateway list (gateway lists go stale; export them while you can).\n\n"
            "This module does not invent click-by-click setup for any of those programs, and it does not bundle their installers. If a manual for one of them is already in the Lastbook library, prefer that manual. If it is not, that is a gap: do not guess a vendor menu path from memory."
        ),
    },
]
