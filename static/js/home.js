(() => {
  'use strict';

  const page = document.querySelector('.home-page');
  if (!page) return;

  const select = page.querySelector('#category-select');
  const form = page.querySelector('#map-filter');
  const areaButton = page.querySelector('#area-btn');
  const status = page.querySelector('#search-status');
  const feedback = page.querySelector('.home-map-feedback');
  const surface = page.querySelector('#home-map-surface');
  const results = page.querySelector('#home-map-results');
  const placeList = page.querySelector('#home-place-list');
  const categoryLinks = page.querySelectorAll('[data-home-category]');

  // Preserve the existing category keys and OpenStreetMap tag queries.
  const categories = {
    gadget: [['shop', 'mobile_phone'], ['shop', 'computer'], ['craft', 'electronics_repair'], ['shop', 'electronics_repair']],
    elektronik: [['craft', 'electronics_repair'], ['shop', 'electronics_repair'], ['shop', 'appliance'], ['craft', 'electrician']],
    mobil: [['shop', 'car_repair']],
    motor: [['shop', 'motorcycle_repair'], ['shop', 'motorcycle']],
    sepeda: [['shop', 'bicycle']],
    furnitur: [['craft', 'carpenter'], ['craft', 'upholsterer'], ['shop', 'furniture']],
    sepatu: [['craft', 'shoemaker'], ['shop', 'shoe_repair']],
    pakaian: [['craft', 'tailor'], ['shop', 'tailor']],
    jam: [['craft', 'watchmaker']],
    perhiasan: [['craft', 'jeweller']],
    lainnya: [['shop', 'repair']]
  };
  let map;
  let markers;
  let controller;
  let requestId = 0;

  function announce(message, state = 'idle') {
    status.textContent = message;
    feedback.dataset.state = state;
    surface.setAttribute('aria-busy', state === 'loading' ? 'true' : 'false');
  }

  function updateSelection() {
    categoryLinks.forEach(link => {
      if (link.dataset.homeCategory === select.value) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
    areaButton.disabled = !map || !categories[select.value];
  }

  categoryLinks.forEach(link => {
    link.addEventListener('click', () => {
      select.value = link.dataset.homeCategory;
      updateSelection();
      // Native anchor navigation runs after this handler; focus its destination afterwards.
      requestAnimationFrame(() => select.focus({ preventScroll: true }));
      loadPlaces();
    });
  });
  select.addEventListener('change', () => {
    updateSelection();
    loadPlaces();
  });
  form.addEventListener('submit', event => {
    event.preventDefault();
    loadPlaces();
  });

  function buildQuery(filters, bounds) {
    const box = `(${bounds.getSouth()},${bounds.getWest()},${bounds.getNorth()},${bounds.getEast()})`;
    const parts = filters.map(filter => `nwr["${filter[0]}"="${filter[1]}"]${box};`);
    return `[out:json][timeout:25];(${parts.join('')});out center 100;`;
  }

  function placeContent(tags, label) {
    const content = document.createElement('div');
    content.className = 'home-popup';
    const name = document.createElement('strong');
    name.textContent = tags.name || 'Tempat tanpa nama';
    content.append(name);
    [label, tags['addr:street'], tags.phone].filter(Boolean).forEach(value => {
      const line = document.createElement('span');
      line.textContent = value;
      content.append(line);
    });
    return content;
  }

  async function loadPlaces() {
    const currentId = ++requestId;
    if (controller) controller.abort();
    if (!map) return;
    markers.clearLayers();
    placeList.replaceChildren();
    results.hidden = true;
    const key = select.value;
    if (!categories[key]) {
      announce('Pilih kategori untuk mencari tempat reparasi di area peta.');
      return;
    }
    if (map.getZoom() < 12) {
      announce('Perbesar peta terlebih dahulu, lalu tekan “Cari di area ini”.');
      return;
    }

    controller = new AbortController();
    const label = select.options[select.selectedIndex].text;
    announce('Sedang mencari tempat reparasi di area ini…', 'loading');
    try {
      const response = await fetch('https://overpass-api.de/api/interpreter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: 'data=' + encodeURIComponent(buildQuery(categories[key], map.getBounds())),
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`Overpass ${response.status}`);
      const data = await response.json();
      if (currentId !== requestId) return;
      if (!Array.isArray(data.elements)) throw new Error('Invalid Overpass response');

      let count = 0;
      data.elements.forEach(element => {
        const lat = element.lat ?? element.center?.lat;
        const lon = element.lon ?? element.center?.lon;
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
        const tags = element.tags || {};
        const marker = L.marker([lat, lon], { title: tags.name || 'Tempat tanpa nama' })
          .bindPopup(placeContent(tags, label)).addTo(markers);
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = tags.name || 'Tempat tanpa nama';
        button.addEventListener('click', () => {
          map.panTo([lat, lon]);
          marker.openPopup();
          marker.getElement()?.focus();
        });
        item.append(button);
        [tags['addr:street'], tags.phone].filter(Boolean).forEach(value => {
          const detail = document.createElement('span');
          detail.textContent = value;
          item.append(detail);
        });
        placeList.append(item);
        count++;
      });
      results.hidden = count === 0;
      announce(count
        ? `Ditemukan ${count} tempat dari OpenStreetMap untuk ${label}. Pilih penanda atau buka daftar tempat.`
        : 'Belum ada hasil OpenStreetMap untuk kategori ini di area pencarian. Coba area lain, lalu cari ulang.', count ? 'success' : 'empty');
    } catch (error) {
      if (error.name === 'AbortError' || currentId !== requestId) return;
      announce('Pencarian belum berhasil. Periksa koneksi, lalu tekan “Cari di area ini” untuk mencoba lagi.', 'error');
    }
  }

  if (typeof window.L === 'undefined') {
    announce('Peta belum berhasil dimuat. Periksa koneksi dan muat ulang halaman untuk mencoba lagi.', 'error');
    return;
  }
  try {
    // Zoom 12 lets the first category search run without an extra zoom step.
    map = L.map('map', { scrollWheelZoom: false }).setView([-6.2088, 106.8456], 12);
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    tiles.on('tileerror', () => { page.querySelector('#home-tile-warning').hidden = false; });
    markers = L.layerGroup().addTo(map);
    updateSelection();
    announce('Pilih kategori, lalu jelajahi tempat reparasi di area peta. Gunakan tombol + dan − untuk memperbesar atau memperkecil.');
  } catch (error) {
    map = null;
    updateSelection();
    announce('Peta belum dapat ditampilkan. Muat ulang halaman untuk mencoba lagi. Bagian lain tetap dapat digunakan.', 'error');
  }
})();
