/**
 * Leaflet map: load GeoJSON from API, style by white_spot_score, show tooltip and panel.
 * All user-facing labels in German.
 */

// Map center (Hamburg) and default zoom level
var mapCenter = [53.55, 10.0];
var mapZoom = 11;

// Create Leaflet map and add OSM tile layer
var map = L.map("map").setView(mapCenter, mapZoom);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap",
}).addTo(map);

// Return fill colour from white_spot_score (aligned with CSS legend)
function getColor(score) {
  if (score === undefined || score === null) return "#94a3b8";
  var s = Math.max(0, Math.min(1, score));
  if (s < 0.5) {
    return s < 0.25 ? "#059669" : "#ca8a04";
  }
  return s < 0.75 ? "#ea580c" : "#dc2626";
}

// Style GeoJSON layer by white_spot_score
function style(feature) {
  var score = feature.properties && feature.properties.white_spot_score;
  return {
    fillColor: getColor(score),
    weight: 1.5,
    opacity: 1,
    color: "#333",
    fillOpacity: 0.65,
  };
}

// Tooltip content (German labels). stadtteilOverride = official ALKIS name at cursor (optional).
function tooltipContent(props, stadtteilOverride) {
  if (!props) return "";
  var plz = props.plz != null ? props.plz : "–";
  var stadtteil = (stadtteilOverride != null && stadtteilOverride !== "") ? stadtteilOverride : (props.stadtteil != null && props.stadtteil !== "" ? props.stadtteil : "–");
  var einwohner = props.inhabitants != null ? props.inhabitants : "–";
  var betriebe = props.business_count != null ? props.business_count : "–";
  var ppb = props.people_per_business != null ? props.people_per_business : "–";
  var score = props.white_spot_score != null ? props.white_spot_score : "–";
  return (
    "<strong>PLZ " + plz + "</strong><br>" +
    "Stadtteil (amtl.): " + stadtteil + "<br>" +
    "Einwohner: " + einwohner + "<br>" +
    "Betriebe: " + betriebe + "<br>" +
    "Einwohner pro Betrieb: " + ppb + "<br>" +
    "White-Spot-Score: " + score
  );
}

// Fill info panel and show it; hide the map hint
function showInfoPanel(props) {
  var panel = document.getElementById("info-panel");
  var content = document.getElementById("info-content");
  var hint = document.getElementById("map-hint");
  if (!panel || !content) return;
  content.innerHTML = "";
  var labels = {
    plz: "Postleitzahl",
    stadtteil: "Stadtteil",
    inhabitants: "Einwohner",
    business_count: "Betriebe",
    people_per_business: "Einwohner pro Betrieb",
    white_spot_score: "White-Spot-Score",
  };
  var keys = ["plz", "stadtteil", "inhabitants", "business_count", "people_per_business", "white_spot_score"];
  keys.forEach(function (key) {
    var dt = document.createElement("dt");
    dt.textContent = labels[key] || key;
    content.appendChild(dt);
    var dd = document.createElement("dd");
    dd.setAttribute("data-key", key);
    dd.textContent = props[key] != null ? props[key] : "–";
    content.appendChild(dd);
  });
  panel.classList.remove("hidden");
  if (hint) hint.classList.add("hidden");
}

function hideInfoPanel() {
  var panel = document.getElementById("info-panel");
  var hint = document.getElementById("map-hint");
  if (panel) panel.classList.add("hidden");
  if (hint) hint.classList.remove("hidden");
}

// Currently highlighted district layer (so we can reset its style when another is clicked)
var highlightedLayer = null;

// Highlight style: same fill colour but thicker stroke so the actual polygon shape stands out
function highlightStyle(feature) {
  var base = style(feature);
  return {
    fillColor: base.fillColor,
    fillOpacity: 0.9,
    weight: 3,
    color: "#1a1a1a",
    opacity: 1,
  };
}

// PLZ features and ALKIS Stadtteil features for point-in-polygon (hover shows correct Stadtteil)
var plzFeatures = [];
var alkisStadtteilFeatures = [];
// Floating tooltip updated on mousemove (Stadtteil from ALKIS can change within one PLZ)
var hoverTooltip = null;

// Find PLZ feature containing the given latlng (Turf point-in-polygon)
function findPlzAt(latlng) {
  var pt = [latlng.lng, latlng.lat];
  for (var i = 0; i < plzFeatures.length; i++) {
    var f = plzFeatures[i];
    if (f.geometry && turf.booleanPointInPolygon(pt, f)) return f;
  }
  return null;
}

// Find official ALKIS Stadtteil name at the given latlng
function findStadtteilNameAt(latlng) {
  var pt = [latlng.lng, latlng.lat];
  for (var i = 0; i < alkisStadtteilFeatures.length; i++) {
    var f = alkisStadtteilFeatures[i];
    if (f.geometry && turf.booleanPointInPolygon(pt, f)) {
      var name = f.properties && f.properties.stadtteil_name;
      return name != null && name !== "" ? name : "–";
    }
  }
  return null;
}

// Load PLZ choropleth and ALKIS Stadtteile, then wire hover/click
Promise.all([
  fetch("/api/geojson").then(function (res) { return res.json(); }),
  fetch("/api/alkis-stadtteile").then(function (res) { return res.json(); }),
])
  .then(function (results) {
    var geojson = results[0];
    var alkisGeo = results[1];
    plzFeatures = geojson.features || [];
    alkisStadtteilFeatures = alkisGeo.features || [];

    // Create choropleth layer (PLZ) – no per-layer tooltip; we use global hover tooltip
    var layer = L.geoJSON(geojson, {
      style: style,
      onEachFeature: function (feature, leafletLayer) {
        leafletLayer.feature = feature;
        // On click: highlight this PLZ polygon and show panel with ALKIS Stadtteil at click point
        leafletLayer.on("click", function (e) {
          if (highlightedLayer && highlightedLayer !== leafletLayer) {
            var prevFeature = highlightedLayer.feature;
            if (prevFeature) highlightedLayer.setStyle(style(prevFeature));
          }
          leafletLayer.setStyle(highlightStyle(feature));
          leafletLayer.bringToFront();
          highlightedLayer = leafletLayer;
          var stadtteilName = findStadtteilNameAt(e.latlng);
          var props = Object.assign({}, feature.properties || {});
          if (stadtteilName != null) props.stadtteil = stadtteilName;
          showInfoPanel(props);
        });
      },
    });
    layer.addTo(map);
    if (plzFeatures.length > 0) {
      map.fitBounds(layer.getBounds(), { padding: [20, 20] });
    }

    // Single tooltip for hover: update content from PLZ + ALKIS Stadtteil at cursor
    hoverTooltip = L.tooltip({ className: "map-tooltip", direction: "top", permanent: false });
    map.on("mousemove", function (e) {
      var plzFeature = findPlzAt(e.latlng);
      var stadtteilName = findStadtteilNameAt(e.latlng);
      if (plzFeature && plzFeature.properties) {
        hoverTooltip.setLatLng(e.latlng).setContent(tooltipContent(plzFeature.properties, stadtteilName)).openOn(map);
      } else {
        map.closeTooltip(hoverTooltip);
      }
    });
    map.on("mouseout", function () {
      map.closeTooltip(hoverTooltip);
    });

    // Hamburg border (load after PLZ/ALKIS so map is ready)
    return fetch("/api/hamburg-boundary").then(function (res) { return res.json(); });
  })
  .then(function (boundaryGeoJson) {
    if (!boundaryGeoJson || !boundaryGeoJson.features || boundaryGeoJson.features.length === 0) return;
    var borderLayer = L.geoJSON(boundaryGeoJson, {
      style: {
        fill: false,
        color: "#0f172a",
        weight: 2.5,
        opacity: 1,
      },
    });
    borderLayer.addTo(map);
    borderLayer.bringToFront();
  })
  .catch(function (err) {
    console.error("Failed to load map data", err);
  });

// Hide info panel when user clicks "Schließen"
document.getElementById("close-panel").addEventListener("click", hideInfoPanel);

// --- Address search: call API, show district analysis, add user marker ---

// Keep a reference to the user location marker so we can remove or move it
var userLocationMarker = null;

/**
 * Remove the user location marker from the map if it exists.
 */
function removeUserLocationMarker() {
  if (userLocationMarker) {
    map.removeLayer(userLocationMarker);
    userLocationMarker = null;
  }
}

/**
 * Add a red marker for the user's location and optionally pan the map to include it.
 */
function addUserLocationMarker(lat, lon) {
  removeUserLocationMarker();
  userLocationMarker = L.circleMarker([lat, lon], {
    radius: 10,
    fillColor: "#dc2626",
    color: "#991b1b",
    weight: 2,
    opacity: 1,
    fillOpacity: 0.9,
  })
    .addTo(map)
    .bindPopup("Ihre Adresse");
  map.setView([lat, lon], Math.max(map.getZoom(), 14));
}

/**
 * Build HTML for the address analysis result and show the result panel.
 */
function showAddressResult(data) {
  var panel = document.getElementById("address-result-panel");
  var content = document.getElementById("address-result-content");
  if (!panel || !content) return;
  content.innerHTML = "";
  if (data.error) {
    var p = document.createElement("p");
    p.className = "error-msg";
    p.textContent = data.error;
    content.appendChild(p);
  } else {
    var districtTitle = document.createElement("h3");
    districtTitle.textContent = "Stadtteil: ";
    var districtSpan = document.createElement("span");
    districtSpan.className = "district-name";
    districtSpan.textContent = data.district;
    districtTitle.appendChild(districtSpan);
    content.appendChild(districtTitle);
    var countP = document.createElement("p");
    countP.textContent = "Anzahl Elektriker: " + data.count;
    content.appendChild(countP);
    if (data.businesses && data.businesses.length > 0) {
      var listLabel = document.createElement("p");
      listLabel.textContent = "Elektriker in der Nähe:";
      listLabel.style.marginTop = "0.75rem";
      listLabel.style.fontWeight = "600";
      listLabel.style.fontSize = "0.8125rem";
      content.appendChild(listLabel);
      var ul = document.createElement("ul");
      ul.className = "business-list";
      data.businesses.forEach(function (b) {
        var li = document.createElement("li");
        li.textContent = b.name || "Unbenannt";
        if (b.address) {
          var br = document.createElement("br");
          li.appendChild(br);
          var small = document.createElement("small");
          small.style.color = "var(--color-text-muted)";
          small.textContent = b.address;
          li.appendChild(small);
        }
        ul.appendChild(li);
      });
      content.appendChild(ul);
    }
    if (data.user_lat != null && data.user_lon != null) {
      addUserLocationMarker(data.user_lat, data.user_lon);
    }
  }
  content.className = "address-result-content";
  panel.classList.remove("hidden");
}

function hideAddressResultPanel() {
  var panel = document.getElementById("address-result-panel");
  if (panel) panel.classList.add("hidden");
  removeUserLocationMarker();
}

document.getElementById("close-address-panel").addEventListener("click", hideAddressResultPanel);

// --- Address suggestions (autocomplete, Google Maps–style) ---
var addressSuggestionsList = document.getElementById("address-suggestions-list");
var addressSuggestionsDebounceTimer = null;
var addressSuggestionsAbortController = null;
var addressSuggestionsItems = [];
var addressSuggestionsSelectedIndex = -1;

/**
 * Show the suggestions dropdown and fill it with the given list of display names.
 */
function showAddressSuggestions(items) {
  addressSuggestionsItems = items;
  addressSuggestionsSelectedIndex = -1;
  if (!addressSuggestionsList) return;
  addressSuggestionsList.innerHTML = "";
  if (!items || items.length === 0) {
    addressSuggestionsList.setAttribute("hidden", "");
    addressSuggestionsList.classList.remove("is-visible");
    return;
  }
  items.forEach(function (item, i) {
    var label = typeof item === "string" ? item : (item.label || item.display_name);
    var displayName = typeof item === "string" ? item : (item.display_name || item.label);
    var li = document.createElement("li");
    li.setAttribute("role", "option");
    li.setAttribute("id", "address-suggestion-" + i);
    li.setAttribute("aria-selected", "false");
    li.textContent = label;
    li.addEventListener("click", function () {
      var input = document.getElementById("address-input");
      if (input) input.value = label;
      hideAddressSuggestions();
      input && input.focus();
    });
    addressSuggestionsList.appendChild(li);
  });
  addressSuggestionsList.removeAttribute("hidden");
  addressSuggestionsList.classList.add("is-visible");
  var input = document.getElementById("address-input");
  if (input) input.setAttribute("aria-expanded", "true");
}

/**
 * Hide the suggestions dropdown and clear selection.
 */
function hideAddressSuggestions() {
  addressSuggestionsItems = [];
  addressSuggestionsSelectedIndex = -1;
  if (addressSuggestionsList) {
    addressSuggestionsList.setAttribute("hidden", "");
    addressSuggestionsList.classList.remove("is-visible");
    addressSuggestionsList.innerHTML = "";
  }
  var input = document.getElementById("address-input");
  if (input) input.setAttribute("aria-expanded", "false");
}

/**
 * Show a loading state in the dropdown so the user sees that a search is in progress.
 */
function showAddressSuggestionsLoading() {
  addressSuggestionsItems = [];
  addressSuggestionsSelectedIndex = -1;
  if (!addressSuggestionsList) return;
  addressSuggestionsList.innerHTML = "";
  var li = document.createElement("li");
  li.className = "address-suggestions-loading";
  li.setAttribute("aria-busy", "true");
  li.textContent = "Suche…";
  addressSuggestionsList.appendChild(li);
  addressSuggestionsList.removeAttribute("hidden");
  addressSuggestionsList.classList.add("is-visible");
  var input = document.getElementById("address-input");
  if (input) input.setAttribute("aria-expanded", "true");
}

/**
 * Fetch suggestions from the API and show them in the dropdown (debounced).
 * Cancels any previous in-flight request so only the latest query is shown.
 */
function fetchAddressSuggestions(query) {
  if (!query || query.length < 2) {
    hideAddressSuggestions();
    return;
  }
  if (addressSuggestionsAbortController) {
    addressSuggestionsAbortController.abort();
  }
  addressSuggestionsAbortController = new AbortController();
  var signal = addressSuggestionsAbortController.signal;
  showAddressSuggestionsLoading();
  fetch("/api/address-suggestions?q=" + encodeURIComponent(query), { signal: signal })
    .then(function (res) {
      if (!res.ok) {
        console.warn("Address suggestions API error:", res.status, res.statusText);
        return [];
      }
      return res.json();
    })
    .then(function (data) {
      var items = Array.isArray(data)
        ? data
            .filter(function (r) {
              return r && (r.label || r.display_name);
            })
            .map(function (r) {
              return { label: r.label || r.display_name, display_name: r.display_name || r.label };
            })
        : [];
      showAddressSuggestions(items);
    })
    .catch(function (err) {
      if (err.name === "AbortError") return;
      console.warn("Address suggestions request failed:", err);
      hideAddressSuggestions();
    });
}

// Debounced input: wait 280 ms so we often send the full query (e.g. "Grindelallee") in one request and avoid rate-limit queueing
document.getElementById("address-input").addEventListener("input", function () {
  var input = document.getElementById("address-input");
  var q = (input && input.value) ? input.value.trim() : "";
  if (addressSuggestionsDebounceTimer) clearTimeout(addressSuggestionsDebounceTimer);
  addressSuggestionsDebounceTimer = setTimeout(function () {
    addressSuggestionsDebounceTimer = null;
    fetchAddressSuggestions(q);
  }, 280);
});

// Hide suggestions when focus leaves the input (delay so click on suggestion is processed first)
document.getElementById("address-input").addEventListener("blur", function () {
  setTimeout(function () {
    var list = document.getElementById("address-suggestions-list");
    var input = document.getElementById("address-input");
    var active = document.activeElement;
    if (list && !list.hasAttribute("hidden") && input && active !== input && active && !list.contains(active)) {
      hideAddressSuggestions();
    }
  }, 150);
});

// Keyboard: ArrowDown / ArrowUp to move selection, Enter to select suggestion or submit
document.getElementById("address-input").addEventListener("keydown", function (e) {
  if (e.key === "ArrowDown") {
    if (addressSuggestionsList && !addressSuggestionsList.hasAttribute("hidden") && addressSuggestionsItems.length > 0) {
      e.preventDefault();
      addressSuggestionsSelectedIndex = Math.min(addressSuggestionsSelectedIndex + 1, addressSuggestionsItems.length - 1);
      var opt = document.getElementById("address-suggestion-" + addressSuggestionsSelectedIndex);
      addressSuggestionsList.querySelectorAll("[aria-selected=true]").forEach(function (el) { el.setAttribute("aria-selected", "false"); });
      if (opt) opt.setAttribute("aria-selected", "true");
      return;
    }
  }
  if (e.key === "ArrowUp") {
    if (addressSuggestionsList && !addressSuggestionsList.hasAttribute("hidden") && addressSuggestionsItems.length > 0) {
      e.preventDefault();
      addressSuggestionsSelectedIndex = Math.max(addressSuggestionsSelectedIndex - 1, -1);
      addressSuggestionsList.querySelectorAll("[aria-selected=true]").forEach(function (el) { el.setAttribute("aria-selected", "false"); });
      if (addressSuggestionsSelectedIndex >= 0) {
        var opt = document.getElementById("address-suggestion-" + addressSuggestionsSelectedIndex);
        if (opt) opt.setAttribute("aria-selected", "true");
      }
      return;
    }
  }
  if (e.key === "Enter") {
    if (addressSuggestionsList && !addressSuggestionsList.hasAttribute("hidden") && addressSuggestionsItems.length > 0 && addressSuggestionsSelectedIndex >= 0) {
      e.preventDefault();
      var chosen = addressSuggestionsItems[addressSuggestionsSelectedIndex];
      var input = document.getElementById("address-input");
      if (input && chosen) {
        input.value = typeof chosen === "string" ? chosen : (chosen.label || chosen.display_name);
      }
      hideAddressSuggestions();
      document.getElementById("address-search-btn").click();
      return;
    }
    document.getElementById("address-search-btn").click();
  }
});

document.getElementById("address-search-btn").addEventListener("click", function () {
  var input = document.getElementById("address-input");
  var btn = document.getElementById("address-search-btn");
  var address = (input && input.value) ? input.value.trim() : "";
  hideAddressSuggestions();
  if (!address) return;
  btn.disabled = true;
  fetch("/api/address-analysis?address=" + encodeURIComponent(address))
    .then(function (res) {
      return res.json();
    })
    .then(function (data) {
      showAddressResult(data);
    })
    .catch(function (err) {
      showAddressResult({ error: "Anfrage fehlgeschlagen. Bitte später erneut versuchen." });
      console.error("Address analysis failed", err);
    })
    .finally(function () {
      btn.disabled = false;
    });
});
