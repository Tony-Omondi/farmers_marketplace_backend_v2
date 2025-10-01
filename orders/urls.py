from django.urls import path
from .views import (
    CartListCreateView,
    CartItemListCreateView,
    CartItemDetailView,
    ApplyCouponView,
    OrderListCreateView,
    OrderDetailView,
    InitiatePaymentView,
    PaymentCallbackView,
    AdminCartListView,
    AdminCartDetailView,
)

app_name = 'orders'

urlpatterns = [
    path('carts/', CartListCreateView.as_view(), name='cart-list-create'),
    path('cart-items/', CartItemListCreateView.as_view(), name='cart-item-list-create'),
    path('cart-items/<int:pk>/', CartItemDetailView.as_view(), name='cart-item-detail'),
    path('carts/apply-coupon/', ApplyCouponView.as_view(), name='apply-coupon'),
    path('orders/', OrderListCreateView.as_view(), name='order-list-create'),
    path('orders/<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('orders/payment/initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path('orders/payment/callback/', PaymentCallbackView.as_view(), name='payment-callback'),
    path('adamin/carts/', AdminCartListView.as_view(), name='admin-cart-list'),
    path('adamin/carts/<str:cart_id>/', AdminCartDetailView.as_view(), name='admin-cart-detail'),
]