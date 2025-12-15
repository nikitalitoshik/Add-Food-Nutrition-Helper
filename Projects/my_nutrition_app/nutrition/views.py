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
    totals = {'calories':0.0,'protein':0.0,'fat':0.0,'carbs':0.0}
    for e in entries:
        totals['calories'] += e.calories()
        totals['protein'] += e.protein()
        totals['fat'] += e.fat()
        totals['carbs'] += e.carbs()
    # округлить для отображения
    for k in totals:
        totals[k] = round(totals[k], 2)
    return totals

def _compute_recommendation(profile):
    age = profile['age']
    sex = profile['sex']
    weight = profile['weight']
    height = profile['height']
    activity = float(profile['activity_level'])
    goal = profile['goal']
    # Mifflin-St Jeor
    if sex == 'M':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    tdee = bmr * activity
    adj = {'lose': -500, 'maintain': 0, 'gain': 500}[goal]
    recommended = tdee + adj
    # Простое макро-распределение:
    protein_g = round(1.6 * weight, 1)  # g protein per kg
    protein_cal = protein_g * 4
    fat_cal = 0.25 * recommended
    fat_g = round(fat_cal / 9, 1)
    carbs_cal = recommended - protein_cal - fat_cal
    carbs_g = round(max(carbs_cal, 0) / 4, 1)
    return {
        'bmr': round(bmr,1),
        'tdee': round(tdee,1),
        'recommended_kcal': round(recommended,1),
        'protein_g': protein_g,
        'fat_g': fat_g,
        'carbs_g': carbs_g
    }

def _per_g_from_entry(ce, field_name):
    """
    Return per-gram baseline for field_name on an Entry instance.
    field_name: 'kcal'|'protein'|'fat'|'carbs'
    Priority:
      1) use ce.<field_name>_per100 if > 0
      2) else if ce.amount > 0, use ce.<field_name> / ce.amount (per-entry baseline)
      3) else 0
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
        pass
    return 0.0

def home(request):
    if request.method == 'POST':
        form = FoodEntryForm(request.POST)
        if form.is_valid():
            fe_kwargs = {
                'product': form.cleaned_data['product'],
                'amount': form.cleaned_data['amount'],
                'initial_amount': form.cleaned_data['amount']
            }
            if request.user.is_authenticated:
                fe_kwargs['user'] = request.user
            FoodEntry.objects.create(**fe_kwargs)
            return redirect('nutrition:home')
    else:
        form = FoodEntryForm()

    products = Product.objects.all()
    today = timezone.now().date()

    # build datetime range for "today"
    start_dt = timezone.make_aware(dt.datetime.combine(today, dt.time.min))
    end_dt = timezone.make_aware(dt.datetime.combine(today, dt.time.max))

    # fetch FoodEntry rows and custom Entry rows for the current user (or public ones if anonymous)
    if request.user.is_authenticated:
        qs_food = FoodEntry.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt, user=request.user)
        qs_entry = Entry.objects.filter(user=request.user, created_at__gte=start_dt, created_at__lte=end_dt)
    else:
        qs_food = FoodEntry.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt, user__isnull=True)
        qs_entry = Entry.objects.none()

    # build unified list and compute totals across both sources
    combined_entries = []
    totals = {'calories': 0.0, 'protein': 0.0, 'fat': 0.0, 'carbs': 0.0}

    for fe in qs_food:
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
            'origin': 'food'
        })

    for ce in qs_entry:
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
            'origin': 'entry'
        })

    # round totals for display (same shape as before)
    for k in totals:
        totals[k] = round(totals[k], 2)
    entries = combined_entries

    recommendation = None
    # use user's Profile when authenticated
    if request.user.is_authenticated:
        profile, created = Profile.objects.get_or_create(user=request.user)
        # ensure profile has enough data before computing
        if profile.age and profile.weight and profile.height and profile.activity_level and profile.goal:
            # build a dict matching previous profile shape
            profile_data = {
                'age': profile.age,
                'sex': profile.sex,
                'weight': profile.weight,
                'height': profile.height,
                'activity_level': profile.activity_level,
                'goal': profile.goal
            }
            recommendation = _compute_recommendation(profile_data)
    else:
        # fallback: use session-stored profile (existing behavior)
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
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('nutrition:home')
    else:
        form = ProfileForm(instance=profile)
    recommendation = None
    if profile.age and profile.weight and profile.height and profile.activity_level and profile.goal:
        profile_data = {
            'age': profile.age,
            'sex': profile.sex,
            'weight': profile.weight,
            'height': profile.height,
            'activity_level': profile.activity_level,
            'goal': profile.goal
        }
        recommendation = _compute_recommendation(profile_data)
    return render(request, 'nutrition/profile.html', {
        'form': form,
        'recommendation': recommendation
    })

def add_meal(request):
    """
    This view expects POST with 'product' (id) and 'amount' (grams).
    """
    if request.method == 'POST':
        product_id = request.POST.get('product')
        amount = request.POST.get('amount')
        try:
            product = Product.objects.get(pk=product_id)
            amount_val = float(amount)
            if amount_val > 0:
                # сохраняем автора записи, если пользователь аутентифицирован
                fe_kwargs = {
                    'product': product,
                    'amount': amount_val,
                    'initial_amount': amount_val
                }
                if request.user.is_authenticated:
                    fe_kwargs['user'] = request.user
                FoodEntry.objects.create(**fe_kwargs)
        except Exception:
            pass
    return redirect('nutrition:home')

def calculator(request):
    """
    Calculator page: accepts age/sex/weight/height/activity/goal (POST)
    or uses logged-in user's Profile (if available) and shows computed result.
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
            profile = {
                'age': age,
                'sex': sex,
                'weight': weight,
                'height': height,
                'activity_level': activity_level,
                'goal': goal
            }
            result = _compute_recommendation(profile)
        except Exception:
            result = None
    else:
        # try to prefill from user Profile if available
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
                        'goal': profile_obj.goal
                    }
                    result = _compute_recommendation(profile)
            except Exception:
                pass
    return render(request, 'nutrition/calculator.html', {
        'result': result
    })

def progress(request):
    """
    Progress page: prepare last 14 days calories for charting.
    """
    today = timezone.now().date()
    start = today - timezone.timedelta(days=13)  # include today -> 14 days

    # build datetime range for DB query (start 00:00 of start, end 23:59:59.999999 of today)
    start_dt = timezone.make_aware(dt.datetime.combine(start, dt.time.min))
    end_dt = timezone.make_aware(dt.datetime.combine(today, dt.time.max))

    if request.user.is_authenticated:
        qs_food = FoodEntry.objects.filter(user=request.user, created_at__gte=start_dt, created_at__lte=end_dt)
        qs_entry = Entry.objects.filter(user=request.user, created_at__gte=start_dt, created_at__lte=end_dt)
    else:
        qs_food = FoodEntry.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt, user__isnull=True)
        qs_entry = Entry.objects.none()

    # initialize zeroed days
    daily = {}
    for i in range(14):
        d = (start + timezone.timedelta(days=i))
        daily[d.strftime('%Y-%m-%d')] = 0.0

    # accumulate FoodEntry calories (method) and Entry.kcal (field)
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
    return render(request, 'nutrition/progress.html', {
        'dates_json': json.dumps(dates),
        'calories_json': json.dumps(calories),
    })

def signup(request):
    """
    Регистрация: использует SignUpForm (валидация email uniqueness).
    При успешной регистрации — перенаправляет на страницу логина.
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
    Proxy search to OpenFoodFacts and return simplified JSON results.
    GET param: q
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
	Принимает JSON payload от клиента (см. client code).
	Поддерживает разные имена полей: kcal, kcal_per100, kcal_per_entry, protein_per100 и т.д.
	Возвращает { success: True, id: <entry_id> } или { success: False, error: ... }.
	"""
	try:
		payload = json.loads(request.body.decode('utf-8') or '{}')
	except Exception:
		return JsonResponse({'success': False, 'error': 'invalid_json'}, status=400)

	# basic fields
	name = (payload.get('name') or '').strip()[:255]
	try:
		amount = float(payload.get('amount') or payload.get('mass') or 100)
	except Exception:
		amount = 100.0

	# resolve per-entry kcal: prefer explicit kcal, then kcal_per_entry, then compute from per100
	def to_float(v, default=0.0):
		try:
			return float(v)
		except Exception:
			return default

	# prefer direct kcal/per-entry, else compute from per-100; also capture per100 baselines
	k100 = to_float(payload.get('kcal_per100') or payload.get('kcal_100') or payload.get('kcal100') or payload.get('kcalPer100') or 0.0)
	kcal = to_float(payload.get('kcal')) or to_float(payload.get('kcal_per_entry')) or (k100 * amount / 100.0) or 0.0

	# also capture protein/fat/carbs per100 if provided
	protein_per100 = to_float(payload.get('protein_per100') or payload.get('protein100') or 0.0)
	fat_per100 = to_float(payload.get('fat_per100') or payload.get('fat100') or 0.0)
	carbs_per100 = to_float(payload.get('carbs_per100') or payload.get('carbs100') or 0.0)

	protein = to_float(payload.get('protein')) or (protein_per100 * amount / 100.0) or 0.0
	fat = to_float(payload.get('fat')) or (fat_per100 * amount / 100.0) or 0.0
	carbs = to_float(payload.get('carbs')) or (carbs_per100 * amount / 100.0) or 0.0

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
    Lookup product by barcode (UPC) via OpenFoodFacts.
    GET param: barcode
    Returns JSON: { result: { name, kcal, protein, fat, carbs } } or { error: '...' }
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
            'barcode': barcode
        }
        return JsonResponse({'result': result})
    except requests.RequestException as e:
        return JsonResponse({'error': 'External lookup failed'}, status=502)
