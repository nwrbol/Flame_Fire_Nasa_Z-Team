// Liquid Glass: move each button's glint (::before) towards the pointer via --mx / --my.
// Pure presentation — no button logic is touched. Skipped for reduced motion.
(() => {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const SEL = '.glass-btn, .btn, .chip, .fab, .theme-btn, .send, .ico, .pager button, .drawer .x, .sugg button, .nearest button, .msg.err button, .seg button';
  addEventListener('pointermove', (e) => {
    const el = e.target instanceof Element && e.target.closest(SEL);
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty('--mx', `${e.clientX - r.left}px`);
    el.style.setProperty('--my', `${e.clientY - r.top}px`);
  }, { passive: true });
})();
