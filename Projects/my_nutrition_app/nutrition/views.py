from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import Product, FoodEntry, Profile
from .forms import FoodEntryForm, ProfileForm
import json
from django.db.models import Sum

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
    Этот view ожидает POST с 'product' (id) и 'amount' (граммы).
    Создаёт FoodEntry и редиректит на домашнюю страницу.
    """
    if request.method == 'POST':
        product_id = request.POST.get('product')
        amount = request.POST.get('amount')
        try:
            product = Product.objects.get(pk=product_id)
            amount_val = float(amount)
            if amount_val > 0:
                FoodEntry.objects.create(product=product, amount=amount_val)
        except Exception:
            # ненужные данные или ошибка — просто перенаправим на главную
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
