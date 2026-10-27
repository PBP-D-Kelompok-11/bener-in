(function () {
  'use strict';

  var STAR_LABELS = { 1: 'Buruk', 2: 'Kurang', 3: 'Cukup', 4: 'Puas', 5: 'Sangat puas' };

  function stars(n) {
    return '★'.repeat(n) + '☆'.repeat(5 - n);
  }

//   bintang, karakter
  function initForm() {
    var form = document.querySelector('.rv-form');
    if (!form) return;

    var preview = form.querySelector('[data-stars-preview]');
    var radios = form.querySelectorAll('input[name="rating"]');
    function showStars() {
      var checked = form.querySelector('input[name="rating"]:checked');
      if (!preview) return;
      preview.textContent = checked
        ? stars(+checked.value) + '  ' + STAR_LABELS[checked.value]
        : 'Pilih rating untuk melihat pratinjau bintang.';
    }
    radios.forEach(function (r) { r.addEventListener('change', showStars); });
    showStars();

    var area = form.querySelector('textarea');
    var counter = form.querySelector('[data-counter]');
    if (area && counter) {
      var max = area.maxLength > 0 ? area.maxLength : 1000;
      var update = function () {
        var n = area.value.length;
        counter.textContent = n + ' / ' + max + ' karakter';
        counter.classList.toggle('rv-counter--warn', n >= max * 0.9);
      };
      area.addEventListener('input', update);
      update();
    }

    form.addEventListener('submit', function () {
      var btn = form.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Menyimpan...';
      }
    });
  }

//   filter rating 
  function initFilter() {
    var group = document.querySelector('[data-rating-filter]');
    if (!group) return;
    var items = document.querySelectorAll('[data-review-item]');
    var count = document.querySelector('[data-filter-count]');
    var empty = document.querySelector('[data-filter-empty]');
    var chips = group.querySelectorAll('button[data-rating]');

    function apply(value) {
      var shown = 0;
      items.forEach(function (li) {
        var match = value === 'all' || li.getAttribute('data-rating') === value;
        li.hidden = !match;
        if (match) shown += 1;
      });
      chips.forEach(function (c) {
        c.setAttribute('aria-pressed', String(c.getAttribute('data-rating') === value));
      });
      if (count) count.textContent = 'Menampilkan ' + shown + ' dari ' + items.length + ' review';
      if (empty) empty.hidden = shown !== 0;
    }

    chips.forEach(function (c) {
      c.addEventListener('click', function () { apply(c.getAttribute('data-rating')); });
    });
    apply('all');
  }

//   delete via ajax
  function flash(text, isError) {
    var box = document.querySelector('[data-flash]');
    if (!box) return;
    box.innerHTML = '';
    var ul = document.createElement('ul');
    ul.className = 'rv-messages';
    var li = document.createElement('li');
    li.className = 'rv-message' + (isError ? ' rv-message--error' : '');
    li.textContent = text;
    ul.appendChild(li);
    box.appendChild(ul);
  }

  function syncEmpty(container, text) {
    if (!container.querySelector('li')) {
      container.innerHTML = '';
      var p = document.createElement('p');
      p.className = 'rv-empty';
      p.textContent = text;
      container.appendChild(p);
    }
  }

  function addPendingCard(info) {
    var box = document.querySelector('#rv-pending');
    if (!box || !info) return;
    var list = box.querySelector('ul');
    if (!list) {
      box.innerHTML = '';
      list = document.createElement('ul');
      list.className = 'rv-list';
      box.appendChild(list);
    }
    var li = document.createElement('li');
    li.className = 'rv-card rv-card--accent';

    var top = document.createElement('div');
    top.className = 'rv-card__top';
    var title = document.createElement('span');
    title.className = 'rv-card__title';
    title.textContent = info.item;
    var meta = document.createElement('span');
    meta.className = 'rv-meta';
    meta.textContent = info.mitra;
    top.appendChild(title);
    top.appendChild(meta);

    var actions = document.createElement('div');
    actions.className = 'rv-actions';
    var a = document.createElement('a');
    a.className = 'btn btn-solid';
    a.href = info.url;
    a.textContent = 'Tulis review';
    actions.appendChild(a);

    li.appendChild(top);
    li.appendChild(actions);
    list.appendChild(li);
  }

  function initDelete() {
    var page = document.querySelector('[data-csrf]');
    if (!page) return;
    var csrf = page.getAttribute('data-csrf');

    document.querySelectorAll('[data-ajax-delete]').forEach(function (link) {
      var armed = false;
      var timer = null;
      var original = link.textContent;

      link.addEventListener('click', function (e) {
        e.preventDefault();

        //klik pertama konfirm, kedua hapus
        if (!armed) {
          armed = true;
          link.textContent = 'Yakin hapus?';
          link.classList.add('rv-confirm');
          timer = setTimeout(function () {
            armed = false;
            link.textContent = original;
            link.classList.remove('rv-confirm');
          }, 3000);
          return;
        }
        clearTimeout(timer);
        link.textContent = 'Menghapus...';
        link.setAttribute('aria-disabled', 'true');

        fetch(link.href, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
        })
          .then(function (res) {
            if (!res.ok) throw new Error('gagal');
            return res.json();
          })
          .then(function (data) {
            var card = link.closest('li');
            card.classList.add('rv-card--removing');
            setTimeout(function () {
              card.remove();
              syncEmpty(document.querySelector('#rv-reviews'), 'Kamu belum menulis review.');
              addPendingCard(data.pending);
            }, 300);
            flash(data.message, false);
          })
          .catch(function () {
            armed = false;
            link.textContent = original;
            link.classList.remove('rv-confirm');
            link.removeAttribute('aria-disabled');
            flash('Gagal menghapus review. Coba lagi.', true);
          });
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initForm();
    initFilter();
    initDelete();
  });
})();