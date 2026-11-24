"""Amateur satellites, ISS/ARISS, pass prediction, satellite messengers and PLBs, weather-satellite imagery."""

ENTRIES = [
    {
        "id": "amateur-satellites-iss",
        "title": "Amateur satellites, ISS voice, APRS and SSTV",
        "publisher": "NASA / ARISS public information / FCC Part 97",
        "section": "47 CFR 97.207, 97.209, 97.211; NASA/ARISS published ISS amateur operations",
        "edition": "eCFR Part 97; ARISS/NASA public ISS amateur radio fact sheets. ISS crew and transponder setups change; confirm against a current plan if you have one.",
        "year": "2024",
        "license": "Part 97 is a US government work. ISS frequency figures below are the widely published ARISS/NASA values for recent crossband and APRS operation, dated as such — not a live schedule.",
        "trust": "official",
        "keywords": [
            "satellite", "amsat", "iss", "ariss", "crossband", "sstv", "aprs digipeater",
            "fm sat", "so-50", "uplink", "downlink", "doppler", "145.800", "145.825", "437.800",
        ],
        "frequencies_mhz": [145.800, 145.825, 437.800],
        "text": (
            "Amateur satellites (§ 97.207, space stations; § 97.209, earth stations) are ordinary amateur stations in orbit: you work them with a licensed amateur transceiver, usually VHF/UHF, during a short line-of-sight pass (low-Earth orbit passes are often 8–15 minutes).\n\n"
            "FM “easy sats.” A typical FM amateur satellite has a UHF uplink and a VHF downlink, or the reverse, with a CTCSS tone on the uplink. You listen on the downlink, transmit on the uplink, and walk both frequencies a few kilohertz during the pass to follow Doppler shift (the downlink falls as the satellite goes by; the uplink is corrected the other way). Open the squelch. Use the minimum power that the downlink reports. Do not occupy the bird with a long QSO while others are waiting. Specific transponder frequencies and which satellites are alive change as birds fail or are launched; this module does not ship a live satellite almanac.\n\n"
            "International Space Station (ARISS / NASA public figures, recent configuration — crews change this):\n"
            "— Voice downlink has commonly been 145.800 MHz, with a UHF uplink near 437.800 MHz for the crossband voice repeater when that repeater is on.\n"
            "— The ISS APRS packet digipeater has commonly been 145.825 MHz (the standard amateur satellite APRS frequency).\n"
            "— SSTV (slow-scan television) from the ISS, when scheduled, has commonly been transmitted on 145.800 MHz FM.\n"
            "Treat those figures as the last widely published ARISS values, not as a guarantee of today’s crew setup. If you have a printed or saved ARISS operations plan, that plan wins.\n\n"
            "An amateur license and the usual identification rules apply to amateur-satellite work. The ISS also runs scheduled ARISS school contacts; do not interrupt one."
        ),
    },
    {
        "id": "satellite-passes-tle",
        "title": "Predicting satellite passes offline (TLE basics)",
        "publisher": "NASA / USSPACECOM two-line element format (public)",
        "section": "NASA/NORAD two-line element set format; SGP4 propagation (standard orbital element practice)",
        "edition": "Public TLE format documentation. This app does not fetch TLEs and does not propagate orbits itself.",
        "year": "2024",
        "license": "The TLE format is a public US government / NORAD convention. Element sets themselves go stale and are not bundled here.",
        "trust": "official",
        "keywords": [
            "tle", "kepler", "sgp4", "pass prediction", "gpredict", "orbitron", "aos", "los",
            "orbital elements", "offline", "two-line",
        ],
        "text": (
            "A pass prediction answers: when will this satellite rise above my horizon, how high will it get, and on what heading. The usual input is a Two-Line Element set (TLE), the NASA/NORAD text format that describes one object’s orbit at an epoch. A propagator (the standard is SGP4) turns that element set, plus your latitude, longitude and time, into a look angle.\n\n"
            "TLEs go stale. For low-Earth orbit (ISS, NOAA weather sats, most amateur FM sats), a set more than one or two weeks old will put the bird in the wrong part of the sky. Fresh sets are issued by USSPACECOM and redistributed by public catalogs. Lastbook does not fetch them: there is no network call, and no TLE file is bundled (it would be stale before the library reaches you).\n\n"
            "Offline practice: while you still have a computer and a file, save TLE text for the objects you care about (ISS, NOAA-15/18/19 if still transmitting, Meteor-M, the amateur sats you actually use). Point an already-installed offline predictor at that file. Common local applications that work without the internet once installed and once they have a TLE file include Gpredict and Orbitron. Set your observer location (grid or lat/lon). Read AOS (acquisition of signal), max elevation, and LOS (loss of signal). For the ISS and FM sats, a pass below about 10 degrees is often blocked by trees and buildings; a high, overhead pass is the one worth sitting up for.\n\n"
            "If you have no TLE and no predictor, you cannot honestly “compute a pass” from memory. You can still listen on the published downlink during a window when the bird might be in view, but that is luck, not a prediction."
        ),
    },
    {
        "id": "satellite-messengers-phones",
        "title": "Satellite messengers, PLBs and satellite phones",
        "publisher": "NOAA SARSAT / FCC",
        "section": "47 CFR 80.1061, 87.199; NOAA SARSAT PLB/EPIRB guidance; public constellation coverage characteristics",
        "edition": "eCFR; NOAA SARSAT. Vendor setup wizards are not reproduced and are not in this library.",
        "year": "2024",
        "license": "Beacon rules and NOAA guidance are US government works. Constellation descriptions are operational facts about licensed systems, not a vendor manual.",
        "trust": "official",
        "keywords": [
            "iridium", "inmarsat", "globalstar", "inreach", "zoleo", "spot", "isatphone",
            "bgan", "iridium go", "sat phone", "messenger", "plb", "garmin", "somewear",
        ],
        "text": (
            "Three different jobs are often lumped together. They are not the same device.\n\n"
            "1. A 406 MHz PLB, EPIRB or ELT is a distress beacon for COSPAS-SARSAT. It tells rescue authorities that a registered beacon has gone off, and where. It is not a chat device. See the 406 MHz beacon entry. Register it.\n\n"
            "2. A satellite messenger (Garmin inReach and similar Iridium-based two-way messengers, Zoleo, Somewear; older SPOT units on Globalstar) sends short texts and a dedicated SOS to a response center. Two-way messengers can also receive a short reply. This is messaging, not a full mailbox. Many of these devices can be reached from the public email or SMS network by an address the vendor issued for that handset, with tight length limits. They need a clear view of the sky, a charged battery, and usually an already-activated subscription. They do not depend on terrestrial cell service. They do depend on the vendor’s ground system and, for SOS, a response center still answering.\n\n"
            "3. A satellite phone or terminal places a voice call, and often low-rate data or email, through a constellation:\n"
            "— Iridium. Low-Earth orbit, true pole-to-pole coverage, including oceans and polar routes. Handsets and terminals such as Iridium GO / GO exec, which present a local Wi-Fi link to a phone for voice, short email and weather once the terminal can see the sky.\n"
            "— Inmarsat. Geostationary. Reliable at mid-latitudes; poor or unusable at high latitudes and at the edge of a satellite footprint. IsatPhone and BGAN/Fleet terminals; BGAN can carry more data (including email) than a messenger.\n"
            "— Globalstar. LEO, coverage is regional with known gaps; some handsets and the SPOT family use it.\n\n"
            "None of these is amateur radio. They are licensed commercial or distress systems. In an emergency, a PLB or EPIRB is the device built to be heard by SAR; a messenger’s SOS is a close second if the device is activated and has a sky view; a sat phone is how you talk once you have someone to call. Pre-activate and test before you need them. Vendor step-by-step app setup is not in this library (recorded as a gap)."
        ),
    },
    {
        "id": "weather-satellites-sdr",
        "title": "Receiving NOAA and Meteor weather-satellite imagery with an SDR",
        "publisher": "NOAA / NESDIS",
        "section": "NOAA POES APT frequencies and public direct-readout practice; Meteor-M LRPT as publicly documented",
        "edition": "NOAA NESDIS direct-readout public information. Operational status of individual satellites changes and is not bundled.",
        "year": "2024",
        "license": "NOAA frequency and direct-readout facts are US government works. Meteor-M (Roscosmos) LRPT frequency is the publicly documented downlink, noted as such.",
        "trust": "official",
        "keywords": [
            "noaa apt", "lrpt", "meteor", "sdr", "rtl-sdr", "137.62", "137.9125",
            "weather satellite", "wxtoimg", "satdump", "apt", "hrpt", "137 mhz",
        ],
        "frequencies_mhz": [137.1, 137.62, 137.9125, 137.9],
        "text": (
            "Polar-orbiting weather satellites broadcast imagery on VHF that a modest antenna and a software-defined radio (SDR) can receive, with no transmitter and no license for receive-only.\n\n"
            "NOAA APT (Automatic Picture Transmission) has been transmitted by the POES satellites around 137 MHz FM, historically:\n"
            "137.6200 MHz and 137.9125 MHz (and, in earlier generations, 137.100 MHz). "
            "Which satellite is on which frequency, and which birds are still transmitting, changes as spacecraft are retired. NOAA has been winding down the legacy POES APT service. This module does not ship a live status board. If you have a saved NOAA direct-readout notice, use that.\n\n"
            "Meteor-M (Russian polar orbiters) have broadcast LRPT (Low-Rate Picture Transmission), a digital VHF downlink commonly documented around 137.900 MHz. That service also changes with each spacecraft.\n\n"
            "What you need, locally, with no internet at receive time:\n"
            "— A VHF antenna (a turnstile, QFH, or even a simple dipole or whip outdoors, clear of the building).\n"
            "— An SDR receiver that can do 137 MHz (an RTL-SDR class dongle is the common low-cost option) and a computer or phone already loaded with the decoder.\n"
            "— For APT: an FM demodulated audio stream into an APT decoder (WxtoImg, noaa-apt, and similar already-installed tools). For LRPT: a digital demodulator and decoder (SatDump and similar).\n"
            "— A pass prediction for that bird (see the TLE entry). Record during the pass; decode after if the computer is slow.\n\n"
            "This is receive-only. It gives you a recent visible or infrared picture of cloud, ice and surface over your region, which is useful when terrestrial weather data is gone. It is not a NOAA Weather Radio warning stream; for watches and warnings use the VHF NWS transmitters on 162.4–162.55 MHz if any are still on the air."
        ),
    },
]
