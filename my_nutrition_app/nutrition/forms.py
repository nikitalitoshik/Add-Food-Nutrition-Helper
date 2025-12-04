from django import forms
from .models import Product, Profile
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class FoodEntryForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all())
    amount = forms.FloatField(min_value=0.1, label='Количество (грамм)')

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['age', 'sex', 'weight', 'height', 'activity_level', 'goal']

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already registered.')
        return email

class ProductForm(forms.ModelForm):
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
