(() => {
  const form = document.querySelector('[data-repair-wizard]');
  if (!form) return;

  const steps = [...form.querySelectorAll('[data-step]')];
  const progress = [...form.querySelectorAll('[data-progress-step]')];
  const categoryInputs = [...form.querySelectorAll('input[name="category"]')];
  const partnerInputs = [...form.querySelectorAll('input[name="mitra"]')];
  const partnerCards = [...form.querySelectorAll('[data-partner-card]')];
  const matchingSection = form.querySelector('[data-matching-section]');
  const matchingList = form.querySelector('[data-matching-list]');
  const matchingEmpty = form.querySelector('[data-matching-empty]');
  const otherSection = form.querySelector('[data-other-section]');
  const otherList = form.querySelector('[data-other-list]');
  const otherHeading = form.querySelector('[data-other-heading]');
  const otherHint = form.querySelector('[data-other-hint]');
  const itemInput = form.querySelector('[name="item_name"]');
  const descriptionInput = form.querySelector('[name="description"]');
  const submitButton = form.querySelector('[data-submit]');
  const displayedCategory = form.querySelector('[name="displayed_category"]');
  let currentStep = Number(form.dataset.startStep) || 0;
  let submitting = false;

  form.classList.add('is-enhanced');
  form.noValidate = true;

  function selected(name) {
    return form.querySelector(`input[name="${name}"]:checked`);
  }

  function setError(name, message) {
    const error = form.querySelector(`[data-error-for="${name}"]`);
    const controls = form.querySelectorAll(`[name="${name}"]`);
    if (error) {
      error.textContent = message;
      error.hidden = !message;
    }
    controls.forEach((control) => {
      if (message) control.setAttribute('aria-invalid', 'true');
      else control.removeAttribute('aria-invalid');
    });
  }

  function showStep(index, focus = true) {
    currentStep = Math.max(0, Math.min(index, steps.length - 1));
    steps.forEach((step, stepIndex) => { step.hidden = stepIndex !== currentStep; });
    progress.forEach((item, stepIndex) => {
      item.classList.toggle('is-complete', stepIndex < currentStep);
      if (stepIndex === currentStep) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    if (focus) steps[currentStep].querySelector('h2').focus();
  }

  function arrangePartners() {
    if (!matchingSection || !otherSection) return;
    const category = selected('category')?.value;
    let matched = 0;
    let other = 0;
    partnerCards.forEach((card) => {
      const services = card.dataset.categories.split(',').filter(Boolean);
      if (category && services.includes(category)) {
        matchingList.append(card);
        matched += 1;
      } else {
        otherList.append(card);
        other += 1;
      }
    });
    matchingSection.hidden = matched === 0;
    if (matchingEmpty) matchingEmpty.hidden = !category || matched !== 0;
    otherSection.hidden = other === 0;
    otherHeading.textContent = category ? 'Mitra aktif lainnya' : 'Mitra terdaftar';
    otherHint.hidden = !category;
  }

  function updateSummary() {
    const categoryLabel = selected('category')?.closest('label')?.querySelector('.repair-choice-card__body')?.textContent.trim();
    const partnerName = selected('mitra')?.closest('label')?.querySelector('.repair-partner-card__top strong')?.textContent.trim();
    form.querySelector('[data-summary-category]').textContent = categoryLabel || 'Belum dipilih';
    form.querySelector('[data-summary-mitra]').textContent = partnerName || 'Belum dipilih';
    form.querySelector('[data-summary-item]').textContent = itemInput.value.trim() || 'Belum diisi';
    form.querySelector('[data-summary-description]').textContent = descriptionInput.value.trim() || 'Belum diisi';
  }

  function validateStep(index) {
    if (index === 0) {
      const valid = Boolean(selected('category'));
      setError('category', valid ? '' : 'Pilih kategori barang sebelum melanjutkan.');
      if (!valid) categoryInputs[0]?.focus();
      return valid;
    }
    if (index === 1) {
      const valid = Boolean(selected('mitra'));
      setError('mitra', valid ? '' : 'Pilih mitra aktif sebelum melanjutkan.');
      if (!valid) partnerInputs[0]?.focus();
      return valid;
    }
    if (index === 2) {
      const item = itemInput.value.trim();
      const description = descriptionInput.value.trim();
      const itemError = !item ? 'Isi nama barang.' : item.length > 150 ? 'Nama barang terlalu panjang.' : '';
      const descriptionError = description ? '' : 'Jelaskan masalah pada barang.';
      setError('item_name', itemError);
      setError('description', descriptionError);
      if (itemError) itemInput.focus();
      else if (descriptionError) descriptionInput.focus();
      return !itemError && !descriptionError;
    }
    return true;
  }

  categoryInputs.forEach((input) => input.addEventListener('change', () => {
    partnerInputs.forEach((partner) => { partner.checked = false; });
    displayedCategory.value = input.value;
    setError('category', '');
    setError('mitra', '');
    arrangePartners();
    updateSummary();
  }));
  partnerInputs.forEach((input) => input.addEventListener('change', () => {
    setError('mitra', '');
    updateSummary();
  }));
  [itemInput, descriptionInput].forEach((input) => input.addEventListener('input', () => {
    setError(input.name, '');
    updateSummary();
  }));
  form.querySelectorAll('[data-next]').forEach((button) => button.addEventListener('click', () => {
    if (validateStep(currentStep)) {
      updateSummary();
      showStep(currentStep + 1);
    }
  }));
  form.querySelectorAll('[data-back]').forEach((button) => button.addEventListener('click', () => {
    showStep(currentStep - 1);
  }));
  form.addEventListener('submit', (event) => {
    if (submitting) {
      event.preventDefault();
      return;
    }
    if (currentStep < 3) {
      event.preventDefault();
      if (validateStep(currentStep)) showStep(currentStep + 1);
      return;
    }
    for (let index = 0; index < 3; index += 1) {
      if (!validateStep(index)) {
        event.preventDefault();
        showStep(index);
        return;
      }
    }
    submitting = true;
    submitButton.disabled = true;
    submitButton.textContent = 'Mengirim…';
  });

  arrangePartners();
  updateSummary();
  showStep(currentStep, false);
})();

(() => {
  const page = document.querySelector('[data-customer-list]');
  if (!page) return;

  const filters = page.querySelector('[data-customer-filters]');
  const results = page.querySelector('[data-customer-results]');
  const live = page.querySelector('[data-customer-live]');
  const notice = page.querySelector('[data-customer-notice]');
  let controller;
  let version = 0;
  let searchTimer;

  function showError(message) {
    notice.replaceChildren();
    notice.hidden = !message;
    if (!message) return;
    notice.append(document.createTextNode(message));
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'repair-mitra-retry';
    retry.textContent = 'Coba lagi';
    retry.addEventListener('click', () => loadResults(false));
    notice.append(retry);
  }

  function selectedUrl() {
    const url = new URL(filters.action, window.location.href);
    for (const [name, value] of new FormData(filters)) {
      if (value) url.searchParams.set(name, value);
    }
    return url;
  }

  function restoreFilters() {
    const params = new URL(window.location.href).searchParams;
    filters.elements.q.value = params.get('q') || '';
    filters.elements.status.value = params.get('status') || '';
    filters.elements.category.value = params.get('category') || '';
  }

  async function loadResults(push = true) {
    version += 1;
    const current = version;
    controller?.abort();
    controller = new AbortController();
    const url = selectedUrl();
    if (push && url.href !== window.location.href) window.history.pushState(null, '', url);
    results.setAttribute('aria-busy', 'true');
    results.firstElementChild?.classList.add('is-loading');
    live.textContent = 'Memuat permintaan…';
    showError('');
    try {
      const response = await fetch(url, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        signal: controller.signal,
      });
      if (!response.ok || response.redirected) throw new Error('Daftar tidak dapat dimuat.');
      const html = await response.text();
      const content = new DOMParser().parseFromString(html, 'text/html')
        .querySelector('[data-customer-result-content]');
      if (!content) throw new Error('Respons daftar tidak lengkap.');
      if (current !== version) return;
      results.replaceChildren(content);
      live.textContent = `${content.dataset.resultCount} permintaan ditampilkan.`;
    } catch (error) {
      if (error.name === 'AbortError' || current !== version) return;
      showError('Daftar tidak dapat dimuat. Periksa koneksi lalu coba lagi.');
      live.textContent = 'Gagal memuat permintaan.';
    } finally {
      if (current === version) {
        results.setAttribute('aria-busy', 'false');
        results.firstElementChild?.classList.remove('is-loading');
      }
    }
  }

  filters.addEventListener('submit', (event) => {
    event.preventDefault();
    clearTimeout(searchTimer);
    loadResults();
  });
  filters.addEventListener('change', (event) => {
    if (event.target === filters.elements.q) return;
    clearTimeout(searchTimer);
    loadResults();
  });
  filters.elements.q.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadResults(), 300);
  });
  page.addEventListener('click', (event) => {
    if (!event.target.closest('[data-customer-reset]')) return;
    event.preventDefault();
    clearTimeout(searchTimer);
    filters.elements.q.value = '';
    filters.elements.status.value = '';
    filters.elements.category.value = '';
    loadResults();
  });
  window.addEventListener('popstate', () => {
    clearTimeout(searchTimer);
    restoreFilters();
    loadResults(false);
  });
})();

(() => {
  const dashboard = document.querySelector('[data-mitra-dashboard]');
  if (!dashboard) return;

  const filters = dashboard.querySelector('[data-mitra-filters]');
  const results = dashboard.querySelector('[data-mitra-results]');
  const live = dashboard.querySelector('[data-mitra-live]');
  const notice = dashboard.querySelector('[data-mitra-notice]');
  let filterController;
  let filterVersion = 0;
  let searchTimer;

  function announce(message) {
    live.textContent = message;
  }

  function showNotice(message, error = false, retry = false) {
    notice.replaceChildren();
    notice.hidden = !message;
    notice.classList.toggle('is-error', error);
    if (!message) return;
    notice.append(document.createTextNode(message));
    if (retry) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'repair-mitra-retry';
      button.textContent = 'Muat ulang daftar';
      button.addEventListener('click', () => loadResults(false));
      notice.append(button);
    }
  }

  function updateCounts(source) {
    ['incoming', 'active', 'history'].forEach((group) => {
      const value = source[group] ?? source[`${group}Count`];
      const badge = filters.querySelector(`[data-count="${group}"]`);
      if (badge && value !== undefined) badge.textContent = value;
    });
  }

  function replaceResults(html) {
    const parsed = new DOMParser().parseFromString(html, 'text/html');
    const content = parsed.querySelector('[data-mitra-result-content]');
    if (!content) throw new Error('Respons daftar tidak lengkap.');
    results.replaceChildren(content);
    updateCounts(content.dataset);
    results.setAttribute('aria-busy', 'false');
    announce(`${content.dataset.resultCount} permintaan ditampilkan.`);
  }

  function selectedUrl() {
    const url = new URL(filters.action, window.location.href);
    const data = new FormData(filters);
    for (const [key, value] of data.entries()) {
      if (value) url.searchParams.set(key, value);
    }
    return url;
  }

  function setFiltersFromUrl() {
    const params = new URL(window.location.href).searchParams;
    const group = params.get('group') || 'incoming';
    const radio = filters.querySelector(`input[name="group"][value="${CSS.escape(group)}"]`);
    (radio || filters.querySelector('input[name="group"][value="incoming"]')).checked = true;
    filters.elements.q.value = params.get('q') || '';
    filters.elements.category.value = params.get('category') || '';
    filters.elements.status.value = params.get('status') || '';
  }

  function invalidateFilters() {
    filterVersion += 1;
    filterController?.abort();
  }

  async function loadResults(push = true) {
    invalidateFilters();
    const version = filterVersion;
    filterController = new AbortController();
    const url = selectedUrl();
    if (push && url.href !== window.location.href) {
      window.history.pushState(null, '', url);
    }
    results.setAttribute('aria-busy', 'true');
    results.firstElementChild?.classList.add('is-loading');
    announce('Memuat permintaan…');
    showNotice('');
    try {
      const response = await fetch(url, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        signal: filterController.signal,
      });
      if (!response.ok || response.redirected) throw new Error('Daftar tidak dapat dimuat.');
      const html = await response.text();
      if (version === filterVersion) replaceResults(html);
      return true;
    } catch (error) {
      if (error.name === 'AbortError' || version !== filterVersion) return false;
      showNotice('Daftar tidak dapat dimuat. Periksa koneksi lalu coba lagi.', true, true);
      announce('Gagal memuat permintaan.');
      return false;
    } finally {
      if (version === filterVersion) {
        results.setAttribute('aria-busy', 'false');
        results.firstElementChild?.classList.remove('is-loading');
      }
    }
  }

  filters.addEventListener('submit', (event) => {
    event.preventDefault();
    clearTimeout(searchTimer);
    loadResults();
  });
  filters.addEventListener('change', (event) => {
    if (event.target === filters.elements.q) return;
    clearTimeout(searchTimer);
    loadResults();
  });
  filters.elements.q.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadResults(), 300);
  });
  filters.querySelector('[data-mitra-reset]').addEventListener('click', (event) => {
    event.preventDefault();
    clearTimeout(searchTimer);
    filters.elements.q.value = '';
    filters.elements.category.value = '';
    filters.elements.status.value = '';
    filters.querySelector('input[name="group"][value="incoming"]').checked = true;
    loadResults();
  });
  window.addEventListener('popstate', () => {
    clearTimeout(searchTimer);
    setFiltersFromUrl();
    loadResults(false);
  });

  results.addEventListener('toggle', (event) => {
    const details = event.target.closest('.repair-work-action--reason');
    if (details?.open) details.querySelector('textarea')?.focus();
  }, true);

  results.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-mitra-action]');
    if (!form) return;
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const feedback = form.querySelector('[data-action-feedback]');
    const card = form.closest('[data-request-id]');
    if (button.disabled || card.dataset.actionBusy === 'true') return;
    card.dataset.actionBusy = 'true';
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    feedback.hidden = true;
    showNotice('');
    const actionQuery = window.location.search;
    const actionUrl = new URL(form.action);
    actionUrl.search = actionQuery;
    let refreshRequired = false;
    try {
      const response = await fetch(actionUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value,
        },
        body: new FormData(form),
      });
      const contentType = response.headers.get('Content-Type') || '';
      const data = contentType.includes('application/json') ? await response.json() : null;
      if (response.ok && data?.ok) {
        invalidateFilters();
        let refreshed = true;
        if (window.location.search === actionQuery) {
          replaceResults(data.results_html);
          updateCounts(data.counts);
        } else {
          refreshed = await loadResults(false);
        }
        showNotice(
          refreshed ? data.message : `${data.message} Daftar belum dapat dimuat ulang.`,
          !refreshed, !refreshed,
        );
        return;
      }
      const message = data?.error || (response.status === 403
        ? 'Sesi atau izin berubah. Muat ulang halaman sebelum mencoba lagi.'
        : 'Status belum dapat dipastikan. Muat ulang daftar sebelum mencoba lagi.');
      if (response.status === 400) {
        feedback.textContent = message;
        feedback.hidden = false;
        button.disabled = false;
        button.removeAttribute('aria-busy');
        delete card.dataset.actionBusy;
        return;
      }
      showNotice(message, true, true);
      refreshRequired = true;
    } catch (error) {
      showNotice('Koneksi terputus. Status mungkin sudah berubah; muat ulang daftar sebelum mencoba lagi.', true, true);
      refreshRequired = true;
    }
    if (refreshRequired) {
      const refreshed = await loadResults(false);
      if (refreshed) showNotice('Daftar telah dimuat ulang. Periksa status sebelum mencoba lagi.', true);
    }
  });
})();
