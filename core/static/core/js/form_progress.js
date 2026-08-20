(function () {
  var runtime = window.SigmaTaste;
  var pageshowBound = false;

  function readText(value, fallback) {
    var text = typeof value === 'string' ? value.trim() : '';
    return text || fallback;
  }

  function initProgressForm(form) {
    if (form.dataset.progressReady === '1') {
      return;
    }
    form.dataset.progressReady = '1';

    var submitBtn = form.querySelector('[data-progress-submit]');
    var progress = form.querySelector('[data-ai-progress]');
    var progressBar = form.querySelector('[data-ai-progress-bar]');
    if (!submitBtn || !progress) {
      return;
    }

    var titleNode = form.querySelector('[data-ai-progress-title]');
    var stageNode = form.querySelector('[data-ai-stage]');
    var elapsedNode = form.querySelector('[data-ai-elapsed]');
    var originalButtonText = readText(submitBtn.textContent, 'Submit');
    var elapsedTimer = null;
    var elapsedSeconds = 0;
    var submitting = false;

    var config = {
      defaultTitle: readText(
        form.dataset.progressTitle,
        readText(titleNode && titleNode.textContent, 'Working on your request')
      ),
      defaultStage: readText(
        form.dataset.progressStage,
        readText(stageNode && stageNode.textContent, 'Please wait...')
      ),
      defaultButton: readText(form.dataset.progressButton, originalButtonText)
    };

    function clearTimer() {
      if (elapsedTimer) {
        window.clearInterval(elapsedTimer);
        elapsedTimer = null;
      }
    }

    function currentProgressText() {
      return {
        title: config.defaultTitle,
        stage: config.defaultStage,
        button: config.defaultButton
      };
    }

    function startProgress() {
      var text = currentProgressText();
      progress.hidden = false;
      progress.classList.add('is-active');
      progress.setAttribute('aria-hidden', 'false');

      if (titleNode) {
        titleNode.textContent = text.title;
      }
      if (stageNode) {
        stageNode.textContent = text.stage;
      }
      if (progressBar) {
        progressBar.setAttribute('aria-valuetext', text.stage);
      }

      submitBtn.disabled = true;
      submitBtn.setAttribute('aria-busy', 'true');
      submitBtn.textContent = text.button;
      form.setAttribute('aria-busy', 'true');

      elapsedSeconds = 0;
      if (elapsedNode) {
        elapsedNode.textContent = '0 s';
      }
      clearTimer();
      elapsedTimer = window.setInterval(function () {
        elapsedSeconds += 1;
        if (elapsedNode) {
          elapsedNode.textContent = elapsedSeconds + ' s';
        }
      }, 1000);
    }

    function resetSubmitState() {
      var text = currentProgressText();
      clearTimer();
      submitting = false;
      submitBtn.disabled = false;
      submitBtn.removeAttribute('aria-busy');
      submitBtn.textContent = originalButtonText;
      form.removeAttribute('aria-busy');
      progress.classList.remove('is-active');
      progress.hidden = true;
      progress.setAttribute('aria-hidden', 'true');
      if (titleNode) {
        titleNode.textContent = text.title;
      }
      if (stageNode) {
        stageNode.textContent = text.stage;
      }
      if (progressBar) {
        progressBar.setAttribute('aria-valuetext', text.stage);
      }
      if (elapsedNode) {
        elapsedNode.textContent = '0 s';
      }
    }
    form.__sigmaProgressReset = resetSubmitState;

    form.addEventListener('submit', function (event) {
      var submitter = event && event.submitter ? event.submitter : null;
      if (submitter && !submitter.hasAttribute('data-progress-submit')) {
        return;
      }
      if (submitting) {
        return;
      }
      submitting = true;
      startProgress();
    });
  }

  function bindPageShowReset() {
    if (pageshowBound) {
      return;
    }
    pageshowBound = true;
    window.addEventListener('pageshow', function () {
      var forms = document.querySelectorAll('form[data-progress-form][data-progress-ready="1"]');
      for (var index = 0; index < forms.length; index += 1) {
        var form = forms[index];
        if (typeof form.__sigmaProgressReset === 'function') {
          form.__sigmaProgressReset();
        }
      }
    });
  }

  function init(root) {
    bindPageShowReset();
    var forms = (root || document).querySelectorAll('form[data-progress-form]');
    for (var index = 0; index < forms.length; index += 1) {
      initProgressForm(forms[index]);
    }
  }

  if (runtime && typeof runtime.registerInitializer === 'function') {
    runtime.registerInitializer('form-progress', init);
    return;
  }

  init(document);
})();
