from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

app_name = 'nutrition'

urlpatterns = [
    # явные пути для удобной ссылки из шаблонов: {% url 'nutrition:login' %} и {% url 'nutrition:logout' %}
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='nutrition:home'), name='logout'),

    path('', views.home, name='home'),
    path('profile/', views.profile, name='profile'),
    path('add-meal/', views.add_meal, name='add_meal'),
    path('calculator/', views.calculator, name='calculator'),
    path('progress/', views.progress, name='progress'),
    # добавить стандартные маршруты авторизации (login, logout, password)
    path('accounts/', include('django.contrib.auth.urls')),
    # добавить регистрацию
    path('signup/', views.signup, name='signup'),
    path('products/', views.products, name='products'),
    # new API endpoints
    path('api/product-search/', views.api_product_search, name='api_product_search'),
    path('api/product-lookup/', views.api_product_lookup, name='api_product_lookup'),
    path('api/add-entry/', views.api_add_entry, name='api_add_entry'),
    # редактирование и удаление записей
    path('entry/<int:entry_id>/edit/', views.edit_entry, name='edit_entry'),
    path('entry/<int:entry_id>/delete/', views.delete_entry, name='delete_entry'),
]
