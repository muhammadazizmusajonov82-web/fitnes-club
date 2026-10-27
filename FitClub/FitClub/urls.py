from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from ilovalar import views
from ilovalar.sitemaps import FitClubSitemap

sitemaps = {'fitclub': FitClubSitemap}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('register/', views.register, name='register'),
    path('accounts/register/', views.register),
    path('', views.landing_page, name='landing_page'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('home/', views.home, name='home'),
    path('trainer/<int:trainer_id>/', views.trainer_detail, name='trainer_detail'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('buy-membership/<int:plan_id>/', views.buy_membership, name='buy_membership'),
    path('payments/click/callback/', views.click_callback, name='click_callback'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
