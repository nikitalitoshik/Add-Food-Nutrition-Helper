from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .models import Product, FoodEntry, Profile
from .forms import FoodEntryForm, ProfileForm, SignUpForm, ProductForm
import json
import requests
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.apps import apps
from django.shortcuts import get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext as _

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

def home(request):
    if request.method == 'POST':
        form = FoodEntryForm(request.POST)
        if form.is_valid():
            FoodEntry.objects.create(
                product=form.cleaned_data['product'],
                amount=form.cleaned_data['amount']
            )
            return redirect('nutrition:home')
    else:
        form = FoodEntryForm()

    products = Product.objects.all()
    today = timezone.now().date()
    entries = FoodEntry.objects.filter(created_at=today)
    totals = _compute_totals(entries)

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
                FoodEntry.objects.create(
                    product=product, 
                    amount=amount_val,
                    initial_amount=amount_val  # <-- добавить
                )
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
    qs = FoodEntry.objects.filter(created_at__range=(start, today))
    # initialize zeroed days
    daily = {}
    for i in range(14):
        d = (start + timezone.timedelta(days=i))
        daily[d.strftime('%Y-%m-%d')] = 0.0
    for e in qs:
        key = e.created_at.strftime('%Y-%m-%d')
        daily[key] = daily.get(key, 0.0) + (e.calories() if callable(getattr(e, 'calories', None)) else 0.0)
    dates = list(daily.keys())
    calories = [round(daily[d], 2) for d in dates]
    return render(request, 'nutrition/progress.html', {
        'dates_json': json.dumps(dates),
        'calories_json': json.dumps(calories),
    })

def signup(request):
    """
    Простая регистрация: использует UserCreationForm,
    после удачного сохранения перенаправляет на страницу логина.
    """
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Account created. You can now log in."))
            return redirect('nutrition:login')
    else:
        form = UserCreationForm()
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
def api_add_entry(request):
    """
    API endpoint: add entry.
    Safe: does not include model objects/methods in JsonResponse.
    Tries to find Product and Entry models dynamically via apps.get_model.
    """
    import json, traceback

    # parse JSON body (fall back to POST)
    try:
        if request.content_type and 'application/json' in request.content_type:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        else:
            payload = request.POST.dict()
    except Exception as exc:
        print('api_add_entry: failed to parse payload:', exc)
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)

    # find models dynamically
    try:
        Product = apps.get_model('nutrition', 'Product')
    except LookupError:
        Product = None
    try:
        # try common candidate names for entry model
        Entry = None
        for cand in ('Entry','FoodEntry','Consumption','ConsumedEntry','FoodLog','Record','NutritionEntry','UserEntry','MealEntry'):
            try:
                Entry = apps.get_model('nutrition', cand)
                if Entry:
                    break
            except LookupError:
                Entry = None
    except Exception:
        Entry = None

    if Product is None:
        return JsonResponse({'success': False, 'error': 'Server error: Product model not found'}, status=500)
    if Entry is None:
        return JsonResponse({'success': False, 'error': 'Server error: Entry model not found'}, status=500)

    # extract fields
    prod_id = payload.get('id') or payload.get('product_id')
    name = payload.get('name')
    try:
        amount = float(str(payload.get('amount') or 0).replace(',', '.'))
    except Exception:
        amount = 0.0

    if not prod_id and not name:
        return JsonResponse({'success': False, 'error': 'Missing product id or name'}, status=400)

    # get or create product
    try:
        if prod_id:
            product = get_object_or_404(Product, pk=int(prod_id))
        else:
            # attempt to create product when name provided — only set defaults for known fields
            defaults = {}
            # try to read possible numeric fields from payload
            def to_float(v):
                try: return float(str(v).replace(',', '.'))
                except Exception: return 0.0
            possible = {
                'kcal_per_100g': to_float(payload.get('kcal') or payload.get('kcal100')),
                'protein_per_100g': to_float(payload.get('protein') or payload.get('protein100')),
                'fat_per_100g': to_float(payload.get('fat') or payload.get('fat100')),
                'carbs_per_100g': to_float(payload.get('carbs') or payload.get('carbs100')),
            }
            model_field_names = {f.name for f in Product._meta.get_fields()}
            for k,v in possible.items():
                if k in model_field_names:
                    defaults[k] = v
            product, created = Product.objects.get_or_create(name=name, defaults=defaults or None)
    except Exception as exc:
        print('api_add_entry: product lookup/create failed:', exc)
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': 'Product lookup/create failed'}, status=500)

    # compute nutrition values using available product fields
    try:
        def get_attr_num(obj, *names):
            for n in names:
                if hasattr(obj, n):
                    try:
                        return float(getattr(obj, n) or 0)
                    except Exception:
                        continue
            return 0.0

        kcal100 = get_attr_num(product, 'kcal_per_100g', 'kcal', 'energy_kcal', 'calories')
        protein100 = get_attr_num(product, 'protein_per_100g', 'protein')
        fat100 = get_attr_num(product, 'fat_per_100g', 'fat')
        carbs100 = get_attr_num(product, 'carbs_per_100g', 'carbs')

        factor = (amount / 100.0) if amount > 0 else 0.0
        calories = round(kcal100 * factor, 2)
        protein = round(protein100 * factor, 2)
        fat = round(fat100 * factor, 2)
        carbs = round(carbs100 * factor, 2)

        # prepare creation kwargs only for fields that actually exist on Entry model
        entry_fields = {f.name for f in Entry._meta.get_fields()}
        create_kwargs = {}
        if 'product' in entry_fields:
            create_kwargs['product'] = product
        if 'amount' in entry_fields:
            create_kwargs['amount'] = amount
        if 'calories' in entry_fields:
            create_kwargs['calories'] = calories
        if 'protein' in entry_fields:
            create_kwargs['protein'] = protein
        if 'fat' in entry_fields:
            create_kwargs['fat'] = fat
        if 'carbs' in entry_fields:
            create_kwargs['carbs'] = carbs
        # attach user if model has user FK
        if 'user' in entry_fields:
            create_kwargs['user'] = request.user if request.user.is_authenticated else None

        entry = Entry.objects.create(**create_kwargs)
    except Exception as exc:
        print('api_add_entry: failed to create entry:', exc)
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': 'Failed to create entry'}, status=500)

    # respond with only simple serializable values
    try:
        return JsonResponse({'success': True, 'entry_id': int(getattr(entry, 'pk', 0))})
    except Exception as exc:
        print('api_add_entry: failed to build JsonResponse:', exc)
        traceback.print_exc()
        return JsonResponse({'success': True, 'entry_id': 0})

@require_POST
def edit_entry(request, entry_id):
    """
    Update amount for existing FoodEntry (POST: amount).
    Redirects back to home.
    """
    entry = get_object_or_404(FoodEntry, pk=entry_id)
    try:
        amount = float(request.POST.get('amount', '0'))
        if amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
        else:
            entry.amount = amount
            entry.save()
            messages.success(request, "Entry updated.")
    except (ValueError, TypeError):
        messages.error(request, "Invalid amount.")
    return redirect('nutrition:home')

@require_POST
def delete_entry(request, entry_id):
    """
    Delete FoodEntry by id (POST).
    """
    entry = get_object_or_404(FoodEntry, pk=entry_id)
    entry.delete()
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
