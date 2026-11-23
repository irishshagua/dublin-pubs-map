(function() {
  'use strict';

  // Remove the home address saved by the retired route planner.
  try {
    localStorage.removeItem('dublin-pubs-home-address');
  } catch (error) {
    // Browser storage may be unavailable.
  }

  var count = document.getElementById('licence-count');
  fetch('https://raw.githubusercontent.com/irishshagua/dublin-pubs-map/master/remaining-pubs.json')
    .then(function(response) {
      if (!response.ok) throw new Error('Unable to load licence data');
      return response.json();
    }).then(function(data) {
      if (!Array.isArray(data.pubs) || typeof data.source_date !== 'string') throw new Error('Invalid licence data');
      count.textContent = data.pubs.length + ' seven-day publican licences in Dublin city and county (Revenue register ' + data.source_date + '). Licences may not represent distinct pubs.';
    }).catch(function() {
      count.textContent = 'Dublin licence total is unavailable. Please try again later.';
    });

  var map;
  if (window.L) {
    map = L.map('osm-map').setView([53.34584, -6.26432], 14);
    var tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });
    tiles.on('tileerror', function() {
      document.getElementById('map-status').textContent = 'Some map tiles could not be loaded.';
    });
    tiles.addTo(map);
  } else {
    document.getElementById('map-status').textContent = 'The map could not be loaded.';
  }

  getPubs().then(function(pubs) {
    document.getElementById('pubCount').textContent = pubs.length + ' pubs and counting';
    if (!map) return;
    pubs.forEach(function(pub) {
      var latitude = Number(pub.latitude);
      var longitude = Number(pub.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return;
      var popup = document.createElement('div');
      var name = document.createElement('b');
      name.textContent = pub.name;
      popup.appendChild(name);
      popup.appendChild(document.createElement('br'));
      popup.appendChild(document.createTextNode(pub.description));
      L.marker([latitude, longitude]).addTo(map).bindPopup(popup);
    });
  }, function() {
    document.getElementById('pubCount').textContent = 'Unable to load visited pubs. Please try again later.';
  });
})();
