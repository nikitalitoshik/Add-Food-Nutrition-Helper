from django.urls import path, include
from . import views

app_name = 'nutrition'

urlpatterns = [
    path('', views.home, name='home'),
    path('profile/', views.profile, name='profile'),
    path('add-meal/', views.add_meal, name='add_meal'),
    path('calculator/', views.calculator, name='calculator'),
    path('progress/', views.progress, name='progress'),
    # добавить стандартные маршруты авторизации (login, logout, password)
    path('accounts/', include('django.contrib.auth.urls')),
]
