"""Channel and frequency tables: FRS, GMRS, MURS, CB, marine VHF, aviation distress, NOAA weather radio, 406 MHz beacons."""

# Frequencies are in MHz. Sources are cited on each entry.

FRS_GMRS_SIMPLEX = [
    # ch, freq, FRS power ERP W, GMRS power W, notes
    (1,  "462.5625", "2",  "5",   "interstitial 462; FRS and GMRS simplex"),
    (2,  "462.5875", "2",  "5",   "interstitial 462; FRS and GMRS simplex"),
    (3,  "462.6125", "2",  "5",   "interstitial 462; FRS and GMRS simplex"),
    (4,  "462.6375", "2",  "5",   "interstitial 462; FRS and GMRS simplex"),
    (5,  "462.6625", "2",  "5",   "interstitial 462; FRS and GMRS simplex"),
    (6,  "462.6875", "2",  "5",   "interstitial 462; FRS and GMRS simplex"),
    (7,  "462.7125", "2",  "5",   "interstitial 462; FRS and GMRS simplex"),
    (8,  "467.5625", "0.5","0.5", "interstitial 467; FRS and GMRS simplex; no repeaters"),
    (9,  "467.5875", "0.5","0.5", "interstitial 467; FRS and GMRS simplex; no repeaters"),
    (10, "467.6125", "0.5","0.5", "interstitial 467; FRS and GMRS simplex; no repeaters"),
    (11, "467.6375", "0.5","0.5", "interstitial 467; FRS and GMRS simplex; no repeaters"),
    (12, "467.6625", "0.5","0.5", "interstitial 467; FRS and GMRS simplex; no repeaters"),
    (13, "467.6875", "0.5","0.5", "interstitial 467; FRS and GMRS simplex; no repeaters"),
    (14, "467.7125", "0.5","0.5", "interstitial 467; FRS and GMRS simplex; no repeaters"),
    (15, "462.5500", "2",  "50",  "462 main channel; FRS simplex / GMRS simplex or repeater output"),
    (16, "462.5750", "2",  "50",  "462 main channel; FRS simplex / GMRS simplex or repeater output"),
    (17, "462.6000", "2",  "50",  "462 main channel; FRS simplex / GMRS simplex or repeater output"),
    (18, "462.6250", "2",  "50",  "462 main channel; FRS simplex / GMRS simplex or repeater output"),
    (19, "462.6500", "2",  "50",  "462 main channel; FRS simplex / GMRS simplex or repeater output"),
    (20, "462.6750", "2",  "50",  "462 main channel; FRS simplex / GMRS simplex or repeater output"),
    (21, "462.7000", "2",  "50",  "462 main channel; FRS simplex / GMRS simplex or repeater output"),
    (22, "462.7250", "2",  "50",  "462 main channel; FRS simplex / GMRS simplex or repeater output"),
]

GMRS_REPEATER_INPUTS = [
    (15, "467.5500"),
    (16, "467.5750"),
    (17, "467.6000"),
    (18, "467.6250"),
    (19, "467.6500"),
    (20, "467.6750"),
    (21, "467.7000"),
    (22, "467.7250"),
]

def _table(rows, header):
    lines = [header, '-' * len(header)]
    lines.extend(rows)
    return '\n'.join(lines)

frs_rows = []
for ch, f, frs_p, gmrs_p, note in FRS_GMRS_SIMPLEX:
    frs_rows.append(f"{ch:>2}  {f}  FRS {frs_p} W ERP  GMRS {gmrs_p} W  {note}")

gmrs_rep = [f"Ch {ch:>2}  output {next(f for c,f,_,_,_ in FRS_GMRS_SIMPLEX if c==ch)}  input {inp}  (+5 MHz split)" for ch, inp in GMRS_REPEATER_INPUTS]

CB = [
    (1, "26.965"), (2, "26.975"), (3, "26.985"), (4, "27.005"), (5, "27.015"),
    (6, "27.025"), (7, "27.035"), (8, "27.055"), (9, "27.065"), (10, "27.075"),
    (11, "27.085"), (12, "27.105"), (13, "27.115"), (14, "27.125"), (15, "27.135"),
    (16, "27.155"), (17, "27.165"), (18, "27.175"), (19, "27.185"), (20, "27.205"),
    (21, "27.215"), (22, "27.225"), (23, "27.255"), (24, "27.235"), (25, "27.245"),
    (26, "27.265"), (27, "27.275"), (28, "27.285"), (29, "27.295"), (30, "27.305"),
    (31, "27.315"), (32, "27.325"), (33, "27.335"), (34, "27.345"), (35, "27.355"),
    (36, "27.365"), (37, "27.375"), (38, "27.385"), (39, "27.395"), (40, "27.405"),
]
cb_lines = []
for ch, f in CB:
    tag = ""
    if ch == 9:
        tag = "  emergency communications and traveler assistance (reserved by rule)"
    elif ch == 19:
        tag = "  widely used as a highway calling channel (not an FCC-reserved emergency channel)"
    elif ch == 23:
        tag = "  frequency is 27.255 (out of numerical order; 24 and 25 sit between 22 and 23)"
    cb_lines.append(f"Ch {ch:>2}  {f} MHz{tag}")

ENTRIES = [
    {
        "id": "frs-channels",
        "title": "FRS channels, frequencies and power",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 95.563, 95.567, 95.531, 95.587",
        "edition": "eCFR Title 47 Part 95 Subpart B (Family Radio Service)",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "frs", "family radio", "walkie", "walkie-talkie", "channel", "462", "467",
            "frs 1", "frs 22", "unlicensed", "part 95",
        ],
        "channels": [f"FRS {c}" for c, *_ in FRS_GMRS_SIMPLEX] + [str(c) for c, *_ in FRS_GMRS_SIMPLEX],
        "frequencies_mhz": [float(f) for _, f, *_ in FRS_GMRS_SIMPLEX],
        "text": (
            "The Family Radio Service (FRS) is a personal radio service under 47 CFR Part 95 Subpart B. "
            "No individual FCC license is required to operate an FCC-certified FRS transmitter (§ 95.531). "
            "FRS shares 22 channels with GMRS. An FRS unit must be a certified handheld (or similar) radio; "
            "it may not be a removable-antenna or high-power GMRS transmitter used as FRS.\n\n"
            "Power (§ 95.567): 2 watts ERP on channels 1–7 and 15–22; 0.5 watt ERP on channels 8–14. "
            "FRS may not use repeaters. Bandwidth and emission limits are in § 95.573 and § 95.587.\n\n"
            + _table(
                frs_rows,
                "Ch  MHz        Power                          Notes",
            )
            + "\n\nFRS may be used for two-way voice, including emergency communications, with other FRS or GMRS units on these channels."
        ),
    },
    {
        "id": "gmrs-channels",
        "title": "GMRS channels, repeater pairs and licensing",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 95.1763, 95.1767, 95.1705, 95.1731",
        "edition": "eCFR Title 47 Part 95 Subpart E (General Mobile Radio Service)",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "gmrs", "repeater", "462", "467", "license", "50 watt", "gmrs 20",
            "general mobile", "family license",
        ],
        "channels": [f"GMRS {c}" for c, *_ in FRS_GMRS_SIMPLEX] + ["repeater"],
        "frequencies_mhz": [float(f) for _, f, *_ in FRS_GMRS_SIMPLEX] + [float(f) for _, f in GMRS_REPEATER_INPUTS],
        "text": (
            "The General Mobile Radio Service (GMRS) is a licensed personal radio service (§ 95.1705). "
            "A GMRS license is issued in the licensee’s name and covers the licensee’s immediate family. "
            "The license term is 10 years (amended from 5 years by FCC 17-119 in 2017). Older library manuals "
            "that still say five years are out of date on that point.\n\n"
            "Power (§ 95.1767): up to 50 watts on the 462 MHz main channels (15–22) and their 467 MHz repeater "
            "inputs; up to 5 watts on the 462 MHz interstitial channels (1–7); 0.5 watt on the 467 MHz interstitial "
            "channels (8–14). GMRS may operate through repeaters on the main-channel pairs. FRS units must not key a repeater.\n\n"
            "Simplex channels are the same 22 frequencies as FRS (see the FRS table). Repeater pairs, GMRS only:\n\n"
            + "\n".join(gmrs_rep)
            + "\n\n"
            "§ 95.1731 permits personal and family two-way communications, including emergency messages. "
            "Identify as the rule requires (§ 95.1751): the call sign at the end of a transmission or series, and at least every 15 minutes during a long exchange."
        ),
    },
    {
        "id": "murs-channels",
        "title": "MURS channels and limits",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 95.2773, 95.2767, 95.2731",
        "edition": "eCFR Title 47 Part 95 Subpart J (Multi-Use Radio Service)",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": ["murs", "multi-use", "151.820", "151.880", "151.940", "154.570", "154.600", "blue dot", "green dot"],
        "frequencies_mhz": [151.820, 151.880, 151.940, 154.570, 154.600],
        "text": (
            "The Multi-Use Radio Service (MURS) is a VHF personal radio service. No individual license is required "
            "to operate a certified MURS transmitter (§ 95.2731). Five channels (§ 95.2773):\n\n"
            "151.820 MHz\n"
            "151.880 MHz\n"
            "151.940 MHz\n"
            "154.570 MHz  (sometimes labeled “Green Dot” on older business radios)\n"
            "154.600 MHz  (sometimes labeled “Blue Dot” on older business radios)\n\n"
            "Power is 2 watts (§ 95.2767). External antennas are allowed, unlike FRS. MURS is useful for short-range "
            "local voice or data around a farm, neighborhood or site when FRS/GMRS is crowded, but it is still line-of-sight VHF with no built-in national calling channel."
        ),
    },
    {
        "id": "cb-channels",
        "title": "CB (Citizens Band) channels, including channel 9 emergency and channel 19",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 95.963, 95.957, 95.967, 95.931",
        "edition": "eCFR Title 47 Part 95 Subpart D (CB Radio Service)",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "cb", "citizens band", "channel 9", "channel 19", "27 mhz", "11 meter",
            "cb 9", "cb 19", "emergency channel", "highway",
        ],
        "channels": [f"CB {c}" for c, _ in CB] + ["channel 9", "ch 9", "channel 19", "ch 19"],
        "frequencies_mhz": [float(f) for _, f in CB],
        "text": (
            "Citizens Band is 40 channels on 26.965–27.405 MHz (11 meters). No individual license is required "
            "for a certified CB transmitter. Power (§ 95.967): 4 watts carrier on AM, 12 watts PEP on SSB.\n\n"
            "§ 95.957 reserves channel 9 (27.065 MHz) for emergency communications or assistance to a traveler. "
            "If you have an emergency or need traveler help, that is the first CB channel to try. Channel 19 "
            "(27.185 MHz) is widely used in the US as a highway calling and traffic channel; the FCC does not "
            "reserve it as an emergency channel, but many mobile stations monitor it.\n\n"
            "Channel 23 is 27.255 MHz, which sits above 24 and 25 (27.235 and 27.245). That numbering is in the rule, not a typo.\n\n"
            + "\n".join(cb_lines)
        ),
    },
    {
        "id": "marine-vhf",
        "title": "Marine VHF distress, calling and working channels (US)",
        "publisher": "Federal Communications Commission / US Coast Guard",
        "section": "47 CFR 80.313, 80.314, 80.369, 80.871, 80.148",
        "edition": "eCFR Title 47 Part 80; ITU Radio Regulations Appendix 18 as applied in the US",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "marine", "vhf", "channel 16", "channel 13", "channel 22a", "22a", "156.8",
            "distress", "coast guard", "bridge-to-bridge", "dsc", "channel 70", "channel 6",
            "mayday", "pan-pan",
        ],
        "channels": ["16", "13", "22A", "22a", "6", "9", "70", "67", "marine 16", "channel 16"],
        "frequencies_mhz": [156.800, 156.650, 157.100, 156.300, 156.450, 156.525, 156.375, 156.625],
        "text": (
            "US marine VHF uses the international channel plan (ITU RR Appendix 18) as implemented in 47 CFR Part 80. "
            "These are the channels that matter first in an emergency or when you need official help:\n\n"
            "Channel 16  156.800 MHz  Distress, safety and calling. This is the voice distress and hailing channel. "
            "Ships required to carry VHF keep a watch on 16. Make a distress or safety call here, then move to a working channel when told.\n"
            "Channel 13  156.650 MHz  Bridge-to-bridge (navigational) — ship maneuvering, passing, locks and bridges. "
            "Keep transmissions short and navigational.\n"
            "Channel 22A 157.100 MHz  US Coast Guard liaison (US simplex on 157.100; this is not international duplex channel 22). "
            "The Coast Guard often directs you from 16 to 22A for working traffic.\n"
            "Channel 6   156.300 MHz  Intership safety.\n"
            "Channel 9   156.450 MHz  Alternate calling in many US areas (commercial and non-commercial).\n"
            "Channel 67  156.375 MHz  Alternate bridge-to-bridge in some waters.\n"
            "Channel 70  156.525 MHz  Digital Selective Calling (DSC) only — no voice.\n"
            "Channel 72  156.625 MHz  Intership (non-commercial).\n\n"
            "Distress procedure on 16 (§ 80.314 and the international spoken procedure): "
            "MAYDAY MAYDAY MAYDAY, THIS IS (vessel name spoken three times), MAYDAY (name), POSITION, NATURE OF DISTRESS, "
            "ASSISTANCE REQUIRED, NUMBER OF PERSONS, other useful information, OVER. "
            "Urgency (a serious situation that is not yet a distress) uses PAN-PAN, spoken three times, instead of MAYDAY. "
            "Security messages (navigational or weather warnings) use SECURITE.\n\n"
            "If you cannot speak, a DSC distress alert on channel 70, or any other means that attracts attention and gives position, is used under the same distress rules. "
            "A 406 MHz EPIRB is the dedicated maritime distress beacon (see the 406 MHz entry)."
        ),
    },
    {
        "id": "aviation-emergency",
        "title": "Aviation emergency and distress frequencies",
        "publisher": "Federal Communications Commission / FAA",
        "section": "47 CFR 87.195, 87.199, 87.187",
        "edition": "eCFR Title 47 Part 87; FAA AIM distress procedures",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "aviation", "121.5", "243", "guard", "elt", "aircraft", "mayday", "121.500", "243.0", "123.1", "sar",
        ],
        "frequencies_mhz": [121.5, 243.0, 123.1],
        "text": (
            "121.500 MHz is the international aeronautical emergency (distress and urgency) frequency in the VHF air band (§ 87.195). "
            "It is often called “Guard.” Aircraft in distress or urgency use 121.5 if they cannot reach a control frequency, and many towers, centers, and rescue aircraft guard it.\n\n"
            "243.000 MHz is the UHF military distress (“UHF Guard”) frequency, the harmonic counterpart of 121.5. Military aircraft and many rescue assets guard 243.0.\n\n"
            "123.100 MHz is a common search-and-rescue on-scene frequency in US and ICAO practice, used once SAR aircraft and ground parties are working a scene. It is not a substitute for 121.5 as the distress calling frequency.\n\n"
            "Emergency locators: an ELT (aircraft), EPIRB (maritime) or PLB (personal) transmits on 406.0–406.1 MHz to the COSPAS-SARSAT satellite system, usually with a 121.5 MHz homing transmitter for local direction-finding (§ 87.199, § 80.1061). "
            "121.5 is no longer the satellite-detected distress beacon frequency; 406 MHz is. Register a 406 MHz beacon with the national registry (in the US, NOAA SARSAT) so a hit has a name and contacts."
        ),
    },
    {
        "id": "noaa-weather-radio",
        "title": "NOAA Weather Radio frequencies",
        "publisher": "NOAA National Weather Service",
        "section": "NWS NOAA Weather Radio All Hazards transmitter frequencies",
        "edition": "NOAA/NWS public frequency list",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "noaa", "weather radio", "nws", "same", "162.55", "162.400", "wx1", "wx2", "weather",
            "alert", "all hazards",
        ],
        "channels": ["WX1", "WX2", "WX3", "WX4", "WX5", "WX6", "WX7"],
        "frequencies_mhz": [162.400, 162.425, 162.450, 162.475, 162.500, 162.525, 162.550],
        "text": (
            "NOAA Weather Radio All Hazards transmits continuous weather and warning audio on seven VHF-FM frequencies (NWS):\n\n"
            "162.400 MHz\n"
            "162.425 MHz\n"
            "162.450 MHz\n"
            "162.475 MHz\n"
            "162.500 MHz\n"
            "162.525 MHz\n"
            "162.550 MHz\n\n"
            "Common consumer and marine “WX” channel labels (these labels are radio-maker practice, not an NWS rule):\n"
            "WX1 162.550   WX2 162.400   WX3 162.475   WX4 162.425\n"
            "WX5 162.450   WX6 162.500   WX7 162.525\n\n"
            "A radio with SAME (Specific Area Message Encoding) alerting can be set to a county or SAME code so it wakes on warnings for that area. "
            "Coverage is by transmitter site, not by a single national frequency: you must use the frequency of the transmitter that serves your location. "
            "This module does not include a site-by-site list (those assignments are local). If you already know the frequency posted for your county, use it. "
            "Marine VHF radios often include these as weather channels, receive-only."
        ),
    },
    {
        "id": "beacons-406",
        "title": "406 MHz distress beacons (EPIRB, PLB, ELT)",
        "publisher": "NOAA SARSAT / FCC",
        "section": "47 CFR 80.1061, 87.199; COSPAS-SARSAT 406.0–406.1 MHz",
        "edition": "eCFR; NOAA SARSAT beacon guidance",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "406", "epirb", "plb", "elt", "cospas", "sarsat", "beacon", "distress beacon",
            "121.5 homing", "personal locator",
        ],
        "frequencies_mhz": [406.0, 406.1, 121.5],
        "text": (
            "COSPAS-SARSAT distress beacons transmit in 406.0–406.1 MHz. The satellite system detects the beacon, locates it, and issues an alert to search-and-rescue authorities. "
            "Classes:\n"
            "— EPIRB: Emergency Position-Indicating Radio Beacon, for vessels.\n"
            "— ELT: Emergency Locator Transmitter, for aircraft.\n"
            "— PLB: Personal Locator Beacon, for a person on land or as a personal backup.\n\n"
            "A 406 MHz beacon typically also radiates a 121.5 MHz homing signal so a rescue aircraft or ground party can direction-find the last few miles. "
            "Satellite detection itself is on 406 MHz, not 121.5.\n\n"
            "Registration is part of how the system works: a US 406 MHz beacon is registered with NOAA SARSAT so an alert includes identity and emergency contacts. "
            "An unregistered beacon can still be detected, but the authorities lose the name, trip plan and phone numbers that turn a hit into a faster rescue. "
            "Keep the registration current when ownership or contacts change. Test only as the manufacturer and NOAA instruct (the self-test function), not by firing a live distress alert."
        ),
    },
]
