# Team Mapping Report — WC 2026 Fantasy

Generated during the id-based refactor. All 48 WC2026 teams mapped to
their stable registry ids from `teams.json`. Use this to cross-verify
`config.py`.

## Mapping logic

For each config team name:
1. Lowercased the name and looked it up via `normalize_name` (which also
   applied existing `TEAM_ALIASES` for variants like "Czech Republic (Czechia)").
2. Matched the result against `registry.name_en` (also lowercased) to find the
   authoritative record and its `id`.
3. Verified: 48/48 resolved with **zero collisions** and **zero unresolved names**.
   All 48 registry teams covered by `TEAM_TIERS`; all 48 roster slots map to
   unique teams (no team owned by two contenders).

## Full 48-team table

| id  | FIFA | Registry name_en                      | Display      | Tier | Owner    | Dark Horse? |
|-----|------|---------------------------------------|--------------|------|----------|-------------|
|  1  | MEX  | Mexico                                | Mexico       |  T1  | Tushar   |             |
|  2  | RSA  | South Africa                          | South Africa |  T4  | Ashwini  |             |
|  3  | KOR  | South Korea                           | South Korea  |  T2  | Ojus     |             |
|  4  | CZE  | Czech Republic                        | **Czechia**  |  T4  | Shishir  | Shishir ★   |
|  5  | CAN  | Canada                                | Canada       |  T1  | Ashwini  |             |
|  6  | BIH  | Bosnia and Herzegovina                | Bosnia and Herzegovina | T4 | Nikhil | Nikhil ★ |
|  7  | QAT  | Qatar                                 | Qatar        |  T3  | Shivansh |             |
|  8  | SUI  | Switzerland                           | Switzerland  |  T2  | Ghanghas |             |
|  9  | BRA  | Brazil                                | Brazil       |  T1  | Tushar   |             |
| 10  | MAR  | Morocco                               | Morocco      |  T2  | Ghanghas |             |
| 11  | HAI  | Haiti                                 | Haiti        |  T4  | Ojus     |             |
| 12  | SCO  | Scotland                              | Scotland     |  T3  | Tushar   |             |
| 13  | USA  | United States                         | United States|  T1  | Shishir  |             |
| 14  | PAR  | Paraguay                              | Paraguay     |  T3  | Ojus     | Ojus ★      |
| 15  | AUS  | Australia                             | Australia    |  T2  | Shishir  |             |
| 16  | TUR  | Turkey                                | **Türkiye**  |  T4  | Ghanghas | Ghanghas ★  |
| 17  | GER  | Germany                               | Germany      |  T1  | Shishir  |             |
| 18  | CUW  | Curaçao                               | Curaçao      |  T4  | Shishir  |             |
| 19  | CIV  | Ivory Coast                           | Ivory Coast  |  T3  | Tushar   |             |
| 20  | ECU  | Ecuador                               | Ecuador      |  T2  | Shivansh |             |
| 21  | NED  | Netherlands                           | Netherlands  |  T1  | Shishir  |             |
| 22  | JPN  | Japan                                 | Japan        |  T2  | Ojus     |             |
| 23  | SWE  | Sweden                                | Sweden       |  T3  | Tushar   | Tushar ★    |
| 24  | TUN  | Tunisia                               | Tunisia      |  T3  | Shivansh |             |
| 25  | BEL  | Belgium                               | Belgium      |  T1  | Shivansh |             |
| 26  | EGY  | Egypt                                 | Egypt        |  T3  | Ashwini  |             |
| 27  | IRN  | Iran                                  | Iran         |  T2  | Tushar   |             |
| 28  | NZL  | New Zealand                           | New Zealand  |  T4  | Tushar   |             |
| 29  | ESP  | Spain                                 | Spain        |  T1  | Shivansh |             |
| 30  | CPV  | Cape Verde                            | Cape Verde   |  T4  | Nikhil   |             |
| 31  | KSA  | Saudi Arabia                          | Saudi Arabia |  T3  | Nikhil   |             |
| 32  | URU  | Uruguay                               | Uruguay      |  T2  | Ghanghas |             |
| 33  | FRA  | France                                | France       |  T1  | Ashwini  |             |
| 34  | SEN  | Senegal                               | Senegal      |  T2  | Nikhil   |             |
| 35  | IRQ  | Iraq                                  | Iraq         |  T4  | Nikhil   |             |
| 36  | NOR  | Norway                                | Norway       |  T3  | Ashwini  | Ashwini ★   |
| 37  | ARG  | Argentina                             | Argentina    |  T1  | Ojus     |             |
| 38  | ALG  | Algeria                               | Algeria      |  T3  | Shivansh | Shivansh ★  |
| 39  | AUT  | Austria                               | Austria      |  T2  | Ghanghas |             |
| 40  | JOR  | Jordan                                | Jordan       |  T4  | Shivansh |             |
| 41  | POR  | Portugal                              | Portugal     |  T1  | Nikhil   |             |
| 42  | COD  | Democratic Republic of the Congo      | **DR Congo** |  T4  | Ashwini  |             |
| 43  | UZB  | Uzbekistan                            | Uzbekistan   |  T3  | Ojus     |             |
| 44  | COL  | Colombia                              | Colombia     |  T2  | Tushar   |             |
| 45  | ENG  | England                               | England      |  T1  | Nikhil   |             |
| 46  | CRO  | Croatia                               | Croatia      |  T2  | Ghanghas |             |
| 47  | GHA  | Ghana                                 | Ghana        |  T4  | Shivansh |             |
| 48  | PAN  | Panama                                | Panama       |  T3  | Ashwini  |             |

**Bold** display names are overrides from `TEAM_DISPLAY_OVERRIDES` (ids 4, 16, 42).
★ = Dark Horse pick for that contender.

## Per-contender rosters (ids)

| Contender | Team ids (with display names) |
|-----------|-------------------------------|
| Shishir   | 17 Germany · 21 Netherlands · 13 United States · 15 Australia · 18 Curaçao · **4 Czechia** |
| Tushar    | 9 Brazil · 1 Mexico · 44 Colombia · 27 Iran · 19 Ivory Coast · 12 Scotland · **23 Sweden** · 28 New Zealand |
| Shivansh  | 25 Belgium · 29 Spain · 20 Ecuador · **38 Algeria** · 7 Qatar · 24 Tunisia · 47 Ghana · 40 Jordan |
| Ghanghas  | 39 Austria · 46 Croatia · 10 Morocco · 8 Switzerland · 32 Uruguay · **16 Türkiye** |
| Ojus      | 37 Argentina · 22 Japan · 3 South Korea · **14 Paraguay** · 43 Uzbekistan · 11 Haiti |
| Nikhil    | 45 England · 41 Portugal · 34 Senegal · 31 Saudi Arabia · **6 Bosnia and Herzegovina** · 30 Cape Verde · 35 Iraq |
| Ashwini   | 5 Canada · 33 France · 26 Egypt · **36 Norway** · 48 Panama · 42 DR Congo · 2 South Africa |

**Bold** = dark horse team for that contender.
