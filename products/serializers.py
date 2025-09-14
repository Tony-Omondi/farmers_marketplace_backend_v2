# products/serializers.py
from rest_framework import serializers
from .models import Product, ProductImage, Category

class ProductImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.image.url) if obj.image else None

    class Meta:
        model = ProductImage
        fields = ["id", "image"]

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    image_files = serializers.ListField(child=serializers.ImageField(), write_only=True, required=False)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), allow_null=True)

    class Meta:
        model = Product
        fields = ["id", "name", "description", "price", "stock", "category", "images", "image_files", "created_at", "updated_at"]

    def create(self, validated_data):
        image_files = validated_data.pop('image_files', [])
        product = Product.objects.create(**validated_data)
        for image_file in image_files:
            ProductImage.objects.create(product=product, image=image_file)
        return product

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]