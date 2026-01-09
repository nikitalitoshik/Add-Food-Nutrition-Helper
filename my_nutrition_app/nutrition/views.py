from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Product, FoodEntry, Profile, Entry
from .forms import FoodEntryForm, ProfileForm, ProductForm, SignUpForm
import json
import requests
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _
import datetime as dt

logger = logging.getLogger(__name__)


def _compute_totals(entries):
    # Aprēķina summas sarakstam ar ierakstiem `entries`.
    # Sagaida, ka katram ierakstam var izsaukt metodes: calories(), protein(), fat(), carbs().
    totals = {'calories': 0.0, 'protein': 0.0, 'fat': 0.0, 'carbs': 0.0}
    for e in entries:
        # Katrā iterācijā pieskaita katra ieraksta vērtības
        totals['calories'] += e.calories()
        totals['protein'] += e.protein()
        totals['fat'] += e.fat()
        totals['carbs'] += e.carbs()

    # Noapaļo rezultātus divām zīmēm pēc komata pirms atgriešanas
    for k in totals:
        totals[k] = round(totals[k], 2)
    return totals


def _compute_recommendation(profile):
    """
    Aprēķina bāzes metabolisma (BMR), TDEE un vienkāršu ieteikumu dienas kalorijām
    un makro vielu sadalījumu.

    Ievads:
      `profile` - vārdnīca ar atslēgām: 'age','sex','weight','height','activity_level','goal'

    Atgriež vārdnīcu ar atslēgām 'bmr','tdee','recommended_kcal','protein_g','fat_g','carbs_g'.
    """
    age = profile['age']
    sex = profile['sex']
    weight = profile['weight']
    height = profile['height']
    activity = float(profile['activity_level'])
    goal = profile['goal']

    # Mifflin–St Jeor formula BMR aprēķinam: atšķiras pēc dzimuma
    if sex == 'M':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # TDEE = BMR reizināts ar aktivitātes koeficientu
    tdee = bmr * activity

    # Mērķa korekcija kalorijām: zaudēt (-500), saglabāt (0), pieņemties (+500)
    adj = {'lose': -500, 'maintain': 0, 'gain': 500}[goal]
    recommended = tdee + adj

    # Vienkāršs makro aprēķins: proteīns pēc ķermeņa masas, tauki 25% no kcal, pārējais - ogļhidrāti
    protein_g = round(1.6 * weight, 1)  # grami proteīna uz kg
    protein_cal = protein_g * 4
    fat_cal = 0.25 * recommended
    fat_g = round(fat_cal / 9, 1)
    carbs_cal = recommended - protein_cal - fat_cal
    carbs_g = round(max(carbs_cal, 0) / 4, 1)
    return {
        'bmr': round(bmr, 1),
        'tdee': round(tdee, 1),
        'recommended_kcal': round(recommended, 1),
        'protein_g': protein_g,
        'fat_g': fat_g,
        'carbs_g': carbs_g,
    }


def _per_g_from_entry(ce, field_name):
    """
    Atgriež vienības vērtību (piem., kcal/proteīns/fat/carbs) uz 1 gramu no Entry objekta `ce`.

    Prioritāte:
      1) ja ir <field_name>_per100 > 0, izmanto to (dalīts ar 100),
      2) citādi, ja ir `amount` un <field_name> vērtība — dalīt ar `amount`,
      3) ja neizdodas, atgriež 0.0.
    """
    try:
        per100_attr = getattr(ce, f"{field_name}_per100", None)
        if per100_attr and float(per100_attr) > 0:
            return float(per100_attr) / 100.0
        val = float(getattr(ce, field_name) or 0.0)
        amt = float(getattr(ce, 'amount') or 0.0)
        if amt > 0 and val:
            return val / amt
    except Exception:
        # Drošības nolūkos, ja kaut kas neparedzēts, atgriež 0.0
        pass
    return 0.0


def home(request):
    """
    Galvenā mājas lapa, kas apstrādā šādas darbības:
    - POST pieprasījums ar `FoodEntryForm` (pievieno jaunu pārtikas ierakstu),
    - sagatavo sarakstu ar šodienas ierakstiem (FoodEntry un Entry),
    - aprēķina totals un rekomendācijas (ja pieejams `Profile`).

    Šo skatu var redzēt mājas šablonā `nutrition/home.html`.
    """
    if request.method == 'POST':
        form = FoodEntryForm(request.POST)
        if form.is_valid():
            # Sagatavo argumentus jaunam FoodEntry objektam no formas
            fe_kwargs = {
                'product': form.cleaned_data['product'],
                'amount': form.cleaned_data['amount'],
                'initial_amount': form.cleaned_data['amount'],
            }
            if request.user.is_authenticated:
                # Ja lietotājs pieslēdzies, sasaista ierakstu ar šo lietotāju
                fe_kwargs['user'] = request.user
            FoodEntry.objects.create(**fe_kwargs)
            return redirect('nutrition:home')
    else:
        # GET pieprasījums — izveido tukšu formu
        form = FoodEntryForm()

    products = Product.objects.all()  # visu produktu saraksts, izmanto front-end izvēlnei
    today = timezone.now().date()

    # Build datetime range for "today" in aware timezone
    start_dt = timezone.make_aware(dt.datetime.combine(today, dt.time.min))
    end_dt = timezone.make_aware(dt.datetime.combine(today, dt.time.max))

    # Nokopē FoodEntry vai Entry, atkarībā no tā, vai lietotājs ir pieslēdzies
    if request.user.is_authenticated:
        qs_food = FoodEntry.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt, user=request.user)
        qs_entry = Entry.objects.filter(user=request.user, created_at__gte=start_dt, created_at__lte=end_dt)
    else:
        # anonīmi lietotāji redz publiskos ierakstus (user is null)
        qs_food = FoodEntry.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt, user__isnull=True)
        qs_entry = Entry.objects.none()

    # Apvieno abus ierakstu tipus vienā sarakstā, sagatavojot datus priekš šablona
    combined_entries = []
    totals = {'calories': 0.0, 'protein': 0.0, 'fat': 0.0, 'carbs': 0.0}

    for fe in qs_food:
        # drošības pārbaude: ja objekts satur metodes, izmanto tās
        kcal = fe.calories() if callable(getattr(fe, 'calories', None)) else 0.0
        p = fe.protein() if callable(getattr(fe, 'protein', None)) else 0.0
        f = fe.fat() if callable(getattr(fe, 'fat', None)) else 0.0
        c = fe.carbs() if callable(getattr(fe, 'carbs', None)) else 0.0
        totals['calories'] += kcal
        totals['protein'] += p
        totals['fat'] += f
        totals['carbs'] += c
        combined_entries.append({
            'pk': fe.pk,
            'id': fe.pk,
            'name': fe.product.name,
            'amount': fe.amount,
            'initial_amount': fe.initial_amount,
            'kcal': round(kcal, 2),
            'protein': round(p, 2),
            'fat': round(f, 2),
            'carbs': round(c, 2),
            'origin': 'food',
        })

    for ce in qs_entry:
        # Entry ir pielāgots ieraksts — šeit vērtības parasti jau ir laukos
        kcal = float(getattr(ce, 'kcal', 0.0) or 0.0)
        p = float(getattr(ce, 'protein', 0.0) or 0.0)
        f = float(getattr(ce, 'fat', 0.0) or 0.0)
        c = float(getattr(ce, 'carbs', 0.0) or 0.0)
        totals['calories'] += kcal
        totals['protein'] += p
        totals['fat'] += f
        totals['carbs'] += c
        combined_entries.append({
            'pk': ce.pk,
            'id': ce.pk,
            'name': ce.name,
            'amount': ce.amount,
            'initial_amount': getattr(ce, 'initial_amount', ce.amount),
            'kcal': round(kcal, 2),
            'protein': round(p, 2),
            'fat': round(f, 2),
            'carbs': round(c, 2),
            'origin': 'entry',
        })

    # Noapaļo totālus pirms padošanas uz šablonu
    for k in totals:
        totals[k] = round(totals[k], 2)
    entries = combined_entries

    recommendation = None
    # Ja lietotājs pieslēdzies, mēģina izmantot saistīto `Profile` objektu
    if request.user.is_authenticated:
        profile, created = Profile.objects.get_or_create(user=request.user)
        # Pārliecinās, ka profila dati ir pietiekami, lai veiktu aprēķinu
        if profile.age and profile.weight and profile.height and profile.activity_level and profile.goal:
            profile_data = {
                'age': profile.age,
                'sex': profile.sex,
                'weight': profile.weight,
                'height': profile.height,
                'activity_level': profile.activity_level,
                'goal': profile.goal,
            }
            recommendation = _compute_recommendation(profile_data)
    else:
        # Ja nav pieslēguma, mēģina izmantot sesijas `profile` datus (ja lietotājs saglabājis)
        session_profile = request.session.get('profile')
        if session_profile:
            recommendation = _compute_recommendation(session_profile)

    return render(request, 'nutrition/home.html', {
        'products': products,
        'form': form,
        'totals': totals,
        'entries': entries,
        'recommendation': recommendation,
    })

@login_required
def profile(request):
    # Atrod vai izveido `Profile` objektu lietotājam (`get_or_create`)
    profile, _ = Profile.objects.get_or_create(user=request.user)

    # Ja lietotājs iesniedz profila formu (POST), saglabā izmaiņas
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('nutrition:home')
    else:
        # GET — priekšizpilda formu ar profila objekta datiem
        form = ProfileForm(instance=profile)

    # Sagatavo rekomendāciju, ja profila dati ir pietiekami
    recommendation = None
    if profile.age and profile.weight and profile.height and profile.activity_level and profile.goal:
        profile_data = {
            'age': profile.age,
            'sex': profile.sex,
            'weight': profile.weight,
            'height': profile.height,
            'activity_level': profile.activity_level,
            'goal': profile.goal,
        }
        recommendation = _compute_recommendation(profile_data)

    # Renderē profila lapu ar formu un (ja ir) rekomendāciju
    return render(request, 'nutrition/profile.html', {
        'form': form,
        'recommendation': recommendation,
    })

def add_meal(request):
    """
    Pievieno pārtikas ierakstu (FoodEntry).

    Sagaida POST ar laukiem `product` (produkta ID) un `amount` (gramos).
    Ja produkts un daudzums ir derīgi, izveido `FoodEntry`. Pēc tam
    pārsūta uz mājas lapu. Funkcija ir idempotenta (drošības nolūkos
    tver izņēmumus un vienkārši atgriežas uz māju).
    """
    if request.method == 'POST':
        product_id = request.POST.get('product')
        amount = request.POST.get('amount')
        try:
            product = Product.objects.get(pk=product_id)
            amount_val = float(amount)
            if amount_val > 0:
                # Sagatavo datus jaunam FoodEntry ierakstam
                fe_kwargs = {
                    'product': product,
                    'amount': amount_val,
                    'initial_amount': amount_val,
                }
                if request.user.is_authenticated:
                    # Ja lietotājs ir pieslēdzies, pievieno saistību
                    fe_kwargs['user'] = request.user
                FoodEntry.objects.create(**fe_kwargs)
        except Exception:
            # Drošības nolūkos ignorē jebkādas kļūdas (neuzbrūk)
            pass
    return redirect('nutrition:home')

def calculator(request):
    """
    Kalkulators: aprēķina BMR/TDEE/rekomendācijas no iesniegtajiem laukiem
    vai priekš‑aizpilda no pieslēgtā lietotāja `Profile`.
    """
    result = None
    if request.method == 'POST':
        try:
            age = int(request.POST.get('age') or 0)
            sex = request.POST.get('sex') or 'M'
            weight = float(request.POST.get('weight') or 0)
            height = float(request.POST.get('height') or 0)
            activity_level = request.POST.get('activity_level') or '1.2'
            goal = request.POST.get('goal') or 'maintain'

            # Server-side validation: ensure positive values
            if age <= 0 or weight <= 0 or height <= 0:
                messages.error(request, _('Please enter positive values for age, weight and height.'))
                result = None
            else:
                profile = {
                    'age': age,
                    'sex': sex,
                    'weight': weight,
                    'height': height,
                    'activity_level': activity_level,
                    'goal': goal,
                }
                result = _compute_recommendation(profile)
        except Exception:
            # Ja ievades pārveidošana neizdodas, atgriež None
            result = None
    else:
        # Mēģina priekš‑aizpildīt formu no lietotāja profila, ja pieslēdzies
        if request.user.is_authenticated:
            try:
                profile_obj = getattr(request.user, 'profile', None)
                if profile_obj and profile_obj.age and profile_obj.weight and profile_obj.height and profile_obj.activity_level and profile_obj.goal:
                    profile = {
                        'age': profile_obj.age,
                        'sex': profile_obj.sex,
                        'weight': profile_obj.weight,
                        'height': profile_obj.height,
                        'activity_level': profile_obj.activity_level,
                        'goal': profile_obj.goal,
                    }
                    result = _compute_recommendation(profile)
            except Exception:
                pass

    return render(request, 'nutrition/calculator.html', {
        'result': result,
    })

def progress(request):
    """
    Progress lapa: sagatavo pēdējo 14 dienu kaloriju sēriju diagrammai.

    Loģika:
    - Izveido laika logu (14 dienas, iekļaujot šodienu),
    - Nolasa gan `FoodEntry` (metode calories()) gan `Entry` (lauku kcal),
    - Akumulē pēc datuma un nodod JSON rindas priekš front-end grafika.
    """
    today = timezone.now().date()
    start = today - timezone.timedelta(days=13)  # include today -> 14 days

    # Būvē aware datetime robežas vaicājumam
    start_dt = timezone.make_aware(dt.datetime.combine(start, dt.time.min))
    end_dt = timezone.make_aware(dt.datetime.combine(today, dt.time.max))

    recommendation = None
    if request.user.is_authenticated:
        qs_food = FoodEntry.objects.filter(user=request.user, created_at__gte=start_dt, created_at__lte=end_dt)
        qs_entry = Entry.objects.filter(user=request.user, created_at__gte=start_dt, created_at__lte=end_dt)
        # Mēģina iegūt rekomendāciju no profila
        try:
            profile_obj = getattr(request.user, 'profile', None)
            if profile_obj and profile_obj.age and profile_obj.weight and profile_obj.height and profile_obj.activity_level and profile_obj.goal:
                profile = {
                    'age': profile_obj.age,
                    'sex': profile_obj.sex,
                    'weight': profile_obj.weight,
                    'height': profile_obj.height,
                    'activity_level': profile_obj.activity_level,
                    'goal': profile_obj.goal,
                }
                recommendation = _compute_recommendation(profile)
        except Exception:
            recommendation = None
    else:
        qs_food = FoodEntry.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt, user__isnull=True)
        qs_entry = Entry.objects.none()

    # Iniciālizē dienu vārdnīcu ar nullēm
    daily = {}
    for i in range(14):
        d = (start + timezone.timedelta(days=i))
        daily[d.strftime('%Y-%m-%d')] = 0.0

    # Uzkrāj FoodEntry kalorijas (izmantojot metodi) grupējot pēc datuma
    for e in qs_food:
        try:
            key = timezone.localtime(e.created_at).strftime('%Y-%m-%d')
        except Exception:
            key = getattr(e, 'created_at').strftime('%Y-%m-%d')
        daily[key] = daily.get(key, 0.0) + (e.calories() if callable(getattr(e, 'calories', None)) else 0.0)

    # Uzkrāj pielāgoto Entry.kcal laukus
    for e in qs_entry:
        try:
            key = timezone.localtime(e.created_at).strftime('%Y-%m-%d')
        except Exception:
            key = getattr(e, 'created_at').strftime('%Y-%m-%d')
        daily[key] = daily.get(key, 0.0) + (getattr(e, 'kcal', 0.0) or 0.0)

    dates = list(daily.keys())
    calories = [round(daily[d], 2) for d in dates]
    return render(request, 'nutrition/progress.html', {
        'dates_json': json.dumps(dates),
        'calories_json': json.dumps(calories),
        'recommendation': recommendation,
    })


def api_daily_calories(request):
    """
    API: atgriež JSON ar datumiem un kalorijām pēdējām `days` dienām.

    GET parametrs: `days` (noklusējums 14). Atgriež datus gan pieslēgtam
    lietotājam (viņa ieraksti), gan publiskus ierakstus anonīmiem.
    """
    try:
        days = int(request.GET.get('days', 14))
    except Exception:
        days = 14
    days = max(1, min(365, days))
    today = timezone.now().date()
    start = today - timezone.timedelta(days=days - 1)
    start_dt = timezone.make_aware(dt.datetime.combine(start, dt.time.min))
    end_dt = timezone.make_aware(dt.datetime.combine(today, dt.time.max))

    if request.user.is_authenticated:
        qs_food = FoodEntry.objects.filter(user=request.user, created_at__gte=start_dt, created_at__lte=end_dt)
        qs_entry = Entry.objects.filter(user=request.user, created_at__gte=start_dt, created_at__lte=end_dt)
    else:
        qs_food = FoodEntry.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt, user__isnull=True)
        qs_entry = Entry.objects.none()

    daily = {}
    for i in range(days):
        d = (start + timezone.timedelta(days=i))
        daily[d.strftime('%Y-%m-%d')] = 0.0

    for e in qs_food:
        try:
            key = timezone.localtime(e.created_at).strftime('%Y-%m-%d')
        except Exception:
            key = getattr(e, 'created_at').strftime('%Y-%m-%d')
        daily[key] = daily.get(key, 0.0) + (e.calories() if callable(getattr(e, 'calories', None)) else 0.0)

    for e in qs_entry:
        try:
            key = timezone.localtime(e.created_at).strftime('%Y-%m-%d')
        except Exception:
            key = getattr(e, 'created_at').strftime('%Y-%m-%d')
        daily[key] = daily.get(key, 0.0) + (getattr(e, 'kcal', 0.0) or 0.0)

    dates = list(daily.keys())
    calories = [round(daily[d], 2) for d in dates]
    return JsonResponse({'dates': dates, 'calories': calories})

def signup(request):
    """
    Reģistrācijas skats: apstrādā `SignUpForm` iesniegšanu.

    Ja forma derīga, izveido kontu un parāda paziņojumu, tad pārsūta uz
    autorizācijas lapu. GET pieprasījumā atgriež reģistrācijas formu.
    """
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Account created. You can now log in."))
            return redirect('nutrition:login')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

def _is_staff(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(_is_staff)
def products(request):
    """
    List products and allow staff to add new products on the same page.
    """
    qs = Product.objects.all().order_by('name')
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Product saved.")
            return redirect('nutrition:products')
    else:
        form = ProductForm()
    return render(request, 'nutrition/products.html', {
        'products': qs,
        'form': form,
    })

def api_product_search(request):
    """
    Meklē produktus OpenFoodFacts datubāzē un atgriež vienkāršotu JSON rezultātu sarakstu.
    GET parametrs: `q` (meklēšanas frāze). Ierobežo rezultātus līdz 12 produktiem.
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'results': []})
    url = 'https://world.openfoodfacts.org/cgi/search.pl'
    params = {
        'search_terms': q,
        'search_simple': 1,
        'action': 'process',
        'json': 1,
        'page_size': 12,
    }
    try:
        r = requests.get(url, params=params, timeout=6)
        r.raise_for_status()
        data = r.json()
        results = []
        for p in data.get('products', [])[:12]:
            name = p.get('product_name') or p.get('generic_name') or p.get('brands') or ''
            if not name:
                continue
            nutr = p.get('nutriments', {})
            kcal = nutr.get('energy-kcal_100g') or nutr.get('energy_100g') or 0
            protein = nutr.get('proteins_100g') or nutr.get('proteins') or 0
            fat = nutr.get('fat_100g') or nutr.get('fat') or 0
            carbs = nutr.get('carbohydrates_100g') or nutr.get('carbohydrates') or 0
            results.append({
                'name': name,
                'kcal': float(kcal) if kcal else 0.0,
                'protein': float(protein) if protein else 0.0,
                'fat': float(fat) if fat else 0.0,
                'carbs': float(carbs) if carbs else 0.0,
            })
        return JsonResponse({'results': results})
    except Exception as e:
        return JsonResponse({'results': [], 'error': str(e)})


@require_POST
@login_required
def api_add_entry(request):
    """
    Pieņem JSON payload no klienta, atbalsta vairākus lauku nosaukumus
    un izveido pielāgotu `Entry` ierakstu pieslēgtam lietotājam.

    Ieeja var saturēt `kcal`, `kcal_per100`, `kcal_per_entry`, `protein_per100` utt.
    Atgriež JSON ar `success` un izveidotā ieraksta `id`.
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'success': False, 'error': 'invalid_json'}, status=400)

    # pamatlauki
    name = (payload.get('name') or '').strip()[:255]
    try:
        amount = float(payload.get('amount') or payload.get('mass') or 100)
    except Exception:
        amount = 100.0

    # palīdzfunkcija drošai pārvēršanai uz float
    def to_float(v, default=0.0):
        try:
            return float(v)
        except Exception:
            return default

    # preferē tiešu kcal/per-entry; ja nav, aprēķina no per-100
    k100 = to_float(payload.get('kcal_per100') or payload.get('kcal_100') or payload.get('kcal100') or payload.get('kcalPer100') or 0.0)
    kcal = to_float(payload.get('kcal')) or to_float(payload.get('kcal_per_entry')) or (k100 * amount / 100.0) or 0.0

    # nolasīt makro per100 ja dota
    protein_per100 = to_float(payload.get('protein_per100') or payload.get('protein100') or 0.0)
    fat_per100 = to_float(payload.get('fat_per100') or payload.get('fat100') or 0.0)
    carbs_per100 = to_float(payload.get('carbs_per100') or payload.get('carbs100') or 0.0)

    protein = to_float(payload.get('protein')) or (protein_per100 * amount / 100.0) or 0.0
    fat = to_float(payload.get('fat')) or (fat_per100 * amount / 100.0) or 0.0
    carbs = to_float(payload.get('carbs')) or (carbs_per100 * amount / 100.0) or 0.0

    # Validation: amount must be positive and no nutrient value may be negative
    try:
        if float(amount) <= 0:
            return JsonResponse({'success': False, 'error': 'amount_must_be_positive'}, status=400)
    except Exception:
        return JsonResponse({'success': False, 'error': 'invalid_amount'}, status=400)

    if any(x < 0 for x in [k100, kcal, protein_per100, fat_per100, carbs_per100, protein, fat, carbs]):
        return JsonResponse({'success': False, 'error': 'negative_values_not_allowed'}, status=400)

    entry = Entry.objects.create(
        user=request.user,
        name=name or 'Custom',
        amount=amount,
        kcal=round(kcal, 3),
        protein=round(protein, 3),
        fat=round(fat, 3),
        carbs=round(carbs, 3),
        kcal_per100=round(k100, 3),
        protein_per100=round(protein_per100, 3),
        fat_per100=round(fat_per100, 3),
        carbs_per100=round(carbs_per100, 3),
    )

    return JsonResponse({'success': True, 'id': entry.id})

@require_POST
def edit_entry(request, entry_id):
    """
    Update amount for existing FoodEntry or custom Entry (both POST 'amount').
    Supports JSON (AJAX) requests: accepts {"amount": <number>} and returns JSON.
    For normal form POST uses messages + redirect.
    """
    # helper to detect JSON request
    content_type = request.META.get('CONTENT_TYPE', '') or request.headers.get('Content-Type', '')
    is_json = content_type.startswith('application/json')

    # extract amount from JSON body if present, otherwise from request.POST
    def _get_amount_from_request():
        if is_json:
            try:
                payload = json.loads(request.body.decode('utf-8') or '{}')
                return float(payload.get('amount', 0))
            except Exception as ex:
                logger.debug("Invalid JSON payload for edit_entry: %s", ex)
                return None
        else:
            try:
                return float(request.POST.get('amount', '0'))
            except Exception:
                return None

    # try FoodEntry first
    try:
        fe = FoodEntry.objects.get(pk=entry_id)
        amount = _get_amount_from_request()
        if amount is None:
            if is_json:
                return JsonResponse({'success': False, 'error': 'invalid_amount'}, status=400)
            messages.error(request, "Invalid amount.")
            return redirect('nutrition:home')

        if amount <= 0:
            if is_json:
                return JsonResponse({'success': False, 'error': 'amount_must_be_positive'}, status=400)
            messages.error(request, "Amount must be greater than 0.")
            return redirect('nutrition:home')

        fe.amount = amount
        # persist new amount first
        fe.save()
        # compute authoritative per-100 baselines from Product (if available)
        prod = getattr(fe, 'product', None)
        kcal_per100 = 0.0
        protein_per100 = 0.0
        fat_per100 = 0.0
        carbs_per100 = 0.0
        if prod is not None:
            try:
                kcal_per100 = float(getattr(prod, 'calories_per_100g', 0) or 0.0)
            except Exception:
                kcal_per100 = 0.0
            try:
                protein_per100 = float(getattr(prod, 'protein_per_100g', 0) or 0.0)
            except Exception:
                protein_per100 = 0.0
            try:
                fat_per100 = float(getattr(prod, 'fat_per_100g', 0) or 0.0)
            except Exception:
                fat_per100 = 0.0
            try:
                carbs_per100 = float(getattr(prod, 'carbs_per_100g', 0) or 0.0)
            except Exception:
                carbs_per100 = 0.0

        # If kcal_per100 missing but macros present, compute kcal_per100 from macros
        if not kcal_per100 and (protein_per100 or fat_per100 or carbs_per100):
            kcal_per100 = (protein_per100 * 4.0) + (fat_per100 * 9.0) + (carbs_per100 * 4.0)

        # Now compute authoritative per-entry values
        amount_val = float(fe.amount or 0.0)
        kcal = round(amount_val * (kcal_per100 or 0.0) / 100.0, 3)
        protein = round(amount_val * (protein_per100 or 0.0) / 100.0, 3)
        fat = round(amount_val * (fat_per100 or 0.0) / 100.0, 3)
        carbs = round(amount_val * (carbs_per100 or 0.0) / 100.0, 3)

        logger.info("FoodEntry %s updated by user %s: amount=%s (kcal=%s, p=%s f=%s c=%s)", fe.pk, getattr(request.user, 'username', 'anonymous'), amount, kcal, protein, fat, carbs)

        if is_json:
            return JsonResponse({
                'success': True,
                'id': fe.pk,
                'amount': float(fe.amount),
                'kcal': kcal,
                'protein': protein,
                'fat': fat,
                'carbs': carbs,
            })
        messages.success(request, "Entry updated.")
        return redirect('nutrition:home')

    except FoodEntry.DoesNotExist:
        # try custom Entry
        try:
            ce = Entry.objects.get(pk=entry_id)
        except Entry.DoesNotExist:
            if is_json:
                return JsonResponse({'success': False, 'error': 'not_found'}, status=404)
            messages.error(request, "Entry not found.")
            return redirect('nutrition:home')

        # require owner for custom entries
        if not request.user.is_authenticated or ce.user_id != request.user.id:
            logger.warning("Unauthorized edit attempt on Entry %s by user %s", entry_id, getattr(request.user, 'username', 'anonymous'))
            if is_json:
                return JsonResponse({'success': False, 'error': 'forbidden'}, status=403)
            messages.error(request, "You are not allowed to edit this entry.")
            return redirect('nutrition:home')

        new_amount = _get_amount_from_request()
        if new_amount is None or new_amount <= 0:
            if is_json:
                return JsonResponse({'success': False, 'error': 'invalid_amount'}, status=400)
            messages.error(request, "Invalid amount.")
            return redirect('nutrition:home')

        # Recompute per-entry values пропорционально изменению количества
        # Use helper to derive reliable per-gram baselines
        kcal_per_g = _per_g_from_entry(ce, 'kcal')
        protein_per_g = _per_g_from_entry(ce, 'protein')
        fat_per_g = _per_g_from_entry(ce, 'fat')
        carbs_per_g = _per_g_from_entry(ce, 'carbs')

        ce.amount = new_amount
        ce.kcal = round(kcal_per_g * new_amount, 3)
        ce.protein = round(protein_per_g * new_amount, 3)
        ce.fat = round(fat_per_g * new_amount, 3)
        ce.carbs = round(carbs_per_g * new_amount, 3)
        # keep per100 fields unchanged (they remain authoritative baselines)
        ce.save()
        logger.info("Entry %s updated by user %s: amount=%s", ce.pk, request.user.username, new_amount)

        if is_json:
            return JsonResponse({
                'success': True,
                'id': ce.pk,
                'amount': float(ce.amount),
                'kcal': float(ce.kcal),
                'protein': float(ce.protein),
                'fat': float(ce.fat),
                'carbs': float(ce.carbs),
            })
        messages.success(request, "Entry updated.")
        return redirect('nutrition:home')

@require_POST
def delete_entry(request, entry_id):
    """
    Delete a FoodEntry or a custom Entry.
    Supports JSON (AJAX) requests: returns JSON on success/error.
    """
    content_type = request.META.get('CONTENT_TYPE', '') or request.headers.get('Content-Type', '')
    is_json = content_type.startswith('application/json')

    # first try FoodEntry
    try:
        fe = FoodEntry.objects.get(pk=entry_id)
        fe.delete()
        logger.info("FoodEntry %s deleted by user %s", entry_id, getattr(request.user, 'username', 'anonymous'))
        if is_json:
            return JsonResponse({'success': True})
        messages.success(request, "Entry deleted.")
        return redirect('nutrition:home')
    except FoodEntry.DoesNotExist:
        # try custom Entry
        try:
            ce = Entry.objects.get(pk=entry_id)
        except Entry.DoesNotExist:
            if is_json:
                return JsonResponse({'success': False, 'error': 'not_found'}, status=404)
            messages.error(request, "Entry not found.")
            return redirect('nutrition:home')

        if not request.user.is_authenticated or ce.user_id != request.user.id:
            logger.warning("Unauthorized delete attempt on Entry %s by user %s", entry_id, getattr(request.user, 'username', 'anonymous'))
            if is_json:
                return JsonResponse({'success': False, 'error': 'forbidden'}, status=403)
            messages.error(request, "You are not allowed to delete this entry.")
            return redirect('nutrition:home')

        ce.delete()
        logger.info("Entry %s deleted by owner %s", entry_id, request.user.username)
        if is_json:
            return JsonResponse({'success': True})
        messages.success(request, "Entry deleted.")
        return redirect('nutrition:home')

def api_product_lookup(request):
    """
    Produkta meklēšana pēc svītrkoda OpenFoodFacts API.

    GET parametrs: `barcode`. Ja produkts atrasts, atgriež pamatinformāciju
    (nosaukums, kcal, proteīns, tauki, ogļhidrāti, barcode). Ja neizdodas,
    atgriež atbilstošu kļūdas HTTP statusu.
    """
    barcode = request.GET.get('barcode', '').strip()
    if not barcode:
        return JsonResponse({'error': 'Missing barcode'}, status=400)
    url = f'https://world.openfoodfacts.org/api/v0/product/{barcode}.json'
    try:
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        data = r.json()
        product = data.get('product') or {}
        status = data.get('status')
        if status != 1:
            return JsonResponse({'error': 'Product not found'}, status=404)
        name = product.get('product_name') or product.get('generic_name') or product.get('brands') or ''
        nutr = product.get('nutriments', {})
        kcal = nutr.get('energy-kcal_100g') or nutr.get('energy_100g') or 0
        protein = nutr.get('proteins_100g') or nutr.get('proteins') or 0
        fat = nutr.get('fat_100g') or nutr.get('fat') or 0
        carbs = nutr.get('carbohydrates_100g') or nutr.get('carbohydrates') or 0
        result = {
            'name': name,
            'kcal': float(kcal) if kcal else 0.0,
            'protein': float(protein) if protein else 0.0,
            'fat': float(fat) if fat else 0.0,
            'carbs': float(carbs) if carbs else 0.0,
            'barcode': barcode,
        }
        return JsonResponse({'result': result})
    except requests.RequestException:
        return JsonResponse({'error': 'External lookup failed'}, status=502)
