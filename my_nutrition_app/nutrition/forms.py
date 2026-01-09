from django import forms
from .models import Product, Profile, FoodEntry
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class FoodEntryForm(forms.ModelForm):
    """Forma, ko izmanto, lai pievienotu jaunu `FoodEntry` no UI.

    Ietver lauku `product` (produkts) un `amount` (gramos). Widgets nodrošina
    soļus un minimālo vērtību skaitliskajam ievadam.
    """
    class Meta:
        model = FoodEntry
        fields = ['product', 'amount']
        labels = {'amount': 'Количество (грамм)'}
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.1', 'min': '0.1'}),
        }


class ProfileForm(forms.ModelForm):
    """Forma lietotāja profilam (`Profile`) — izmanto BMR/TDEE kalkulatoram.

    Lauki: `age`, `sex`, `weight`, `height`, `activity_level`, `goal`.
    """
    class Meta:
        model = Profile
        fields = ['age', 'sex', 'weight', 'height', 'activity_level', 'goal']
        widgets = {
            'age': forms.NumberInput(attrs={'min': '1', 'step': '1'}),
            'weight': forms.NumberInput(attrs={'min': '1', 'step': '0.1'}),
            'height': forms.NumberInput(attrs={'min': '1', 'step': '0.1'}),
        }

    def clean(self):
        cleaned = super().clean()
        age = cleaned.get('age')
        weight = cleaned.get('weight')
        height = cleaned.get('height')
        errors = {}
        if age is not None and age <= 0:
            errors['age'] = forms.ValidationError('Age must be a positive number.')
        if weight is not None and weight <= 0:
            errors['weight'] = forms.ValidationError('Weight must be a positive number.')
        if height is not None and height <= 0:
            errors['height'] = forms.ValidationError('Height must be a positive number.')
        if errors:
            raise forms.ValidationError(errors)
        return cleaned


class SignUpForm(UserCreationForm):
    """Reģistrācijas forma, paplašinot Django `UserCreationForm` ar email lauku.

    Metode `clean_email` nodrošina, ka e-pasts nav jau reģistrēts sistēmā.
    """
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            # Validācijas kļūda, ja e-pasts jau eksistē
            raise forms.ValidationError('Email already registered.')
        return email


class ProductForm(forms.ModelForm):
    """Formas definīcija administratora lietošanai produktu saraksta pārvaldībai.

    Lauki ietver nosaukumu un uzturvielu vērtības uz 100 g. Widgets satur
    vienkāršas atribūtu norādes front-end atveidei.
    """
    class Meta:
        model = Product
        fields = ['name', 'calories_per_100g', 'protein_per_100g', 'fat_per_100g', 'carbs_per_100g']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Apple', 'class': 'form-input'}),
            'calories_per_100g': forms.NumberInput(attrs={'step': '0.1', 'class': 'form-input'}),
            'protein_per_100g': forms.NumberInput(attrs={'step': '0.1', 'class': 'form-input'}),
            'fat_per_100g': forms.NumberInput(attrs={'step': '0.1', 'class': 'form-input'}),
            'carbs_per_100g': forms.NumberInput(attrs={'step': '0.1', 'class': 'form-input'}),
        }
