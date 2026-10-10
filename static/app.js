document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) window.lucide.createIcons();
  const menu = document.querySelector('.menu-toggle');
  menu?.addEventListener('click', () => {
    const expanded = menu.getAttribute('aria-expanded') === 'true';
    menu.setAttribute('aria-expanded', String(!expanded));
    document.querySelector('#main-nav').classList.toggle('is-open', !expanded);
  });
  document.querySelectorAll('[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  document.querySelectorAll('[data-quote-form]').forEach(form => {
    const children = form.querySelector('[data-children-count]');
    const infants = form.querySelector('[data-infants-count]');
    const updateAges = () => {
      form.querySelectorAll('[data-child-age], [data-infant-dob]').forEach(label => {
        const child = label.hasAttribute('data-child-age');
        const index = Number(child ? label.dataset.childAge : label.dataset.infantDob);
        const visible = index <= Number(child ? children.value : infants.value);
        label.hidden = !visible;
        label.querySelector('input').required = visible;
        label.querySelector('input').disabled = !visible;
      });
    };
    children.addEventListener('input', updateAges);
    infants.addEventListener('input', updateAges);
    updateAges();
    const departure = form.querySelector('[name=dateDeparture]');
    const returning = form.querySelector('[name=dateReturn]');
    departure.addEventListener('change', () => {
      if (!departure.value) return;
      const day = new Date(departure.value + 'T12:00:00Z');
      day.setUTCDate(day.getUTCDate() + 1);
      returning.min = day.toISOString().slice(0, 10);
    });
    form.addEventListener('submit', () => {
      const button = form.querySelector('[type=submit]');
      button.disabled = true;
      button.textContent = 'Checking…';
      form.querySelector('.quote-progress').hidden = false;
    });
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) window.location.reload();
  });
});
