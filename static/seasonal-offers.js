(() => {
  const section = document.querySelector('[data-seasonal-offers]');
  if (!section) return;
  const money = value => 'R ' + Math.ceil(value).toLocaleString('en-ZA', {maximumFractionDigits: 0});
  const csrf = section.querySelector('[name="csrf_token"]').value;
  const glanceSelect = section.querySelector('[data-glance-select]');
  const summaries = new Map();
  const renderGlance = () => {
    const result = summaries.get(glanceSelect.value);
    const priced = result && result.status === 'priced' && result.expires * 1000 > Date.now();
    const write = (selector, value) => { section.querySelector(selector).textContent = value; };
    write('[data-glance-flights]', priced ? 'Flights included in this supplier quote.' + (result.carriers?.length ? ' Airline: ' + result.carriers.join(', ') + '. Confirm the schedule before booking.' : ' Confirm the airline and schedule before booking.') : 'Flights requested. Ask Dirk to confirm flight options for these dates.');
    write('[data-glance-transfers]', !priced || result.transfers_included == null ? 'Confirm inclusion, transfer type and arrival arrangements with Dirk.' : result.transfers_included ? 'Transfers included in this supplier quote.' + (result.transfer_type ? ' ' + result.transfer_type + '.' : '') + ' Confirm arrival arrangements with Dirk.' : 'Transfers are not included in this supplier quote. Ask Dirk to arrange them separately.');
    write('[data-glance-room]', priced ? result.room + ', for 2 adults sharing.' : 'Room category to be confirmed, for 2 adults sharing.');
    write('[data-glance-meal]', priced ? result.meal : 'Meal plan');
    write('[data-glance-meal-note]', priced ? 'Meal plan in this supplier quote. Confirm restaurant, drink and dining inclusions before booking.' : 'Meal plan to be confirmed for these dates.');
    write('[data-glance-note]', priced ? result.availability + ' - subject to confirmation. Nothing is held or booked.' : 'Supplier details need checking for these dates. Nothing is held or booked.');
  };
  glanceSelect.addEventListener('change', renderGlance);
  const set = (card, selector, value) => {
    const element = card.querySelector(selector);
    element.textContent = value;
    element.hidden = false;
  };
  const load = async () => {
    for (const card of section.querySelectorAll('[data-seasonal-offer]')) {
      try {
        const response = await fetch(card.dataset.priceUrl, {method: 'POST', headers: {'X-CSRFToken': csrf, 'Accept': 'application/json'}});
        if (!response.ok) throw new Error('Price unavailable');
        const result = await response.json();
        summaries.set(card.dataset.offerKey, result);
        renderGlance();
        if (result.status === 'priced') {
          card.dataset.priceState = 'priced';
          card.dataset.availability = result.availability.toLowerCase().includes('on request') ? 'request' : 'other';
          set(card, '[data-offer-status]', result.availability + ' - subject to confirmation');
          set(card, '[data-offer-price]', 'From ' + money(result.person));
          card.querySelector('[data-offer-basis]').hidden = false;
          set(card, '[data-offer-total]', money(result.total) + ' total for 2 adults');
          set(card, '[data-offer-room]', result.room);
          set(card, '[data-offer-meal]', result.meal);
          const expire = () => {
            card.dataset.priceState = 'expired';
            for (const selector of ['[data-offer-price]', '[data-offer-basis]', '[data-offer-total]', '[data-offer-room]', '[data-offer-meal]']) card.querySelector(selector).hidden = true;
            set(card, '[data-offer-status]', 'Price check expired. Request a fresh quote.');
            summaries.delete(card.dataset.offerKey);
            renderGlance();
          };
          setTimeout(expire, Math.max(0, result.expires * 1000 - Date.now()));
        } else {
          card.dataset.priceState = 'unavailable';
          card.querySelector('[data-offer-form]').hidden = true;
          card.querySelector('[data-offer-enquire]').hidden = false;
          card.querySelector('[data-offer-help]').hidden = false;
          set(card, '[data-offer-status]', result.message);
        }
      } catch (_) {
        card.dataset.priceState = 'unavailable';
        card.querySelector('[data-offer-form]').hidden = true;
        card.querySelector('[data-offer-enquire]').hidden = false;
        card.querySelector('[data-offer-help]').hidden = false;
        set(card, '[data-offer-status]', 'Let me check these dates for you. Request a personalised quote.');
        summaries.delete(card.dataset.offerKey);
        renderGlance();
      }
    }
  };
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) { observer.disconnect(); load(); }
  }, {rootMargin: '100px'});
  observer.observe(section);
  for (const button of section.querySelectorAll('[data-season-filter]')) {
    button.addEventListener('click', () => {
      for (const option of section.querySelectorAll('[data-season-filter]')) option.setAttribute('aria-pressed', String(option === button));
      for (const card of section.querySelectorAll('[data-seasonal-offer]')) card.hidden = button.dataset.seasonFilter !== 'all' && card.dataset.season !== button.dataset.seasonFilter;
      const selectedCard = [...section.querySelectorAll('[data-seasonal-offer]')].find(card => card.dataset.offerKey === glanceSelect.value);
      if (selectedCard?.hidden) {
        glanceSelect.value = section.querySelector('[data-seasonal-offer]:not([hidden])').dataset.offerKey;
        renderGlance();
      }
    });
  }
  section.querySelector('[data-family-quote]').addEventListener('click', () => {
    const children = document.querySelector('#quote [name="nbrChildren"]');
    if (children) setTimeout(() => children.focus({preventScroll: true}), 100);
  });
})();
