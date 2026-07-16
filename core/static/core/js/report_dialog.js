(function () {
  // The dialog lives inside .page-wrap, so soft navigation swaps it out; always
  // resolve it at click time instead of caching a reference that can go stale.
  function getDialog() {
    var dialog = document.querySelector('[data-report-dialog]');
    if (!dialog || typeof dialog.showModal !== 'function') {
      return null;
    }
    return dialog;
  }

  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-report-dialog-trigger]');
    var dialog = getDialog();
    if (!trigger) {
      if (dialog && event.target === dialog) {
        dialog.close();
      }
      return;
    }

    // Without <dialog> support the trigger links fall through to the standalone report page.
    if (!dialog) {
      return;
    }

    event.preventDefault();
    var form = dialog.querySelector('[data-report-dialog-form]');
    var titleNode = dialog.querySelector('[data-report-dialog-title]');
    form.setAttribute('action', trigger.getAttribute('href'));
    titleNode.textContent = trigger.getAttribute('data-report-title') || 'Report';
    dialog.showModal();
  });
})();
