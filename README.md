# Dublin Pubs - The Impossible Dream

Myself and my brother have a goal to drink in every pub in Dublin. The site keeps our visits and reviews alongside the current Revenue licence list.

## Site

[Dublin Pubs Map](https://irishshagua.github.io/dublin-pubs-map)

The map switches between historical visits and current-licence candidates. Blue pins are remaining candidates; yellow markers may already be visited. Only entries with coordinates appear on the map. Licence counts distinguish matched visits, probable name-only matches, remaining candidates, unverified entries and exclusions. They are estimates of licences, not necessarily distinct pubs. Historical visits and reviews remain separate and unchanged.

Enter a home address and select up to three candidates from the lists or map to open a Google Maps walking route starting and ending at home. Unverified entries may already have been visited or may not be eligible. Google Maps searches unlocated stops by name and address, so check the results. The home address is stored only in this browser and sent to Google only when directions are opened; it can be cleared on the page.

The site reads `remaining-pubs.json` from `master`. Statuses are `visited`, `probable`, `remaining`, `review` and `excluded`; coordinates may be null. The existing visit list remains the source of historical reviews and coordinates.

The template used for the site is from [StartBootstrap](https://github.com/BlackrockDigital/startbootstrap-stylish-portfolio).
