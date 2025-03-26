// static/js/map_draw.js
function drawRouteOnMap(mapId, segments, forceCenter = false, stops = []) {
  // segments boşsa harita çizilmesin
  if (!segments || segments.length === 0) return null;

  // İlk segmentin ilk noktasını referans alarak haritayı başlat
  const firstLat = segments[0].points[0][0];
  const firstLon = segments[0].points[0][1];

  // Harita oluştur
  const map = L.map(mapId).setView([firstLat, firstLon], 13);

  // Tile Layer (OpenStreetMap)
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap Katkıda Bulunanlar"
  }).addTo(map);

  let boundsArray = [];

  // Rota segmentlerini çiz
  segments.forEach(seg => {
    // Her bir segmentin koordinatlarını al
    const latlngs = seg.points.map(p => [p[0], p[1]]);
    // Polyline olarak ekle
    L.polyline(latlngs, {
      color: seg.color || "blue",
      weight: 5,
      opacity: 0.8
    }).addTo(map);

    // Bounds hesabı için koordinatları sakla
    latlngs.forEach(ll => boundsArray.push(ll));
  });

  // Tüm durakları haritaya marker olarak ekle
  stops.forEach(stop => {
    const marker = L.marker([stop.lat, stop.lon]).addTo(map);
    // Popup'ta durak adı ve tipini göster
    marker.bindPopup(`${stop.name} (${stop.type})`);

    // Bounds içine bu noktaları da dahil et
    boundsArray.push([stop.lat, stop.lon]);
  });

  // Tüm noktalar için uygun zoom ayarı
  const bounds = L.latLngBounds(boundsArray);
  if (!bounds.isValid() || forceCenter) {
    // Geçersiz bounds durumunda (veya forceCenter=true ise) fallback
    map.setView([40.77, 29.95], 13); // Örn. Kocaeli merkez
  } else {
    map.fitBounds(bounds, { maxZoom: 14 });
  }

  return map;
}
