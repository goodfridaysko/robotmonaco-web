(() => {
  const doc = document.documentElement;
  doc.classList.add('js');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // loader: shown once per tab. Lifts when the page has loaded, but never before the logo has had its
  // moment (min) and never later than max, whatever a slow image is doing.
  const loader = document.querySelector('.loader');
  if (loader && !doc.classList.contains('no-loader')) {
    document.body.classList.add('is-loading');
    const t0 = performance.now();
    const min = reduce ? 0 : 1100, max = 2600;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      loader.classList.add('is-done');
      document.body.classList.remove('is-loading');
      try { sessionStorage.setItem('rr-loaded', '1'); } catch (e) {}
      setTimeout(() => loader.remove(), 1000);
    };
    const onLoad = () => setTimeout(finish, Math.max(0, min - (performance.now() - t0)));
    if (document.readyState === 'complete') onLoad(); else addEventListener('load', onLoad, { once: true });
    setTimeout(finish, max);
  } else if (loader) {
    loader.remove();
  }

  // nav: hairline once content scrolls under it
  const nav = document.querySelector('.nav');
  const onScrollNav = () => nav && nav.classList.toggle('is-scrolled', scrollY > 8);
  addEventListener('scroll', onScrollNav, { passive: true });
  onScrollNav();

  // mobile menu
  const burger = document.querySelector('.burger');
  if (burger) {
    burger.addEventListener('click', () => {
      const open = document.body.classList.toggle('menu-open');
      burger.setAttribute('aria-expanded', open);
    });
    document.querySelectorAll('.menu-links a').forEach(a =>
      a.addEventListener('click', () => { document.body.classList.remove('menu-open'); burger.setAttribute('aria-expanded', 'false'); }));
    addEventListener('keydown', e => { if (e.key === 'Escape') { document.body.classList.remove('menu-open'); burger.setAttribute('aria-expanded', 'false'); } });
  }

  // reveal on scroll
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }), { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));

  // manifesto: words light up with scroll progress (text stays in DOM for crawlers)
  document.querySelectorAll('[data-words]').forEach(p => {
    if (reduce) return;
    const words = p.textContent.trim().split(/\s+/);
    p.innerHTML = words.map(w => `<span class="w">${w}</span>`).join(' ');
    const spans = [...p.querySelectorAll('.w')];
    let ticking = false;
    const update = () => {
      ticking = false;
      const r = p.getBoundingClientRect();
      const vh = innerHeight;
      const progress = Math.min(1, Math.max(0, (vh * 0.85 - r.top) / (r.height + vh * 0.35)));
      const lit = Math.round(progress * spans.length);
      spans.forEach((s, i) => s.classList.toggle('on', i < lit));
    };
    addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  });

  // 3D stage: fetch the viewer and the model only when the stage is about to be seen
  const stages = document.querySelectorAll('.stage[data-model]');
  if (stages.length) {
    let lib;
    // A still, for reading artwork: no clip and no camera direction, just the pair framed to fit the stage
    // at whatever shape the stage has, and turnable by hand.
    const stillStage = (el, mv) => {
      const attrs = {
        src: el.dataset.model, alt: el.dataset.alt, 'camera-controls': '', 'disable-zoom': '', 'disable-pan': '',
        'touch-action': 'pan-y', 'interaction-prompt': 'none', 'shadow-intensity': '1.1', 'shadow-softness': '0.8',
        exposure: '1.0', 'tone-mapping': 'commerce', 'environment-image': '/assets/env/studio.hdr',
        'field-of-view': '24deg', 'min-camera-orbit': 'auto 70deg 1m', 'max-camera-orbit': 'auto 95deg 14m',
        'interpolation-decay': '140'
      };
      Object.entries(attrs).forEach(([k, v]) => mv.setAttribute(k, v));
      const K = Math.tan(12 * Math.PI / 180);                  // half of the 24deg vertical field of view
      const frame = jump => {
        const aspect = el.clientWidth / Math.max(1, el.clientHeight);
        // The pair stands about 1.34 m tall and 1.4 m across. Height gets a fifth of the frame as margin,
        // so the heads clear the hint; width gets less, because a portrait phone is width-bound anyway.
        const r = Math.max(0.89 / K, 0.72 / (K * aspect));
        const turned = el.classList.contains('is-touched') && mv.getCameraOrbit;
        mv.cameraTarget = '0m 0.66m 0m';
        mv.cameraOrbit = `${turned ? mv.getCameraOrbit().theta + 'rad' : '0deg'} 84deg ${r.toFixed(2)}m`;
        if (jump) { try { mv.jumpCameraToGoal(); } catch (e) {} }
      };
      frame(true);
      mv.addEventListener('load', () => {
        frame(true);
        el.classList.add('is-ready', 'is-wide');
        setTimeout(() => el.classList.add('hint-off'), 9000);
      }, { once: true });
      if ('ResizeObserver' in window) new ResizeObserver(() => frame(false)).observe(el);
    };
    const mount = el => {
      lib = lib || import('/assets/vendor/model-viewer.min.js');
      lib.then(() => {
        const mv = document.createElement('model-viewer');
        if ('still' in el.dataset) stillStage(el, mv); else {
        const attrs = {
          src: el.dataset.model, alt: el.dataset.alt, 'camera-controls': '', 'disable-zoom': '', 'disable-pan': '',
          'touch-action': 'pan-y', 'interaction-prompt': 'none', 'shadow-intensity': '1.6', 'shadow-softness': '0.55',
          exposure: '0.95', 'tone-mapping': 'commerce', 'environment-image': '/assets/env/studio.hdr',
          'camera-orbit': '25deg 82deg 5m', 'camera-target': '0m 0.8m 0m', 'min-camera-orbit': 'auto 60deg auto', 'max-camera-orbit': 'auto 95deg 30m',
          'field-of-view': '24deg', 'interpolation-decay': '120'
        };
        // Intro: open on a close-up of the head, then pull back to the full figure once the stage is on screen.
        const WIDE = { orbit: '25deg 82deg 5m', target: '0m 0.8m 0m' };   // metres, not %: the cast changes the model bounds
        const CLOSE = { orbit: '14deg 84deg 0.95m', target: '0m 1.2m 0m' };
        if (!reduce) {
          Object.assign(attrs, { 'animation-name': 'show', 'camera-orbit': CLOSE.orbit, 'camera-target': CLOSE.target,
            'min-camera-orbit': 'auto 60deg 0.6m', 'interpolation-decay': '260' });
        }
        Object.entries(attrs).forEach(([k, v]) => mv.setAttribute(k, v));
        mv.addEventListener('load', () => {
          if (reduce) { el.classList.add('is-ready', 'is-wide'); return; }
          mv.jumpCameraToGoal();                       // start exactly on the close-up, no drift while fading in
          el.classList.add('is-ready');
          const pullBack = () => {
            mv.cameraOrbit = WIDE.orbit;
            mv.cameraTarget = WIDE.target;
            mv.play();
            setTimeout(() => el.classList.add('is-wide'), 2200);   // controls appear once the figure is in frame
            setTimeout(() => el.classList.add('hint-off'), 9000);  // the hint has done its job by then
            setTimeout(() => {                         // hand the camera over to the visitor once the move has settled
              mv.setAttribute('interpolation-decay', '140');
              mv.setAttribute('min-camera-orbit', 'auto 60deg auto');
              direct();
            }, 4200);
          };
          // Camera direction, driven by the show clock. Runs every frame; every value is eased here, so
          // model-viewer gets a smooth stream instead of steps. Once the visitor drags, only distance and
          // target stay ours.
          // Shots: [from second, half-height, half-width] the frame must hold around the robot.
          const SHOTS = [[0, 1.0, 0.75], [6.8, 1.02, 0.9], [47.5, 1.0, 0.75]];
          const K = Math.tan(12 * Math.PI / 180);              // half of the 24deg vertical field of view
          let path = null;
          fetch(el.dataset.model.split('?')[0].replace('.glb', '.path.json')).then(r => r.json()).then(p => { path = p; }).catch(() => {});
          const at = t => {
            if (!path) return [0, 0, 0];
            let lo = 0, hi = path.length - 1;
            while (hi - lo > 1) { const m = (lo + hi) >> 1; if (path[m][0] <= t) lo = m; else hi = m; }
            return [path[lo][1], path[lo][2], path[lo][3] || 0];
          };
          const cam = { tx: 0, ty: 0.8, tz: 0, r: 5, theta: 25 };
          const direct = () => {
            mv.setAttribute('interpolation-decay', '40');
            let last = performance.now();
            const tick = now => {
              const dt = Math.min(0.05, (now - last) / 1000); last = now;
              requestAnimationFrame(tick);
              if (document.hidden || !mv.loaded) return;
              const t = mv.currentTime;
              const shot = SHOTS.filter(s => t >= s[0]).pop();
              const aspect = el.clientWidth / Math.max(1, el.clientHeight);
              const wantR = Math.max(shot[1] / K, shot[2] / (K * aspect));
              const [px, py, pz] = at(t);                         // MuJoCo x forward, y left, z up
              const k = 1 - Math.exp(-dt * 2.6);                  // ~0.4 s time constant
              cam.r += (wantR - cam.r) * k;
              cam.tx += (py - cam.tx) * k;                        // glTF x = MuJoCo y
              cam.tz += (px - cam.tz) * k;                        // glTF z = MuJoCo x
              cam.ty += (0.8 + 0.5 * pz - cam.ty) * k;
              const touched = el.classList.contains('is-touched');
              const o = mv.getCameraOrbit();
              const theta = touched ? o.theta * 180 / Math.PI : 8 + 18 * Math.sin(t * 2 * Math.PI / 26);
              const phi = touched ? o.phi * 180 / Math.PI : 82;
              mv.cameraTarget = `${cam.tx.toFixed(3)}m ${cam.ty.toFixed(3)}m ${cam.tz.toFixed(3)}m`;
              mv.cameraOrbit = `${theta.toFixed(2)}deg ${phi.toFixed(2)}deg ${cam.r.toFixed(3)}m`;
            };
            requestAnimationFrame(tick);
          };
          const seen = new IntersectionObserver(es => {
            if (es.some(en => en.isIntersecting)) { seen.disconnect(); setTimeout(pullBack, 900); }
          }, { threshold: 0.45 });
          seen.observe(el);
        }, { once: true });
        }
        mv.addEventListener('pointerdown', () => el.classList.add('is-touched'), { once: true });
        // If WebGL, the network or the file lets us down, show the product photo instead of a dark box.
        const fallback = () => {
          if (el.classList.contains('is-ready') || el.classList.contains('is-fallback')) return;
          el.classList.add('is-fallback');
          mv.remove();
          const img = new Image();
          img.src = el.dataset.fallback || '/assets/photos/montari-tile.png';
          img.alt = el.dataset.alt || '';
          img.className = 'stage-fallback';
          el.appendChild(img);
        };
        mv.addEventListener('error', fallback);
        setTimeout(() => { if (!mv.loaded) fallback(); }, 20000);
        el.appendChild(mv);
      }).catch(() => {
        el.classList.add('is-fallback');
        const img = new Image();
        img.src = el.dataset.fallback || '/assets/photos/montari-tile.png';
        img.alt = el.dataset.alt || '';
        img.className = 'stage-fallback';
        el.appendChild(img);
      });
    };
    const so = new IntersectionObserver(es => es.forEach(en => {
      if (en.isIntersecting) { so.unobserve(en.target); mount(en.target); }
    }), { rootMargin: '400px 0px' });
    // Never compete with first paint, and stay out of the way on data-saver connections.
    const saveData = navigator.connection && navigator.connection.saveData;
    const start = () => stages.forEach(s => so.observe(s));
    if (!saveData) {
      if (document.readyState === 'complete') start();
      else addEventListener('load', start, { once: true });
    }
  }

  // video: swap the poster for the real player only when somebody asks for it
  document.querySelectorAll('.video[data-src]').forEach(v => {
    const btn = v.querySelector('.video-play');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const f = document.createElement('iframe');
      f.src = v.dataset.src;
      f.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
      f.allowFullscreen = true;
      f.title = btn.getAttribute('aria-label') || 'Video';
      v.replaceChildren(f);
    }, { once: true });
  });

  // gallery paddles
  document.querySelectorAll('.gallery').forEach(g => {
    const rail = g.querySelector('.rail');
    // the paddles sit in the section head, so look for them in the enclosing section
    const scope = g.closest('section') || g.parentElement;
    const [prev, next] = scope.querySelectorAll('.paddle');
    if (!rail || !prev || !next) return;
    const step = () => (rail.querySelector('.card')?.getBoundingClientRect().width || 320) + 20;
    const sync = () => {
      prev.disabled = rail.scrollLeft < 8;
      next.disabled = rail.scrollLeft + rail.clientWidth > rail.scrollWidth - 8;
    };
    prev.addEventListener('click', () => rail.scrollBy({ left: -step() * 2, behavior: reduce ? 'auto' : 'smooth' }));
    next.addEventListener('click', () => rail.scrollBy({ left: step() * 2, behavior: reduce ? 'auto' : 'smooth' }));
    rail.addEventListener('scroll', sync, { passive: true });
    sync();
  });

  // gallery: tag filter + lightbox (the link still works without JS, it opens the full JPEG)
  const gal = document.querySelector('.gal');
  if (gal) {
    const chips = document.querySelectorAll('.gal-filter button[data-tag]');
    chips.forEach(c => c.addEventListener('click', () => {
      const tag = c.dataset.tag;
      chips.forEach(x => { x.classList.toggle('is-on', x === c); x.setAttribute('aria-pressed', x === c); });
      gal.querySelectorAll('.gal-item').forEach(f => f.classList.toggle('is-hidden', !!tag && !(' ' + f.dataset.tags + ' ').includes(' ' + tag + ' ')));
    }));
    const box = document.querySelector('.lightbox');
    if (box && typeof box.showModal === 'function') {
      const img = box.querySelector('img'), cap = box.querySelector('figcaption');
      gal.querySelectorAll('a[data-full]').forEach(a => a.addEventListener('click', ev => {
        ev.preventDefault();
        img.src = a.dataset.full; img.alt = a.querySelector('img')?.alt || ''; cap.textContent = a.dataset.caption || '';
        box.showModal();
      }));
      box.querySelector('.lightbox-close').addEventListener('click', () => box.close());
      box.addEventListener('click', ev => { if (ev.target === box) box.close(); });
    }
    // deep link from a strip: #<file> scrolls to the photo and opens it
    if (location.hash) {
      const target = document.getElementById(location.hash.slice(1));
      if (target) setTimeout(() => { target.scrollIntoView({ block: 'center' }); target.querySelector('a[data-full]')?.click(); }, 300);
    }
  }

  // faq: one open at a time
  document.querySelectorAll('.faq-list').forEach(list => {
    list.querySelectorAll('details').forEach(d => d.addEventListener('toggle', () => {
      if (d.open) list.querySelectorAll('details[open]').forEach(o => { if (o !== d) o.open = false; });
    }));
  });

  // contact forms -> POST /send.php (same endpoint and encoding as the previous site)
  document.querySelectorAll('form[data-lead]').forEach(f => {
    f.addEventListener('submit', ev => {
      ev.preventDefault();
      const data = {};
      new FormData(f).forEach((v, k) => { if (String(v).trim()) data[k] = String(v).trim(); });
      data['Stránka'] = location.pathname;
      const body = Object.keys(data).map(k => encodeURIComponent(k) + '=' + encodeURIComponent(data[k])).join('&');
      const btn = f.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
      f.classList.remove('is-error');
      fetch('/send.php', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' }, body })
        .then(r => r.json().catch(() => ({ ok: r.ok })))
        .then(r => {
          if (!r.ok) throw new Error('send failed');
          f.classList.add('is-sent');
          f.reset();
        })
        .catch(() => { f.classList.add('is-error'); })
        .finally(() => { if (btn) btn.disabled = false; });
    });
  });

  /* language dropdown: close on outside click and Escape */
  document.querySelectorAll('.lang-dd').forEach(dd => {
    addEventListener('click', e => { if (dd.open && !dd.contains(e.target)) dd.open = false; });
    addEventListener('keydown', e => { if (e.key === 'Escape' && dd.open) { dd.open = false; dd.querySelector('summary').focus(); } });
  });

  /* Slow right-to-left auto-scroll for the "where a robot fits" rails. The cards are duplicated once so the
     loop is seamless; it pauses on hover, focus and while the visitor scrolls, and never runs for reduced motion. */
  document.querySelectorAll('.rail[data-autoscroll]').forEach(rail => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const cards = [...rail.children];
    if (cards.length < 3) return;
    cards.forEach(c => { const copy = c.cloneNode(true); copy.setAttribute('aria-hidden', 'true'); copy.tabIndex = -1; rail.append(copy); });
    const first = rail.children[0], firstCopy = rail.children[cards.length];
    rail.classList.add('is-auto');
    const loop = () => firstCopy.offsetLeft - first.offsetLeft;   // exact distance of one set, padding excluded
    let paused = false, idle = 0, last = performance.now();
    const hold = () => { paused = true; idle = 600; };
    rail.addEventListener('pointerenter', () => { paused = true; });
    rail.addEventListener('pointerleave', () => { paused = false; });
    rail.addEventListener('focusin', () => { paused = true; });
    rail.addEventListener('focusout', () => { paused = false; });
    rail.addEventListener('pointerdown', hold);
    rail.addEventListener('wheel', hold, { passive: true });
    rail.addEventListener('touchstart', hold, { passive: true });
    const step = now => {
      const dt = Math.min(48, now - last);
      last = now;
      if (idle > 0) { idle -= dt; if (idle <= 0) paused = false; }
      if (!paused && !document.hidden) {
        rail.scrollLeft += dt * 0.022;                     // ~22 px per second: slow enough to read
        const span = loop();
        if (span > 0 && rail.scrollLeft >= span) rail.scrollLeft -= span;
      }
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
})();
