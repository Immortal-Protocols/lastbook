"""Email over radio: Winlink (VARA, ARDOP, packet, Pactor; RMS; Express and Pat; P2P and radio-only), JS8Call relay, and satellite email."""

ENTRIES = [
    {
        "id": "winlink-architecture",
        "title": "Winlink radio email: how the system is built",
        "publisher": "Winlink system public architecture, as used in ARES/RACES practice / 47 CFR 97.221, 97.115",
        "section": "47 CFR 97.221 (automatically controlled digital stations), 97.115 (third-party traffic), 97.305–97.309; Winlink public system description as used by ARES field references",
        "edition": "Part 97; public Winlink system roles (client, RMS, CMS, radio-only/Hybrid, peer-to-peer). No vendor user manual is copied here.",
        "year": "2024",
        "license": "Part 97 is a US government work. System-role description is operational public knowledge used in emergency-comms practice; it is not a reproduction of Winlink Express help text.",
        "trust": "official",
        "keywords": [
            "winlink", "rms", "cms", "radio email", "email over radio", "gateway",
            "hybrid", "radio-only", "peer-to-peer", "p2p", "winlink express", "pat",
        ],
        "text": (
            "Winlink moves ordinary email over amateur (and some authorized government/maritime) radio. A message is composed offline in a client, handed to a radio mode, and either delivered to another radio client or injected into the internet mail system at a gateway.\n\n"
            "The pieces:\n"
            "— Client. The program on your computer that stores an inbox and outbox, lets you write and read messages (including to internet email addresses), and drives a radio or TNC. Two clients used in the field: Winlink Express (the official Windows client) and Pat (a cross-platform client used on Linux, macOS, Windows and Raspberry Pi). Both can compose and store mail with no internet connection.\n"
            "— RMS (Radio Mail Server). A gateway station on HF, VHF or UHF that your client connects to over the radio. When that RMS still has an internet path, it talks to the Winlink Common Message Servers (CMS) on the internet, which is how a radio-originated message becomes ordinary email, and how ordinary email waiting for you is collected.\n"
            "— CMS. The internet-side message servers. They are out of the picture when the internet path is gone.\n"
            "— Peer-to-peer (P2P). Two clients connect radio-to-radio, no RMS and no internet, and exchange the messages they have for each other. This works as long as the two stations can hear one another and have agreed a frequency, mode and time.\n"
            "— Radio-only / Hybrid. When the internet and the CMS are down, Winlink can move messages through RMS stations that store and forward over radio (HF) to other RMS stations, without the cloud. This is the mode that still delivers radio email in a wide outage, provided enough Hybrid/radio-only RMS stations are on the air and your client is set to use them. It is slower and more limited than the internet-connected system, and it is the one to practice before you need it.\n\n"
            "Automatically controlled digital stations that act as gateways are subject to § 97.221. Third-party messages (mail for or from a person who is not an amateur) are subject to § 97.115, including the international third-party restrictions, except where § 97.403 or § 97.405 authorizes essential life-and-property communications.\n\n"
            "A live RMS frequency list is not bundled here: those assignments change. Export or print a channel list (or an ICS-217A) while you still can, and keep a P2P frequency plan with the people you actually need to reach."
        ),
    },
    {
        "id": "winlink-modes",
        "title": "Winlink radio modes: VARA HF, VARA FM, ARDOP, packet and Pactor",
        "publisher": "FCC Part 97 emission and symbol-rate rules",
        "section": "47 CFR 97.307, 97.309; FCC 23-93 (2023) amendment removing the amateur baud-rate limit in favor of a bandwidth limit",
        "edition": "eCFR Title 47 Part 97, including the 2023 symbol-rate amendment (FCC 23-93)",
        "year": "2023",
        "license": "US government work, public domain (the rule and the Commission order). Mode names identify the protocols; no protocol specification is copied from a vendor.",
        "trust": "official",
        "keywords": [
            "vara", "vara hf", "vara fm", "ardop", "pactor", "pactor 3", "pactor 4",
            "packet", "ax.25", "winmor", "sound card", "scs", "fcc 23-93", "symbol rate",
        ],
        "text": (
            "A Winlink client does not put RF on the air by itself. It needs a modem path. These are the paths in common emergency use:\n\n"
            "VARA HF. A sound-card HF modem, widely used for Winlink on HF because it is fast on a fair channel and needs only a sound-card interface, not a hardware TNC. “Wide” and narrower VARA HF bandwidths exist; stay inside the amateur data segment and the bandwidth the band allows (§ 97.307).\n\n"
            "VARA FM. The VHF/UHF FM counterpart. Faster than HF on a solid local path, used to a local VHF/UHF RMS when one is in range.\n\n"
            "ARDOP (Amateur Radio Digital Open Protocol). An open HF sound-card protocol supported by Winlink clients, including Pat. A practical option when you want a non-proprietary HF path.\n\n"
            "Packet (AX.25). The classic VHF/UHF method, typically 1200 baud AFSK on FM, sometimes 9600 baud on radios and TNCs that support it. A hardware TNC or a local software TNC such as Direwolf provides the link. Slow compared with VARA FM, but widely available and well understood. This is also the path many VHF RMS gateways still offer.\n\n"
            "Pactor. A family of HF protocols from SCS (Pactor 1, 2, 3 and 4), used with an SCS hardware modem. Pactor 3 and 4 are fast and robust on HF and have long been used by Winlink RMS stations. Pactor 4 was historically blocked for US amateurs by the symbol-rate (baud) limit in § 97.307. In 2023 the Commission adopted FCC 23-93, which replaced that baud-rate limit with a bandwidth limit. Pactor 4 may be used by a US amateur station when the emission stays within the bandwidth and other emission rules that now apply. The modem itself is proprietary hardware.\n\n"
            "WINMOR, an older sound-card HF mode, has been retired from the Winlink system and should not be planned on.\n\n"
            "Pick a mode your client, your interface, and the station on the other end (RMS or P2P) all actually support. A pre-arranged P2P frequency and mode with a specific person beats a stale gateway list."
        ),
    },
    {
        "id": "winlink-clients-offline",
        "title": "Winlink Express and Pat as offline-capable clients",
        "publisher": "Lastbook comms reference (client roles; not a vendor manual)",
        "section": "Operational description of the two clients used with the Winlink system, for offline and radio-only use",
        "edition": "This module. It does not copy Winlink Express or Pat documentation and does not ship either application.",
        "year": "2026",
        "license": "Original Lastbook reference text identifying publicly documented clients and their offline roles.",
        "trust": "official",
        "keywords": [
            "winlink express", "pat", "la5nta", "linux", "raspberry pi", "windows",
            "offline client", "inbox", "outbox", "telnet",
        ],
        "text": (
            "Winlink Express. The official Windows client. It composes, stores and displays mail on the local computer with no internet connection. It can then send and receive via VARA HF, VARA FM, ARDOP, packet, Pactor (with an SCS modem), and, when the internet exists, via a Telnet session to the CMS. For emergency use, configure at least one radio mode, store a gateway or P2P list locally, and practice a radio-only or peer-to-peer session — not only Telnet.\n\n"
            "Pat. A cross-platform Winlink client (Linux, macOS, Windows, Raspberry Pi) used widely on computers that are not running Windows. It also stores mail locally, works with ARDOP, VARA, packet and other transports, and can run as a local web interface on the same computer. It is a practical client for a Pi or a Linux laptop that will live in a go-kit. Install and configure it before the outage; it does not need the internet to exchange mail over radio.\n\n"
            "Neither client is bundled with Lastbook. Neither should be configured for the first time in the dark. The steps that matter, and that are not a copied manual page: install the client and the modem software on the machine that will go into the field; put your call sign and a recoverable message store on that machine; attach the radio through a known-good interface; save RMS or P2P frequencies locally; send a test message over RF, including one P2P or radio-only test, not only an internet Telnet test.\n\n"
            "If a current official manual is not in this library, that is a gap. Do not invent a menu path."
        ),
    },
    {
        "id": "js8-email-relay",
        "title": "JS8Call as a messaging and relay path (not email)",
        "publisher": "FCC Part 97 digital rules",
        "section": "47 CFR 97.305, 97.307, 97.309",
        "edition": "eCFR Part 97; JS8Call used as a named mode for short-message relay",
        "year": "2024",
        "license": "Part 97 is a US government work. Mode description is operational, not a copy of the JS8Call manual.",
        "trust": "official",
        "keywords": [
            "js8", "js8call", "relay", "store and forward", "short message", "hf message",
            "email alternative",
        ],
        "text": (
            "JS8Call is not an email system. It will not hand a message to an internet mailbox by itself. It is included here because, when Winlink gateways are off the air and a satellite terminal is not available, a short JS8 message and its store-and-forward / relay feature are a working way to move a welfare or coordination text across HF with very little power.\n\n"
            "A station can send a short free-text message to a specific call sign, ask for an acknowledgment, and — if other JS8 stations have relay enabled — have that message stored and forwarded along a chain. The useful emergency plan is to pre-agree call signs, a window of time, and a published JS8 frequency inside a data segment you are licensed for, and to keep messages short: a name, a location, a condition, a request.\n\n"
            "For genuine email format (To, Subject, a longer body, attachments, delivery to an internet address when any gateway still has a path), use Winlink. For a short HF text when nothing else is available, use JS8Call. Both can live on the same computer and radio."
        ),
    },
    {
        "id": "satellite-email",
        "title": "Satellite email and inReach-style messaging",
        "publisher": "NOAA SARSAT (beacons) / operational description of licensed commercial systems",
        "section": "Licensed commercial satellite services (Iridium, Inmarsat, Globalstar) and 406 MHz distress beacons. Not amateur radio.",
        "edition": "Public operational characteristics. Vendor account and app setup is not in this library and is not invented here.",
        "year": "2024",
        "license": "Beacon facts are US government works where they cite NOAA/FCC. Commercial system descriptions are operational facts, not a vendor manual.",
        "trust": "official",
        "keywords": [
            "iridium go", "iridium email", "inreach email", "garmin inreach", "zoleo",
            "bgan", "isatphone", "satellite email", "spot", "somewear",
        ],
        "text": (
            "When terrestrial internet and amateur gateways are both down, commercial satellite terminals can still move a message if the device is already activated and has a clear sky view.\n\n"
            "Iridium GO and GO exec. A compact Iridium terminal that presents a local wireless link to a phone. With its companion software already installed and an account already active, it can place voice calls and send short email and weather queries over the Iridium constellation, pole to pole, with no terrestrial network. Message size and rate are limited compared with a café Wi-Fi. This is real email, not just an SOS button, but it is not a Winlink-sized mailbox and it is not free of a vendor account.\n\n"
            "inReach-style messengers (Garmin inReach and similar Iridium two-way messengers; Zoleo; Somewear). These send and receive short texts and can issue an SOS to a response center. Many can be addressed from the public email or SMS network via a device-specific address issued by the vendor, with tight length limits. That path looks like email on the sender’s end and a short message on the device. It is not SMTP as a laptop knows it, and it is not Winlink. It is often the most practical “tell one person we are alive and where” path in a pack.\n\n"
            "Inmarsat BGAN and similar GEO data terminals can carry fuller email sessions at mid-latitudes when the terminal can see the geostationary satellite. They fail at high latitudes. A handheld Inmarsat phone (IsatPhone) is primarily voice, with limited messaging.\n\n"
            "A 406 MHz PLB or EPIRB is still the dedicated distress beacon for SAR and should not be confused with email. Use a messenger or sat-phone email to talk to a person; use a registered 406 MHz beacon to call rescue.\n\n"
            "Vendor activation, billing and app menu paths are not in this library. Devices that need an account must be activated and tested before the outage; there is no way to invent that process here."
        ),
    },
]
