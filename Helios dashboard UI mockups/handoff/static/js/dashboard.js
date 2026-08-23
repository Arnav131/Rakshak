// Rakshak dashboard — sparkline chart renderer
// Renders any <div data-spark data-values="1,2,3..." data-color="#hex"></div>
(function () {
  function renderSpark(el) {
    const values = (el.dataset.values || '').split(',').map(Number).filter(v => !isNaN(v));
    if (!values.length) return;
    const stroke = el.dataset.color || '#c9a24a';
    const w = 200, h = 44, pad = 4;
    const min = Math.min(...values), max = Math.max(...values);
    const stepX = (w - pad * 2) / (values.length - 1);
    const scaleY = v => h - pad - ((v - min) / (max - min || 1)) * (h - pad * 2);
    const pts = values.map((v, i) => [pad + i * stepX, scaleY(v)]);
    let d = `M ${pts[0][0]} ${pts[0][1]}`;
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
      const cx = (x0 + x1) / 2;
      d += ` C ${cx} ${y0}, ${cx} ${y1}, ${x1} ${y1}`;
    }
    const area = `${d} L ${pts[pts.length - 1][0]} ${h} L ${pts[0][0]} ${h} Z`;
    const gid = 'g' + Math.random().toString(36).slice(2, 8);
    el.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
        <defs>
          <linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${stroke}" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="${stroke}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="${area}" fill="url(#${gid})"/>
        <path d="${d}" stroke="${stroke}" stroke-width="2" fill="none" stroke-linecap="round"/>
      </svg>`;
  }
  document.querySelectorAll('[data-spark]').forEach(renderSpark);

  // Theme cards — click to visually mark active (visual only)
  document.querySelectorAll('.theme-card').forEach(c => {
    c.addEventListener('click', () => {
      document.querySelectorAll('.theme-card').forEach(x => x.classList.remove('active'));
      c.classList.add('active');
    });
  });
})();
