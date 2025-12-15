(function(window){
	// ...common helpers for templates...
	const NH = window.NH = window.NH || {};

	NH.parseLocaleNumber = function(v){
		if(v === null || v === undefined) return 0;
		const s = String(v).trim().replace(/\s+/g,'').replace(',', '.');
		const n = parseFloat(s);
		return isNaN(n) ? 0 : n;
	};

	NH.getCsrfFromCookie = function() {
		const name = 'csrftoken=';
		const c = document.cookie.split(';').map(s=>s.trim()).find(s=>s.startsWith(name));
		return c ? decodeURIComponent(c.split('=')[1]) : '';
	};

	// alias for existing templates that expect csrfFromCookie or csrfToken()
	NH.csrfFromCookie = NH.getCsrfFromCookie;
	NH.csrfToken = NH.getCsrfFromCookie;

	NH.computeKcalFromMacros = function(p, f, c, amt){
		p = Number(p)||0; f = Number(f)||0; c = Number(c)||0; amt = Number(amt)||100;
		return (p * 4 + f * 9 + c * 4) * (amt / 100);
	};

	NH.fmt = function(n, dp){ return (isFinite(n) ? Number(n) : 0).toFixed(dp); };

	NH.escapeHtml = function(s){ return String(s).replace(/[&<>"']/g, (m)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); };

	NH.sleep = function(ms){ return new Promise(res => setTimeout(res, ms)); };

	// expose short global names for backward compatibility with existing inline scripts
	window.parseLocaleNumber = NH.parseLocaleNumber;
	window.getCsrfFromCookie = NH.getCsrfFromCookie;
	window.csrfFromCookie = NH.csrfFromCookie;
	window.csrfToken = NH.csrfToken;
	window.computeKcalFromMacros = NH.computeKcalFromMacros;
	window.fmt = NH.fmt;
	window.escapeHtml = NH.escapeHtml;
	window.sleep = NH.sleep;

})(window);
