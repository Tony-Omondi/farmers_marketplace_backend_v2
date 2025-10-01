from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from orders.views import PaymentCallbackView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path('api/orders/', include('orders.urls', namespace='orders')),
    path('api/', include('products.urls')),
    path('api/adamin/', include('adamin.urls')),
    path('payment-callback/', PaymentCallbackView.as_view(), name='payment-callback'),
]

# Serve static & media files during development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Serve React app for SPA routes
urlpatterns += [
    re_path(r'^(?!api/).*', TemplateView.as_view(template_name='index.html'), name='app'),
]