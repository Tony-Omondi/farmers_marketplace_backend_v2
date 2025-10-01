from django.urls import path
from .views import (
    AdminDashboardView, ProductListCreateView, CategoryListView,
    OrderListView, PaymentListView, UserSearchView, OrderCreateView,
    CreateCategoryView, OrderDetailView, UserCreateView, FarmerSalesView,
    FarmerListView, AdminCartListView, AdminCartDetailView
)

urlpatterns = [
    path('products/', ProductListCreateView.as_view(), name='admin-product-list-create'),
    path('categories/', CategoryListView.as_view(), name='admin-category-list'),
    path('orders/', OrderListView.as_view(), name='admin-order-list'),
    path('orders/<str:order_id>/', OrderDetailView.as_view(), name='order-detail'),
    path('payments/', PaymentListView.as_view(), name='admin-payment-list'),
    path('users/', UserSearchView.as_view(), name='admin-user-search'),
    path('orders/create/', OrderCreateView.as_view(), name='admin-order-create'),
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('categories/create/', CreateCategoryView.as_view(), name='admin-category-create'),
    path('users/create/', UserCreateView.as_view(), name='admin-user-create'),
    path('farmers/sales/', FarmerSalesView.as_view(), name='admin-farmer-sales'),
    path('farmers/', FarmerListView.as_view(), name='farmer-list'),
    path('carts/', AdminCartListView.as_view(), name='admin-cart-list'),
    path('carts/<str:cart_id>/', AdminCartDetailView.as_view(), name='admin-cart-detail'),
]