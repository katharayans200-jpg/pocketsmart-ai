/* PocketSmart AI - frontend logic (vanilla JS).
   All server data is rendered with textContent / createElement - never innerHTML - so AI output cannot inject HTML. */
(function () {
  'use strict';

  // ---------- helpers ----------
  function h(tag, props, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'style') el.setAttribute('style', v);
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of children.flat()) {
      if (c == null || c === false) continue;
      el.append(c.nodeType ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN');
  const COLORS = ['#1d4ed8', '#0ea5e9', '#6366f1', '#14b8a6', '#f59e0b', '#ec4899', '#84cc16'];
  const PLANNER_LABEL = { home: 'Home', party: 'Party', jewelry: 'Jewelry' };
  const fmtDate = (iso) => new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
  function safeUrl(u) {
    try { const x = new URL(u); return x.protocol === 'https:' ? x.href : null; } catch (e) { return null; }
  }

  // ---------- navigation ----------
  const toggle = document.querySelector('[data-nav-toggle]');
  if (toggle) toggle.addEventListener('click', () => {
    const open = document.getElementById('nav-links').classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });

  // ---------- rendering of a plan (used by planner pages and the detail page) ----------
  function sourceBadge(result) {
    if (result.source === 'gemini') return h('span', { class: 'badge badge-gemini', text: 'Live AI · Gemini' + (result.model ? ' (' + result.model + ')' : '') });
    if (result.source === 'fallback') return h('span', { class: 'badge badge-fallback', text: 'Sample data (Gemini unavailable)' });
    return h('span', { class: 'badge badge-demo', text: 'Demo mode · sample data' });
  }

  function renderItem(item) {
    const links = (item.links || []).map((l) => {
      const href = safeUrl(l.url);
      return href ? h('a', { class: 'link-btn', href, target: '_blank', rel: 'noopener noreferrer nofollow', text: l.label + ' ↗' }) : null;
    });
    return h('div', { class: 'item' },
      h('div', { class: 'cat' }, item.category, item.is_sample ? ' ' : null, item.is_sample ? h('span', { class: 'badge badge-sample', text: 'SAMPLE' }) : null),
      h('h4', { text: item.name }),
      item.description ? h('p', { text: item.description }) : null,
      item.reason ? h('p', { class: 'reason', text: item.reason }) : null,
      h('div', { class: 'price-row' },
        h('small', { text: item.quantity > 1 ? item.quantity + ' × ' + inr(item.unit_price) + ' (est.)' : 'Estimated price' }),
        h('strong', { text: inr(item.total_price) })),
      h('div', { class: 'links' }, links));
  }

  function renderPlan(result) {
    const s = result.summary;
    const root = h('div', { class: 'plan' });
    root.append(h('div', { class: 'saved-bar' }, h('h2', { class: 'plan-title', text: s.title }), sourceBadge(result)));
    if (result.notice) root.append(h('div', { class: 'alert alert-warn', role: 'status', text: result.notice }));

    // budget summary
    const pct = Math.min(100, s.percent_used);
    const segs = result.sections.length > 1
      ? result.sections.map((x) => ({ name: x.name, value: x.subtotal }))
      : (result.sections[0] ? result.sections[0].items.map((x) => ({ name: x.name, value: x.total_price })) : []);
    const stack = h('div', { class: 'stack', role: 'img', 'aria-label': 'Spending by ' + (result.sections.length > 1 ? 'category' : 'item') });
    segs.forEach((g, i) => { if (g.value > 0) stack.append(h('i', { style: 'width:' + (100 * g.value / s.total_budget) + '%;background:' + COLORS[i % COLORS.length], title: g.name + ': ' + inr(g.value) })); });
    const legend = h('div', { class: 'legend' }, segs.map((g, i) => h('span', {}, h('b', { style: 'background:' + COLORS[i % COLORS.length] }), g.name + ' ' + inr(g.value))));
    root.append(h('div', { class: 'summary' },
      h('div', { class: 'summary-head', text: '📊 Budget summary' }),
      h('div', { class: 'summary-body' },
        h('div', { class: 'totals' },
          h('div', { class: 'total' }, h('span', { text: 'Total budget' }), h('strong', { text: inr(s.total_budget) })),
          h('div', { class: 'total' }, h('span', { text: 'Estimated total' }), h('strong', { text: inr(s.planned_total) })),
          h('div', { class: 'total remaining' }, h('span', { text: 'Remaining budget' }), h('strong', { text: inr(s.remaining) }))),
        h('div', { class: 'bar', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': pct }, h('i', { style: 'width:' + pct + '%' })),
        h('div', { class: 'bar-label' }, h('span', { text: s.percent_used + '% of budget planned' }), h('span', { text: 'Estimates, not verified prices' })),
        stack, legend)));

    (result.warnings || []).forEach((w) => root.append(h('div', { class: 'alert alert-info', text: w })));

    if (result.outfit_analysis) {
      const o = result.outfit_analysis;
      root.append(h('div', { class: 'card outfit' }, h('h3', { text: '👗 Outfit analysis' }),
        h('p', { class: 'hint', text: "Gemini's visual impression of your photo — not a precise measurement." }),
        h('dl', {},
          h('div', {}, h('dt', { text: 'Colours' }), h('dd', {}, h('div', { class: 'swatches' }, (o.colors || []).map((c) => h('span', { class: 'swatch', text: c }))))),
          h('div', {}, h('dt', { text: 'Style' }), h('dd', { text: o.style || '—' })),
          h('div', {}, h('dt', { text: 'Formality' }), h('dd', { text: o.formality || '—' }))),
        o.notes ? h('p', { text: o.notes }) : null));
    }

    result.sections.forEach((sec, i) => {
      const used = sec.allocation > 0 ? Math.min(100, 100 * sec.subtotal / sec.allocation) : 0;
      root.append(h('section', { class: 'section-card' },
        h('div', { class: 'section-head' },
          h('h3', { text: sec.name }),
          h('div', { class: 'amounts' }, 'Allocation ', h('strong', { text: inr(sec.allocation) }), ' · Estimated ', h('strong', { text: inr(sec.subtotal) }), ' · Left ', inr(sec.remaining))),
        h('div', { style: 'padding:0 20px' }, h('div', { class: 'bar', style: 'margin-top:12px' }, h('i', { style: 'width:' + used + '%;background:' + COLORS[i % COLORS.length] }))),
        sec.note ? h('div', { class: 'section-note', text: sec.note }) : null,
        h('div', { class: 'items' }, sec.items.map(renderItem))));
    });

    if (result.tips && result.tips.length) {
      root.append(h('div', { class: 'card tips' }, h('h3', { text: '💡 Tips' }), h('ul', {}, result.tips.map((t) => h('li', { text: t })))));
    }
    root.append(h('p', { class: 'price-note', text: result.price_note }));
    root.append(h('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => window.print() }, '🖨️ Print / save as PDF'));
    return root;
  }

  // ---------- planner forms ----------
  async function parseJson(resp) { try { return await resp.json(); } catch (e) { return {}; } }

  function clearErrors(form) {
    form.querySelectorAll('.invalid').forEach((e) => e.classList.remove('invalid'));
    form.querySelectorAll('.field-error.js').forEach((e) => e.remove());
    const box = document.getElementById('form-error'); if (box) { box.hidden = true; box.textContent = ''; }
  }
  function showFieldError(form, name, msg) {
    const input = form.elements[name];
    if (!input || !input.closest) return false;
    input.classList.add('invalid');
    const label = input.closest('.field');
    if (label) label.append(h('small', { class: 'field-error js', text: msg }));
    return true;
  }
  function showFormError(msg) {
    const box = document.getElementById('form-error');
    if (box) { box.textContent = msg; box.hidden = false; box.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
  }

  function buildJson(form) {
    const body = {};
    for (const el of form.elements) {
      if (!el.name || el.disabled) continue;
      if (el.type === 'checkbox') body[el.name] = el.checked;
      else if (el.type === 'number') body[el.name] = el.value === '' ? null : Number(el.value);
      else body[el.name] = el.value.trim();
    }
    return body;
  }

  function initPlanner(form) {
    const endpoint = form.dataset.endpoint;
    const results = document.getElementById('results');
    const btn = form.querySelector('button[type=submit]');
    const spinner = btn.querySelector('.spinner'); const label = btn.querySelector('.btn-label');
    const isMultipart = form.getAttribute('enctype') === 'multipart/form-data';
    const maxMb = Number(form.dataset.maxMb || 5);

    // outfit image preview + client-side checks
    const fileInput = form.querySelector('input[type=file]');
    if (fileInput) {
      const preview = document.getElementById('image-preview');
      const img = preview.querySelector('img');
      const reset = () => { fileInput.value = ''; preview.hidden = true; img.removeAttribute('src'); };
      document.getElementById('remove-image').addEventListener('click', reset);
      fileInput.addEventListener('change', () => {
        clearErrors(form);
        const f = fileInput.files[0]; if (!f) { reset(); return; }
        const okType = /\.(jpe?g|png)$/i.test(f.name) && /^image\/(jpeg|png)$/.test(f.type);
        if (!okType) { showFormError('Please choose a JPG, JPEG or PNG image.'); reset(); return; }
        if (f.size > maxMb * 1024 * 1024) { showFormError('That image is larger than ' + maxMb + ' MB.'); reset(); return; }
        img.src = URL.createObjectURL(f); preview.hidden = false;
      });
    }

    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      clearErrors(form);
      if (!form.checkValidity()) {
        form.reportValidity();
        const bad = form.querySelector(':invalid'); if (bad) bad.classList.add('invalid');
        showFormError('Please fill in the highlighted fields correctly.');
        return;
      }
      btn.disabled = true; spinner.hidden = false; label.textContent = 'Generating…';
      results.replaceChildren(h('div', { class: 'loading-block', role: 'status' }, h('span', { class: 'spinner' }), 'Building your plan — this can take up to a minute when Gemini is enabled…'));
      try {
        let opts;
        if (isMultipart) {
          const fd = new FormData(form);
          const f = fd.get('outfit_image'); if (f && !f.name) fd.delete('outfit_image');
          opts = { method: 'POST', body: fd, credentials: 'same-origin' };
        } else {
          opts = { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(buildJson(form)) };
        }
        const resp = await fetch(endpoint, opts);
        const data = await parseJson(resp);
        if (resp.status === 401) { window.location.href = '/login'; return; }
        if (!resp.ok) {
          results.replaceChildren();
          (data.errors || []).forEach((e) => showFieldError(form, e.field, e.message));
          showFormError(data.detail || 'Something went wrong. Please try again.');
          return;
        }
        results.replaceChildren(
          h('div', { class: 'alert alert-info' }, '✅ Saved to your history. ', h('a', { href: '/history/' + data.id, text: 'Open saved plan' })),
          renderPlan(data.result));
        results.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (err) {
        results.replaceChildren();
        showFormError('Could not reach the server. Check that it is still running, then try again.');
      } finally {
        btn.disabled = false; spinner.hidden = true; label.textContent = form.dataset.label || label.dataset.orig;
      }
    });
    label.dataset.orig = label.textContent;
  }
  const plannerForm = document.querySelector('form[data-endpoint]');
  if (plannerForm) initPlanner(plannerForm);

  // ---------- auth forms ----------
  const regForm = document.querySelector('form[data-validate="register"]');
  if (regForm) {
    const pw = regForm.elements.password; const meter = regForm.querySelector('[data-strength] i');
    pw.addEventListener('input', () => {
      const v = pw.value; let score = 0;
      if (v.length >= 8) score++; if (/[A-Za-z]/.test(v) && /\d/.test(v)) score++; if (v.length >= 12) score++; if (/[^A-Za-z0-9]/.test(v)) score++;
      meter.style.width = (score * 25) + '%'; meter.style.background = ['#b91c1c', '#d97706', '#ca8a04', '#15803d', '#15803d'][score];
    });
  }
  document.querySelectorAll('form[data-validate]').forEach((form) => {
    form.addEventListener('submit', (ev) => {
      const box = form.querySelector('[data-form-error]'); box.hidden = true;
      let msg = '';
      if (!form.checkValidity()) msg = 'Please fill in all fields correctly.';
      else if (form.dataset.validate === 'register') {
        if (form.elements.password.value !== form.elements.confirm_password.value) msg = 'Passwords do not match.';
        else if (!(/[A-Za-z]/.test(form.elements.password.value) && /\d/.test(form.elements.password.value))) msg = 'Password needs at least one letter and one number.';
      }
      if (msg) { ev.preventDefault(); box.textContent = msg; box.hidden = false; form.reportValidity(); }
    });
  });

  // ---------- history page ----------
  const list = document.getElementById('history-list');
  if (list) {
    const load = async (planner) => {
      list.replaceChildren(h('div', { class: 'loading-block', role: 'status' }, h('span', { class: 'spinner' }), 'Loading your plans…'));
      try {
        const resp = await fetch('/recommendations/history' + (planner ? '?planner=' + encodeURIComponent(planner) : ''), { credentials: 'same-origin' });
        if (resp.status === 401) { window.location.href = '/login'; return; }
        const data = await parseJson(resp);
        if (!resp.ok) throw new Error(data.detail || 'error');
        if (!data.items.length) {
          list.replaceChildren(h('div', { class: 'empty' }, h('div', { class: 'empty-icon', text: '🗂️' }), h('h3', { text: 'No plans here yet' }),
            h('p', { text: 'Create a plan with one of the planners and it will show up here.' }),
            h('a', { class: 'btn btn-primary', href: '/dashboard', text: 'Go to dashboard' })));
          return;
        }
        list.replaceChildren(...data.items.map((r) => h('article', { class: 'card hist-card ' + r.planner_type },
          h('div', { class: 'hist-top' }, h('span', { class: 'chip chip-' + r.planner_type, text: PLANNER_LABEL[r.planner_type] || r.planner_type }), h('span', { text: fmtDate(r.created_at) })),
          h('h3', { text: r.title }), h('p', { class: 'hint', text: r.details }),
          h('div', { class: 'hist-money' },
            h('div', {}, h('small', { text: 'Total budget' }), h('strong', { text: inr(r.total_budget) })),
            h('div', {}, h('small', { text: 'Remaining' }), h('strong', { text: inr(r.remaining) }))),
          h('div', {}, r.source === 'gemini' ? h('span', { class: 'badge badge-gemini', text: 'Live AI' }) : h('span', { class: 'badge badge-demo', text: 'Sample data' })),
          h('a', { class: 'btn btn-primary btn-sm', href: '/history/' + r.id, text: 'View full details' }))));
      } catch (e) {
        list.replaceChildren(h('div', { class: 'alert alert-error', text: 'Could not load your history. Please refresh the page.' }));
      }
    };
    document.querySelectorAll('#history-filters .filter').forEach((b) => b.addEventListener('click', () => {
      document.querySelectorAll('#history-filters .filter').forEach((x) => x.classList.remove('active'));
      b.classList.add('active'); load(b.dataset.filter);
    }));
    load('');
  }

  // ---------- detail page ----------
  const detail = document.getElementById('rec-detail');
  if (detail) {
    (async () => {
      try {
        const resp = await fetch('/recommendations/' + encodeURIComponent(detail.dataset.recId), { credentials: 'same-origin' });
        if (resp.status === 401) { window.location.href = '/login'; return; }
        const data = await parseJson(resp);
        if (!resp.ok) throw new Error(data.detail || 'error');
        const rows = Object.entries(data.input).filter(([, v]) => v !== '' && v !== null && v !== undefined)
          .map(([k, v]) => h('tr', {}, h('td', { text: k.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()) }),
            h('td', { text: typeof v === 'boolean' ? (v ? 'Yes' : 'No') : (typeof v === 'number' && /budget/.test(k) ? inr(v) : String(v)) })));
        detail.replaceChildren(
          h('div', { class: 'detail-head' }, h('div', {}, h('span', { class: 'chip chip-' + data.planner_type, text: PLANNER_LABEL[data.planner_type] }), ' ', h('span', { class: 'hint', text: 'Created ' + fmtDate(data.created_at) })),
            h('a', { class: 'btn btn-ghost btn-sm', href: '/' + data.planner_type + '-planner', text: '+ New ' + data.planner_type + ' plan' })),
          h('div', { class: 'card', style: 'margin-bottom:18px' }, h('h3', { text: 'Your inputs' }),
            data.has_image ? h('img', { class: 'detail-img', src: '/recommendations/' + data.id + '/image', alt: 'Uploaded outfit image' }) : null,
            h('table', { class: 'inputs-table' }, h('tbody', {}, rows))),
          renderPlan(data.result));
      } catch (e) {
        detail.replaceChildren(h('div', { class: 'alert alert-error', text: 'Could not load this recommendation.' }));
      }
    })();
  }
})();
