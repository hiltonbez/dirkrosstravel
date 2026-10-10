(() => {
  const links = [...document.querySelectorAll('[data-resort-photo]')];
  const dialog = document.querySelector('.resort-viewer');
  if (!dialog || !dialog.showModal) return;
  const photo = dialog.querySelector('[data-photo-full]');
  let index = 0;
  let opener;
  function show(next) {
    index = (next + links.length) % links.length;
    const link = links[index];
    photo.src = link.href;
    photo.alt = link.dataset.caption;
    dialog.querySelector('[data-photo-caption]').textContent = link.dataset.caption;
    dialog.querySelector('[data-photo-note]').textContent = link.dataset.note;
    dialog.querySelector('[data-photo-counter]').textContent = `${index + 1} / ${links.length}`;
  }
  photo.onerror = () => {
    dialog.querySelector('[data-photo-note]').textContent = 'This image is unavailable. Please try another photograph.';
  };
  links.forEach((link, position) => link.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    opener = link;
    show(position);
    dialog.showModal();
  }));
  dialog.querySelector('[data-photo-close]').onclick = () => dialog.close();
  dialog.querySelector('[data-photo-prev]').onclick = () => show(index - 1);
  dialog.querySelector('[data-photo-next]').onclick = () => show(index + 1);
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      show(index + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => { photo.removeAttribute('src'); opener?.focus(); });
})();
