"""Emergency-use rules: 47 CFR 97.403/97.405, GMRS/FRS/CB/marine emergency provisions, and operating when authority is not functioning."""

ENTRIES = [
    {
        "id": "part97-403-405",
        "title": "Amateur stations: safety of life, protection of property, and stations in distress",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 97.403, 97.405",
        "edition": "eCFR Title 47 Part 97 Subpart E",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "97.403", "97.405", "emergency", "distress", "any means", "safety of life",
            "protection of property", "part 97", "imminent", "life", "property",
            "break the rules", "override",
        ],
        "text": (
            "§ 97.403 Safety of life and protection of property.\n"
            "“No provision of these rules prevents the use by an amateur station of any means of radiocommunication at its disposal to provide essential communication in connection with the immediate safety of human life and immediate protection of property when normal communication systems are not available.”\n\n"
            "§ 97.405 Station in distress.\n"
            "(a) “No provision of these rules prevents the use by an amateur station in distress of any means at its disposal to attract attention, make known its condition and location, and obtain assistance.”\n"
            "(b) “No provision of these rules prevents the use by a station, in the exceptional circumstances described in paragraph (a) of this section, of any means of radiocommunications at its disposal to assist a station in distress.”\n\n"
            "What that means in practice:\n"
            "— The trigger in § 97.403 is immediate safety of human life, or immediate protection of property, and normal communication systems are not available. That is a present threat, not a convenient workaround for everyday traffic.\n"
            "— “Any means of radiocommunication at its disposal” includes a frequency, mode, or power you would not otherwise be allowed to use, including means outside the amateur service, if that is what you have and it is what will get essential traffic through.\n"
            "— § 97.405(a) covers you when you are the station in distress: any means to attract attention, give condition and location, and get help.\n"
            "— § 97.405(b) covers everyone else in that situation: any means to assist the station in distress.\n"
            "— You do not need prior permission, a net control’s blessing, or a working telephone to a regulator before using these sections. The text is the authorization. It sits in the rules specifically so the rest of Part 97 does not block a rescue.\n"
            "— Identify, give position, state the condition, say what you need, and keep the channel open for the work. When the immediate threat has passed and normal systems are back, the ordinary rules apply again."
        ),
    },
    {
        "id": "no-functioning-government",
        "title": "Operating when civil authority is not functioning",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 97.403, 97.405, 97.119; 47 CFR 80.314; 47 CFR 87.195",
        "edition": "eCFR Title 47, applied to a failure of civil authority",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "no government", "collapsed", "no authority", "grid down", "no fcc",
            "no license", "civil authority", "anarchy", "when rules end", "martial",
            "failed state", "no dispatch", "no 911",
        ],
        "text": (
            "Licensing, enforcement and dispatch all assume a functioning state. Radio does not. If government, including the FCC and local dispatch, cannot be reached or has ceased to function, the radio still transmits and the people who can help will be on the same distress and calling channels they were trained to watch.\n\n"
            "§ 97.403 and § 97.405 already authorize any means of radiocommunication when life or property is immediately at risk and normal systems are not available, and any means to assist a station in distress. Those sections do not require a working regulator. They were written for the case where the ordinary system, including the rest of the rules, would otherwise get in the way.\n\n"
            "If there is no functioning licensing authority left to issue, renew, or enforce a license, the operational problem is not paperwork. It is reaching someone who can act. Use the frequencies and procedures other trained operators will recognize:\n"
            "— Distress and calling channels first: marine VHF 16 (156.800 MHz), aviation 121.500 MHz and 243.000 MHz, CB channel 9 (27.065 MHz), NOAA Weather Radio for official warnings if any transmitter is still on the air, amateur national FM calling 146.520 MHz and 446.000 MHz, and the HF nets people actually monitor in your area if you know them.\n"
            "— Spoken distress format: MAYDAY (life-threatening distress), PAN-PAN (urgency), then identity, position, condition, what you need, number of people, OVER. On amateur voice the same information in plain language, with EMERGENCY or PRIORITY at the front, is what net control and other operators are trained to stop for.\n"
            "— Identify as plainly as you can (a call sign if you have one; a name, vessel, or location if you do not). § 97.119 is the ordinary identification rule; in a distress it still helps the other end know who and where you are.\n"
            "— Precedence: life, then immediate protection of property, then medical and coordination traffic, then everything else. Yield the frequency to distress. Keep transmissions short. Do not occupy a distress channel with traffic that can wait or can move off.\n"
            "— Compatibility is what gets a reply: standard frequencies, ITU phonetics, standard distress words, a position, and a clear request.\n\n"
            "A false distress wastes the only channels that still work. Where law still operates, false distress is a crime. Where it does not, it still burns watchers, batteries and time. Do not hoist a hoax; do not jam a frequency that is carrying rescue traffic.\n\n"
            "When some authority is back on the air (a net, a military or civil station, a ship, an aircraft), listen first, then check in with the station that is organizing the frequency. If no one is organizing it, state that you will hold a short watch and take emergency traffic, and do that."
        ),
    },
    {
        "id": "gmrs-frs-cb-emergency",
        "title": "GMRS, FRS and CB emergency provisions",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 95.1731, 95.531, 95.957, 95.931",
        "edition": "eCFR Title 47 Part 95",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "gmrs emergency", "frs emergency", "cb emergency", "channel 9", "95.957",
            "traveler assistance", "personal radio",
        ],
        "channels": ["CB 9", "channel 9"],
        "frequencies_mhz": [27.065],
        "text": (
            "GMRS (§ 95.1731). A GMRS station may be used for personal and family two-way communications, and that includes emergency messages. There is no separate “wait for a disaster declaration” step in the GMRS rules. If you hold a GMRS license (or are covered as family), you may use the licensed GMRS station to pass emergency traffic on GMRS channels, including through a repeater.\n\n"
            "FRS (§ 95.531 and Subpart B). An FRS unit may be used for two-way voice with other FRS or GMRS units on the shared channels, and may be used for emergency communications. No individual license is required. Power and the no-repeater limit still apply in ordinary use; an immediate threat to life or property with no other path is the same kind of situation Part 95, like Part 97, does not exist to block.\n\n"
            "CB (§ 95.957, § 95.931). Channel 9 (27.065 MHz) is reserved for emergency communications or assistance to a traveler. Permissible CB communications include emergency communications. If you need help and CB is what you have, call on channel 9 first; many highway users also monitor channel 19 (27.185 MHz) and can relay, but 19 is not the reserved emergency channel."
        ),
    },
    {
        "id": "marine-aviation-distress-rules",
        "title": "Marine and aviation distress rules",
        "publisher": "Federal Communications Commission / US Coast Guard / FAA",
        "section": "47 CFR 80.313, 80.314, 80.325; 47 CFR 87.195",
        "edition": "eCFR Title 47 Parts 80 and 87",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "mayday", "pan-pan", "securite", "marine distress", "aviation distress",
            "80.314", "coast guard", "silence", "seelonce",
        ],
        "frequencies_mhz": [156.8, 121.5, 243.0],
        "text": (
            "Maritime (Part 80). § 80.313 and § 80.314 set distress, urgency and safety communications. The spoken distress signal is MAYDAY, used only when a vessel, aircraft, or person is in grave and imminent danger and needs immediate help. The urgency signal is PAN-PAN, when a very urgent message concerning the safety of a ship, aircraft, or person must be sent, but the distress threshold is not met. The safety signal is SECURITE, for navigational or important meteorological warnings. A distress call and message have absolute priority. Other stations must cease transmission that might interfere, listen, and assist if they can (§ 80.325 and the international silence rules).\n\n"
            "On VHF, start on channel 16 (156.800 MHz). On MF/HF maritime bands, use the distress frequency for that band if you have it. A DSC alert on channel 70, or a 406 MHz EPIRB, is a distress means as well as voice.\n\n"
            "Aviation (Part 87, FAA AIM). An aircraft in distress or urgency uses the frequency it is already on if a controlling agency is there, or 121.500 MHz (and 243.000 MHz for military UHF). The same MAYDAY / PAN-PAN words are used. Transmit squawk 7700 when able. An ELT on 406 MHz (with 121.5 homing) is the dedicated aircraft beacon."
        ),
    },
    {
        "id": "races-ares-emergency-org",
        "title": "RACES and ARES in an emergency",
        "publisher": "Federal Communications Commission / FEMA / ARRL ARES public manuals",
        "section": "47 CFR 97.407; ARES Field Resources Manual (in-library)",
        "edition": "eCFR Title 47; ARES public field reference",
        "year": "2019",
        "license": "§ 97.407 is a US government work (public domain); ARES manual text is not reproduced here — cite the in-library copy",
        "trust": "official",
        "keywords": [
            "races", "ares", "97.407", "radio amateur civil emergency", "net",
            "emergency traffic", "served agency", "ntc", "nts",
        ],
        "text": (
            "RACES (Radio Amateur Civil Emergency Service) is in the FCC rules at § 97.407. It is a civil-defense radio service that uses amateur stations, registered with a civil defense organization, when that organization is activated. RACES operation is limited to the communications the rule describes (civil defense, immediate safety of life, immediate protection of property, and certain relief and coordination traffic) and, in some declared conditions, to designated frequencies and registered operators.\n\n"
            "ARES (Amateur Radio Emergency Service) is an ARRL-sponsored field organization, not itself a separate FCC service. ARES operators work under ordinary Part 97 (and under § 97.403/97.405 when those apply), often in support of a served agency. The in-library ARES Manual and ARES Field Resources Manual cover organization, net discipline, and message handling.\n\n"
            "Traffic precedence used on amateur emergency nets (ARES/NTS practice): EMERGENCY (life or death, or a grave threat to property, in the moment), PRIORITY (official and urgent, including serious injury not in the EMERGENCY class, and time-critical official traffic), WELFARE (health-and-welfare inquiries and replies), ROUTINE. EMERGENCY traffic breaks anything else.\n\n"
            "If a served agency, RACES, or ARES net is on the air, check in and follow net control. If none is, see the entry on operating when civil authority is not functioning."
        ),
    },
]
