// NVIDIA mirror — minimal progressive enhancement
document.addEventListener('DOMContentLoaded', function () {
  // Keep business feedback readable until the next navigation.
  // Escape closes the native details menu and returns focus to its control.
  document.querySelectorAll('.site-menu').forEach(function (menu) {
    menu.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && menu.open) {
        menu.open = false;
        menu.querySelector('summary').focus();
      }
    });
  });
});
