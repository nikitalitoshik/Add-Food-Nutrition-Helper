
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.i18n import JavaScriptCatalog
from nutrition import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('add-meal/', views.add_meal, name='add_meal'),
    path('nutrition/', include('nutrition.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    # JavaScript translations catalog (used by client-side gettext calls)
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
