"""Signaling for help, Morse code, and the encode / tone practice page. Morse decode is a later PR."""

ENTRIES = [
    {
        "id": "signaling-distress",
        "title": "Visual and sound signals for help",
        "publisher": "FEMA / Ready.gov / US Coast Guard / Army ATP 3-50.21 Survival (in-library)",
        "section": "Ready.gov and USCG distress-signaling practice; Army ATP 3-50.21 Survival (library copy) on signaling",
        "edition": "US government public guidance; in-library Army survival manual chapter on signaling",
        "year": "2018",
        "license": "US government works, public domain, plus the in-library Army manual as a citable library source for field signaling detail",
        "trust": "official",
        "keywords": [
            "signal", "sos", "mirror", "whistle", "three blasts", "ground to air",
            "signal fire", "panel", "flare", "smoke", "light", "help",
        ],
        "text": (
            "When you need to be found, make a signal that is obviously artificial, repeated, and contrasty, and put it where a searcher will look (a clearing, a ridgeline, a deck, a rooftop).\n\n"
            "The short distress pattern in US and international practice is a group of three: three whistle blasts, three gunshots, three fires in a triangle, three flashes. Repeat, then pause, then repeat. SOS in Morse (dit-dit-dit dah-dah-dah dit-dit-dit, as one sign) is the radiotelegraph and flashing-light distress signal.\n\n"
            "A signal mirror, used with a clear line to an aircraft or a distant point, is one of the longer-range daytime tools a person can carry. A whistle carries farther than a voice and uses less energy. A bright panel, an orange tarp, or arranged rocks and logs in a large SOS or a single V (as taught in survival manuals for ground-to-air) helps an aircraft see you; the in-library Army ATP 3-50.21 Survival manual has the ground-to-air panel figures.\n\n"
            "Fire and smoke: a smoky fire by day, a bright fire by night, in a place that will not start an uncontrolled wildfire. Pyrotechnic flares and smoke are marine and aviation equipment with a limited burn time; fire them when a searcher is in a position to see them, not as a hope on an empty horizon.\n\n"
            "If you have a radio, a 406 MHz beacon, or a satellite messenger, use those as well as a visual signal. A signal does not replace a distress call; it helps the searcher close the last distance."
        ),
    },
    {
        "id": "morse-code-encode",
        "title": "International Morse code: encode, distress, and practice tones",
        "publisher": "ITU / FCC / US Coast Guard",
        "section": "ITU-R M.1677-1 (International Morse code); distress signal SOS as used in the Radio Regulations and USCG / FCC practice",
        "edition": "ITU-R M.1677-1 character set and spacing; PARIS timing standard. This app implements encode and tones; it does not implement decode from audio or light.",
        "year": "2009",
        "license": "The Morse character set and spacing are the international standard (ITU-R M.1677-1). This module implements the standard; it does not copy the recommendation’s prose. SOS as a distress signal is international public procedure.",
        "trust": "official",
        "keywords": [
            "morse", "cw", "encode", "sos", "prosign", "dit", "dah", "wpm", "tones",
            "practice", "telegraph", "paris", "itu",
        ],
        "href": "#/morse",
        "text": (
            "International Morse (ITU-R M.1677-1) represents letters, figures and a set of punctuation as dits (short, written “.”) and dahs (long, written “-”). "
            "A dit is one unit. A dah is three units. The gap inside a character is one unit, the gap between characters is three units, and the gap between words is seven units. "
            "Speed is measured in words per minute using the standard word PARIS (50 units including its trailing word space). At 20 WPM, one unit is 60 milliseconds.\n\n"
            "The distress signal SOS is a single prosign, sent without letter spaces: ...---...  (not S, then O, then S with letter gaps). On voice it is spoken as “SOS” or replaced by MAYDAY. On a whistle, a light, or a key, send the prosign, pause, and repeat.\n\n"
            "Other common prosigns, each sent as one character: AR (end of message), SK (end of work), BT (break / separator), KN (invitation to a specific station), AS (wait), HH (error, eight dits).\n\n"
            "Lastbook can encode text to Morse and play the tones on this device (the Morse practice page, offline, using this computer’s sound). The chat tool lookup_comms will also encode a string when you ask it to. "
            "Decoding Morse from a microphone, a recording, or a flashing light is not in this build; the engine leaves a decode() hook for that work.\n\n"
            "On the amateur bands, Morse is “CW” and may be used wherever the license class and § 97.305 allow CW. Identify with your call sign (§ 97.119). Start slow; a clean 12–15 WPM that the other station can copy is more use than a fast string they cannot."
        ),
    },
    {
        "id": "morse-itu-table",
        "title": "ITU Morse letters and figures",
        "publisher": "ITU",
        "section": "ITU-R M.1677-1 letters and figures",
        "edition": "ITU-R M.1677-1",
        "year": "2009",
        "license": "International Morse character set (ITU-R M.1677-1). Implemented, not copied as prose.",
        "trust": "official",
        "keywords": ["morse table", "alphabet", "letters", "figures", "code chart"],
        "href": "#/morse",
        "text": (
            "Letters:\n"
            "A .-    B -...  C -.-.  D -..   E .     F ..-.\n"
            "G --.   H ....  I ..    J .---  K -.-   L .-..\n"
            "M --    N -.    O ---   P .--.  Q --.-  R .-.\n"
            "S ...   T -     U ..-   V ...-  W .--   X -..-\n"
            "Y -.--  Z --..\n\n"
            "Figures:\n"
            "0 -----  1 .----  2 ..---  3 ...--  4 ....-\n"
            "5 .....  6 -....  7 --...  8 ---..  9 ----.\n\n"
            "A few punctuation signs in the same standard: period .-.-.-  comma --..--  question ..--..  slash -..-.  hyphen -....-  equals / BT -...-  plus / AR .-.-.  at-sign .--.-.\n\n"
            "The practice page on this device will play these signs as tones."
        ),
    },
]
