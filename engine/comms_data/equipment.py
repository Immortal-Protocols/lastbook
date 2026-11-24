"""Equipment interoperation, found-radio practice, and public-domain manual candidates.

Inventory rows live in equipment_rows.py (108 sourced models). This module holds the
citable narrative entries. Commercial manufacturer manuals are cited, not bundled.
"""

ENTRIES = [
    {
        "id": "equipment-interop",
        "title": "How emergency-comms equipment interoperate — and when they do not",
        "publisher": "Lastbook comms equipment survey, November 2026",
        "section": "Survey §1, How this equipment fits a comms plan (interop paragraph); 47 CFR Parts 95 and 97; PRC-25/77 and PRC-104 TMs",
        "edition": "Survey compiled from manufacturer specifications, FCC rules, and U.S. military technical manuals. November 2026.",
        "year": "2026",
        "license": "Original survey summary. Rule facts are US government works. The survey does not copy commercial manuals.",
        "trust": "survey",
        "keywords": [
            "interop", "interoperate", "interoperability", "compatible", "will it talk",
            "prc-25", "prc-77", "frs gmrs", "marine aviation", "layer", "found radio",
            "equipment", "surplus", "50 khz", "channel spacing",
        ],
        "frequencies_mhz": [146.520, 52.525],
        "text": (
            "Radios only talk to each other when frequency, mode, channel spacing, and (for digital) protocol all match. A practical plan is layered, because no single radio covers every distance or every audience.\n\n"
            "Layers, typical use, and example gear:\n"
            "— Wire / sound-powered (hundreds of yards to longer runs of WD-1): fixed site, house-to-barn. EE-8, TA-312, WD-1/TT.\n"
            "— Local voice, unlicensed or licensed-by-rule (neighborhood to a few miles, more with height): FRS, MURS, CB AM/SSB.\n"
            "— Local licensed higher power (miles to tens of miles, further through a repeater): GMRS mobiles and repeaters.\n"
            "— VHF/UHF amateur (line-of-sight, plus repeaters if still powered): HTs, mobiles, dual-band bases; ARES/RACES, APRS.\n"
            "— LoRa mesh text (blocks to hills, hops through other nodes): Meshtastic on 915 MHz in the US. Text and position, not voice.\n"
            "— HF amateur / marine SSB (regional NVIS to intercontinental): 100 W HF rig, PRC-104, marine SSB.\n"
            "— Broadcast receive: NOAA Weather Radio 162 MHz, AM/FM, shortwave, scanners.\n"
            "— Satellite messenger or phone: inReach, Iridium, IsatPhone — needs an already-active account and a sky view.\n"
            "— 406 MHz distress beacon: PLB or EPIRB, one-way alert to SAR, register it.\n"
            "— Email / text over radio: Winlink, VARA, Pactor, JS8Call, packet, mesh.\n\n"
            "What does and does not interoperate:\n"
            "— A 1960s PRC-25 will talk to a PRC-77 and to many later VHF-FM military sets on 50 kHz channels between 30 and 75.95 MHz. It will not land on the 2-meter amateur calling frequency 146.520 MHz. On 6 meters it cannot hit 52.525 MHz on its 50 kHz steps (52.50 and 52.55 are the adjacent steps).\n"
            "— FRS and GMRS share the same 22 channels at 462/467 MHz, so a 2-watt FRS handheld can talk to a 50-watt GMRS mobile on channels 1–7 and 15–22 if CTCSS/DCS tones match. FRS still cannot key a GMRS repeater.\n"
            "— Marine VHF does not share FRS/GMRS channels. Aviation VHF AM (118–137 MHz) does not interoperate with FM land-mobile or amateur FM. CB 27 MHz AM/SSB does not interoperate with amateur 10-meter FM or with FRS.\n"
            "— Email systems need a matching modem and, for Winlink, a reachable RMS gateway, a radio-only/Hybrid path, or a peer-to-peer schedule.\n"
            "— A late-generation military handheld (PRC-152, PRC-148, PRC-117) without keys, hopping fills, or SATCOM provisioning may still do plain analog FM if that mode is enabled; it will not do Type-1 voice or hopping. Analog FM interop with a PRC-77 is possible only on a shared 30–88 MHz frequency and compatible spacing.\n\n"
            "Power and antennas decide whether a found radio is usable. A 100-watt HF transceiver is inert without about 13.8 V at about 20 A, a 50-ohm antenna near resonance (or a tuner and a wire), and a microphone or key. A handheld may run on a leftover pack or a AA case. A tube HF rig may need 120 VAC and a warm-up, and the final tubes may be weak. Military HF manpacks such as the PRC-104 typically want 24–28 V, not 12 V. Plan power and wire first."
        ),
    },
    {
        "id": "found-radio-identify-power",
        "title": "Identifying, powering and using a found radio",
        "publisher": "Lastbook comms equipment survey, November 2026",
        "section": "Survey §2.5 (found HF rig) and §8 (military surplus operating notes)",
        "edition": "November 2026 survey, sourced from manufacturer practice and U.S. Army TMs for the surplus sets named",
        "year": "2026",
        "license": "Original survey operating notes. PRC-25/PRC-104 figures follow the public U.S. Army technical manuals named in the manuals entry.",
        "trust": "survey",
        "keywords": [
            "found radio", "identify", "power", "13.8", "24 volt", "tube", "solid state",
            "battery", "microphone", "repair", "scavenge", "surplus", "pinout", "powerpole",
        ],
        "text": (
            "When you find a radio you do not already know:\n"
            "1. Read the model on the front panel or rear cage, exactly. The inventory in this tool can be searched by make or model (for example PRC-25, UV-5R, IC-7300, EE-8).\n"
            "2. Identify the power connector before applying anything. A three-pin IEC or two-pin mains socket means a built-in AC supply — many older base HF rigs. A large 13.8 V connector (later go-kits often use Anderson Powerpole) means a DC radio: do not apply 120 VAC. Some Heathkit HF rigs expect a specific HP-23 supply. Military HF often wants 24–28 V (PRC-104; Clansman PRC-320), not 12 V.\n"
            "3. Tube versus solid state: heavy, ventilation over a PA cage, a “plate” or “tune/load” pair, and a warm-up of a minute or more indicate tubes. High voltage inside is lethal; discharge capacitors before any internal work.\n"
            "4. On tube and hybrid rigs, look for a rusted cage, leaky electrolytics, and an unstable VFO. Recap a bad power supply first. Confirm power into a dummy load before an antenna.\n"
            "5. On solid-state 100 W rigs, confirm 13.8 V at 20+ A and a fuse. Keying into no antenna or a short is a common way to destroy the PA.\n"
            "6. Band coverage: pre-WARC HF radios may lack 30, 17 and 12 m, and often 60 m. Many can still listen to WWV at 10 or 15 MHz.\n"
            "7. Microphones are often unique (8-pin Yaesu, Kenwood and Icom pinouts differ). A mismatched mic may have no PTT or no audio. A straight key on the key jack still sends CW if the radio has CW.\n\n"
            "PRC-25 / PRC-77 (30–75.95 MHz FM, 50 kHz steps, about 1.5–2 W): seat a good 12–15 V battery after inspecting the box for leaked residue; attach the H-189 or H-250 handset; set a 50 kHz channel; this is not a 2-meter ham set. The PRC-25 PA final is a 2DF4 tube and holds lethal voltage. See TM 11-5820-398-12 (public-domain candidate).\n\n"
            "PRC-104 / 104A (2–30 MHz USB/LSB/CW/FSK, 20 W PEP, 100 Hz steps): needs a nominal 24–28 V pack. It auto-couples to a whip and can work amateur HF if the operator is authorized and the signal is clean. See TM 11-5820-919-12.\n\n"
            "A cheap dual-band handheld (Baofeng UV-5R class) is widely used on amateur 2 m and 70 cm. It is not an FRS or GMRS radio unless that specific model is certified under Part 95. Common failures: stock antennas, brittle battery clips, wrong wide/narrow or tone programming, dirty SMA connectors.\n\n"
            "This tool’s equipment inventory has 108 sourced models and families (1960s through 2026). Ask for a make or model to pull the row. Commercial service manuals for Yaesu, Kenwood, Icom, Midland, Garmin and the like are copyrighted and are not bundled; U.S. government TMs and dated 47 CFR snapshots are the clean ingest path (see the public-domain manuals entry)."
        ),
    },
    {
        "id": "manuals-pd-candidates",
        "title": "Public-domain manuals worth ingesting (not bundled in this build)",
        "publisher": "U.S. government works / Lastbook comms manual-candidate list, November 2026",
        "section": "17 U.S.C. § 105; TM 11-333; TM 11-5820-398-12; TM 11-5820-919-12; dated 47 CFR Parts 95 and 97 snapshots",
        "edition": "Candidate list November 2026. These manuals are not shipped inside this app; this entry names them so a later library ingest can add citable pages.",
        "year": "2026",
        "license": "The manuals named here are U.S. government works (17 U.S.C. § 105) or official rule text, except where a distribution legend is flagged. This entry does not bundle the files and does not include commercial manufacturer manuals.",
        "trust": "official",
        "keywords": [
            "manual", "tm 11-333", "tm 11-5820", "prc-25 manual", "prc-104 manual",
            "ee-8", "r-390a", "part 97 snapshot", "part 95 snapshot", "public domain",
            "technical manual", "field telephone", "ingest",
        ],
        "text": (
            "U.S. government works are not subject to U.S. copyright under 17 U.S.C. § 105. Those are the clean manuals to add to the Lastbook library later, so a guide can cite a real page. This build quotes the cited 47 CFR sections and names the TMs; it does not ship the PDF files.\n\n"
            "First ingest candidates (clear U.S. government works):\n"
            "— A dated snapshot of 47 CFR Part 97 (at least §§ 97.403, 97.405, and the license/band portions) and Part 95 (FRS, CB, GMRS, MURS channel and power sections). This tool already quotes those cited sections; a full official edition in the library would close the remaining gap.\n"
            "— NOAA Weather Radio frequency/SAME material and USCG VHF channel / watchkeeping pages.\n"
            "— TM 11-333, Telephones EE-8, EE-8-A and EE-8-B (War Department, 1945). Install, operate, maintain and repair the common WWII/Korea field phone still in surplus. Pre-distribution-statement era.\n"
            "— TM 11-5820-398-12, Operator and Organizational Maintenance Manual, Radio Set AN/PRC-25 (November 1965, with later changes). Identify, power, set frequency, use AT-271/AT-892 antennas, organizational maintenance. Complement: the January 1963 Field and Depot Maintenance Manual (schematics, 2DF4 final).\n"
            "— TM 11-5820-919-12, Operator’s and Organizational Maintenance Manual, Radio Set AN/PRC-104(A) (15 January 1986). 2–30 MHz, USB/LSB/CW/FSK, 24 V batteries, organizational repair, HF propagation notes, and dipole kit instructions.\n"
            "— TM 11-5820-358-35, Field and depot maintenance, Radio Receiver R-390A/URR (1961 lineage with changes), if the library wants “found a heavy military HF receiver.”\n"
            "— NOAA SARSAT 406 MHz beacon registration guidance, and a short official EMP/shielding text such as the 2022 DHS S&T EMP mitigation best practices, if those pages are ingested as dated snapshots.\n\n"
            "Check the title-page distribution statement on any Army TM from the 1980s onward before ingesting. A legend that limits distribution to DoD is not a copyright statement, but it is a redistribution restriction; prefer an earlier unrestricted printing. FM 24-18 and FM 24-19 (radio operator procedures) are useful companions after that check.\n\n"
            "Do not bundle: commercial manufacturer manuals (Yaesu, Kenwood, Icom, Midland, Garmin, SCS, Kantronics, Sony and similar); ARRL books and the ARES manuals already in the library under their own licences; UK Clansman and Racal manuals (Crown or commercial copyright, not automatically public domain in the US); random photocopies of copyrighted books from “manual warehouse” sites. An archive that also hosts a U.S. government TM is not a licence to copy the commercial files sitting next to it."
        ),
    },
]
