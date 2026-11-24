(function() {
  'use strict';

  var base = 'https://raw.githubusercontent.com/irishshagua/dublin-pubs-map/master/';
  var homeKey = 'dublin-pubs-home-address';
  var mobileBrowser = /Android|iPhone|iPad|iPod|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
    Boolean(navigator.userAgentData && navigator.userAgentData.mobile) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  var maxStops = mobileBrowser ? 3 : 9;
  var home = document.getElementById('home-address');
  var search = document.getElementById('candidate-search');
  var visitsStatus = document.getElementById('visits-status');
  var candidatesStatus = document.getElementById('candidates-status');
  var listStatus = document.getElementById('candidate-list-status');
  var routeStatus = document.getElementById('route-status');
  var storageStatus = document.getElementById('storage-status');
  var directions = document.getElementById('directions-link');
  var visits = null;
  var candidateData = null;
  var visitFailed = false;
  var candidateFailed = false;
  var candidates = [];
  var selected = [];
  var checkboxes = [];
  var updateOpenPopup = null;
  var map;
  var doneLayer;
  var undoneLayer;

  function fetchJSON(file) {
    return fetch(base + file).then(function(response) {
      if (!response.ok) throw new Error('Unable to load ' + file);
      return response.json();
    });
  }

  function validLocation(item) {
    return typeof item.latitude === 'number' && Number.isFinite(item.latitude) && Math.abs(item.latitude) <= 90 &&
      typeof item.longitude === 'number' && Number.isFinite(item.longitude) && Math.abs(item.longitude) <= 180;
  }

  function validVisits(data) {
    var ids = new Set();
    return Array.isArray(data) && data.every(function(visit) {
      if (!visit || typeof visit.id !== 'string' || !visit.id || ids.has(visit.id) ||
          typeof visit.name !== 'string' || typeof visit.review !== 'string' ||
          !(visit.osm_id === null || (typeof visit.osm_id === 'string' && /^(node|way|relation)\/[1-9][0-9]*$/.test(visit.osm_id))) || !validLocation(visit)) return false;
      ids.add(visit.id);
      return true;
    });
  }

  function validCandidates(data) {
    var ids = new Set();
    var osmIds = new Set();
    return data && typeof data.source_date === 'string' && Array.isArray(data.pubs) && data.pubs.every(function(pub) {
      if (!pub || typeof pub.id !== 'string' || !pub.id || ids.has(pub.id) ||
          typeof pub.name !== 'string' || !pub.name || !validLocation(pub) ||
          !Array.isArray(pub.osm_ids) || pub.osm_ids.indexOf(pub.id) === -1 ||
          !pub.osm_ids.every(function(id) {
            if (typeof id !== 'string' || !/^(node|way|relation)\/[1-9][0-9]*$/.test(id) || osmIds.has(id)) return false;
            osmIds.add(id);
            return true;
          })) return false;
      ids.add(pub.id);
      return true;
    });
  }

  fetchJSON('remaining-pubs.json').then(function(data) {
    if (!Array.isArray(data.pubs) || typeof data.source_date !== 'string') throw new Error('Invalid licence data');
    document.getElementById('licence-count').textContent = data.pubs.length + ' seven-day publican licences in Dublin city and county (Revenue register ' + data.source_date + '). Licences may not represent distinct pubs.';
  }).catch(function() {
    document.getElementById('licence-count').textContent = 'Dublin licence total is unavailable. Please try again later.';
  });

  if (window.L) {
    map = L.map('osm-map').setView([53.34584, -6.26432], 14);
    doneLayer = L.layerGroup().addTo(map);
    undoneLayer = L.layerGroup();
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).on('tileerror', function() {
      document.getElementById('map-status').textContent = 'Some map tiles could not be loaded; the pub list is still available when data loads.';
    }).addTo(map);
  } else {
    document.getElementById('map-status').textContent = 'The map could not be loaded; use the candidate list below when data loads.';
  }

  Array.prototype.forEach.call(document.querySelectorAll('input[name="map-mode"]'), function(input) {
    input.addEventListener('change', function() {
      if (!map || !input.checked) return;
      if (input.value === 'done' || input.value === 'both') doneLayer.addTo(map);
      else map.removeLayer(doneLayer);
      if (input.value === 'undone' || input.value === 'both') undoneLayer.addTo(map);
      else map.removeLayer(undoneLayer);
    });
  });

  function popupText(name, detail) {
    var popup = document.createElement('div');
    var heading = document.createElement('strong');
    heading.textContent = name;
    popup.appendChild(heading);
    popup.appendChild(document.createElement('br'));
    popup.appendChild(document.createTextNode(detail));
    return popup;
  }

  function showVisits() {
    if (!map) return;
    visits.forEach(function(visit) {
      var popup = popupText(visit.name, visit.review);
      if (visit.osm_id) {
        popup.appendChild(document.createElement('br'));
        popup.appendChild(sourceLink({ id: visit.osm_id }));
      }
      L.circleMarker([visit.latitude, visit.longitude], { color: '#126b33', fillOpacity: 0.8, radius: 7 })
        .bindPopup(popup).addTo(doneLayer);
    });
  }

  function updateDirections() {
    var address = home.value.trim();
    var stops = document.getElementById('selected-stops');
    stops.textContent = '';
    selected.forEach(function(pub) {
      var item = document.createElement('li');
      var remove = document.createElement('button');
      item.appendChild(document.createTextNode(pub.name + ' '));
      remove.type = 'button';
      remove.textContent = 'Remove';
      remove.setAttribute('aria-label', 'Remove ' + pub.name + ' from route');
      remove.addEventListener('click', function() { toggleCandidate(pub); });
      item.appendChild(remove);
      stops.appendChild(item);
    });
    if (!selected.length || !address) {
      directions.hidden = true;
      directions.removeAttribute('href');
      routeStatus.textContent = 'Enter a home address and select at least one candidate to open directions.';
      return;
    }
    var params = new URLSearchParams({
      api: '1', origin: address, destination: address, travelmode: 'walking',
      waypoints: selected.map(function(pub) { return pub.latitude + ',' + pub.longitude; }).join('|')
    });
    directions.href = 'https://www.google.com/maps/dir/?' + params.toString();
    directions.hidden = false;
    routeStatus.textContent = selected.length + ' of ' + maxStops + ' stops selected, in the order shown.';
  }

  function isSelected(pub) {
    return selected.some(function(stop) { return stop.id === pub.id; });
  }

  function toggleCandidate(pub) {
    if (isSelected(pub)) selected = selected.filter(function(stop) { return stop.id !== pub.id; });
    else if (selected.length < maxStops) selected.push(pub);
    updateDirections();
    checkboxes.forEach(function(entry) {
      entry.input.checked = isSelected(entry.pub);
      entry.input.disabled = !entry.input.checked && selected.length >= maxStops;
    });
    if (updateOpenPopup) updateOpenPopup();
  }

  function sourceLink(pub) {
    var link = document.createElement('a');
    link.href = 'https://www.openstreetmap.org/' + pub.id;
    link.textContent = 'OSM ' + pub.id;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  }

  function renderList() {
    var list = document.getElementById('candidate-list');
    var term = search.value.trim().toLocaleLowerCase();
    var filtered = candidates.filter(function(pub) { return pub.name.toLocaleLowerCase().indexOf(term) !== -1; });
    list.textContent = '';
    checkboxes = [];
    listStatus.textContent = filtered.length + ' unconfirmed candidate' + (filtered.length === 1 ? '' : 's') + ' shown. Select up to ' + maxStops + '.';
    filtered.forEach(function(pub) {
      var item = document.createElement('li');
      var label = document.createElement('label');
      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = isSelected(pub);
      checkbox.disabled = !checkbox.checked && selected.length >= maxStops;
      checkboxes.push({ input: checkbox, pub: pub });
      checkbox.addEventListener('change', function() { toggleCandidate(pub); });
      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(' ' + pub.name));
      item.appendChild(label);
      item.appendChild(document.createTextNode(' '));
      item.appendChild(sourceLink(pub));
      list.appendChild(item);
    });
  }

  function showCandidates() {
    if (!map) return;
    candidates.forEach(function(pub) {
      var marker = L.circleMarker([pub.latitude, pub.longitude], { color: '#a24500', fillOpacity: 0.8, radius: 6 });
      marker.on('popupopen', function(event) {
        var popup = popupText(pub.name, 'Unconfirmed candidate: may already have been visited.');
        var button = document.createElement('button');
        popup.appendChild(document.createElement('br'));
        popup.appendChild(sourceLink(pub));
        popup.appendChild(document.createElement('br'));
        button.type = 'button';
        function updateButton() {
          button.textContent = isSelected(pub) ? 'Remove from route' : 'Add to route';
          button.disabled = !isSelected(pub) && selected.length >= maxStops;
        }
        updateOpenPopup = updateButton;
        updateButton();
        button.addEventListener('click', function() { toggleCandidate(pub); });
        popup.appendChild(button);
        event.popup.setContent(popup);
      });
      marker.on('popupclose', function() { updateOpenPopup = null; });
      marker.bindPopup(document.createElement('div')).addTo(undoneLayer);
    });
  }

  function updateCandidates() {
    if (visitFailed || candidateFailed) {
      if (visitFailed && !candidateFailed && candidateData) {
        candidatesStatus.textContent = 'OpenStreetMap candidates loaded, but cannot be checked without visits.';
      }
      listStatus.textContent = 'Candidates cannot be shown without both the visits and OpenStreetMap datasets. Check your connection and reload.';
      return;
    }
    if (!visits || !candidateData) return;
    var linked = new Set(visits.map(function(visit) { return visit.osm_id; }).filter(function(id) { return id !== null; }));
    candidates = candidateData.pubs.filter(function(pub) {
      return !pub.osm_ids.some(function(id) { return linked.has(id); });
    });
    candidatesStatus.textContent = candidates.length + ' unconfirmed OpenStreetMap candidates (data ' + candidateData.source_date + '); some may already be visited.';
    search.disabled = false;
    renderList();
    showCandidates();
  }

  fetchJSON('visits.json').then(function(data) {
    if (!validVisits(data)) throw new Error('Invalid visits data');
    visits = data;
    visitsStatus.textContent = visits.length + ' verified visits. Green markers show Done.';
    document.getElementById('pubCount').textContent = visits.length + ' pubs and counting';
    showVisits();
    updateCandidates();
  }).catch(function() {
    visitFailed = true;
    visitsStatus.textContent = 'Visits could not be loaded. Undone candidates are unavailable because visits cannot be checked; please check your connection and reload.';
    document.getElementById('pubCount').textContent = 'Unable to load visited pubs. Please try again later.';
    updateCandidates();
  });

  fetchJSON('osm-pubs.json').then(function(data) {
    if (!validCandidates(data)) throw new Error('Invalid OpenStreetMap data');
    candidateData = data;
    candidatesStatus.textContent = 'OpenStreetMap candidates loaded; waiting for visits to check confirmed links.';
    updateCandidates();
  }).catch(function() {
    candidateFailed = true;
    candidatesStatus.textContent = 'OpenStreetMap candidates could not be loaded. Done visits remain available if their data loads; please check your connection and reload.';
    updateCandidates();
  });

  try {
    home.value = localStorage.getItem(homeKey) || '';
  } catch (error) {
    storageStatus.textContent = 'Browser storage is unavailable; your address will not be saved.';
  }
  home.addEventListener('input', function() {
    try {
      if (home.value) localStorage.setItem(homeKey, home.value);
      else localStorage.removeItem(homeKey);
    } catch (error) {
      storageStatus.textContent = 'Browser storage is unavailable; your address may not be saved.';
    }
    updateDirections();
  });
  document.getElementById('clear-home').addEventListener('click', function() {
    home.value = '';
    try {
      localStorage.removeItem(homeKey);
      storageStatus.textContent = 'Saved home address cleared from this browser.';
    } catch (error) {
      storageStatus.textContent = 'Could not clear browser storage; remove the address in your browser settings.';
    }
    updateDirections();
  });
  search.addEventListener('input', renderList);
  updateDirections();
})();
