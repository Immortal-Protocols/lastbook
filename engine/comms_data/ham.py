"""Ham radio from zero: licenses, bands, contacts, calling frequencies, repeaters, phonetics, Q-codes, nets, antennas and power."""

PHONETIC = (
    "A Alfa    B Bravo     C Charlie   D Delta     E Echo\n"
    "F Foxtrot G Golf      H Hotel     I India     J Juliett\n"
    "K Kilo    L Lima      M Mike      N November  O Oscar\n"
    "P Papa    Q Quebec    R Romeo     S Sierra    T Tango\n"
    "U Uniform V Victor    W Whiskey   X X-ray     Y Yankee\n"
    "Z Zulu\n\n"
    "Figures, as often spoken on voice: 0 Zee-ro, 1 Wun, 2 Too, 3 Tree, 4 Fow-er, "
    "5 Fife, 6 Six, 7 Sev-en, 8 Ait, 9 Nin-er. ITU-R M.1677 also lists the longer "
    "figure codes (NADAZERO, UNAONE, and so on) used on some radiotelephone circuits."
)

QCODES = (
    "QRL  Are you busy? / I am busy. (Is this frequency in use?)\n"
    "QRM  Is my transmission being interfered with? / Interference from other stations.\n"
    "QRN  Are you troubled by static? / Natural or atmospheric noise.\n"
    "QRO  Shall I increase power? / Increase power.\n"
    "QRP  Shall I decrease power? / Decrease power. Also: low-power operation.\n"
    "QRQ  Shall I send faster? / Send faster.\n"
    "QRS  Shall I send more slowly? / Send more slowly.\n"
    "QRT  Shall I stop sending? / Stop sending; closing station.\n"
    "QRV  Are you ready? / I am ready.\n"
    "QRX  Stand by. / I will call you again at …\n"
    "QRZ  Who is calling me?\n"
    "QSB  Is my signal fading? / Fading.\n"
    "QSL  Can you acknowledge receipt? / I acknowledge receipt.\n"
    "QSO  Can you communicate with …? / A contact.\n"
    "QSY  Shall I change frequency? / Change frequency (to …).\n"
    "QTH  What is your location? / My location is …\n"
    "QST  A general call preceding a message to all amateurs (ARRL usage).\n"
)

ENTRIES = [
    {
        "id": "ham-licenses",
        "title": "US amateur licenses, from zero",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 97.9, 97.17, 97.119, 97.501, 97.509",
        "edition": "eCFR Title 47 Part 97",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "license", "technician", "general", "extra", "amateur extra", "ham ticket",
            "element 2", "element 3", "element 4", "volunteer examiner", "ve", "fcc registration",
            "frn", "call sign", "from zero", "how to get licensed", "novice", "advanced",
        ],
        "text": (
            "A US amateur station must be operated by a licensed amateur, or under the privileges and supervision the rules allow (§ 97.9, § 97.105). "
            "There are three current license classes, each obtained by passing a written exam administered by Volunteer Examiners (§ 97.509):\n\n"
            "Technician (Element 2). The entry license. Full privileges on the amateur bands above 50 MHz (6 meters and up), and limited HF privileges: Morse (CW) on segments of 80, 40 and 15 meters, and CW, data and a slice of phone on 10 meters (§ 97.301). "
            "This is the license most people start with for local VHF/UHF repeaters, simplex, and many emergency nets.\n\n"
            "General (Elements 2 and 3). Adds the major HF phone, CW and data segments used for long-distance and nationwide emergency nets.\n\n"
            "Amateur Extra (Elements 2, 3 and 4). Adds the remaining HF segments reserved to Extra, including the band edges often used for CW DX and some net frequencies.\n\n"
            "Novice and Advanced licenses are no longer issued; existing ones remain valid under the privileges in § 97.301.\n\n"
            "Practical path: get an FCC Registration Number (FRN), sit a VE session with a photo ID, pass the exam, and wait for the call sign to appear in the FCC database (the license is valid when granted in ULS). You must identify with that call sign (§ 97.119): at the end of a communication, and at least every 10 minutes during a long exchange. A Club or vanity call is a later option, not a requirement.\n\n"
            "The exam question pools change on a published cycle. The in-library Technician study guide is written for the 2014–2018 pool; use it for concepts, not as the current question set. This module quotes the operating rules, not a question-pool dump."
        ),
    },
    {
        "id": "ham-bands-privileges",
        "title": "US amateur bands and license privileges",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 97.301, 97.303, 97.305, 97.313",
        "edition": "eCFR Title 47 Part 97",
        "year": "2024",
        "license": "US government work, public domain",
        "trust": "official",
        "keywords": [
            "band plan", "privileges", "hf", "vhf", "uhf", "80 meters", "40 meters",
            "20 meters", "2 meters", "70 centimeters", "10 meters", "6 meters", "60 meters",
            "technician privileges", "band edges",
        ],
        "frequencies_mhz": [
            1.8, 3.5, 5.3, 7.0, 10.1, 14.0, 18.068, 21.0, 24.89, 28.0,
            50.0, 144.0, 222.0, 420.0, 902.0, 1240.0,
        ],
        "text": (
            "US amateur frequency allocations and which class may use them are in § 97.301 (with notes in § 97.303). "
            "Mode rules are in § 97.305 and the emission standards in § 97.307. The figures below are the US amateur band edges, not a substitute for the segment-by-segment table in § 97.301.\n\n"
            "HF and MF (MHz):\n"
            "160 m  1.800–2.000     General and Extra (full band as allocated to those classes).\n"
            "80 m   3.500–4.000     Technician: 3.525–3.600 CW only. General and Extra: wider CW/data and phone segments; Extra has the 3.500–3.525 edge.\n"
            "60 m   five USB channels plus a 15 kHz segment as in § 97.303; 100 W ERP, USB only, listed channels. General and Extra.\n"
            "40 m   7.000–7.300     Technician: 7.025–7.125 CW only. General/Extra: CW/data and phone as segmented; region-2 phone starts at 7.125 for Extra and 7.175 for General (see § 97.301).\n"
            "30 m   10.100–10.150   General and Extra; CW and data only; 200 W PEP (§ 97.313).\n"
            "20 m   14.000–14.350   General and Extra, with Extra-only CW/data at the bottom edge.\n"
            "17 m   18.068–18.168   General and Extra.\n"
            "15 m   21.000–21.450   Technician: 21.025–21.200 CW only. General and Extra: remainder as segmented.\n"
            "12 m   24.890–24.990   General and Extra.\n"
            "10 m   28.000–29.700   Technician: 28.000–28.300 CW/data, 28.300–28.500 CW and phone; General and Extra: the full band, including FM around 29.6.\n\n"
            "VHF and up (Technician, General and Extra all have these amateur allocations, subject to § 97.301 and power/mode rules):\n"
            "6 m    50–54 MHz\n"
            "2 m    144–148 MHz\n"
            "1.25 m 222–225 MHz\n"
            "70 cm  420–450 MHz\n"
            "33 cm  902–928 MHz\n"
            "23 cm  1240–1300 MHz\n"
            "plus higher microwave amateur bands in § 97.301.\n\n"
            "Power (§ 97.313): 1,500 W PEP is the general amateur peak-envelope-power limit, with lower caps on some bands and for some classes (200 W PEP on 30 m; 100 W ERP on 60 m; lower Novice/Technician HF limits where those segments apply). Use the minimum power required to carry out the communication, as the rule also says.\n\n"
            "A one-page color band chart is in the library (ARRL US amateur band chart). Use that chart plus § 97.301 for the exact phone/CW segment edges before you transmit on HF."
        ),
    },
    {
        "id": "ham-calling-simplex",
        "title": "National FM simplex calling frequencies and how to make a contact",
        "publisher": "ARES Field Resources Manual / FCC Part 97 operating rules",
        "section": "47 CFR 97.119, 97.101; ARES Field Resources Manual (in-library) national calling frequencies",
        "edition": "Part 97; ARES Field Resources Manual 2019 (library copy)",
        "year": "2019",
        "license": "§ 97.119 and § 97.101 are US government works. The calling frequencies themselves are the published US national FM simplex frequencies used in ARES field references and the standard US VHF/UHF band plan; Part 97 does not itself name “calling frequencies.”",
        "trust": "official",
        "keywords": [
            "146.52", "146.520", "446.000", "446", "simplex", "calling frequency",
            "how to call", "make a contact", "cq", "52.525", "223.500", "29.600",
            "national calling", "2 meter calling",
        ],
        "frequencies_mhz": [29.600, 52.525, 146.520, 223.500, 446.000, 1294.500],
        "text": (
            "Part 97 does not designate “national calling frequencies.” The frequencies below are the published US national FM simplex calling frequencies used in ARES field references and the standard US amateur band plan. They are factual, in-band amateur frequencies. The in-library ARES Field Resources Manual is a citable source for this usage.\n\n"
            "29.600 MHz   10 m FM calling\n"
            "52.525 MHz   6 m FM calling\n"
            "146.520 MHz  2 m FM national simplex calling\n"
            "223.500 MHz  1.25 m FM calling\n"
            "446.000 MHz  70 cm FM national simplex calling\n"
            "1294.500 MHz 23 cm FM calling\n\n"
            "How to make a voice contact:\n"
            "1. Listen first. If the frequency is in use, wait or move. On CW, “QRL?” is the usual question; on FM, just listen.\n"
            "2. On a calling frequency, make a short call, then move off for the conversation so the calling channel stays clear. “This is (call sign) listening” or “CQ 2 meters, this is (call sign)” is enough. Answer with both call signs: “(their call) this is (your call).”\n"
            "3. Identify as § 97.119 requires: at the end, and at least every 10 minutes during a long contact.\n"
            "4. On a repeater, listen through a tail or two, then call. Use the repeater’s offset and tone (see the repeaters entry). A call on a repeater is usually to a station or “monitoring,” not a long CQ.\n"
            "5. Exchange what matters: your call, your location (grid or place), whether this is emergency or routine traffic, and a clear request if you need a relay.\n"
            "6. When you are done, sign clearly (“(call) out” or “clear”) and, on a calling frequency or repeater, leave the channel.\n\n"
            "A widely published HF frequency used for maritime mobile and long-range emergency-related nets is 14.300 MHz USB (20 m). HF net lists change; use a frequency you know is watched, or the net your local ARES/RACES plan names."
        ),
    },
    {
        "id": "ham-repeaters",
        "title": "Repeaters, offsets and tones",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 97.205, 97.119, 97.101",
        "edition": "eCFR Title 47 Part 97; standard US VHF/UHF repeater practice",
        "year": "2024",
        "license": "US government work, public domain (the rule). Offset conventions below are standard US coordinator/band-plan practice, not a Part 97 table.",
        "trust": "official",
        "keywords": [
            "repeater", "offset", "plus 600", "minus 600", "5 mhz", "ctcss", "pl tone",
            "dcs", "duplex", "input", "output", "coordinator",
        ],
        "text": (
            "A repeater (§ 97.205) listens on one frequency (input) and retransmits on another (output) so handhelds and mobiles can reach farther, often from high ground. You transmit on the input and listen on the output. Identification still uses your call sign; the repeater also identifies itself as the rule requires.\n\n"
            "Standard US amateur offsets (band-plan / coordinator practice; a local machine may differ):\n"
            "2 m (144–148 MHz): 600 kHz. A common pattern is a minus offset below 147 MHz and a plus offset above 147 MHz, but check the actual machine. If the output is 146.840, a minus-600 input is 146.240. If the output is 147.150, a plus-600 input is 147.750.\n"
            "70 cm (420–450 MHz): commonly +5 MHz (output 446.000 is not a repeater calling pair; a 447.xxx output often has a 442.xxx input, or the reverse, depending on the region).\n"
            "1.25 m (222–225 MHz): commonly −1.6 MHz.\n"
            "6 m: often 500 kHz or 1 MHz; local practice varies more.\n\n"
            "Tones: most repeaters require a CTCSS (PL) or DCS tone on the input so they do not key on noise or skip. The tone is a local coordinator or trustee setting. This module does not include a national repeater directory; those lists change and are not in the FCC rules. Use a printed or previously saved local list, a club handout, or a repeater you already programmed.\n\n"
            "Open a repeater with the correct offset and tone, say your call sign, and listen. If you cannot key it, the usual causes are wrong offset, wrong or missing tone, being out of range, or a machine that is down. Do not “kerchunk” repeatedly without identifying (§ 97.119 still applies)."
        ),
    },
    {
        "id": "phonetic-alphabet",
        "title": "ITU / ICAO phonetic alphabet",
        "publisher": "FAA / ITU",
        "section": "FAA Aeronautical Information Manual phonetic alphabet; ITU-R M.1677",
        "edition": "FAA AIM (US government); ITU-R M.1677-1 International Morse and phonetics as used in US government radiotelephone practice",
        "year": "2024",
        "license": "FAA AIM is a US government work, public domain. The alphabet is the international ICAO/ITU standard reproduced there.",
        "trust": "official",
        "keywords": [
            "phonetic", "alphabet", "alfa", "alpha", "bravo", "icao", "itu",
            "nato", "spell", "call sign",
        ],
        "text": (
            "Use the international radiotelephony spelling alphabet (ICAO / ITU, printed in the FAA Aeronautical Information Manual) when spelling a call sign, a place, or a difficult word. The official spellings are Alfa (not “Alpha”) and Juliett (with two t’s).\n\n"
            + PHONETIC
            + "\n\nOn a noisy channel, spell the call sign every time you give it, then say it as a word if it is pronounceable. Do not invent a private phonetic set when working a net or a station you do not already know; the other end is listening for this one."
        ),
    },
    {
        "id": "q-codes-prowords",
        "title": "Q-codes and voice prowords",
        "publisher": "ITU / US Coast Guard / FEMA ICS practice",
        "section": "ITU Q-code meanings as used in amateur and maritime service; spoken distress and procedure words from ITU RR / USCG and ICS",
        "edition": "Standard international procedure; USCG and ICS public usage",
        "year": "2024",
        "license": "Procedure words and Q-code meanings as used in US government maritime, aeronautical and ICS practice; not a reproduction of a copyrighted ITU recommendation’s prose.",
        "trust": "official",
        "keywords": [
            "q-code", "qth", "qsl", "qsy", "qrt", "qrz", "qrp", "proword", "mayday",
            "pan-pan", "over", "out", "roger", "wilco", "break", "say again", "securite",
        ],
        "text": (
            "Q-codes are three-letter signals, originally from the international Q-code, still used on CW and often spoken on amateur voice (especially HF). A Q-code can be a question or a statement depending on how it is sent. Common amateur and emergency-net usage:\n\n"
            + QCODES
            + "\n"
            "Voice procedure words (maritime, aeronautical, ICS, and amateur emergency nets):\n"
            "MAYDAY — distress (grave and imminent danger, immediate help needed). Spoken three times at the start of a distress call.\n"
            "PAN-PAN — urgency (a serious safety message that is not yet a distress). Spoken three times.\n"
            "SECURITE — a safety or navigational / weather warning.\n"
            "THIS IS — the station speaking is about to give its identity.\n"
            "OVER — I have finished this transmission and I expect a reply.\n"
            "OUT — I have finished; no reply is required. (Do not say “over and out.”)\n"
            "ROGER — I have received and understood your last transmission. It does not by itself mean I will comply.\n"
            "WILCO — I have received, understood, and will comply.\n"
            "SAY AGAIN — repeat your last (or the portion named).\n"
            "CORRECTION — I made an error; the correct words follow.\n"
            "I SPELL — the next group is spelled phonetically.\n"
            "FIGURES — the next group is numerals.\n"
            "BREAK — a boundary between parts of a message, or a request to interrupt for urgent traffic (on some nets, “break break” flags emergency traffic).\n"
            "WAIT / STAND BY — a short pause; I will resume.\n"
            "AFFIRMATIVE / NEGATIVE — yes / no, when “yes” and “no” could be lost in noise.\n"
            "UNKNOWN STATION — used when you hear a station but do not have its call sign.\n\n"
            "On an organized amateur net, follow net control. Offer emergency traffic first, in plain language, with the precedence (EMERGENCY, PRIORITY, WELFARE, ROUTINE) at the front."
        ),
    },
    {
        "id": "ham-nets-traffic",
        "title": "Nets and emergency traffic handling",
        "publisher": "ARES public field manuals / 47 CFR 97.101, 97.115, 97.407",
        "section": "47 CFR 97.101, 97.115, 97.407; ARES Field Resources Manual (in-library)",
        "edition": "Part 97; ARES field reference",
        "year": "2019",
        "license": "Part 97 is a US government work. Message-handling practice summarized from public ARES field references already in the library; the manuals themselves are not copied here.",
        "trust": "official",
        "keywords": [
            "net", "net control", "ncs", "traffic", "radiogram", "ics-213", "third party",
            "97.115", "welfare", "precedence", "directed net",
        ],
        "text": (
            "A net is a scheduled or ad-hoc gathering on one frequency, with a net-control station (NCS) directing who transmits. In an emergency this is how a frequency stays usable: one station invites check-ins, lists traffic, and calls stations in turn.\n\n"
            "If you hear an emergency or ARES/RACES net, listen, then check in only as NCS asks (usually “with or without traffic,” and whether that traffic is Emergency, Priority, Welfare or Routine). Do not call CQ on a directed net. If you have Emergency traffic, say so immediately — “break, emergency traffic” — and wait to be recognized unless the channel is silent and the traffic cannot wait.\n\n"
            "Message form: formal amateur radiograms (NTS) and ICS-213 general message forms are the two formats most served agencies and ARES groups expect. The in-library ARES manuals show the blanks. At minimum a formal message has: a number, a precedence, the originating station, time and date, the addressee, the text, and a signature. Read it slowly, in groups, and get a fill on anything missed.\n\n"
            "Third-party traffic (§ 97.115): passing a message for someone who is not an amateur is allowed under the conditions in that rule, including the international restrictions (some countries do not permit third-party amateur traffic). In a § 97.403/97.405 situation, essential life-and-property traffic is authorized by those sections.\n\n"
            "Tactical call signs (for example “Shelter 2”) are common on a served-agency net; Part 97 still requires the FCC call sign on the regular identification interval (§ 97.119)."
        ),
    },
    {
        "id": "ham-antennas-power",
        "title": "Antennas and power basics",
        "publisher": "Federal Communications Commission",
        "section": "47 CFR 97.13, 97.15, 97.313",
        "edition": "eCFR Title 47 Part 97",
        "year": "2024",
        "license": "US government work, public domain. Length-of-dipole figures are the standard half-wave formulas taught in the amateur exam pools and public study material.",
        "trust": "official",
        "keywords": [
            "antenna", "dipole", "power", "1500 watts", "erp", "swr", "feedline",
            "vertical", "j-pole", "counterpoise", "97.313", "97.15", "prb-1",
        ],
        "text": (
            "Power (§ 97.313): the general amateur limit is 1,500 watts PEP, with lower caps on some bands (200 W PEP on 30 m, 100 W ERP on 60 m, and the Novice/Technician HF limits in the rule). The same section requires using the minimum power necessary to carry out the communication. A handheld at a few watts on VHF will work through a local repeater or across a few miles of simplex line-of-sight; HF emergency work is more often tens to a few hundred watts into a decent antenna, not a kilowatt.\n\n"
            "Antenna structures (§ 97.15): the FCC, not a homeowners’ association, occupies the field on amateur antenna regulation to the extent of the Commission’s PRB-1 policy and § 97.15, but local safety and aircraft-obstruction rules still apply, and PRB-1 does not pre-empt every private covenant. In an emergency you will use the antenna you can actually raise.\n\n"
            "Half-wave dipole length, in feet, is approximately 468 / f(MHz) for the whole wire (each leg 234 / f). In meters, a half-wave is about 143 / f(MHz) for the whole wire. These are starting lengths; trim for the lowest SWR in the part of the band you will use. A dipole wants to be as high and as clear as you can make it. A vertical needs a counterpoise or radials. A magnetic mount or a handheld “rubber duck” is an antenna of last resort: it will work close in and on a strong repeater, and will disappoint on simplex and HF.\n\n"
            "Feedline: 50-ohm coax is the usual amateur feed. Keep it as short and as low-loss as you can at VHF/UHF (loss is higher there than on HF). A common-mode choke or a few turns of coax at the feed point often quiets RF-in-the-shack problems.\n\n"
            "Station grounding and lightning: bond equipment together; do not invent a second “ground” that can carry a difference of potential through you. Disconnect antennas when a storm is on the station if you can."
        ),
    },
]
