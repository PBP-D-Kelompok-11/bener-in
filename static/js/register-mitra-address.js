// Form daftar mitra: isi kolom "Alamat usaha" otomatis dari titik yang diklik di peta.
//
// File ini SENGAJA terpisah supaya skrip inline di register_mitra.html tidak
// perlu diubah (pola yang sama dengan home-mitra.js). Ia harus dimuat SEBELUM
// skrip inline itu: peta #pick-map ditangkap lewat L.Map.addInitHook, lalu
// ditambah satu pendengar "click". Kalau syaratnya tidak terpenuhi (Leaflet
// tidak ada, URL kosong, kolom alamat tidak ada) skrip diam dan form tetap
// berfungsi seperti biasa dengan alamat diisi manual.
(() => {
  'use strict';

  const script = document.currentScript;
  const reverseUrl = script && script.dataset.reverseUrl;
  if (!reverseUrl || typeof window.L === 'undefined') return;

  const MAP_ID = 'pick-map';
  const FIELD_ID = 'id_alamat';
  let lastAuto = null;     // alamat terakhir yang diisi skrip ini
  let hint = null;
  let controller = null;
  let runId = 0;

  L.Map.addInitHook(function () {
    if (this.getContainer().id !== MAP_ID) return;
    this.on('click', event => onPick(event.latlng));
  });

  function ensureHint(field) {
    if (!hint) {
      hint = document.createElement('p');
      hint.id = 'alamat-hint';
      hint.setAttribute('role', 'status');
      hint.setAttribute('aria-live', 'polite');
      hint.style.cssText = 'margin:.35rem 0 0;font-size:.875rem;opacity:.85';
      field.insertAdjacentElement('afterend', hint);
    }
    return hint;
  }

  function say(field, message, { error = false, action } = {}) {
    const box = ensureHint(field);
    box.className = error ? 'field-error' : '';
    box.style.opacity = error ? '' : '.85';
    box.replaceChildren(document.createTextNode(message));
    if (action) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-ghost';
      button.style.cssText = 'margin-left:.5rem;padding:.15rem .6rem;font-size:.85rem';
      button.textContent = action.label;
      button.addEventListener('click', action.run);
      box.append(button);
    }
  }

  // Alamat yang sudah diketik/diubah pemakai tidak boleh ditimpa diam-diam.
  function editedByUser(field) {
    return field.value.trim() !== '' && field.value !== lastAuto;
  }

  function onPick(latlng) {
    const field = document.getElementById(FIELD_ID);
    if (!field) return;
    if (editedByUser(field)) {
      say(field, 'Alamat sudah kamu ubah, jadi tidak diganti otomatis.', {
        action: { label: 'Pakai alamat dari titik ini', run: () => fill(field, latlng) },
      });
      return;
    }
    fill(field, latlng);
  }

  async function fill(field, latlng) {
    const thisRun = ++runId;
    if (controller) controller.abort();
    controller = new AbortController();
    say(field, 'Mencari alamat dari titik di peta…');

    const params = new URLSearchParams({ lat: latlng.lat.toFixed(6), lng: latlng.lng.toFixed(6) });
    try {
      const response = await fetch(`${reverseUrl}?${params}`, {
        signal: controller.signal, credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      const data = await response.json().catch(() => ({}));
      if (thisRun !== runId) return;  // sudah ada klik yang lebih baru
      if (!response.ok || !data.ok || !data.address) {
        say(field, (data.message || 'Alamat belum bisa diisi otomatis.') + ' Isi alamat secara manual.', { error: true });
        return;
      }
      field.value = data.address;
      lastAuto = data.address;
      field.dispatchEvent(new Event('input', { bubbles: true }));
      say(field, 'Alamat diisi dari titik di peta. Periksa dan sesuaikan bila perlu.');
    } catch (error) {
      if (error.name === 'AbortError') return;
      if (thisRun === runId) say(field, 'Alamat belum bisa diisi otomatis. Isi alamat secara manual.', { error: true });
    }
  }
})();
