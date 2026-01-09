from django.apps import AppConfig


"""
App konfigurācija lietotnei `nutrition`.

Šis fails nosaka Django AppConfig klasi, kur var iestatīt lietotnes
metadata un noklusējuma lauku tipu datubāzē.
"""


class NutritionConfig(AppConfig):
    # Noklusējuma lauka tips modeļiem (BigAutoField labāk lielākiem ID diapazoniem)
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nutrition'
