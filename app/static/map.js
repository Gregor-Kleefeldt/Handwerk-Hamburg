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

// Tooltip content (German labels)
function tooltipContent(props) {
  if (!props) return "";
  var plz = props.plz != null ? props.plz : "–";
  var stadtteil = props.stadtteil != null && props.stadtteil !== "" ? props.stadtteil : "–";
  var einwohner = props.inhabitants != null ? props.inhabitants : "–";
  var betriebe = props.business_count != null ? props.business_count : "–";
  var ppb = props.people_per_business != null ? props.people_per_business : "–";
  var score = props.white_spot_score != null ? props.white_spot_score : "–";
  return (
    "<strong>PLZ " + plz + "</strong><br>" +
    "Stadtteil: " + stadtteil + "<br>" +
    "Einwohner: " + einwohner + "<br>" +
    "Betriebe: " + betriebe + "<br>" +
    "Einwohner pro Betrieb: " + ppb + "<br>" +
    "White-Spot-Score: " + score
  );
}

// Fill info panel and show it
function showInfoPanel(props) {
  var panel = document.getElementById("info-panel");
  var content = document.getElementById("info-content");
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
    dd.textContent = props[key] != null ? props[key] : "–";
    content.appendChild(dd);
  });
  panel.classList.remove("hidden");
}

function hideInfoPanel() {
  var panel = document.getElementById("info-panel");
  if (panel) panel.classList.add("hidden");
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

// Request scored GeoJSON from backend and add choropleth layer to map
fetch("/api/geojson")
  .then(function (res) {
    return res.json();
  })
  .then(function (geojson) {
    // Create GeoJSON layer with style and hover/click handlers
    var layer = L.geoJSON(geojson, {
      style: style,
      onEachFeature: function (feature, layer) {
        // Show tooltip on hover with PLZ and key figures
        layer.bindTooltip(tooltipContent(feature.properties), {
          sticky: true,
          direction: "top",
          className: "map-tooltip",
        });
        // On click: highlight this polygon (actual shape) and show side panel
        layer.on("click", function () {
          // Reset previously highlighted polygon to default style
          if (highlightedLayer && highlightedLayer !== layer) {
            var prevFeature = highlightedLayer.feature;
            if (prevFeature) highlightedLayer.setStyle(style(prevFeature));
          }
          // Apply highlight to the clicked polygon (thicker stroke, no rectangle)
          layer.setStyle(highlightStyle(feature));
          layer.bringToFront();
          highlightedLayer = layer;
          layer.feature = feature;
          showInfoPanel(feature.properties || {});
        });
      },
    });
    layer.addTo(map);
    // Optionally fit map to layer extent when data is loaded
    if (geojson.features && geojson.features.length > 0) {
      map.fitBounds(layer.getBounds(), { padding: [20, 20] });
    }
    // Hamburg border (outline only) for future extensions
    fetch("/api/hamburg-boundary")
      .then(function (res) {
        return res.json();
      })
      .then(function (boundaryGeoJson) {
        if (!boundaryGeoJson.features || boundaryGeoJson.features.length === 0) return;
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
        console.error("Failed to load Hamburg boundary", err);
      });
  })
  .catch(function (err) {
    console.error("Failed to load GeoJSON", err);
  });

// Hide info panel when user clicks "Schließen"
document.getElementById("close-panel").addEventListener("click", hideInfoPanel);
