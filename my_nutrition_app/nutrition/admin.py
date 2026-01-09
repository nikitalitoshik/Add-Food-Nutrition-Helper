from django.contrib import admin
from .models import Product, FoodEntry, Profile, Entry


"""
Admin interfeisa konfigurācijas `nutrition` lietotnei.

Šeit reģistrējam modeļus Django admin panelī un norādām, kuri lauki
ir redzami sarakstā (`list_display`), pēc kā meklēt (`search_fields`)
un kādus filtrus piedāvāt (`list_filter`).
"""


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Rāda svarīgākos laukus produktu sarakstā
    list_display = ('name', 'calories_per_100g', 'protein_per_100g', 'fat_per_100g', 'carbs_per_100g')
    search_fields = ('name',)
    list_filter = ('calories_per_100g',)


@admin.register(FoodEntry)
class FoodEntryAdmin(admin.ModelAdmin):
    # FoodEntry admin skatā ērti redzams lietotājs, produkts, daudzums un laiks
    list_display = ('user', 'product', 'amount', 'created_at', 'calories')
    list_filter = ('created_at',)
    search_fields = ('product__name',)
    readonly_fields = ('created_at',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # Profilu admin saraksts — viegli pārskatīt svaru/augumu/mērķi
    list_display = ('user', 'age', 'weight', 'height', 'goal')
    search_fields = ('user__username',)
    list_filter = ('goal', 'sex')


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    # Pielāgoto ierakstu saraksts adminā
    list_display = ('user', 'name', 'amount', 'kcal', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('name',)
