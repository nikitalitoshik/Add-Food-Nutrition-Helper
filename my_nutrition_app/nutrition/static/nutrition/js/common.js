/*
 File: nutrition/static/nutrition/js/common.js
 Apraksts: Bieži lietotas utilītfunkcijas, ko izmanto HTML šabloni aplikācijā `nutrition`.
 Kur atrodas: statiskajos failos — tiek iekļauts šablonos caur Django static.
 Mērķis: piedāvāt drošus un atpakaļsaderīgus rīkus (skaitļu parsēšana, CSRF saņemšana,
		  kaloriju aprēķini u.c.).
 
*/

(function(window){
	// Namespace `NH` — centrāla vieta utilītfunkcijām, atstāj `window.NH` ja jau eksistē.
	// Kurš to izmanto: inline skripti šablonos, kā arī citi statiskie JS faili.
	const NH = window.NH = window.NH || {};

	// parseLocaleNumber(v)
	// Ko dara: pieņem virkni vai skaitli, kas var saturēt tūkstošu atdalītājus (tukšumu)
	//          vai komatu kā decimāldaļu atdalītāju, un atgriež JavaScript skaitli (float).
	// Kāpēc vajadzīgs: lietotāja ievade var būt lokalizēta (piem., "1 234,56"),
	//                  tāpēc nepieciešama robusta parsēšana pirms matemātiskām operācijām.
	// Kur izmantot: formas, AJAX apstrāde, aprēķini klienta pusē.
	NH.parseLocaleNumber = function(v){
		if(v === null || v === undefined) return 0;
		// Noņem atstarpes, aizstāj komatu ar punktu un mēģina parseFloat.
		const s = String(v).trim().replace(/\s+/g,'').replace(',', '.');
		const n = parseFloat(s);
		return isNaN(n) ? 0 : n;
	};

	// getCsrfFromCookie()
	// Ko dara: nolasa sīkfailu ar nosaukumu `csrftoken` (Django noklusējuma CSRF sīkfails)
	// Kāpēc vajadzīgs: AJAX pieprasījumiem nepieciešams CSRF tokens, ja tiek veikts POST.
	// Kur izmantot: visi skripti, kas veic fetch/XHR uz serveri bez formas submit.
	NH.getCsrfFromCookie = function() {
		const name = 'csrftoken=';
		const c = document.cookie.split(';').map(s=>s.trim()).find(s=>s.startsWith(name));
		return c ? decodeURIComponent(c.split('=')[1]) : '';
	};

	// Alias funkcijas — lai saglabātu atpakaļsaderību ar vecākiem šabloniem.
	// Dažos šablonos tiek gaidīts `csrfFromCookie()` vai `csrfToken()`; tie tagad norāda uz to pašu funkciju.
	NH.csrfFromCookie = NH.getCsrfFromCookie;
	NH.csrfToken = NH.getCsrfFromCookie;

	// computeKcalFromMacros(p, f, c, amt)
	// Ko dara: aprēķina kalorijas no makroelementiem (proteīni, tauki, ogļhidrāti).
	// Parametri: p - proteīns (g uz 100g), f - tauki (g uz 100g), c - ogļhidrāti (g uz 100g),
	//           amt - daudzums gramos (noklusēti 100, tātad aprēķins par 100g vai citur norādītu daudzumu).
	// Formula: proteīns*4 + tauki*9 + ogļhidrāti*4, reizināts ar (amt/100).
	// Kur nepieciešams: uztura kalkulators, ātrs klienta puses atgriezeniskās saites rādīšanai.
	NH.computeKcalFromMacros = function(p, f, c, amt){
		p = Number(p)||0; f = Number(f)||0; c = Number(c)||0; amt = Number(amt)||100;
		return (p * 4 + f * 9 + c * 4) * (amt / 100);
	};

	// fmt(n, dp)
	// Ko dara: formatē skaitli ar dotajām decimāldaļām (dp). Ja nav skaitlis, atgriež 0 ar dp.
	// Kāpēc vajadzīgs: vienkāršs utilīts lai parādītu konsistentu skaitļu formatējumu UI.
	NH.fmt = function(n, dp){ return (isFinite(n) ? Number(n) : 0).toFixed(dp); };

	// escapeHtml(s)
	// Ko dara: aizvieto bīstamas HTML zīmes ar to HTML entītijām, lai novērstu XSS,
	// Kur izmantot: ja dinamiska satura ievietošana HTML bez React/templating drošības slāņa.
	NH.escapeHtml = function(s){ return String(s).replace(/[&<>"']/g, (m)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); };

	// sleep(ms)
	// Ko dara: vienkāršs Promise bāzēts kavētājs — noderīgi asinhronos testos vai UX pauzēm.
	NH.sleep = function(ms){ return new Promise(res => setTimeout(res, ms)); };

	// Globālā ekspozīcija — daudzi esoši inline skripti sagaida šīs īsās funkciju nosaukumu versijas.
	// Tāpēc mēs pievienojam tās arī `window.*` līmenī, lai izvairītos no regresijām.
	window.parseLocaleNumber = NH.parseLocaleNumber;
	window.getCsrfFromCookie = NH.getCsrfFromCookie;
	window.csrfFromCookie = NH.csrfFromCookie;
	window.csrfToken = NH.csrfToken;
	window.computeKcalFromMacros = NH.computeKcalFromMacros;
	window.fmt = NH.fmt;
	window.escapeHtml = NH.escapeHtml;
	window.sleep = NH.sleep;

})(window);
