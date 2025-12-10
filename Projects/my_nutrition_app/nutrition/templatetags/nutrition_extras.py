from django import template

register = template.Library()

@register.filter
def kcal_from_macros(entry):
    """
    Return entry.calories if positive, otherwise compute from macros:
    calories = protein*4 + fat*9 + carbs*4
    Works if `entry` is a model instance or a mapping with attributes/keys.
    """
    try:
        # support attribute or dict-like access
        def get(v, name):
            if hasattr(v, name):
                return getattr(v, name) or 0
            try:
                return v.get(name, 0) or 0
            except Exception:
                return 0

        kcal = float(get(entry, 'calories') or 0)
        if kcal and kcal > 0:
            return kcal
        protein = float(get(entry, 'protein') or 0)
        fat = float(get(entry, 'fat') or 0)
        carbs = float(get(entry, 'carbs') or 0)
        computed = protein * 4.0 + fat * 9.0 + carbs * 4.0
        # round to 2 decimals for display
        return round(computed, 2)
    except Exception:
        return ''
