document.querySelectorAll('.rooms-preview-track').forEach(track => {
  const section = track.closest('section');
  const items = [...track.querySelectorAll('figure')];
  const prev = section.querySelector('[data-room-prev]');
  const next = section.querySelector('[data-room-next]');
  const position = section.querySelector('[data-room-position]');
  const gap = () => parseFloat(getComputedStyle(track).columnGap) || 0;
  const step = () => items.length ? items[0].getBoundingClientRect().width + gap() : 0;
  const update = () => {
    const start = Math.round(track.scrollLeft / step()) + 1;
    const visible = Math.max(1, Math.round((track.clientWidth + gap()) / step()));
    position.textContent = items.length ? 'Photos ' + start + ' - ' + Math.min(items.length, start + visible - 1) + ' of ' + items.length : 'Room photographs are being updated.';
    prev.disabled = track.scrollLeft < 2;
    next.disabled = track.scrollLeft >= track.scrollWidth - track.clientWidth - 2;
  };
  const move = direction => track.scrollBy({left: direction * step(), behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  prev.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));
  track.addEventListener('scroll', update, {passive: true});
  track.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      move(event.key === 'ArrowLeft' ? -1 : 1);
    }
  });
  new ResizeObserver(update).observe(track);
  update();
});
