from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

class FoodProduct(models.Model):
    name = models.CharField(max_length=200)
    calories = models.FloatField()
    protein = models.FloatField()
    fat = models.FloatField()
    carbs = models.FloatField()

    def __str__(self):
        return self.name


class MealEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(FoodProduct, on_delete=models.CASCADE)
    amount_grams = models.FloatField()  # сколько грамм съел
    date = models.DateField(auto_now_add=True)

    @property
    def calories_total(self):
        return self.product.calories * self.amount_grams / 100

    @property
    def protein_total(self):
        return self.product.protein * self.amount_grams / 100

    @property
    def fat_total(self):
        return self.product.fat * self.amount_grams / 100

    @property
    def carbs_total(self):
        return self.product.carbs * self.amount_grams / 100

    def __str__(self):
        return f"{self.product.name} ({self.amount_grams} g)"


class Product(models.Model):
    name = models.CharField(max_length=200)
    calories_per_100g = models.FloatField(default=0)  # kcal per 100 g
    protein_per_100g = models.FloatField(default=0)   # g per 100 g
    fat_per_100g = models.FloatField(default=0)       # g per 100 g
    carbs_per_100g = models.FloatField(default=0)     # g per 100 g

    def __str__(self):
        return self.name

class FoodEntry(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    amount = models.FloatField(help_text="grams")
    initial_amount = models.FloatField(default=0, help_text="grams - initial amount when created")
    created_at = models.DateField(default=timezone.now)

    def calories(self):
        return self.amount * self.product.calories_per_100g / 100.0

    def protein(self):
        return self.amount * self.product.protein_per_100g / 100.0

    def fat(self):
        return self.amount * self.product.fat_per_100g / 100.0

    def carbs(self):
        return self.amount * self.product.carbs_per_100g / 100.0

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    age = models.PositiveIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=1, choices=(('M','Мужской'),('F','Женский')), blank=True)
    weight = models.FloatField(null=True, blank=True, help_text='kg')
    height = models.FloatField(null=True, blank=True, help_text='cm')
    activity_level = models.CharField(
        max_length=10,
        choices=(
            ('1.2','Сидячий (мало активности)'),
            ('1.375','Легкая активность'),
            ('1.55','Умеренная активность'),
            ('1.725','Высокая активность'),
            ('1.9','Очень активный')
        ),
        blank=True
    )
    goal = models.CharField(max_length=10, choices=(('lose','Похудеть'),('maintain','Поддержать вес'),('gain','Набрать вес')), blank=True)

    def __str__(self):
        return f'Profile: {self.user}'
