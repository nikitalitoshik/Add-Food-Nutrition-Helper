(function() {
  /*
   File: nutrition/static/nutrition/js/progress.js
   Apraksts: Zīmē kaloriju diagrammu (Chart.js) lapā "progress".
   Kur atrodas: statiskajos JS failos un tiek iekļauts šablonos, kuriem nepieciešama diagramma.
   Mērķis: parādīt pēdējo 14 dienu kaloriju grafiku ar opciju mērķa līnijai.
   Atkarības: Chart.js pievienots globāli kā `Chart`.
   Piezīmes par drošību: dati var nākt kā JSON virknes dataset atribūtos, tāpēc izmanto `safeJsonParse`.
  */

  // Canvas elements — diagrammas konteineris
  const canvas = document.getElementById('calChart');
  if(!canvas){ console.warn('Chart canvas not found'); return; }

  // showNoData(message)
  // Ko dara: ja nav datu, paslēpj canvas un parāda vienkāršu vietturi ar paskaidrojumu.
  // Kāpēc: izvairās no tukšas/neskaidras diagrammas un lietotājam skaidri parāda, ka datu nav.
  function showNoData(message){
    const wrap = canvas.parentElement;
    canvas.style.display = 'none';
    const el = document.createElement('div');
    el.className = 'no-data-placeholder';
    el.style.padding = '2rem';
    el.style.color = '#666';
    el.style.fontSize = '1rem';
    el.textContent = message || 'No data available for chart';
    wrap.appendChild(el);
  }

  // safeJsonParse(str)
  // Ko dara: droši mēģina parsēt dažādos formātos iekļautu JSON virkni.
  // Kāpēc: daži šabloni/atribūti var iekļaut escapotu JSON vai kombinētus simbolus; šī funkcija mēģina
  // normalizēt un izvilkt derīgu masīvu. Atgriež tukšu masīvu, ja parsēšana neizdodas.
  function safeJsonParse(str){
    if(!str) return [];
    try { return JSON.parse(str); } catch(e){}
    try {
      let s = String(str).replace(/\\u0022/g, '"').replace(/\\n/g,'').replace(/\\r/g,'').replace(/\\"/g,'"').replace(/\\\\/g,'\\');
      return JSON.parse(s);
    } catch(err){
      try { const m = String(str).match(/\[.*\]/s); if(m && m[0]) return JSON.parse(m[0].replace(/\\u0022/g,'"')); } catch(_){}
      return [];
    }
  }

  let dates = safeJsonParse(canvas.getAttribute('data-dates') || canvas.dataset.dates || '[]');
  let calories = safeJsonParse(canvas.getAttribute('data-calories') || canvas.dataset.calories || '[]');

  // fetchFallback()
  // Ko dara: pieprasījums uz servera API, ja lokālie dati nav pieejami kā data-* atribūti.
  // Kāpēc: nodrošina, ka diagramma var aizpildīties arī tad, ja serveris padod datus asinhroni.
  async function fetchFallback(){
    const url = '/nutrition/api/daily_calories/?days=14';
    try {
      const res = await fetch(url, { credentials: 'same-origin' });
      if(!res.ok) return null;
      const json = await res.json();
      if(Array.isArray(json.dates) && Array.isArray(json.calories)) return json;
      return null;
    } catch (err){ return null; }
  }

  (async function initChart(){
    if((!dates || dates.length === 0) || (!calories || calories.length === 0)){
      const fallback = await fetchFallback();
      if(fallback){ dates = fallback.dates || []; calories = fallback.calories || []; }
    }

    if((!dates || dates.length === 0) && (!calories || calories.length === 0)){
      showNoData('No chart data for the last 14 days.');
      return;
    }

    // Normalize lengths and limit to last N points (14)
    const minLen = Math.min(dates.length || 0, calories.length || 0) || Math.max(dates.length, calories.length);
    const take = Math.min(minLen || Math.max(dates.length, calories.length), 14);
    if(minLen > 0){ dates = dates.slice(-take); calories = calories.slice(-take); }
    else if(dates.length && !calories.length){ dates = dates.slice(-take); calories = dates.map(_ => 0); }
    else if(calories.length && !dates.length){ calories = calories.slice(-take); dates = calories.map((_,i) => 'Day ' + (i+1)).slice(-take); }

    if(!dates.length || !calories.length){ showNoData('No chart data for the last 14 days.'); return; }

    // Destroy previous Chart instance if present to avoid duplicates
    try { if(window.calChartInstance && typeof window.calChartInstance.destroy === 'function') window.calChartInstance.destroy(); } catch(e){}

    const ctx = canvas.getContext('2d');
    // Ensure calories is numeric array
    calories = calories.map(v => { const n = Number(v); return isFinite(n) ? n : 0; });

    // Parse localized numeric string from data-rec attribute (user's recommendation/target)
    // Example: '2000' or '2 000' or '2,000' — normalize to JS Number.
    let recRaw = canvas.getAttribute('data-rec') || canvas.dataset.rec || '0';
    console.log('progress.js: raw data-rec=', recRaw);
    recRaw = String(recRaw).trim().replace(/\s/g, '').replace(/,/g, '.').replace(/[^0-9.\-]/g, '');
    let recTarget = Number(recRaw);
    if (!isFinite(recTarget)) recTarget = 0;
    console.log('progress.js: recTarget=', recTarget, 'parsed from', recRaw);

    // We'll draw the target as a dashed line dataset (easier for tooltip control than plugin)
    const datasets = [
      {
        label: 'Calories per day',
        data: calories,
        backgroundColor: 'rgba(76,175,80,0.7)',
        borderColor: 'rgba(76, 175, 80, 1)',
        borderWidth: 1,
        borderRadius: 4,
        type: 'bar'
      }
    ];

    if(recTarget > 0){
      // Flat array matching labels length
      const tData = (dates && dates.length) ? new Array(dates.length).fill(recTarget) : [];
      datasets.push({
        type: 'line',
        label: 'Target',
        data: tData,
        borderColor: 'rgba(33,150,83,0.9)', // site green
        borderWidth: 2,
        borderDash: [8,6],
        pointRadius: 0,
        fill: false,
        tension: 0,
        order: 2,
        yAxisID: 'y'
      });
    }

    // Create Chart.js instance
    window.calChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: dates,
        datasets: datasets
      },
      options: {
        responsive: false,
        maintainAspectRatio: false,
        animation: false,
        transitions: { active: false },
        devicePixelRatio: 1,
        scales: {
          y: { beginAtZero: true, ticks: { color: '#666' }, grid: { color: '#eee' } },
          x: { ticks: { color: '#666' }, grid: { color: '#eee' } }
        },
        plugins: {
          legend: { labels: { color: '#333', font: { size: 12 } } },
          tooltip: {
            // hide the target dataset from tooltips (so it doesn't interfere with bar hover)
            filter: function(tooltipItem){
              return tooltipItem.dataset && tooltipItem.dataset.label !== 'Target';
            },
            callbacks: { label: function(ctx){ return ctx.dataset.label + ': ' + ctx.formattedValue + ' kcal'; } }
          }
        }
      }
    });

    // debug: log chart extents (useful during development)
    console.log('progress.js: chart dates=', dates.length, 'calories=', calories.length, 'recTarget=', recTarget);

    // refreshChartFromApi()
    // Ko dara: ja dati tiek mainīti citā tabā, šo funkciju var izsaukt, lai pārlādētu datus no API
    // un atjauninātu Chart.js instanci. Tā izmanto `fetchFallback` un atjauno tikai datu masīvus.
    async function refreshChartFromApi(){
      try{
        const fallback = await fetchFallback();
        if(!fallback) { console.log('progress.js: refreshChartFromApi - no data from API'); return; }
        const newDates = Array.isArray(fallback.dates) ? fallback.dates : [];
        const newCalories = Array.isArray(fallback.calories) ? fallback.calories.map(v => { const n = Number(v); return isFinite(n) ? n : 0; }) : [];
        if(window.calChartInstance){
          window.calChartInstance.data.labels = newDates.slice(-14);
          window.calChartInstance.data.datasets[0].data = newCalories.slice(-14);
          window.calChartInstance.update();
          console.log('progress.js: chart refreshed from API');
        }
      }catch(e){ console.warn('progress.js: refreshChartFromApi error', e); }
    }

    // Listen for cross-tab notifications (localStorage key) to refresh chart when entries change elsewhere
    window.addEventListener('storage', function(e){
      if(!e) return;
      if(e.key === 'nutrition:entries-updated'){
        console.log('progress.js: storage event - entries updated, refreshing chart');
        refreshChartFromApi();
      }
    });

    // Also refresh when tab becomes visible (in case updates happened while hidden)
    document.addEventListener('visibilitychange', function(){ if(!document.hidden){ refreshChartFromApi(); } });

    // (plugin already registered above and options set; no further action required)
  })();

})();
