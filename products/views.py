from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser,  IsAuthenticated
from rest_framework import status
from .models import Product, Category, Farmer
from .serializers import ProductSerializer, CategorySerializer, FarmerSerializer
from orders.models import OrderItem
from django.db.models import Sum, F, DecimalField
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.all().select_related('category', 'farmer').prefetch_related('images').order_by("-created_at")
    serializer_class = ProductSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class FarmerSalesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            # Aggregate total sales per farmer
            sales_data = OrderItem.objects.filter(
                product__farmer__isnull=False
            ).values(
                'product__farmer__id',
                'product__farmer__user__email',
                'product__farmer__user__full_name'
            ).annotate(
                total_sales=Sum(F('quantity') * F('product_price'), output_field=DecimalField())
            ).order_by('-total_sales')

            # Serialize the data
            response_data = [
                {
                    'farmer_id': item['product__farmer__id'],
                    'email': item['product__farmer__user__email'],
                    'full_name': item['product__farmer__user__full_name'],
                    'total_sales': float(item['total_sales'])
                }
                for item in sales_data
            ]

            logger.info(f"Farmer sales data fetched by {request.user.email}")
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching farmer sales data: {str(e)}")
            return Response({'detail': 'Error fetching farmer sales data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)