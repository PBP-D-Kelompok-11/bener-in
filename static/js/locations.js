(() => {
  'use strict';

  // ---------- Util bersama ----------
  const csrfToken = () => document.querySelector('[data-csrf]')?.dataset.csrf || '';

  async function request(url, { method = 'GET', body } = {}) {
    const options = {
      method,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' },
    };
    if (method !== 'GET') {
      options.headers['X-CSRFToken'] = csrfToken();
      options.body = body ?? new FormData();
    }
    const response = await fetch(url, options);
    let data = {};
    try { data = await response.json(); } catch (error) { /* bukan JSON */ }
    return { ok: response.ok && data.ok !== false, status: response.status, data };
  }

  let toastTimer;
  function toast(message, { action, state = 'info', duration = 4000 } = {}) {
    const box = document.querySelector('[data-toast]');
    if (!box) return;
    clearTimeout(toastTimer);
    box.replaceChildren();
    box.dataset.state = state;
    const text = document.createElement('span');
    text.textContent = message;
    box.append(text);
    if (action) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = action.label;
      button.addEventListener('click', () => { box.hidden = true; action.run(); });
      box.append(button);
      duration = Math.max(duration, 8000);
    }
    box.hidden = false;
    toastTimer = setTimeout(() => { box.hidden = true; }, duration);
  }

  // ---------- Halaman peta ----------
  function initDiscover() {
    const page = document.querySelector('[data-loc-discover]');
    if (!page) return;

    const form = page.querySelector('#loc-filter');
    const statusBox = page.querySelector('#loc-status');
    const list = page.querySelector('#loc-results');
    const emptyBox = page.querySelector('#loc-results-empty');
    const cfg = page.dataset;
    const authenticated = cfg.authenticated === '1';
    const isCustomer = cfg.customer === '1';
    const saved = new Set(JSON.parse(document.getElementById('loc-saved-ids')?.textContent || '[]'));
    let map, osmLayer, mitraLayer, controller, runId = 0;

    const say = (message, state = 'idle') => {
      statusBox.textContent = message;
      statusBox.dataset.state = state;
    };

    if (typeof window.L === 'undefined') {
      say('Peta belum berhasil dimuat. Periksa koneksi lalu muat ulang halaman.', 'error');
      return;
    }
    map = L.map('loc-map', { scrollWheelZoom: false }).setView([-6.2088, 106.8456], 12);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      // Django default 'same-origin' menghapus Referer; tile OSM menolak tanpa Referer.
      referrerPolicy: 'strict-origin-when-cross-origin',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    osmLayer = L.layerGroup().addTo(map);
    mitraLayer = L.layerGroup().addTo(map);

    function line(parent, text, className) {
      if (!text) return;
      const node = document.createElement('span');
      if (className) node.className = className;
      node.textContent = text;
      parent.append(node);
    }

    function contactLine(parent, item, hidden) {
      if (item.phone) return line(parent, 'Telepon: ' + item.phone);
      if (hidden) {
        const link = document.createElement('a');
        link.href = `${cfg.loginUrl}?next=${encodeURIComponent(location.pathname)}`;
        link.textContent = 'Masuk untuk melihat kontak';
        parent.append(link);
      }
    }

    // Simpan dengan optimistic UI: tombol langsung berubah, dikembalikan jika gagal.
    async function savePlace(place, button) {
      button.disabled = true;
      button.textContent = 'Tersimpan';
      saved.add(place.id);
      const body = new FormData();
      body.append('place_id', place.id);
      body.append('status', 'want');
      try {
        const result = await request(cfg.createUrl, { method: 'POST', body });
        if (!result.ok) throw result;
        toast(result.data.message || 'Tempat disimpan.', {
          action: { label: 'Lihat daftar', run: () => { location.href = cfg.savedUrl; } },
        });
      } catch (result) {
        saved.delete(place.id);
        button.disabled = false;
        button.textContent = 'Simpan';
        const message = result?.data?.message || 'Gagal menyimpan. Coba lagi.';
        toast(message, { state: 'error' });
      }
    }

    function popup(item, kind, hidden) {
      const box = document.createElement('div');
      box.className = 'loc-popup';
      const name = document.createElement('strong');
      name.textContent = item.name;
      box.append(name);
      line(box, item.address);
      contactLine(box, item, hidden);
      if (kind === 'mitra') {
        line(box, `${item.distance_km} km dari pusat peta`);
        const link = document.createElement('a');
        link.className = 'btn btn-outline';
        link.href = item.reviews_url;
        link.textContent = 'Lihat review';
        box.append(link);
      } else if (isCustomer) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-solid';
        button.textContent = saved.has(item.id) ? 'Tersimpan' : 'Simpan';
        button.disabled = saved.has(item.id);
        button.addEventListener('click', () => savePlace(item, button));
        box.append(button);
      } else if (!authenticated) {
        const link = document.createElement('a');
        link.className = 'btn btn-outline';
        link.href = `${cfg.loginUrl}?next=${encodeURIComponent(location.pathname)}`;
        link.textContent = 'Masuk untuk menyimpan';
        box.append(link);
      }
      return box;
    }

    function addItem(item, kind, hidden) {
      const color = kind === 'mitra' ? '#2f7d4f' : '#14261c';
      const marker = L.circleMarker([item.lat, item.lng], {
        radius: kind === 'mitra' ? 9 : 7, color, fillColor: color, fillOpacity: .75, weight: 2,
      }).bindPopup(popup(item, kind, hidden)).addTo(kind === 'mitra' ? mitraLayer : osmLayer);
      const li = document.createElement('li');
      li.dataset.kind = kind;
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = item.name;
      button.addEventListener('click', () => { map.panTo([item.lat, item.lng]); marker.openPopup(); });
      li.append(button);
      line(button, kind === 'mitra' ? 'Mitra bener.in' : 'OpenStreetMap');
      line(button, item.address);
      list.append(li);
    }

    function withinLimit(bounds) {
      return (bounds.getNorth() - bounds.getSouth()) <= 0.6 && (bounds.getEast() - bounds.getWest()) <= 0.6;
    }

    async function getJson(url, signal) {
      const response = await fetch(url, { signal, credentials: 'same-origin' });
      const data = await response.json().catch(() => ({}));
      return { ok: response.ok && data.ok !== false, data };
    }

    // Mitra bener.in: kategori opsional; hasil langsung digambar saat tiba.
    async function loadMitra(params, signal, thisRun) {
      const { ok, data } = await getJson(`${cfg.mitraUrl}?${params}`, signal);
      if (thisRun !== runId) return { count: 0 };
      if (!ok) return { count: 0, error: data.message || 'Mitra bener.in belum berhasil dimuat.' };
      const items = data.mitra || [];
      items.forEach(item => addItem(item, 'mitra', data.contact_hidden));
      return { count: items.length };
    }

    // OpenStreetMap lewat proxy server: kategori wajib.
    async function loadOsm(params, signal, thisRun) {
      const { ok, data } = await getJson(`${cfg.placesUrl}?${params}`, signal);
      if (thisRun !== runId) return { count: 0 };
      if (!ok) return { count: 0, error: data.message || 'Pencarian OpenStreetMap belum berhasil.' };
      const items = data.places || [];
      items.forEach(item => addItem(item, 'osm', data.contact_hidden));
      return { count: items.length, stale: Boolean(data.stale) };
    }

    async function search() {
      const category = form.elements.category.value;
      const wantOsm = Boolean(category);
      const wantMitra = form.querySelector('#loc-mitra').checked;
      if (!wantOsm && !wantMitra) {
        return say('Pilih kategori, atau centang “Tampilkan mitra bener.in”.', 'error');
      }
      const bounds = map.getBounds();
      if (wantOsm && !withinLimit(bounds)) {
        return say('Area terlalu luas. Perbesar peta, lalu cari lagi.', 'error');
      }

      const thisRun = ++runId;
      if (controller) controller.abort();
      controller = new AbortController();
      const { signal } = controller;
      osmLayer.clearLayers();
      mitraLayer.clearLayers();
      list.replaceChildren();
      say('Mencari tempat reparasi…', 'loading');

      const center = map.getCenter();
      const radius = Math.min(100, Math.max(1, map.distance(center, bounds.getNorthEast()) / 1000));
      const mitraParams = new URLSearchParams({ lat: center.lat, lng: center.lng, radius_km: radius.toFixed(1) });
      if (category) mitraParams.set('category', category);
      const placeParams = new URLSearchParams({
        category, q: form.elements.q.value.trim(),
        south: bounds.getSouth(), west: bounds.getWest(), north: bounds.getNorth(), east: bounds.getEast(),
      });

      const [mitraJob, osmJob] = await Promise.allSettled([
        wantMitra ? loadMitra(mitraParams, signal, thisRun) : Promise.resolve({ count: 0 }),
        wantOsm ? loadOsm(placeParams, signal, thisRun) : Promise.resolve({ count: 0 }),
      ]);
      if (thisRun !== runId) return;  // sudah ada pencarian yang lebih baru

      const failed = { count: 0, error: 'Pencarian belum berhasil. Periksa koneksi lalu coba lagi.' };
      const mitra = mitraJob.status === 'fulfilled' ? mitraJob.value : failed;
      const osm = osmJob.status === 'fulfilled' ? osmJob.value : failed;
      const total = mitra.count + osm.count;
      const errors = [mitra.error, osm.error].filter(Boolean);
      emptyBox.hidden = total > 0;

      let message = total
        ? `Ditemukan ${total} tempat.`
        : 'Belum ada hasil di area ini. Coba kategori atau area lain.';
      if (osm.stale) message += ' Server OpenStreetMap sedang sibuk; hasilnya dari data tersimpan sebelumnya.';
      if (!wantOsm) message += ' Pilih kategori untuk juga mencari tempat dari OpenStreetMap.';
      if (errors.length) message += ' ' + errors.join(' ');
      say(message, errors.length ? 'error' : (total ? 'success' : 'idle'));
    }

    form.addEventListener('submit', event => { event.preventDefault(); search(); });
  }

  // ---------- Halaman tempat tersimpan ----------
  function initSaved() {
    const page = document.querySelector('[data-saved-page]');
    if (!page) return;
    const list = page.querySelector('[data-saved-list]');
    const empty = page.querySelector('[data-empty]');
    const count = page.querySelector('[data-count]');

    function refresh() {
      const total = list.querySelectorAll('[data-saved-item]').length;
      count.textContent = `${total} tempat`;
      empty.hidden = total > 0;
    }

    // Hapus optimistis: item hilang seketika; dikembalikan jika server menolak.
    async function remove(form) {
      const item = form.closest('[data-saved-item]');
      const next = item.nextElementSibling;
      const put = () => { list.insertBefore(item, next && next.parentNode === list ? next : null); refresh(); };
      item.remove();
      refresh();
      try {
        const result = await request(form.action, { method: 'POST' });
        if (!result.ok) throw result;
        toast(result.data.message, {
          action: { label: 'Urungkan', run: () => undo(result.data.restore_url, put) },
        });
      } catch (result) {
        put();
        toast(result?.data?.message || 'Gagal menghapus. Coba lagi.', { state: 'error' });
      }
    }

    async function undo(url, put) {
      const result = await request(url, { method: 'POST' });
      if (result.ok) {
        put();
        toast(result.data.message);
      } else {
        toast(result.data.message || 'Gagal mengembalikan.', { state: 'error' });
      }
    }

    list.addEventListener('submit', event => {
      const form = event.target.closest('form[data-ajax-delete]');
      if (!form) return;
      event.preventDefault();
      remove(form);
    });
  }

  initDiscover();
  initSaved();
})();
