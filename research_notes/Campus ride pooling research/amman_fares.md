# Amman Taxi, Ride-Hailing and Bus Fares (2026) + University Distances

Research date: 2026-11-27. Currency: 1 JOD = 100 piasters (qirsh) = 1000 fils.
Labels: **[OFFICIAL]** = from regulator/union announcements reported in news; **[INFERRED]** = derived arithmetically from official numbers; **[ESTIMATE]** = my own approximation, not sourced.

## What is the official Amman yellow taxi meter tariff as of 2026?

### Takeaway
From 11 May 2026 the yellow taxi meter is **39 piasters flag fall + 28 piasters/km by day** and **40 piasters + 33 piasters/km at night**, everywhere in Jordan except Aqaba. That makes the pitch deck's "12 km ≈ JOD 3.75" exactly right for a daytime trip with no waiting: 0.39 + 12 × 0.28 = JOD 3.75. I found no official 2026 waiting rate or minimum fare.

### Cited Findings
- [OFFICIAL] New tariff took effect Monday 11 May 2026. Day flag fall went from 37 to 39 piasters and night from 38 to 40. Day per-km went from 26 to 28 piasters and night from 32 to 33. It applies to taxis and public vehicles in all areas except Aqaba (to be amended later). Meters are recalibrated at union branches in Amman/Salt, Irbid and Aqaba. — [Al-Balad News, 11 May 2026](https://albaladnews.net/article/461466)
- [OFFICIAL] The same figures were announced on 6 May 2026, effective "next Monday". The union head said the new fare doesn't fully cover costs, because drivers had absorbed part of the gasoline price rise. App fares were said to rise 20%. — [Altaj News, 6 May 2026](https://www.altaj.news/article/562281)
- Meter recalibration was slow: about 6,000 of roughly 18,000 taxis had been adjusted at one point, and the union extended the recalibration deadline to 18 June. — [Jodaily](https://jodaily.com/%D8%AA%D9%82%D8%AF%D9%85-%D9%81%D9%8A-%D8%B9%D9%85%D9%84%D9%8A%D8%A9-%D8%AA%D8%B9%D8%AF%D9%8A%D9%84-%D8%AA%D8%B9%D8%B1%D9%81%D8%A9-%D8%B3%D9%8A%D8%A7%D8%B1%D8%A7%D8%AA-%D8%A7%D9%84%D8%A3%D8%AC%D8%B1/); search snippet of [Jo24](https://jo24.net/eng/article/10010) (page now returns 404)
- Previous tariff, for back-testing: 37/38 piasters flag fall, 26/32 piasters/km (day/night). A Dec 2023 union figure put waiting at 26 piasters per 35 seconds by day and 32 per 35 seconds at night. That looks like a garbled snippet; read it with caution. — [Jordan Times (search snippet; page returned 403)](https://jordantimes.com/news/local/half-amman-taxis-adjust-meters-new-tariff-%E2%80%94-taxi-union)
- Conflicting snippet: a 2025 Jordan Times item says the June 2025 tariff was 37/38 piasters base with 28 piasters/km. The May 2026 Arabic reports say per-km was 26 before May 2026. — [Jordan Times search result](https://jordantimes.com/node/318723) vs. [Al-Balad](https://albaladnews.net/article/461466)
- Minimum fare: the only explicit official figure I found is from 2019, when the LTRC set a JD 1 minimum per trip, raised the start tariff to 350 fils and set phone-ordered trips at a JD 1 minimum. — [Jordan Times search snippet (2019)](https://jordantimes.com/node/291605)
- Waiting: a 2019-era report gives JD 2.5/hour, while a tourist guide gives about JOD 5/hour. These don't agree. — search snippets from [Jordan Times](https://jordantimes.com/node/289400) and [Welcome Pickups](https://www.welcomepickups.com/?p=310300)

### Inferences
- [INFERRED] Sample fares for the simulator: day fare = 0.39 + 0.28 × km, night fare = 0.40 + 0.33 × km (JOD, excluding waiting).
  - 5 km: day 1.79, night 2.05
  - 12 km: day **3.75** (matches the deck), night 4.36
  - 20 km: day 5.99, night 7.00
- [INFERRED] Yellow taxi waiting is probably about **4.8 piasters/min by day and about 5.66 at night** (JOD 2.9 and 3.4 per hour). I got these by dividing the official 2026 app waiting rates (5.76 and 6.79) by 1.2, since app fares are legally 1.2 × the taxi meter, and the flag-fall and per-km figures fit that ratio exactly (39 × 1.2 = 46.8, 28 × 1.2 = 33.6, 40 × 1.2 = 48, 33 × 1.2 = 39.6).
- [ESTIMATE] Minimum fare: use JOD 1.00 as a placeholder (the 2019 official figure). It is not confirmed for 2026. In practice, short meter trips (under about 2 km) come out below JOD 1 on the meter.
- [ESTIMATE] Night window: commonly treated as roughly 22:00–06:00 locally. **Not confirmed** by any source I found; make it a configurable parameter.

### Gaps
- No primary LTRC document for the May 2026 taxi tariff was retrievable. Figures come from consistent Arabic news reports (Al-Balad, Altaj, Husna FM, Nesan, Assabeel, Al-Mamlaka).
- No confirmed 2026 waiting rate, minimum fare, or night-hour definition for yellow taxis.

## What are app-based ride-hailing fares in Amman (Careem, Uber, Jeeny), and is there an LTRC floor or ceiling?

### Takeaway
The LTRC sets a **regulatory floor** for all licensed app operators: fares must be at least 20% above the taxi meter. The 2026 schedule (11 May 2026) is **46.8 piasters flag fall + 33.6 piasters/km + 5.76 piasters/waiting-minute by day**, and **48 + 39.6 + 6.79 at night**. No ceiling or minimum trip fare was published. Each company's own published per-km or minimum fares for Jordan weren't found.

### Cited Findings
- [OFFICIAL] LTRC 2026 smart-app tariff, published 11 May 2026. Day: opening 46.8 piasters, 33.6/km, 5.76/min waiting. Night ("late-night hours"): 48, 39.6/km, 6.79/min. It applies to Careem, Uber, Petra Ride, Jeeny and Taxi F, which got one week to comply under threat of legal action. — [Khaberni, 11 May 2026](https://www.khaberni.com/news/808843-here-is-the-new-tariff-schedule-for-smart-application-services-in-jordan---details); [Fact Jo, 11 May 2026](https://factjo.com/news/139861)
- [OFFICIAL] The 20% uplift is framed as a **minimum** (floor, "كحد أدنى"). No maximum fare is given; the stated aim is to prevent "exaggerated" increases. — [Fact Jo](https://factjo.com/news/139861)
- [OFFICIAL] Earlier schedule (3 Feb 2026, before the May taxi change). Day: opening 45, 31.6/km, 6/min waiting. Night: 46.2, 38.9/km, 7/min. It was sent to Careem, Uber, Jeeny and others as the minimum. LTRC said this was not a new decision: the law already requires app fares to be at least 20% above the yellow taxi meter. — search snippets: [Al-Mamlaka](https://www.almamlakatv.com/news/189714), [Alsaa](https://alsaa.net/article/631764/), [Sarahanews](https://www.sarahanews.net/1287826-%D8%AA%D9%86%D8%B8%D9%8A%D9%85-%D8%A7%D9%84%D9%86%D9%82%D9%84-%D8%AA%D9%84%D8%B2%D9%85-%D8%AA%D8%B7%D8%A8%D9%8A%D9%82%D8%A7%D8%AA-%D8%A7%D9%84%D9%86%D9%82%D9%84-%D8%A7%D9%84%D8%B0%D9%83%D9%8A/)
- LTRC wants taxi meter fares under its jurisdiction and the Greater Amman Municipality's unified and linked to the app fare. — [Khaberni](https://www.khaberni.com/news/808843-here-is-the-new-tariff-schedule-for-smart-application-services-in-jordan---details)
- Market example: airport to central Amman costs about 22–28 JOD on Careem vs. 25–30 JOD by official airport taxi (Oct 2026). — [AirTraveler (search snippet)](https://www.airtraveler.club/intel/amman-airport-uber-careem-cost-less-than-taxis/)
- Careem's app also includes yellow taxis (metered). — [Jordan Times](https://jordantimes.com/news/local/careem-app-now-includes-yellow-taxis)

### Inferences
- [INFERRED] App floor fare for the simulator: day = 0.468 + 0.336 × km + 0.0576 × wait_min; night = 0.48 + 0.396 × km + 0.0679 × wait_min.
  - 5 km: day 2.15, night 2.46
  - 12 km: day **4.50**, night 5.23
  - 20 km: day 7.19, night 8.40
- [ESTIMATE] Real app prices can sit above the floor (surge, booking fees, minimum fares). Model apps as floor × a 1.0–1.3 multiplier unless better data turns up.
- [ESTIMATE] For per-minute in-traffic time (not just waiting), the regulator only defines a "waiting" minute rate. Apply it to stop-and-go time, e.g. 15–30% of trip time at peak.

### Gaps
- No Careem, Uber or Jeeny help page with Jordan-specific base, per-km, per-minute or minimum fares was found. Taxis-fare.com Uber figures don't match the regulated tariff and were discarded as unreliable.
- No info on app booking fees or minimum trip fare in Jordan.

## What are typical bus fares on university routes?

### Takeaway
The deck's JOD 0.35–0.65 range matches the official fares at BRT launch (Sweileh–Sports City 0.35, Sports City–Museum 0.40, Sweileh–Museum 0.65) and Amman Bus's 0.30–0.65 range. I found no 2026 fare update, so treat the range as plausible but dated.

### Cited Findings
- [OFFICIAL, ~2021] BRT launch fares set by the Greater Amman Municipality: Route 98 (Sweileh Station–Sports City) 35 piasters, Route 99 (Sweileh–Museum) 65 piasters, Route 100 (Sports City–Museum) 40 piasters. These routes pass the University of Jordan station. — [Jordan News](https://www.jordannews.jo/Section-109/News/Normal-BRT-fares-go-into-effect-5735)
- [OFFICIAL, older] Amman Bus fares range from 30 to 65 piasters. — [Al-Mamlaka](https://almamlakatv.com/news/23032-%D8%A3%D8%AC%D8%B1%D8%A9-%D8%A8%D8%A7%D8%B5-%D8%B9%D9%85%D8%A7%D9%86-%D8%A8%D9%8A%D9%86-30-65-%D9%82%D8%B1%D8%B4%D8%A7)
- The Amman–Salt BRT route (via Sweileh) costs JD 0.65 from Salt to any Amman station. This is relevant to Al-Ahliyya on Salt Road. — [Ammon News](https://en.ammonnews.net/article/89838); [Zawya](https://www.zawya.com/en/economy/levant/jordan-brt-route-connecting-amman-with-salt-launched-vtw9qswf)
- Expat Focus lists about JOD 0.55 per urban BRT ride (as of 2022). — [Expat Focus](https://www.expatfocus.com/jordan/guide/jordan-buses-and-trams)
- Smart cards are sold and topped up at the University of Jordan BRT station, and one card works on both BRT and Amman Bus. — [Amideast](https://www.amideastedabroad.org/home/how-to-use-the-bus)
- Interurban example: the new Jerash–Sweileh–Medical City line costs JD 1.10. — [Al-Mamlaka](https://www.almamlakatv.com/news/202692-)
- The BRT carried 159,000 passengers on the first day of the university term (fare not given). — [Al-Mamlaka](https://almamlakatv.com/ar/news/212519-)

### Inferences
- [ESTIMATE] Simulator bus fare: JOD 0.35 for short intra-Amman BRT hops, 0.40–0.55 for typical trips, 0.65 for Sweileh–downtown or Salt–Amman, and about 1.10 for interurban trips (Zarqa–Amman coaster/bus fares weren't verified; use about 0.5–1.0 as a placeholder).

### Gaps
- No 2026-dated bus fare announcement was found. It's unclear whether fuel-driven 2026 adjustments touched bus fares.

## What are approximate road distances from major universities to student neighborhoods, and their coordinates?

### Takeaway
No source gave published road distances. The figures below are my own estimates: straight-line (haversine) distance between approximate centroids × 1.35 detour factor for Amman's hilly road network. Use them for the demo only, and replace them with a routing API (OSRM or Google Distance Matrix) for anything real.

### Cited Findings
- No authoritative distance table was found. The University of Jordan sits on University of Jordan Street (Sweileh–Jubeiha corridor), next to the UJ BRT station. — [Wikipedia: University of Jordan Street](https://en.wikipedia.org/wiki/University_of_Jordan_Street); [Amideast](https://www.amideastedabroad.org/home/how-to-use-the-bus)

### Inferences
[ESTIMATE] Approximate coordinates (WGS84, neighborhood centroids, accurate to roughly ±0.5 km; from general geographic knowledge, not a cited source):

| Place | Lat | Lon |
|---|---|---|
| University of Jordan (UJ) | 32.0153 | 35.8723 |
| Al-Ahliyya Amman University (AAU, Salt Rd / Al-Saro) | 32.0420 | 35.7240 |
| Applied Science Private Univ. (ASU, Shafa Badran) | 32.0423 | 35.9002 |
| Princess Sumaya Univ. for Technology (PSUT, Jubeiha) | 32.0234 | 35.8762 |
| Sweileh | 32.0237 | 35.8401 |
| Tabarbour | 31.9975 | 35.9370 |
| Al Jubeiha | 32.0275 | 35.8710 |
| Khalda | 31.9905 | 35.8410 |
| Marka | 31.9740 | 35.9900 |
| Abdoun | 31.9500 | 35.8820 |
| Zarqa (city centre) | 32.0728 | 36.0880 |

[ESTIMATE] Distances in km: straight line → estimated road (× 1.35, rounded).

| From \ To | Sweileh | Tabarbour | Jubeiha | Khalda | Marka | Abdoun | Zarqa |
|---|---|---|---|---|---|---|---|
| UJ | 3.2 → 4 | 6.4 → 9 | 1.4 → 2 | 4.0 → 5.5 | 12.0 → 16 | 7.3 → 10 | 21.3 → 28 |
| AAU (Salt Rd) | 11.1 → 15 | 20.7 → 28 | 14.0 → 19 | 12.4 → 17 | 26.2 → 35 | 18.1 → 24 | 34.5 → 45 |
| ASU (Shafa Badran) | 6.0 → 8 | 6.1 → 8 | 3.2 → 4.5 | 8.0 → 11 | 11.4 → 15 | 10.4 → 14 | 18.0 → 24 |
| PSUT (Jubeiha) | 3.4 → 4.5 | 6.4 → 9 | 0.7 → 1 | 4.9 → 6.5 | 12.1 → 16 | 8.2 → 11 | 20.7 → 28 |

- [INFERRED] Sanity check against the deck: a 12 km trip fits UJ ↔ Tabarbour/Abdoun-ish distances. At the 2026 tariff that costs JOD 3.75 by yellow taxi (day), at least JOD 4.50 by app (day), and JOD 0.35–0.65 by bus.

### Gaps
- Real road distances and travel times were not sourced. Zarqa trips via the Amman–Zarqa highway may be shorter or longer than the 1.35 factor implies. The AAU campus coordinates are approximate (the Salt Road campus near Al-Saro/Baqa'a); verify on a map before the demo.
