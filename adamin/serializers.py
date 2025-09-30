from rest_framework import serializers
from accounts.models import User
from products.models import Product, Category, ProductImage
from orders.models import Order, OrderItem, Payment, Coupon

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'is_staff', 'is_active', 'date_joined']

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['email', 'full_name', 'password', 'is_staff']

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'].lower(),
            full_name=validated_data.get('full_name', ''),
            password=validated_data['password'],
            is_staff=validated_data.get('is_staff', False),
            is_active=True  # Admin-created users are active by default
        )
        return user

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.image.url) if obj.image else None

    class Meta:
        model = ProductImage
        fields = ['image']

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    images = ProductImageSerializer(many=True, read_only=True)
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock', 'category', 'images', 'created_at', 'updated_at']

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['coupon_code', 'discount', 'active', 'valid_from', 'valid_to']

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'product_price']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['reference', 'amount', 'payment_status', 'created_at', 'updated_at']

class OrderSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    coupon = CouponSerializer(allow_null=True)
    order_items = OrderItemSerializer(many=True)
    payment = PaymentSerializer(allow_null=True)
    class Meta:
        model = Order
        fields = ['order_id', 'user', 'total_amount', 'status', 'payment_status', 'payment_mode', 'coupon', 'order_items', 'payment', 'created_at', 'updated_at']

class AdminDashboardSerializer(serializers.Serializer):
    users = UserSerializer(many=True)
    products = ProductSerializer(many=True)
    orders = OrderSerializer(many=True)