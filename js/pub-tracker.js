(function() {
  'use strict';

  var licenceUrl = 'https://raw.githubusercontent.com/irishshagua/dublin-pubs-map/master/remaining-pubs.json';
  var homeKey = 'dublin-pubs-home-address';
  var maxStops = 3; // Google Maps supports at least three waypoints on mobile browsers.
  var selected = [];
  var remaining = [];
  var rows = [];
  var reviewRows = [];
  var routeRows = [];
  var popupButtons = [];
  var map;
  var visitedLayer;
  var remainingLayer;
  var home = document.getElementById('home-address');
  var routeStatus = document.getElementById('route-status');

  function text(id, value) {
    document.getElementById(id).textContent = value;
  }

  function coordinates(lat, lon) {
    if (lat === null || lon === null || lat === undefined || lon === undefined || String(lat).trim() === '' || String(lon).trim() === '') return null;
    var latitude = Number(lat);
    var longitude = Number(lon);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return null;
    return [latitude, longitude];
  }

  function appendDetails(parent, pub, prefix) {
    var name = document.createElement('strong');
    name.textContent = pub.name;
    if (prefix) parent.appendChild(document.createTextNode(prefix + ': '));
    parent.appendChild(name);
    if (pub.address) {
      parent.appendChild(document.createElement('br'));
      parent.appendChild(document.createTextNode(pub.address));
    }
    if (pub.licence_ref) {
      parent.appendChild(document.createElement('br'));
      parent.appendChild(document.createTextNode('Licence: ' + pub.licence_ref));
    }
    if (pub.description) {
      parent.appendChild(document.createElement('br'));
      parent.appendChild(document.createTextNode(pub.description));
    }
  }

  function addPlainRow(list, pub, prefix) {
    var row = document.createElement('li');
    appendDetails(row, pub, prefix);
    list.appendChild(row);
  }

  function canRoute(pub) {
    return !!coordinates(pub.latitude, pub.longitude) || !!(pub.name.trim() && pub.address.trim());
  }

  function updateSelection() {
    routeRows.forEach(function(item) {
      var isSelected = selected.indexOf(item.pub) !== -1;
      item.checkbox.checked = isSelected;
      item.checkbox.disabled = !canRoute(item.pub) || (!isSelected && selected.length >= maxStops);
    });
    popupButtons.forEach(function(item) {
      var isSelected = selected.indexOf(item.pub) !== -1;
      item.button.textContent = isSelected ? 'Remove from route' : (item.pub.status !== 'remaining' ? 'Add unverified stop to route' : 'Add to route');
      item.button.disabled = !isSelected && selected.length >= maxStops;
    });
    text('selection-status', selected.length ? 'Selected in route order: ' + selected.map(function(pub) {
      return pub.name + (pub.status !== 'remaining' ? ' (unverified; may already be visited)' : '');
    }).join(' → ') + ' (' + selected.length + '/' + maxStops + ')' : 'No pubs selected.');
    routeStatus.textContent = '';
  }

  function toggleSelection(pub, checked) {
    var index = selected.indexOf(pub);
    if (checked && index === -1 && selected.length < maxStops && canRoute(pub)) selected.push(pub);
    if (!checked && index !== -1) selected.splice(index, 1);
    updateSelection();
  }

  function switchView() {
    var view = document.querySelector('input[name="pub-view"]:checked').value;
    document.getElementById('map-legend').hidden = view !== 'remaining';
    if (!map) return;
    if (view === 'visited') {
      map.removeLayer(remainingLayer);
      map.addLayer(visitedLayer);
    } else {
      map.removeLayer(visitedLayer);
      map.addLayer(remainingLayer);
    }
  }

  if (window.L) {
    map = L.map('osm-map').setView([53.34584, -6.26432], 14);
    var tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });
    tiles.on('tileerror', function() {
      text('map-status', 'Some map tiles could not be loaded. The pub lists and route planner are still available.');
    });
    tiles.addTo(map);
    visitedLayer = L.layerGroup().addTo(map);
    remainingLayer = L.layerGroup();
  } else {
    text('map-status', 'The map could not be loaded. The pub lists and route planner are still available.');
  }

  document.querySelectorAll('input[name="pub-view"]').forEach(function(input) {
    input.addEventListener('change', switchView);
  });

  try {
    home.value = localStorage.getItem(homeKey) || '';
  } catch (error) {
    text('storage-status', 'Browser storage is unavailable; the address will not be saved.');
  }
  home.addEventListener('input', function() {
    try {
      if (home.value) localStorage.setItem(homeKey, home.value);
      else localStorage.removeItem(homeKey);
    } catch (error) {
      text('storage-status', 'Browser storage is unavailable; the address will not be saved.');
    }
    routeStatus.textContent = '';
  });
  document.getElementById('clear-home').addEventListener('click', function() {
    home.value = '';
    try {
      localStorage.removeItem(homeKey);
      text('storage-status', 'Saved address cleared.');
    } catch (error) {
      text('storage-status', 'Browser storage is unavailable; the address could not be cleared from storage.');
    }
    routeStatus.textContent = '';
  });

  document.getElementById('directions').addEventListener('click', function() {
    var address = home.value.trim();
    if (!address || !selected.length) {
      routeStatus.textContent = 'Enter a home address and select at least one remaining or review pub.';
      return;
    }
    var url = new URL('https://www.google.com/maps/dir/');
    url.searchParams.set('api', '1');
    url.searchParams.set('origin', address);
    url.searchParams.set('destination', address);
    url.searchParams.set('travelmode', 'walking');
    url.searchParams.set('waypoints', selected.map(function(pub) {
      var location = coordinates(pub.latitude, pub.longitude);
      return location ? location.join(',') : pub.name + ', ' + pub.address + ', Dublin, Ireland';
    }).join('|'));
    var link = document.createElement('a');
    link.href = url.toString();
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    document.body.appendChild(link);
    link.click();
    link.remove();
    routeStatus.textContent = 'Directions opened in Google Maps. Check the stops, especially any without coordinates.';
  });

  document.getElementById('pub-search').addEventListener('input', function(event) {
    var query = event.target.value.trim().toLocaleLowerCase();
    var shown = 0;
    rows.forEach(function(item) {
      var match = (item.pub.name + ' ' + item.pub.address + ' ' + item.pub.licence_ref).toLocaleLowerCase().indexOf(query) !== -1;
      item.row.hidden = !match;
      if (match) shown++;
    });
    text('remaining-status', 'Showing ' + shown + ' of ' + remaining.length + ' remaining candidates.');
  });

  document.getElementById('review-search').addEventListener('input', function(event) {
    var query = event.target.value.trim().toLocaleLowerCase();
    var shown = 0;
    reviewRows.forEach(function(item) {
      var match = (item.pub.name + ' ' + item.pub.address + ' ' + item.pub.licence_ref).toLocaleLowerCase().indexOf(query) !== -1;
      item.row.hidden = !match;
      if (match) shown++;
    });
    text('review-status', 'Showing ' + shown + ' of ' + reviewRows.length + ' unverified or probably visited licences.');
  });

  function loadLicences(data) {
    var statuses = ['visited', 'probable', 'remaining', 'review', 'excluded'];
    if (!data || typeof data.source_date !== 'string' || !data.source_date || !Array.isArray(data.pubs) || !data.pubs.every(function(pub) {
      return pub && typeof pub.licence_ref === 'string' && typeof pub.name === 'string' && typeof pub.address === 'string' &&
        statuses.indexOf(pub.status) !== -1 && (pub.latitude === null || typeof pub.latitude === 'number') &&
        (pub.longitude === null || typeof pub.longitude === 'number');
    })) throw new Error('Invalid licence data');

    var counts = { visited: 0, probable: 0, remaining: 0, review: 0, excluded: 0 };
    var missing = { visited: 0, probable: 0, remaining: 0, review: 0, excluded: 0 };
    var list = document.getElementById('remaining-list');
    var reviewList = document.getElementById('review-list');
    var unlocatedList = document.getElementById('unlocated-list');
    var labels = { visited: 'Matched or marked visited licence', probable: 'Probably visited (name match only)', remaining: 'Remaining candidate', review: 'Unverified candidate', excluded: 'Excluded' };

    data.pubs.forEach(function(pub) {
      counts[pub.status]++;
      var location = coordinates(pub.latitude, pub.longitude);
      if (!location) {
        missing[pub.status]++;
        addPlainRow(unlocatedList, pub, labels[pub.status]);
      }
      if (pub.status !== 'remaining' && pub.status !== 'review' && pub.status !== 'probable') return;
      if (pub.status === 'remaining') remaining.push(pub);

      var row = document.createElement('li');
      var label = document.createElement('label');
      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      label.appendChild(checkbox);
      var content = document.createElement('span');
      appendDetails(content, pub, pub.status === 'probable' ? 'Probably visited — name match only' : pub.status === 'review' ? 'Unverified — may already be visited' : null);
      if (!location) {
        content.appendChild(document.createElement('br'));
        content.appendChild(document.createTextNode(canRoute(pub) ? 'No coordinates — Google Maps will search by name and address.' : 'No coordinates or usable address — cannot route.'));
      }
      label.appendChild(content);
      row.appendChild(label);
      (pub.status === 'remaining' ? list : reviewList).appendChild(row);
      var item = { pub: pub, row: row, checkbox: checkbox };
      routeRows.push(item);
      (pub.status === 'remaining' ? rows : reviewRows).push(item);
      checkbox.addEventListener('change', function() { toggleSelection(pub, checkbox.checked); });


      if (map && location) {
        var popup = document.createElement('div');
        appendDetails(popup, pub, pub.status === 'probable' ? 'Probably visited — name match only' : pub.status === 'review' ? 'Unverified — may already be visited' : null);
        popup.appendChild(document.createElement('br'));
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-primary btn-sm';
        button.addEventListener('click', function() { toggleSelection(pub, selected.indexOf(pub) === -1); });
        popup.appendChild(button);
        popupButtons.push({ pub: pub, button: button });
        var markerOptions = pub.status !== 'remaining' ? {
          icon: L.divIcon({ className: 'review-marker', html: '!', iconSize: [28, 28], iconAnchor: [14, 14] }),
          title: 'Needs review — may already be visited: ' + pub.name
        } : { title: 'Remaining candidate: ' + pub.name };
        L.marker(location, markerOptions).addTo(remainingLayer).bindPopup(popup);
      }
    });

    var total = counts.visited + counts.probable + counts.remaining + counts.review;
    text('progress', 'Current licences (' + data.source_date + '): ' + counts.visited + ' matched or marked visited, plus ' + counts.probable + ' probably visited (name match only), of ' + total + ' non-excluded licences; ' + counts.remaining + ' remaining candidates; ' + counts.review + ' unverified candidates; ' + counts.excluded + ' excluded. Licence rows may not be distinct pubs.');
    text('review-summary', 'Unverified and probably visited (' + (counts.review + counts.probable) + ')');
    text('unlocated-summary', 'Unlocated licences (' + (missing.visited + missing.probable + missing.remaining + missing.review + missing.excluded) + ')');
    text('remaining-status', 'Showing ' + remaining.length + ' of ' + remaining.length + ' remaining candidates.');
    updateSelection();
    // Apply any search entered while the data was loading.
    document.getElementById('pub-search').dispatchEvent(new Event('input'));
    document.getElementById('review-search').dispatchEvent(new Event('input'));
  }

  fetch(licenceUrl).then(function(response) {
    if (!response.ok) throw new Error('Unable to load licence data');
    return response.json();
  }).then(loadLicences).catch(function() {
    text('progress', 'Unable to load licence data. Licence progress is unavailable; please try again later.');
    text('remaining-status', 'Unable to load remaining pubs.');
    text('review-summary', 'Pubs pending review (unavailable)');
    text('review-status', 'Unable to load pubs pending review.');
    text('unlocated-summary', 'Unlocated licences (unavailable)');
  });

  getPubs().then(function(pubs) {
    var missingVisits = 0;
    var list = document.getElementById('visited-unlocated-list');
    var visits = document.getElementById('visited-list');
    text('pubCount', pubs.length + ' pubs and counting');
    text('visited-summary', 'Historical visits and reviews (' + pubs.length + ')');
    pubs.forEach(function(pub) {
      addPlainRow(visits, pub);
      var location = coordinates(pub.latitude, pub.longitude);
      if (!location) {
        missingVisits++;
        addPlainRow(list, pub);
      } else if (map) {
        var popup = document.createElement('div');
        appendDetails(popup, pub);
        L.marker(location).addTo(visitedLayer).bindPopup(popup);
      }
    });
    text('visited-status', pubs.length + ' historical visits with reviews; ' + missingVisits + ' unlocated. These visits are separate from current licence counts.');
    text('visited-unlocated-summary', 'Unlocated visits (' + missingVisits + ')');
  }, function() {
    text('pubCount', 'Unable to load visited pubs. Please try again later.');
    text('visited-status', 'Unable to load visited pubs and reviews. Please try again later.');
    text('visited-summary', 'Historical visits and reviews (unavailable)');
    text('visited-unlocated-summary', 'Unlocated visits (unavailable)');
  });
})();
