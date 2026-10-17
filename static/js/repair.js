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
