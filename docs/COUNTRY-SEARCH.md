# Emergency numbers in Guides search: a proposal for country context

This is a proposal for discussion, not a decision. It answers the questions raised in #235: how a person tells Guides
search which country they are in, what a bare number does without that, and how to test it. It asks for no location
detection, and everything in it works offline.

A small prototype comes with it: `numberRows` in `web/words.js`, the table in
[emergency-numbers-proposed.json](emergency-numbers-proposed.json), and `test_numbers_need_a_country` in
`app/tests/test_topic_search.py`. `app.js` does not call it, so nothing a person sees changes. The table is read only by
the test and does not ship. Numbers were checked on 20 November 2026 by opening each page named below.

## The problem

Guides search is global. A number in a guide's `keywords` means the same thing for everyone, so it can only be there
if it means the same service everywhere. Several do not:

| Number | Means | Source |
|---|---|---|
| `118` | Ambulance in Italy; fire in Switzerland; police in Sri Lanka | GOV.UK Getting help: [Italy](https://www.gov.uk/foreign-travel-advice/italy/getting-help), [Switzerland](https://www.gov.uk/foreign-travel-advice/switzerland/getting-help), [Sri Lanka](https://www.gov.uk/foreign-travel-advice/sri-lanka/getting-help) |
| `111` | Ambulance, fire and police in New Zealand; NHS medical help in the UK; fire and rescue in Sri Lanka | GOV.UK [New Zealand](https://www.gov.uk/foreign-travel-advice/new-zealand/getting-help), [NHS: when to use 111](https://www.nhs.uk/nhs-services/urgent-and-emergency-care-services/when-to-use-111/), GOV.UK Sri Lanka |
| `115` | Fire in Italy; Edhi ambulance in Pakistan (#98) | GOV.UK Italy. The Edhi number is from #98; GOV.UK's [Pakistan page](https://www.gov.uk/foreign-travel-advice/pakistan/getting-help) lists only 1122 and 15 |
| `119` | Fire in China; ambulance and fire in Japan; police in Sri Lanka | GOV.UK [China](https://www.gov.uk/foreign-travel-advice/china/getting-help), [Japan](https://www.gov.uk/foreign-travel-advice/japan/getting-help), Sri Lanka |

The rule from #98 and #185 is that a fire number should not open first aid, which is why the UAE's `997` and
Thailand's `199` were left out. `111` and `115` are in `hurt.json` today, and both are a fire number somewhere. `118` was
taken out of #235 for the same reason. Adding words one country at a time keeps meeting this, and the fix so far has
been to leave the number out for everyone.

## How the person says which country

Three ways were considered.

1. A setting. The person picks a country once, from a short list, next to Guides search. It is saved with the app's
   other choices (`store.set('country', 'IT')`, the `sg.` keys in `localStorage` that `app.js` already uses), so it works
   in the browser and in the desktop app, offline. It can be cleared at any time, and "No country" is the default.
2. A country name in the search: `118 Italy`, `118 Svizzera`. It needs country names in each language and makes every
   search check for them. It also only helps a person who knows the number is ambiguous.
3. A code in the search: `IT 118`. This does not work with the search as it is. `queryWords` drops two-letter Latin
   words, and many codes are English words or stop words (`IT`, `IN`, `NO`, `IS`, `BE`). `CA` already means California in
   `STATE_CODES` ([REGIONS.md](REGIONS.md)).

The proposal is the setting (1). Nothing existing can stand in for it: the state map chosen in setup says which map was
downloaded, not where the person is, and `web/home-area.json` is a private file of coordinates that never ships.
Reading either as a country would be location detection by another name. Option 2 could follow later if people ask for
it.

The country could be offered at the moment it matters: when a search is answered by the ambiguous-number list below,
that list would end with "Choose your country", which opens the same setting.

## The data

One table, separate from the guides, with a source for every country:

```json
{
  "services": {"ambulance": ["hurt", null], "all": ["hurt", null], "medical": ["hurt", null],
               "fire": ["disaster", "home-fire"], "police": [null, null]},
  "countries": {
    "IT": {"name": "Italy", "source": "https://www.gov.uk/foreign-travel-advice/italy/getting-help",
           "numbers": {"118": "ambulance", "115": "fire", "112": "police"}},
    "CH": {"name": "Switzerland", "source": "https://www.gov.uk/foreign-travel-advice/switzerland/getting-help",
           "numbers": {"112": "all", "144": "ambulance", "118": "fire", "117": "police"}}
  }
}
```

- A country's numbers are copied from its source as written, including the service. GOV.UK lists Italy's 112 as
  "Police", so the table says `police`, even though 112 reaches every service in Italy.
- `services` maps a kind of service to a guide and choice. A fire number opens "Fire in the home", which keeps the rule
  from #185. A police number opens no guide; the row only says what the number is.
- Codes are ISO 3166-1 alpha-2, as in the region proposals.
- In a full version the table would live in `content/` and be served with the topics; keeping it outside the guides
  means a number is never in a guide's `keywords` and in the table at once.

## How search behaves

`numberRows(q, topics, stop, table, country)` in the prototype:

- A number the table does not list is searched as now. `911`, `112` and `999` keep opening first aid.
- With a country chosen that lists the number, its meaning there comes first, labelled with the country:
  `118` in Italy opens Injury and illness, `118` in Switzerland opens Fire in the home.
- Without a country, or with one that does not list the number, a number with one meaning everywhere gets one row, as
  a keyword would. A number with several meanings gets one row per country, ordered by country name, each saying what it
  is there ("Italy: ambulance", "Switzerland: fire"). No guide is picked for the person.
- The other words in the search are ranked as before, without the number. `118 bleeding` in Italy opens the bleeding
  choice.

The neutral list was chosen over returning nothing. Someone who types `118` is likely in an emergency. An empty result
looks like the app does not know the number. The list shows each meaning, each one opens the right guide, and the
choice stays with the person.

## Existing global numbers

`111` and `115` are in `hurt.json` and are fire numbers in Sri Lanka and Italy. The prototype does not change them,
because `app.js` does not call it. In a full version, a number would move from `keywords` to the table as soon as the
table lists it with a second meaning, and `SAME_AS` in the test would drop it. `111` would then give the three-row list
without a country, instead of first aid only. This is a visible change for UK and New Zealand readers, so it is a
question below rather than part of this proposal.

Numbers with one meaning everywhere the table knows (`911`, `999`, `108`, `1122`) can stay as keywords.

## Tests

`test_numbers_need_a_country` runs in all four segmenter modes, like the rest of the file:

| Search | Country | First rows |
|---|---|---|
| `118` | Italy | Injury and illness (ambulance) |
| `118` | Switzerland | Fire in the home (fire); not first aid |
| `118` | Sri Lanka | police, no guide |
| `118` | none, or the UK | Italy: ambulance; Sri Lanka: police; Switzerland: fire |
| `111` | Sri Lanka | Fire in the home |
| `111` | New Zealand | Injury and illness |
| `111` | none | New Zealand; Sri Lanka; United Kingdom |
| `118 bleeding` | Italy | Injury and illness, bleeding |
| `1990` | none | Injury and illness (one meaning) |
| `911` | none | Injury and illness, from the keywords as before |

```bash
python3 -B -m unittest app.tests.test_topic_search
```

## Not in this proposal

- Location detection of any kind, from the system, the map, the time zone or the language.
- Changing the hailstorm work in #235.
- Words other than numbers. Some may need the same treatment later, but numbers are where the harm is.
- Calling a number. The app only finds guides.
- The interface: where the setting sits and how the list looks. That needs screenshots and its own change.

## Questions for the maintainers

1. Is a setting next to Guides search the right place, or should setup ask too?
2. Should `111` and `115` move to the table now, accepting that UK and New Zealand readers would see a list for `111`?
3. Is GOV.UK's Getting help page enough as the one source per country, or should a national source be cited where
   one exists? GOV.UK sometimes lists fewer numbers than a country uses (Pakistan: no 115).
4. Should a police number appear in the list at all, given that it opens no guide?
5. Should the table cover every country GOV.UK lists, or only countries where a number conflicts?
