from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.utils.translation import gettext_lazy as _


"""
Modeļu definīcijas lietotnei `nutrition`.

Šeit ir trīs galvenie modeļi:
- `Product` — saglabā produktu nosaukumu un makro/enerģijas vērtības uz 100g;
- `FoodEntry` — saistīts ar `Product`, glabā lietotāja (vai publisku) ēdienreizi un aprēķina
  makro/kalorijas atbilstoši apēstajiem gramiem;
- `Entry` — lietotāja pielāgots ieraksts (neobligāti ar per-100g bāzēm), kuru var radīt/rediģēt
  caur API.

"""


class Product(models.Model):
    """Produkts ar uzturvielu bāzēm uz 100 g."""
    name = models.CharField(max_length=200)
    calories_per_100g = models.FloatField(default=0)  # kcal uz 100 g
    protein_per_100g = models.FloatField(default=0)   # proteīns (g) uz 100 g
    fat_per_100g = models.FloatField(default=0)       # tauki (g) uz 100 g
    carbs_per_100g = models.FloatField(default=0)     # ogļhidrāti (g) uz 100 g

    def __str__(self):
        return self.name


class FoodEntry(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    # saistība ar lietotāju — ja null, ieraksts ir publisks/anonīms
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    amount = models.FloatField(help_text="grams")
    initial_amount = models.FloatField(default=0, help_text="grams - initial amount when created")
    # Laiks, kad ieraksts izveidots
    created_at = models.DateTimeField(auto_now_add=True)

    # Aprēķina enerģiju un makro atbilstoši `amount` un produkta per-100g bāzēm
    def calories(self):
        return self.amount * self.product.calories_per_100g / 100.0

    def protein(self):
        return self.amount * self.product.protein_per_100g / 100.0

    def fat(self):
        return self.amount * self.product.fat_per_100g / 100.0

    def carbs(self):
        return self.amount * self.product.carbs_per_100g / 100.0

    def __str__(self):
        return f"{self.product.name} — {self.amount}g"


class Profile(models.Model):
    """Lietotāja profils: pamatdati, kas nepieciešami kalkulatoriem (BMR/TDEE).

    Lauki ietver vecumu, dzimumu, svaru, garumu, aktivitātes līmeni un mērķi.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    age = models.PositiveIntegerField(null=True, blank=True)
    sex = models.CharField(
        max_length=1,
        choices=(
            ('M', _('Male')),
            ('F', _('Female')),
        ),
        blank=True,
    )
    weight = models.FloatField(null=True, blank=True, help_text=_('kg'))
    height = models.FloatField(null=True, blank=True, help_text=_('cm'))
    activity_level = models.CharField(
        max_length=10,
        choices=(
            ('1.2', _('Sedentary (low activity)')),
            ('1.375', _('Light activity')),
            ('1.55', _('Moderate activity')),
            ('1.725', _('High activity')),
            ('1.9', _('Very active')),
        ),
        blank=True,
    )
    goal = models.CharField(
        max_length=10,
        choices=(
            ('lose', _('Lose weight')),
            ('maintain', _('Maintain weight')),
            ('gain', _('Gain weight')),
        ),
        blank=True,
    )

    def __str__(self):
        return _('Profile: %(user)s') % {'user': self.user}


class Entry(models.Model):
    """Pielāgots lietotāja ieraksts — izmantojams caur API un UI.

    Šis modelis satur gan per-entry laukus (`kcal`, `protein` utt.), gan
    (neobligātas) per-100g bāzes, kuras izmanto, lai droši pārrēķinātu
    vērtības, ja tiek mainīts `amount`.
    """
    # Lietotāja saistība: katrs Entry pieder konkrētam lietotājam
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='entries')
    name = models.CharField(max_length=255)
    amount = models.FloatField(default=100.0)  # grams
    # Per-entry uzglabātas vērtības (ko rāda klients)
    kcal = models.FloatField(default=0.0)
    protein = models.FloatField(default=0.0)
    fat = models.FloatField(default=0.0)
    carbs = models.FloatField(default=0.0)
    # Neobligātas, autoritatīvas per-100g bāzes, kas palīdz pārrēķinos
    kcal_per100 = models.FloatField(default=0.0)
    protein_per100 = models.FloatField(default=0.0)
    fat_per100 = models.FloatField(default=0.0)
    carbs_per100 = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.amount}g) — {self.kcal} kcal"
