from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, CategoryViewSet, FarmerSalesView, ProductImageDeleteView

router = DefaultRouter()
router.register(r"products", ProductViewSet)
router.register(r"categories", CategoryViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("farmers/sales/", FarmerSalesView.as_view(), name='farmer-sales'),
    path("products/<int:id>/delete-image/", ProductImageDeleteView.as_view(), name='product-image-delete'),
]