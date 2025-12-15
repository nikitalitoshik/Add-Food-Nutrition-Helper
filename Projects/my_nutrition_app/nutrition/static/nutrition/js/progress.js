(function() {
  const canvas = document.getElementById('calChart');
  if(!canvas){ console.warn('Chart canvas not found'); return; }

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

    const minLen = Math.min(dates.length || 0, calories.length || 0) || Math.max(dates.length, calories.length);
    const take = Math.min(minLen || Math.max(dates.length, calories.length), 14);
    if(minLen > 0){ dates = dates.slice(-take); calories = calories.slice(-take); }
    else if(dates.length && !calories.length){ dates = dates.slice(-take); calories = dates.map(_ => 0); }
    else if(calories.length && !dates.length){ calories = calories.slice(-take); dates = calories.map((_,i) => 'Day ' + (i+1)).slice(-take); }

    if(!dates.length || !calories.length){ showNoData('No chart data for the last 14 days.'); return; }

    try { if(window.calChartInstance && typeof window.calChartInstance.destroy === 'function') window.calChartInstance.destroy(); } catch(e){}

    const ctx = canvas.getContext('2d');
    calories = calories.map(v => { const n = Number(v); return isFinite(n) ? n : 0; });

    window.calChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: dates,
        datasets: [{
          label: 'Calories per day',
          data: calories,
          backgroundColor: function(context){
            const v = context.dataset.data[context.dataIndex] || 0;
            return v > 2500 ? 'rgba(255,99,71,0.85)' : 'rgba(76,175,80,0.7)';
          },
          borderColor: 'rgba(76, 175, 80, 1)',
          borderWidth: 1,
          borderRadius: 4
        }]
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
          tooltip: { callbacks: { label: function(ctx){ return ctx.dataset.label + ': ' + ctx.formattedValue + ' kcal'; } } }
        }
      }
    });
  })();

})();
