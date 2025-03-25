// static/js/map_draw.js
function drawRouteOnMap(mapId, segments) {
  if (!segments || segments.length === 0) return null;

  const firstLat = segments[0].points[0][0];
  const firstLon = segments[0].points[0][1];

  // Yeni bir Leaflet haritası oluşturuyoruz.
  const map = L.map(mapId).setView([firstLat, firstLon], 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  let boundsArray = [];

  segments.forEach((seg) => {
    const latlngs = seg.points.map((p) => [p[0], p[1]]);
    L.polyline(latlngs, {
      color: seg.color || "black",
      weight: 5,
      opacity: 0.8,
    }).addTo(map);

    latlngs.forEach((ll) => boundsArray.push(ll));
  });

  const bounds = L.latLngBounds(boundsArray);
  map.fitBounds(bounds);

  // Harita nesnesini döndürüyoruz
  return map;
}
