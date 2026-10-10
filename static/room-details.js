document.querySelectorAll('[data-room-detail]').forEach(button => {
  const dialog = document.getElementById(button.dataset.roomDetail);
  if (!dialog) return;
  button.addEventListener('click', () => {
    dialog.showModal();
    dialog.querySelectorAll('img').forEach(img => { img.loading = 'eager'; });
  });
});
document.querySelectorAll('.room-detail-dialog').forEach(dialog => {
  dialog.querySelector('[data-room-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
});
