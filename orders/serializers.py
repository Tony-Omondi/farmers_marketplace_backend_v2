from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, Payment, Coupon
from products.models import Product

class CartItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'created_at', 'updated_at']

class CartSerializer(serializers.ModelSerializer):
    cart_items = CartItemSerializer(many=True, read_only=True)
    coupon = serializers.PrimaryKeyRelatedField(queryset=Coupon.objects.filter(active=True), required=False, allow_null=True)

    class Meta:
        model = Cart
        fields = ['id', 'uid', 'user', 'is_paid', 'coupon', 'cart_items', 'created_at', 'updated_at']
        read_only_fields = ['user', 'is_paid', 'cart_items', 'created_at', 'updated_at']

class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'product_price', 'created_at', 'updated_at']

class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    coupon = serializers.PrimaryKeyRelatedField(queryset=Coupon.objects.filter(active=True), required=False, allow_null=True)

    class Meta:
        model = Order
        fields = ['id', 'order_id', 'user', 'payment_status', 'payment_mode', 'status', 'coupon', 'total_amount', 'order_items', 'created_at', 'updated_at']
        read_only_fields = ['user', 'order_id', 'payment_status', 'payment_mode', 'status', 'total_amount', 'order_items', 'created_at', 'updated_at']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order', 'amount', 'reference', 'payment_status', 'created_at', 'updated_at']
        read_only_fields = ['order', 'amount', 'reference', 'payment_status', 'created_at', 'updated_at']