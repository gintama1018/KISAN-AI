/**
 * map.js — KISAN AI Leaflet Map
 *
 * Layers:
 *  1. OpenStreetMap base (always available)
 *  2. ISRO Bhuvan WMS — vegetation / crop thematic layer
 *  3. Village marker with risk-color popup
 */

let leafletMap = null;
let farmMarker = null;
let bhuvanLayer = null;

/**
 * Initialize the Leaflet map (called once on first updateMap())
 */
function initMap(lat, lon) {
  if (leafletMap) {
    leafletMap.remove();
    leafletMap = null;
  }

  leafletMap = L.map('map', {
    center: [lat, lon],
    zoom: 10,
    zoomControl: true,
    scrollWheelZoom: true,
  });

  // ── Base Layer: OpenStreetMap ──────────────────────────────────────
  const osm = L.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }
  );

  // ── Satellite Layer: ESRI World Imagery ───────────────────────────
  const satellite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    {
      attribution: 'Tiles © Esri — Source: Esri, Maxar, GeoEye, USGS, USDA FSA',
      maxZoom: 18,
    }
  );

  // ── ISRO Bhuvan WMS Layer ─────────────────────────────────────────
  // Bhuvan provides thematic agricultural + vegetation layers via WMS
  // Layers: vegetation_cover, land_use_2019_2020, drought_monitor
  try {
    bhuvanLayer = L.tileLayer.wms(
      'https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms',
      {
        layers: 'vegetation_cover',    // ISRO vegetation thematic layer
        format: 'image/png',
        transparent: true,
        opacity: 0.55,
        attribution: '📡 ISRO Bhuvan WMS — Vegetation Cover',
        version: '1.1.1',
        crs: L.CRS.EPSG4326,
      }
    );
  } catch (e) {
    console.warn('Bhuvan WMS layer failed to initialize:', e);
  }

  // ── Layer Controls ────────────────────────────────────────────────
  const baseMaps = {
    '🗺️ Street Map': osm,
    '🛰️ Satellite': satellite,
  };

  const overlays = {};
  if (bhuvanLayer) {
    overlays['🌿 ISRO Vegetation (Bhuvan WMS)'] = bhuvanLayer;
  }

  osm.addTo(leafletMap);
  L.control.layers(baseMaps, overlays, { position: 'topright' }).addTo(leafletMap);

  // ── Scale ─────────────────────────────────────────────────────────
  L.control.scale({ imperial: false }).addTo(leafletMap);
}


/**
 * Update map: pan to new village, place risk-colored marker
 */
function updateMap(lat, lon, villageName, droughtLevel) {
  if (!leafletMap) {
    initMap(lat, lon);
  }

  // Remove existing marker
  if (farmMarker) {
    leafletMap.removeLayer(farmMarker);
    farmMarker = null;
  }

  // Smooth pan to village
  leafletMap.flyTo([lat, lon], 11, { duration: 1.2 });

  // Risk color for marker
  const colorMap = {
    'CRITICAL': '#c62828',
    'HIGH':     '#e65100',
    'MODERATE': '#f57f17',
    'HEALTHY':  '#2e7d52',
  };
  const markerColor = colorMap[droughtLevel] || '#2e7d52';

  // Custom SVG marker
  const markerHtml = `
    <div style="
      width: 36px; height: 36px;
      background: ${markerColor};
      border: 3px solid white;
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    "></div>
  `;

  const icon = L.divIcon({
    html: markerHtml,
    className: '',
    iconSize: [36, 36],
    iconAnchor: [18, 36],
    popupAnchor: [0, -36],
  });

  farmMarker = L.marker([lat, lon], { icon })
    .addTo(leafletMap)
    .bindPopup(buildPopup(villageName, lat, lon, droughtLevel), {
      className: 'farm-popup',
      maxWidth: 280,
    })
    .openPopup();

  // Draw a farm polygon around the point (±0.01° ≈ 1km)
  drawFarmPolygon(lat, lon, markerColor);

  // Add Bhuvan WMS overlay
  if (bhuvanLayer) {
    try {
      if (!leafletMap.hasLayer(bhuvanLayer)) {
        bhuvanLayer.addTo(leafletMap);
      }
    } catch (e) {}
  }
}


/**
 * Build popup HTML for the farm marker
 */
function buildPopup(name, lat, lon, level) {
  const levelColors = {
    'CRITICAL': '#c62828', 'HIGH': '#e65100',
    'MODERATE': '#f57f17', 'HEALTHY': '#2e7d52'
  };
  const levelEmoji = {
    'CRITICAL': '🔴', 'HIGH': '🟠', 'MODERATE': '🟡', 'HEALTHY': '🟢'
  };
  const color = levelColors[level] || '#2e7d52';
  const emoji = levelEmoji[level] || '🟢';

  return `
    <div style="font-family: 'Inter', sans-serif; min-width: 200px;">
      <div style="font-size:1.1rem; font-weight:800; margin-bottom:6px; color:#1b2a1e;">
        🌾 ${name}
      </div>
      <div style="
        display: inline-block;
        padding: 4px 12px;
        border-radius: 16px;
        background: ${color}22;
        color: ${color};
        font-weight: 700;
        font-size: 0.85rem;
        margin-bottom: 8px;
      ">
        ${emoji} Drought Risk: ${level}
      </div>
      <div style="font-size:0.77rem; color:#666; margin-top:4px;">
        📍 ${Number(lat).toFixed(4)}°N, ${Number(lon).toFixed(4)}°E
      </div>
      <div style="font-size:0.72rem; color:#999; margin-top:4px;">
        📡 ISRO + NASA satellite data
      </div>
    </div>
  `;
}


/**
 * Draw a representative farm boundary polygon around the point
 */
function drawFarmPolygon(lat, lon, color) {
  // Remove previous polygon
  if (window._farmPolygon) {
    leafletMap.removeLayer(window._farmPolygon);
  }

  const delta = 0.008;   // ~900m — typical smallholder farm
  const bounds = [
    [lat - delta, lon - delta],
    [lat - delta, lon + delta],
    [lat + delta, lon + delta],
    [lat + delta, lon - delta],
  ];

  window._farmPolygon = L.polygon(bounds, {
    color: color,
    weight: 2.5,
    opacity: 0.9,
    fillColor: color,
    fillOpacity: 0.12,
    dashArray: '6, 4',
  }).addTo(leafletMap);
}
