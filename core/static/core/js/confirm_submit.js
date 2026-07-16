(function () {
  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-confirm-submit]');
    if (!button) {
      return;
    }
    var message = (button.getAttribute('data-confirm-submit') || '').trim();
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });
})();
