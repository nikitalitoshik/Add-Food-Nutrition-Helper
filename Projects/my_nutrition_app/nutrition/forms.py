from django import forms
from .models import Product, Profile

class FoodEntryForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.all())
    amount = forms.FloatField(min_value=0.1, label='Количество (грамм)')

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['age', 'sex', 'weight', 'height', 'activity_level', 'goal']
