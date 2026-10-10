document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-finder]');
  if (form) {
    const steps = [...form.querySelectorAll('[data-step]')];
    const controls = form.querySelector('.finder-controls');
    const next = form.querySelector('[data-next]');
    const prev = form.querySelector('[data-prev]');
    const error = form.querySelector('.finder-error');
    let index = 0;
    form.noValidate = true;
    const show = (target, focus = false) => {
      index = target;
      steps.forEach((step, i) => { step.hidden = i !== index; });
      form.querySelectorAll('.finder-progress li').forEach((li, i) => {
        if (i === index) li.setAttribute('aria-current', 'step');
        else li.removeAttribute('aria-current');
      });
      prev.hidden = index === 0;
      next.hidden = index === steps.length - 1;
      error.hidden = true;
      if (focus) {
        const legend = steps[index].querySelector('legend');
        legend.tabIndex = -1;
        legend.focus();
      }
    };
    const valid = (i) => {
      const input = [...steps[i].querySelectorAll('input,select')].find(el => !el.checkValidity());
      if (input) { show(i); input.reportValidity(); return false; }
      let message = '';
      if (i === 0) {
        const traveller = form.querySelector('[name=traveller]:checked').value;
        if ((Number(form.elements.namedItem('children').value) || Number(form.elements.namedItem('infants').value)) && traveller !== 'family') message = 'Choose Family when children or infants are travelling.';
        if (traveller === 'solo' && Number(form.elements.namedItem('adults').value) !== 1) message = 'Choose one adult for solo travel.';
      }
      if (i === 1) {
        const count = form.querySelectorAll('[name=priorities]:checked').length;
        if (count < 1 || count > 3) message = 'Choose one to three priorities.';
      }
      if (message) { show(i); error.textContent = message; error.hidden = false; return false; }
      return true;
    };
    controls.hidden = false;
    show(0);
    next.addEventListener('click', () => { if (valid(index)) show(index + 1, true); });
    prev.addEventListener('click', () => show(index - 1, true));
    form.querySelectorAll('[name=traveller]').forEach(input => input.addEventListener('change', () => {
      if (input.value === 'solo') form.elements.namedItem('adults').value = 1;
    }));
    form.addEventListener('submit', event => {
      for (let i = 0; i < steps.length; i++) {
        if (!valid(i)) { event.preventDefault(); return; }
      }
    });
  }
  const picker = document.querySelector('[data-compare-picker]');
  picker?.addEventListener('submit', event => {
    const count = picker.querySelectorAll('input:checked').length;
    const error = picker.querySelector('[role=alert]');
    if (count < 1 || count > 3) {
      event.preventDefault();
      error.textContent = 'Choose one to three resorts.';
      error.hidden = false;
    }
  });
  document.querySelector('[data-share-comparison]')?.addEventListener('click', async () => {
    const url = new URL('/compare', window.location.origin);
    new URLSearchParams(window.location.search).getAll('resort').forEach(code => url.searchParams.append('resort', code));
    const status = document.querySelector('[data-copy-status]');
    try { await navigator.clipboard.writeText(url.toString()); status.textContent = 'Comparison link copied.'; }
    catch { status.textContent = 'Copy this link: ' + url.toString(); }
  });
});
