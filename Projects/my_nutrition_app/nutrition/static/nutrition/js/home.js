(function(){
  // rely on globals from common.js: parseLocaleNumber, csrfToken/csrfFromCookie, computeKcalFromMacros, fmt, escapeHtml, sleep
  const URLS = window.NUTRITION_URLS || {};

  // small helper: read numeric text or dataset fallback
  function _parseTextOrData(li, selector, dataKey){
    const el = li.querySelector(selector);
    if(el && el.textContent && String(el.textContent).trim() !== ''){
      return parseLocaleNumber(el.textContent);
    }
    return li.dataset && li.dataset[dataKey] ? parseLocaleNumber(li.dataset[dataKey]) : 0;
  }

  // --- addToTotals: update totals block and eat progress ---
  function addToTotals(delta){
    const calEl = document.getElementById('totCalories');
    const pEl = document.getElementById('totProtein');
    const fEl = document.getElementById('totFat');
    const cEl = document.getElementById('totCarbs');
    const curCal = parseLocaleNumber(calEl && calEl.textContent ? calEl.textContent : 0);
    const curP = parseLocaleNumber(pEl && pEl.textContent ? pEl.textContent : 0);
    const curF = parseLocaleNumber(fEl && fEl.textContent ? fEl.textContent : 0);
    const curC = parseLocaleNumber(cEl && cEl.textContent ? cEl.textContent : 0);
    if(calEl) calEl.textContent = fmt(curCal + (Number(delta.kcal)||0), 1);
    if(pEl) pEl.textContent = fmt(curP + (Number(delta.protein)||0), 1);
    if(fEl) fEl.textContent = fmt(curF + (Number(delta.fat)||0), 1);
    if(cEl) cEl.textContent = fmt(curC + (Number(delta.carbs)||0), 1);

    // update eatProgress if present
    const pWrap = document.getElementById('eatProgress');
    if(pWrap){
      const eaten = (parseFloat(pWrap.dataset.eaten)||0) + (Number(delta.kcal)||0);
      pWrap.dataset.eaten = eaten;
      const recRaw = pWrap.dataset.rec;
      const rec = recRaw !== '' ? parseFloat(recRaw) : null;
      if(rec && rec > 0){
        const pct = Math.round(Math.min(100, (eaten / rec) * 100));
        const bar = pWrap.querySelector('.eat-bar');
        const pctEl = document.getElementById('eatPercent');
        const vals = pWrap.querySelector('.eat-values');
        if(bar) bar.style.width = pct + '%';
        if(pctEl) pctEl.textContent = pct + '%';
        if(vals) vals.textContent = eaten.toFixed(0) + ' / ' + rec.toFixed(0) + ' kcal';
        // color thresholds
        if(bar){
          bar.classList.remove('progress-good','progress-warning','progress-over');
          if(pct < 80) bar.classList.add('progress-good');
          else if(pct <= 100) bar.classList.add('progress-warning');
          else bar.classList.add('progress-over');
        }
        const wrap = pWrap.querySelector('.eat-bar-wrap');
        if(wrap) wrap.setAttribute('aria-valuenow', String(pct));
        pWrap.setAttribute('aria-hidden','false');
      }
    }
  }
  // expose globally (other code expects window.addToTotals)
  window.addToTotals = addToTotals;

  // --- helpers to read entry numeric values ---
  function readEntryValues(li){
    const kcal = _parseTextOrData(li, '.entry-kcal', 'kcal');
    const protein = _parseTextOrData(li, '.entry-protein', 'protein');
    const fat = _parseTextOrData(li, '.entry-fat', 'fat');
    const carbs = _parseTextOrData(li, '.entry-carbs', 'carbs');
    return { kcal, protein, fat, carbs };
  }

  // hide edit form safely: if an input inside had focus, move focus to edit toggle (or blur)
  function hideEditForm(formWrap){
    if(!formWrap) return;
    try {
      const input = formWrap.querySelector('input[name="amount"]');
      // if input currently focused or contains focused element, move focus before hiding
      if(input && (document.activeElement === input || formWrap.contains(document.activeElement))){
        const li = formWrap.closest('li');
        const toggleBtn = li ? li.querySelector('[data-action="toggle-edit"], .sticker--edit') : null;
        if(toggleBtn && typeof toggleBtn.focus === 'function'){
          toggleBtn.focus();
        } else {
          // fallback: blur active element
          try { document.activeElement && document.activeElement.blur && document.activeElement.blur(); } catch(e){}
        }
      }
    } catch(e){
      console.debug('hideEditForm focus handling error', e);
    }
    // finally hide the form
    formWrap.classList.remove('visible');
    formWrap.setAttribute('aria-hidden','true');
    formWrap.style.display = 'none';
  }

  // apply authoritative server response to a list <li>
  function applyServerUpdateToListItem(li, data){
    if(!li || !data) return;
    try {
      // elements
      const amountEl = li.querySelector('.entry-amount-current');
      const kcalEl = li.querySelector('.entry-kcal');
      const pEl = li.querySelector('.entry-protein');
      const fEl = li.querySelector('.entry-fat');
      const cEl = li.querySelector('.entry-carbs');

      // read old values (prefer visible text, fallback to dataset)
      const oldK = parseLocaleNumber(kcalEl ? kcalEl.textContent : li.dataset.kcal || 0);
      const oldP = parseLocaleNumber(pEl ? pEl.textContent : li.dataset.protein || 0);
      const oldF = parseLocaleNumber(fEl ? fEl.textContent : li.dataset.fat || 0);
      const oldC = parseLocaleNumber(cEl ? cEl.textContent : li.dataset.carbs || 0);

      // server authoritative values (may be absent)
      const newAmount = (data.amount != null) ? Number(data.amount) : null;
      const newK = (data.kcal != null) ? Number(data.kcal) : null;
      const newP = (data.protein != null) ? Number(data.protein) : null;
      const newF = (data.fat != null) ? Number(data.fat) : null;
      const newC = (data.carbs != null) ? Number(data.carbs) : null;

      // update data-* attributes so future reads are consistent
      if(newK != null) li.dataset.kcal = Number(newK).toFixed(2);
      if(newP != null) li.dataset.protein = Number(newP).toFixed(2);
      if(newF != null) li.dataset.fat = Number(newF).toFixed(2);
      if(newC != null) li.dataset.carbs = Number(newC).toFixed(2);

      // update visible DOM
      if(amountEl && newAmount != null) amountEl.textContent = Number(newAmount).toFixed(1) + 'g';
      if(kcalEl && newK != null) kcalEl.textContent = Number(newK).toFixed(2);
      if(pEl && newP != null) pEl.textContent = Number(newP).toFixed(2);
      if(fEl && newF != null) fEl.textContent = Number(newF).toFixed(2);
      if(cEl && newC != null) cEl.textContent = Number(newC).toFixed(2);

      // compute deltas for totals: prefer server values, otherwise compute from visible fields
      const finalNewK = (newK != null) ? newK : parseLocaleNumber(kcalEl ? kcalEl.textContent : 0);
      const finalNewP = (newP != null) ? newP : parseLocaleNumber(pEl ? pEl.textContent : 0);
      const finalNewF = (newF != null) ? newF : parseLocaleNumber(fEl ? fEl.textContent : 0);
      const finalNewC = (newC != null) ? newC : parseLocaleNumber(cEl ? cEl.textContent : 0);

      if(typeof addToTotals === 'function'){
        addToTotals({
          kcal: Number(finalNewK) - Number(oldK || 0),
          protein: Number(finalNewP) - Number(oldP || 0),
          fat: Number(finalNewF) - Number(oldF || 0),
          carbs: Number(finalNewC) - Number(oldC || 0)
        });
      }

      // visual hint for user
      li.classList.add('entry-updated');
      setTimeout(()=> li.classList.remove('entry-updated'), 900);
    } catch (err){
      console.debug('applyServerUpdateToListItem error', err);
    }
  }

  // --- Add custom form preview + submit via API ---
  (function(){
    const nameEl = document.getElementById('customName');
    const kcalEl = document.getElementById('kcal100');
    const proteinEl = document.getElementById('protein100');
    const fatEl = document.getElementById('fat100');
    const carbsEl = document.getElementById('carbs100');
    const amountEl = document.getElementById('amountGr');
    const preview = document.getElementById('customPreview');
    const pvName = document.getElementById('pvName');
    const pvWeight = document.getElementById('pvWeight');
    const pvKcal = document.getElementById('pvKcal');
    const pvMacros = document.getElementById('pvMacros');
    const submitBtn = document.getElementById('submitCustom');
    const clearBtn = document.getElementById('clearCustom');
    const msg = document.getElementById('customMsg');

    if(!submitBtn) return;

    function updatePreview(){
      const name = (nameEl.value || '').trim();
      const amt = parseLocaleNumber(amountEl.value);
      const k100 = parseLocaleNumber(kcalEl.value);
      const p100 = parseLocaleNumber(proteinEl.value);
      const f100 = parseLocaleNumber(fatEl.value);
      const c100 = parseLocaleNumber(carbsEl.value);
      if(!name || !amt) { preview.style.display='none'; return; }
      const factor = amt/100;
      pvName.textContent = name;
      pvWeight.textContent = amt.toFixed(1) + ' g';
      pvKcal.innerHTML = '<strong>' + (k100*factor).toFixed(2) + '</strong> kcal';
      pvMacros.textContent = (p100*factor).toFixed(2) + ' g protein • ' + (f100*factor).toFixed(2) + ' g fat • ' + (c100*factor).toFixed(2) + ' g carbs';
      preview.style.display = 'block';
    }

    [nameEl,kcalEl,proteinEl,fatEl,carbsEl,amountEl].forEach(el=> el && el.addEventListener && el.addEventListener('input', updatePreview));
    clearBtn && clearBtn.addEventListener('click', ()=>{ nameEl.value=''; kcalEl.value=''; proteinEl.value=''; fatEl.value=''; carbsEl.value=''; amountEl.value='100'; preview.style.display='none'; msg.textContent=''; });

    submitBtn.addEventListener('click', async function(){
      msg.textContent = '';
      const name = (nameEl.value || '').trim();
      const amt = parseLocaleNumber(amountEl.value);
      if(!name){ msg.textContent = 'Enter product name'; return; }
      if(!amt || amt <= 0){ msg.textContent = 'Enter valid amount'; return; }
      const kcal = parseLocaleNumber(kcalEl.value);
      const protein = parseLocaleNumber(proteinEl.value);
      const fat = parseLocaleNumber(fatEl.value);
      const carbs = parseLocaleNumber(carbsEl.value);
      if(kcal === 0 && protein === 0 && fat === 0 && carbs === 0){
        if(!confirm('All nutrient fields are zero. Continue?')) return;
      }

      const kcal_per100 = (kcal && kcal > 0) ? kcal : computeKcalFromMacros(protein, fat, carbs, 100);
      const kcal_value = Number((kcal_per100 * amt / 100).toFixed(3));
      const payload = {
        name: name,
        amount: amt,
        kcal: kcal_value,
        protein: Number(((protein||0) * amt / 100).toFixed(3)),
        fat: Number(((fat||0) * amt / 100).toFixed(3)),
        carbs: Number(((carbs||0) * amt / 100).toFixed(3)),
        kcal_per100: Number(kcal_per100.toFixed(3)),
        kcal_per_entry: kcal_value
      };

      try {
        const resp = await fetch(URLS.api_add_entry || '/nutrition/api/add-entry/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': (window.csrfToken || window.csrfFromCookie || window.getCsrfFromCookie || (()=>''))() },
          credentials: 'same-origin',
          body: JSON.stringify(payload)
        });
        if(resp.status === 401 || resp.status === 403){
          msg.textContent = 'Please log in to save entries.';
          return;
        }
        if(!resp.ok){
          const ct = resp.headers.get('content-type') || '';
          if(ct.includes('application/json')){
            const err = await resp.json();
            msg.textContent = (err && (err.error || err.message)) ? String(err.error || err.message) : 'Add failed';
          } else {
            msg.textContent = 'Add failed (server)';
          }
          return;
        }
        const data = await resp.json().catch(()=>null);
        if(data && data.success){ location.reload(); return; }
        location.reload();
      } catch (err){
        console.error('Add custom request failed', err);
        msg.textContent = 'Network error, try again.';
      }
    });
  })();

  // --- API search / barcode lookup / render results ---
  (function(){
    const apiSearchBtn = document.getElementById('apiSearchBtn');
    const apiSearchInput = document.getElementById('apiSearchInput');
    const apiBarcodeBtn = document.getElementById('apiBarcodeBtn');
    const apiBarcodeInput = document.getElementById('apiBarcodeInput');
    const apiResults = document.getElementById('apiResults');
    if(!apiResults) return;

    function showMessage(msg, type){ apiResults.innerHTML = `<div class="${type==='error'?'error':'success'}" style="padding:0.75rem; border-radius:6px;">${escapeHtml(msg)}</div>`; }

    async function searchProducts(q){
      const url = (URLS.api_product_search || '/nutrition/api/product-search/') + '?q=' + encodeURIComponent(q);
      apiResults.innerHTML = '<p style="color:#666;">Searching...</p>';
      try {
        const res = await fetch(url, { method: 'GET', headers:{ 'Accept':'application/json' }, credentials: 'same-origin' });
        const text = await res.text();
        const json = text ? JSON.parse(text) : null;
        if(!res.ok){ showMessage('Search failed, try again.', 'error'); return; }
        const results = (json && json.results) ? json.results : [];
        if(!results.length){ apiResults.innerHTML = '<p style="color:#666;">No results.</p>'; return; }
        renderResults(results);
      } catch(e){ console.warn('searchProducts error', e); showMessage('External database error. Try again or add product manually.', 'error'); }
    }

    function renderResults(items){
      apiResults.innerHTML = '';
      const list = document.createElement('div');
      list.style.display = 'grid'; list.style.gridTemplateColumns = 'repeat(auto-fit,minmax(220px,1fr))'; list.style.gap = '0.75rem';
      items.forEach(it=>{
        const card = document.createElement('div'); card.className = 'card';
        try { card.dataset.item = JSON.stringify(it); } catch(_){}
        const kcal100 = (parseLocaleNumber(it.kcal) || computeKcalFromMacros(it.protein, it.fat, it.carbs, 100) || 0);
        const prot100 = parseLocaleNumber(it.protein) || 0;
        const fat100 = parseLocaleNumber(it.fat) || 0;
        const carbs100 = parseLocaleNumber(it.carbs) || 0;
        card.innerHTML = `
          <strong style="display:block; margin-bottom:0.5rem;">${escapeHtml(it.name || '(unnamed)')}</strong>
          <div style="font-size:0.95rem; color:#444;">
            <div>Calories: <b>${Number(kcal100||0).toFixed(1)}</b> kcal/100g</div>
            <div>Protein: <b>${Number(prot100).toFixed(1)}</b> g/100g</div>
            <div>Fat: <b>${Number(fat100).toFixed(1)}</b> g/100g</div>
            <div>Carbs: <b>${Number(carbs100).toFixed(1)}</b> g/100g</div>
          </div>
          <div style="margin-top:0.75rem; display:flex; gap:0.5rem; align-items:center;">
            <input type="text" inputmode="decimal" value="100" class="amount-input" style="width:110px; padding:0.4rem; border-radius:6px; border:1px solid var(--border-color);">
            <button class="btn btn-primary add-api-btn">Add from API</button>
          </div>
        `;
        const amountInput = card.querySelector('.amount-input');
        const btn = card.querySelector('.add-api-btn');
        btn.addEventListener('click', async function(){
          const amount = parseLocaleNumber(amountInput.value);
          if(amount <= 0){ alert('Enter a positive amount (grams)'); return; }
          let original = it;
          if(card.dataset.item){ try { original = JSON.parse(card.dataset.item); } catch(e){} }
          const kcal_per100 = (parseLocaleNumber(original.kcal) || computeKcalFromMacros(original.protein, original.fat, original.carbs, 100) || 0);
          const protein_per100 = parseLocaleNumber(original.protein) || 0;
          const fat_per100 = parseLocaleNumber(original.fat) || 0;
          const carbs_per100 = parseLocaleNumber(original.carbs) || 0;
          const kcal_value = (kcal_per100 * amount / 100) || 0;
          const payload = {
            name: (original.name || '').trim(),
            kcal: Number(kcal_value.toFixed(3)),
            protein: Number(((protein_per100 * amount / 100)||0).toFixed(3)),
            fat: Number(((fat_per100 * amount / 100)||0).toFixed(3)),
            carbs: Number(((carbs_per100 * amount / 100)||0).toFixed(3)),
            amount: amount,
            kcal_per100: Number(kcal_per100.toFixed(3)),
            kcal_per_entry: Number(kcal_value.toFixed(3))
          };
          try {
            const resp = await fetch(URLS.api_add_entry || '/nutrition/api/add-entry/', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': (window.csrfToken || window.csrfFromCookie || window.getCsrfFromCookie || (()=>''))() },
              credentials: 'same-origin',
              body: JSON.stringify(payload)
            });
            if(!resp.ok){ alert('Add failed'); return; }
            const data = await resp.json().catch(()=>null);
            if(data && data.success) location.reload(); else alert('Add failed');
          } catch(e){ console.error('add entry error', e); alert('Network error, try again.'); }
        });
        list.appendChild(card);
      });
      apiResults.appendChild(list);
    }

    // events
    apiSearchBtn && apiSearchBtn.addEventListener('click', function(e){ e.preventDefault(); const q = apiSearchInput.value.trim(); if(q) searchProducts(q); });
    apiSearchInput && apiSearchInput.addEventListener('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); apiSearchBtn && apiSearchBtn.click(); } });
    apiBarcodeBtn && apiBarcodeBtn.addEventListener('click', function(e){ e.preventDefault(); const code = apiBarcodeInput.value.trim(); if(code) lookupBarcode(code); });
    apiBarcodeInput && apiBarcodeInput.addEventListener('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); apiBarcodeBtn && apiBarcodeBtn.click(); } });

    async function lookupBarcode(code){
      const url = (URLS.api_product_lookup || '/nutrition/api/product-lookup/') + '?barcode=' + encodeURIComponent(code);
      apiResults.innerHTML = '<p style="color:#666;">Looking up barcode...</p>';
      try {
        const res = await fetch(url, { method:'GET', headers:{ 'Accept':'application/json' }, credentials:'same-origin' });
        const text = await res.text();
        const json = text ? JSON.parse(text) : null;
        if(!res.ok){ if(res.status === 404) showMessage('Product not found for this barcode.', 'error'); else showMessage('Lookup failed, try again.', 'error'); return; }
        const result = json && (json.result || json.item || json.data) ? (json.result || json.item || json.data) : json;
        if(result) renderResults([result]); else showMessage('Product not found for this barcode.', 'error');
      } catch (e){ console.error('lookupBarcode error', e); showMessage('Lookup failed, try again.', 'error'); }
    }
  })();

  // --- sticker actions (toggle edit / delete) and inline edit submit handling ---
  (function(){
    function readEntryValues(li){
      const kcal = _parseTextOrData(li, '.entry-kcal', 'kcal');
      const protein = _parseTextOrData(li, '.entry-protein', 'protein');
      const fat = _parseTextOrData(li, '.entry-fat', 'fat');
      const carbs = _parseTextOrData(li, '.entry-carbs', 'carbs');
      return { kcal, protein, fat, carbs };
    }

    document.addEventListener('click', function(e){
      const btn = e.target.closest('button, [data-action]');
      if(!btn) return;
      const actionEl = btn.closest('[data-action]') || btn;
      const action = actionEl ? actionEl.getAttribute('data-action') : btn.getAttribute('data-action');

      if(action === 'cancel-edit'){
        const formWrap = btn.closest('.entry-edit-form');
        if(formWrap){ hideEditForm(formWrap); }
        return;
      }

      const li = btn.closest('li');
      if(!li) return;

      if(action === 'toggle-edit'){
        const formWrap = li.querySelector('.entry-edit-form');
        if(!formWrap) return;
        const visible = formWrap.classList.toggle('visible');
        if(visible){
          formWrap.setAttribute('aria-hidden','false');
          formWrap.style.display = 'block';
          const input = formWrap.querySelector('input[name="amount"]');
          if(input){ input.focus(); input.select(); }
        } else {
          // hide safely (moves focus away if needed)
          hideEditForm(formWrap);
        }
        return;
      }

      if(action === 'delete'){
        if(!confirm('Are you sure you want to delete this entry?')) return;
        const vals = readEntryValues(li);
        const entryId = li.dataset.entryId || '';
        const delForm = entryId ? document.getElementById('delete-form-' + entryId) : li.querySelector('form[id^="delete-form-"]');

        if(delForm){
          const actionUrl = delForm.action;
          fetch(actionUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': (window.csrfToken || window.csrfFromCookie || window.getCsrfFromCookie || (()=>''))() },
            body: JSON.stringify({})
          }).then(async resp=>{
            const ct = resp.headers.get('content-type') || '';
            if(ct.includes('application/json')){
              const data = await resp.json();
              if(data && data.success){
                if(typeof addToTotals === 'function') addToTotals({ kcal: -vals.kcal, protein: -vals.protein, fat: -vals.fat, carbs: -vals.carbs });
                li.remove();
              } else alert(data && data.error ? data.error : 'Delete failed');
              return;
            }
            if(resp.ok){
              if(typeof addToTotals === 'function') addToTotals({ kcal: -vals.kcal, protein: -vals.protein, fat: -vals.fat, carbs: -vals.carbs });
              li.remove();
            } else {
              const t = await resp.text(); console.error('Delete failed:', t); alert('Delete failed (server)');
            }
          }).catch(err=>{ console.error('Delete request failed', err); alert('Network error, try again.'); });
          return;
        }

        if(typeof addToTotals === 'function') addToTotals({ kcal: -vals.kcal, protein: -vals.protein, fat: -vals.fat, carbs: -vals.carbs });
        li.remove();
        return;
      }
    });

    document.addEventListener('submit', async function(e){
      const form = e.target;
      if(!form.classList || !form.classList.contains('edit-form-inline')) return;
      e.preventDefault();
      const li = form.closest('li');
      if(!li) return;
      const amountInput = form.querySelector('input[name="amount"]');
      const newAmount = parseLocaleNumber(amountInput && amountInput.value ? amountInput.value : 0);
      if(!newAmount || newAmount <= 0){ alert('Enter valid amount'); return; }

      const oldAmountEl = li.querySelector('.entry-amount-current');
      const oldAmount = parseLocaleNumber(oldAmountEl ? oldAmountEl.textContent.replace('g','') : newAmount);

      const kcalEl = li.querySelector('.entry-kcal');
      const pEl = li.querySelector('.entry-protein');
      const fEl = li.querySelector('.entry-fat');
      const cEl = li.querySelector('.entry-carbs');

      const oldKcal = parseLocaleNumber(kcalEl?.textContent || 0);
      const oldP = parseLocaleNumber(pEl?.textContent || 0);
      const oldF = parseLocaleNumber(fEl?.textContent || 0);
      const oldC = parseLocaleNumber(cEl?.textContent || 0);

      const factorOld = oldAmount / 100 || 1;
      const per100 = {
        kcal: factorOld ? (oldKcal / factorOld) : 0,
        protein: factorOld ? (oldP / factorOld) : 0,
        fat: factorOld ? (oldF / factorOld) : 0,
        carbs: factorOld ? (oldC / factorOld) : 0,
      };

      const newKcal = per100.kcal * (newAmount/100);
      const newP = per100.protein * (newAmount/100);
      const newF = per100.fat * (newAmount/100);
      const newC = per100.carbs * (newAmount/100);

      const action = form.getAttribute('action') || '';
      if(action && action.trim() !== ''){
        fetch(action, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': (window.csrfToken || window.csrfFromCookie || window.getCsrfFromCookie || (()=>''))() },
          body: JSON.stringify({ amount: newAmount })
        }).then(async resp=>{
          const ct = resp.headers.get('content-type') || '';
          if(ct.includes('application/json')){
            const data = await resp.json();
            if(data && data.success){
              // Use server-provided authoritative values to update the list row and totals atomically
              if(typeof applyServerUpdateToListItem === 'function'){
                applyServerUpdateToListItem(li, data);
              } else {
                // fallback: partial update
                const oldAmountEl = li.querySelector('.entry-amount-current');
                const kcalEl = li.querySelector('.entry-kcal');
                const pEl = li.querySelector('.entry-protein');
                const fEl = li.querySelector('.entry-fat');
                const cEl = li.querySelector('.entry-carbs');
                if(oldAmountEl && data.amount != null) oldAmountEl.textContent = Number(data.amount).toFixed(1) + 'g';
                if(kcalEl && data.kcal != null) kcalEl.textContent = Number(data.kcal).toFixed(2);
                if(pEl && data.protein != null) pEl.textContent = Number(data.protein).toFixed(2);
                if(fEl && data.fat != null) fEl.textContent = Number(data.fat).toFixed(2);
                if(cEl && data.carbs != null) cEl.textContent = Number(data.carbs).toFixed(2);
              }
              const formWrap = form.closest('.entry-edit-form');
              if(formWrap){ hideEditForm(formWrap); }
              return;
            } else {
               alert((data && (data.error || data.message)) ? (data.error || data.message) : 'Edit failed');
               return;
            }
          }
          if(resp.ok){
            // fallback to previous behavior (server did not return JSON)
            if(oldAmountEl) oldAmountEl.textContent = newAmount.toFixed(1) + 'g';
            if(kcalEl) kcalEl.textContent = newKcal.toFixed(2);
            if(pEl) pEl.textContent = newP.toFixed(2);
            if(fEl) fEl.textContent = newF.toFixed(2);
            if(cEl) cEl.textContent = newC.toFixed(2);
            if(typeof addToTotals === 'function'){
              addToTotals({ kcal: newKcal - oldKcal, protein: newP - oldP, fat: newF - oldF, carbs: newC - oldC });
            }
            const formWrap = form.closest('.entry-edit-form');
            if(formWrap){ hideEditForm(formWrap); }
          } else {
            const t = await resp.text(); console.error('Edit failed', t); alert('Edit failed');
          }
        }).catch(err=>{ console.error('Edit request failed', err); alert('Network error, try again.'); });
        return;
      }

      // local-only update
      if(oldAmountEl) oldAmountEl.textContent = newAmount.toFixed(1) + 'g';
      if(kcalEl) kcalEl.textContent = newKcal.toFixed(2);
      if(pEl) pEl.textContent = newP.toFixed(2);
      if(fEl) fEl.textContent = newF.toFixed(2);
      if(cEl) cEl.textContent = newC.toFixed(2);
      if(typeof addToTotals === 'function'){
        addToTotals({ kcal: newKcal - oldKcal, protein: newP - oldP, fat: newF - oldF, carbs: newC - oldC });
      }
      const formWrap = form.closest('.entry-edit-form');
      if(formWrap){ hideEditForm(formWrap); }
    });
  })();

  // init eat progress on load (ensure visible and show zeros when recommendation missing)
  function initEatProgress(){
    try {
      const p = document.getElementById('eatProgress');
      if(!p) return;
      const eaten = parseFloat(p.dataset.eaten) || 0;
      const recRaw = p.dataset.rec;
      const rec = recRaw !== '' ? parseFloat(recRaw) : 0;
      const pct = (rec && rec > 0) ? Math.round(Math.min(100, (eaten / rec) * 100)) : 0;
      const bar = p.querySelector('.eat-bar');
      const pctEl = document.getElementById('eatPercent');
      const vals = p.querySelector('.eat-values');
      if(bar) bar.style.width = pct + '%';
      if(pctEl) pctEl.textContent = pct + '%';
      if(vals) {
        vals.textContent = (rec && rec > 0) ? eaten.toFixed(0) + ' / ' + rec.toFixed(0) + ' kcal' : (eaten ? eaten.toFixed(0) + ' / 0 kcal' : '0 / 0 kcal');
      }
      if(bar){
        bar.classList.remove('progress-good','progress-warning','progress-over');
        if(rec && rec > 0){
          if(pct < 80) bar.classList.add('progress-good');
          else if(pct <= 100) bar.classList.add('progress-warning');
          else bar.classList.add('progress-over');
        } else {
          bar.classList.add('progress-good');
        }
      }
      const wrap = p.querySelector('.eat-bar-wrap');
      if(wrap) wrap.setAttribute('aria-valuenow', String(pct));
      p.setAttribute('aria-hidden','false');
      p.style.display = '';
    } catch (e) {
      console.debug('initEatProgress error', e);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEatProgress);
  } else {
    initEatProgress();
  }
 
  // end of file
})();
