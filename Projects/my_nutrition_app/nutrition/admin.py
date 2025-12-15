from django.contrib import admin
from .models import Product, FoodEntry, Profile, Entry

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'calories_per_100g', 'protein_per_100g', 'fat_per_100g', 'carbs_per_100g')
    search_fields = ('name',)
    list_filter = ('calories_per_100g',)

@admin.register(FoodEntry)
class FoodEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'amount', 'created_at', 'calories')
    list_filter = ('created_at',)
    search_fields = ('product__name',)
    readonly_fields = ('created_at',)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'age', 'weight', 'height', 'goal')
    search_fields = ('user__username',)
    list_filter = ('goal', 'sex')

@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'amount', 'kcal', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('name',)
