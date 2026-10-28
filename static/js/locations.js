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

    async function search() {
      const category = form.elements.category.value;
      if (!category) return say('Pilih kategori barang dulu.', 'error');
      const bounds = map.getBounds();
      if (!withinLimit(bounds)) return say('Area terlalu luas. Perbesar peta, lalu cari lagi.', 'error');

      const thisRun = ++runId;
      if (controller) controller.abort();
      controller = new AbortController();
      osmLayer.clearLayers();
      mitraLayer.clearLayers();
      list.replaceChildren();
      say('Mencari tempat reparasi…', 'loading');

      const placeParams = new URLSearchParams({
        category, q: form.elements.q.value.trim(),
        south: bounds.getSouth(), west: bounds.getWest(), north: bounds.getNorth(), east: bounds.getEast(),
      });
      const center = map.getCenter();
      const radius = Math.min(100, Math.max(1, map.distance(center, bounds.getNorthEast()) / 1000));
      const mitraParams = new URLSearchParams({ category, lat: center.lat, lng: center.lng, radius_km: radius.toFixed(1) });
      const wantMitra = form.querySelector('#loc-mitra').checked;

      try {
        const [places, mitra] = await Promise.all([
          fetch(`${cfg.placesUrl}?${placeParams}`, { signal: controller.signal, credentials: 'same-origin' }),
          wantMitra ? fetch(`${cfg.mitraUrl}?${mitraParams}`, { signal: controller.signal, credentials: 'same-origin' }) : null,
        ]);
        if (thisRun !== runId) return;
        const placesData = await places.json().catch(() => ({}));
        const mitraData = mitra ? await mitra.json().catch(() => ({})) : { mitra: [] };
        if (thisRun !== runId) return;

        let total = 0;
        (mitraData.mitra || []).forEach(item => { addItem(item, 'mitra', mitraData.contact_hidden); total++; });
        if (places.ok) {
          (placesData.places || []).forEach(item => { addItem(item, 'osm', placesData.contact_hidden); total++; });
        }
        emptyBox.hidden = total > 0;

        if (!places.ok) {
          say(placesData.message || 'Pencarian OpenStreetMap belum berhasil.', 'error');
        } else if (placesData.stale) {
          say(`Server OpenStreetMap sedang sibuk. Menampilkan ${total} hasil dari data tersimpan sebelumnya.`, 'success');
        } else {
          say(total ? `Ditemukan ${total} tempat.` : 'Belum ada hasil di area ini. Coba kategori atau area lain.', total ? 'success' : 'idle');
        }
      } catch (error) {
        if (error.name === 'AbortError' || thisRun !== runId) return;
        say('Pencarian belum berhasil. Periksa koneksi lalu coba lagi.', 'error');
      }
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
