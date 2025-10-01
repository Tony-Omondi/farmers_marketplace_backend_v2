from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem, Payment, Coupon
from products.models import Product
from accounts.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name']

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'stock']

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['coupon_code', 'discount', 'active', 'valid_from', 'valid_to']

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)  # Use full ProductSerializer for details
    quantity = serializers.IntegerField(min_value=1)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )  # Allow writing product ID for updates

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'created_at', 'updated_at']

class CartSerializer(serializers.ModelSerializer):
    cart_items = CartItemSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)
    coupon = CouponSerializer(read_only=True, allow_null=True)
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'uid', 'user', 'is_paid', 'coupon', 'cart_items', 'total_amount', 'created_at', 'updated_at']
        read_only_fields = ['id', 'uid', 'user', 'is_paid', 'cart_items', 'total_amount', 'created_at', 'updated_at']

    def get_total_amount(self, obj):
        return str(obj.get_cart_total_price_after_coupon())  # Ensure decimal is serialized as string

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_id', 'quantity', 'product_price', 'created_at', 'updated_at']

class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)
    coupon = CouponSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Order
        fields = ['id', 'order_id', 'user', 'payment_status', 'payment_mode', 'status', 'coupon', 'total_amount', 'order_items', 'created_at', 'updated_at']
        read_only_fields = ['user', 'order_id', 'payment_status', 'payment_mode', 'status', 'total_amount', 'order_items', 'created_at', 'updated_at']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'order', 'amount', 'reference', 'payment_status', 'created_at', 'updated_at']
        read_only_fields = ['order', 'amount', 'reference', 'payment_status', 'created_at', 'updated_at']