(function () {
  var runtime = window.SigmaTaste;
  var rows = [];
  var resizeObserver = null;
  var resizeBound = false;
  var fontsBound = false;

  function recalcRow(row) {
    if (!row || !row.isConnected) {
      return;
    }

    var tags = Array.from(row.querySelectorAll('.card-tag-item'));
    var more = row.querySelector('.badge-more');
    if (!tags.length || !more) return;
    var fullText = (row.getAttribute('data-overflow-title-text') || '').trim();
    var previewText = fullText;

    row.classList.add('is-managed');

    tags.forEach(function (tag) {
      tag.hidden = false;
    });
    more.hidden = true;
    more.textContent = '+0';
    row.removeAttribute('title');

    var availableWidth = row.clientWidth;
    if (!availableWidth) return;

    if (row.scrollWidth <= availableWidth + 0.5) return;

    more.hidden = false;

    var firstHiddenIndex = tags.length;
    var hiddenCount = 0;
    while (row.scrollWidth > availableWidth + 0.5 && firstHiddenIndex > 0) {
      firstHiddenIndex -= 1;
      hiddenCount += 1;
      tags[firstHiddenIndex].hidden = true;
      more.textContent = '+' + hiddenCount;
    }

    if (!hiddenCount) {
      more.hidden = true;
      more.textContent = '+0';
      return;
    }

    if (previewText) {
      row.setAttribute('title', previewText);
    }
  }

  function pruneRows() {
    rows = rows.filter(function (row) {
      if (row && row.isConnected) {
        return true;
      }
      if (row && resizeObserver) {
        resizeObserver.unobserve(row);
      }
      return false;
    });
  }

  function recalcAll() {
    pruneRows();
    rows.forEach(recalcRow);
  }

  function scheduleRecalc() {
    window.requestAnimationFrame(recalcAll);
  }

  function observeRow(row) {
    if (row.dataset.cardTagOverflowReady === '1') {
      return;
    }
    row.dataset.cardTagOverflowReady = '1';
    rows.push(row);

    if ('ResizeObserver' in window) {
      if (!resizeObserver) {
        resizeObserver = new ResizeObserver(function (entries) {
          entries.forEach(function (entry) {
            recalcRow(entry.target);
          });
        });
      }
      resizeObserver.observe(row);
      return;
    }

    if (!resizeBound) {
      resizeBound = true;
      window.addEventListener('resize', scheduleRecalc, { passive: true });
    }
  }

  function init(root) {
    var scope = root || document;
    var nextRows = scope.querySelectorAll('[data-card-tag-overflow]');
    if (!nextRows.length) {
      return;
    }

    for (var index = 0; index < nextRows.length; index += 1) {
      observeRow(nextRows[index]);
    }

    if (!fontsBound && document.fonts && document.fonts.ready) {
      fontsBound = true;
      document.fonts.ready.then(scheduleRecalc).catch(function () {});
    }

    scheduleRecalc();
  }

  if (runtime && typeof runtime.registerInitializer === 'function') {
    runtime.registerInitializer('card-tag-overflow', init);
    return;
  }

  init(document);
})();
