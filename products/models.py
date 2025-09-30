from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Farmer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farmer_profile')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Farmer: {self.user.full_name} ({self.user.email})"

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    farmer = models.ForeignKey(Farmer, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    is_displayed = models.BooleanField(default=False, help_text="If true, product is visible but non-clickable on frontend")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")

    def __str__(self):
        return f"Image for {self.product.name}"