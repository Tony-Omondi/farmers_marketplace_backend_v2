from django.contrib import admin
from .models import Cart, CartItem, Coupon, Order, OrderItem, Payment


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("uid", "user", "is_paid", "coupon", "created_at", "updated_at")
    list_filter = ("is_paid", "created_at", "updated_at")
    search_fields = ("uid", "user__email")
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "quantity", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("cart__uid", "product__name")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("coupon_code", "discount", "active", "valid_from", "valid_to")
    list_filter = ("active", "valid_from", "valid_to")
    search_fields = ("coupon_code",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_id", "user", "status", "payment_status", "total_amount", "created_at")
    list_filter = ("status", "payment_status", "created_at", "updated_at")
    search_fields = ("order_id", "user__email")
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "product_price", "created_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("order__order_id", "product__name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "order", "amount", "payment_status", "created_at")
    list_filter = ("payment_status", "created_at", "updated_at")
    search_fields = ("reference", "order__order_id")
