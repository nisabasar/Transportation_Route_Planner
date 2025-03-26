// static/js/map_draw.js
function drawRouteOnMap(mapId, segments, forceCenter = false) {
  if (!segments || segments.length === 0) return null;

  // İlk segmentin ilk noktasını referans
  const firstLat = segments[0].points[0][0];
  const firstLon = segments[0].points[0][1];

  const map = L.map(mapId).setView([firstLat, firstLon], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap"
  }).addTo(map);

  let boundsArray = [];
  segments.forEach(seg => {
    const latlngs = seg.points.map(p => [p[0], p[1]]);
    L.polyline(latlngs, {
      color: seg.color || "blue",
      weight: 5,
      opacity: 0.8
    }).addTo(map);
    latlngs.forEach(ll => boundsArray.push(ll));
  });

  const bounds = L.latLngBounds(boundsArray);
  if (!bounds.isValid() || forceCenter) {
    // Kocaeli civarı fallback
    map.setView([40.77, 29.95], 13);
  } else {
    map.fitBounds(bounds, { maxZoom: 14 });
  }
  return map;
}
