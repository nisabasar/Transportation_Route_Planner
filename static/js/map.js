// static/js/map.js
document.addEventListener("DOMContentLoaded", () => {
  // Leaflet harita başlangıç
  const map = L.map("map").setView([40.78259, 29.94628], 13); // Örnek konum: İzmit Otogar civarı

  // Harita katmanını ekle
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap Katkıda Bulunanlar",
  }).addTo(map);

  let startMarker, destMarker;

  // Haritaya tıklandığında
  map.on("click", function (e) {
    if (!startMarker) {
      // İlk tıklamada başlangıç noktası
      startMarker = L.marker(e.latlng, { draggable: true })
        .addTo(map)
        .bindPopup("Başlangıç Noktası")
        .openPopup();
      document.getElementById("start_lat").value = e.latlng.lat;
      document.getElementById("start_lon").value = e.latlng.lng;
    } else if (!destMarker) {
      // İkinci tıklamada varış noktası
      destMarker = L.marker(e.latlng, { draggable: true })
        .addTo(map)
        .bindPopup("Varış Noktası")
        .openPopup();
      document.getElementById("dest_lat").value = e.latlng.lat;
      document.getElementById("dest_lon").value = e.latlng.lng;
    }
  });
});
