// Landing page: tampilkan mitra terdaftar bener.in di peta milik home.js.
//
// File ini SENGAJA terpisah supaya home.js tidak perlu diubah. Ia dimuat tepat
// sebelum home.js, menangkap peta lewat L.Map.addInitHook, lalu menambah
// lapisan titik hijau sendiri. Kalau salah satu syarat tidak terpenuhi
// (elemen tidak ada, peta tidak dibuat), skrip diam dan landing tetap normal.
(() => {
  'use strict';

  const script = document.currentScript;
  const page = document.querySelector('.home-page');
  const mitraUrl = script && script.dataset.mitraUrl;
  const loginUrl = script && script.dataset.loginUrl;
  if (!page || !mitraUrl || typeof window.L === 'undefined') return;

  const select = page.querySelector('#category-select');
  const form = page.querySelector('#map-filter');
  if (!select || !form) return;

  const GREEN = '#2f7d4f';
  let map = null;
  let layer = null;
  let controller = null;
  let runId = 0;
  let legendShown = false;
  let timer = null;

  // Tangkap peta #map milik home.js tanpa menyentuh file itu.
  L.Map.addInitHook(function () {
    if (this.getContainer().id !== 'map') return;
    map = this;
    layer = L.layerGroup().addTo(this);
    this.whenReady(refresh);                       // tampil sejak peta siap
    this.on('moveend', () => schedule(500));       // ikut saat peta digeser/zoom
  });

  function schedule(delay) {
    clearTimeout(timer);
    timer = setTimeout(refresh, delay);
  }

  function showLegend() {
    if (legendShown) return;
    legendShown = true;
    const legend = L.control({ position: 'bottomleft' });
    legend.onAdd = () => {
      const box = L.DomUtil.create('div');
      box.style.cssText = 'background:#fff;padding:.3rem .6rem;border-radius:6px;font-size:.85rem;box-shadow:0 1px 4px rgba(0,0,0,.25)';
      box.textContent = '● Mitra bener.in';
      box.style.color = GREEN;
      return box;
    };
    legend.addTo(map);
  }

  function line(parent, text) {
    if (!text) return;
    const node = document.createElement('span');
    node.textContent = text;
    parent.append(node);
  }

  function popup(m, contactHidden) {
    const box = document.createElement('div');
    box.className = 'home-popup';
    const name = document.createElement('strong');
    name.textContent = m.name;
    box.append(name);
    line(box, 'Mitra bener.in');
    line(box, m.address);
    line(box, (m.layanan || []).join(', '));
    if (m.phone) {
      line(box, 'Telepon: ' + m.phone);
    } else if (contactHidden && loginUrl) {
      const login = document.createElement('a');
      login.href = `${loginUrl}?next=${encodeURIComponent(location.pathname)}`;
      login.textContent = 'Masuk untuk melihat kontak';
      box.append(login);
    }
    const reviews = document.createElement('a');
    reviews.href = m.reviews_url;
    reviews.textContent = 'Lihat review';
    box.append(reviews);
    return box;
  }

  function addMitra(m, contactHidden) {
    const icon = L.divIcon({
      className: '',
      iconSize: [22, 22],
      html: `<span style="display:block;width:22px;height:22px;border-radius:50%;background:${GREEN};border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)"></span>`,
    });
    L.marker([m.lat, m.lng], { icon, title: m.name, alt: `Mitra bener.in: ${m.name}` })
      .bindPopup(popup(m, contactHidden))
      .addTo(layer);
  }

  async function refresh() {
    if (!map || !layer) return;
    const thisRun = ++runId;
    if (controller) controller.abort();
    controller = new AbortController();

    const center = map.getCenter();
    const radius = Math.min(100, Math.max(1, map.distance(center, map.getBounds().getNorthEast()) / 1000));
    const params = new URLSearchParams({ lat: center.lat, lng: center.lng, radius_km: radius.toFixed(1) });
    if (select.value) params.set('category', select.value);

    try {
      const response = await fetch(`${mitraUrl}?${params}`, { signal: controller.signal, credentials: 'same-origin' });
      const data = await response.json();
      if (thisRun !== runId || !response.ok || !data.ok) return;
      layer.clearLayers();
      data.mitra.forEach(m => addMitra(m, data.contact_hidden));
      if (data.mitra.length) showLegend();
    } catch (error) {
      if (error.name !== 'AbortError') console.warn('Mitra bener.in belum termuat:', error);
    }
  }

  // Ganti kategori / tekan "Cari di area ini": muat ulang mitra untuk kategori itu.
  // setTimeout 0 supaya jalan SETELAH handler home.js memperbarui nilai kategori.
  form.addEventListener('submit', () => schedule(0));
  select.addEventListener('change', () => schedule(0));
  page.querySelectorAll('[data-home-category]').forEach(link => {
    link.addEventListener('click', () => schedule(0));
  });
})();
