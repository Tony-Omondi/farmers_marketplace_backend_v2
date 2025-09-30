from rest_framework import generics, serializers
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from orders.models import Order, OrderItem, Payment, Coupon
from .serializers import OrderSerializer, PaymentSerializer, AdminDashboardSerializer, UserCreateSerializer
from products.models import Product, Category
from products.serializers import ProductSerializer, CategorySerializer
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            users = User.objects.all()
            products = Product.objects.all().select_related('category').prefetch_related('images')
            orders = Order.objects.all().select_related('user', 'coupon', 'payment').prefetch_related('order_items__product')
            data = {
                'users': users,
                'products': products,
                'orders': orders,
            }
            serializer = AdminDashboardSerializer(data, context={'request': request})
            logger.info(f"Admin dashboard data fetched for {request.user.email}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching admin dashboard data: {str(e)}")
            return Response({'detail': 'Error fetching data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateCategoryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        try:
            serializer = CategorySerializer(data=request.data)
            if serializer.is_valid():
                category = serializer.save()
                logger.info(f"Category {category.name} created by {request.user.email}")
                return Response({'message': 'Category created successfully'}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating category: {str(e)}")
            return Response({'detail': 'Error creating category'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ['category']
    search_fields = ['name', 'description']

class CategoryListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class OrderListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    filterset_fields = ['status', 'payment_status']
    search_fields = ['order_id', 'user__email']

class PaymentListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    search_fields = ['reference', 'order__order_id']

class UserSearchView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    serializer_class = serializers.Serializer
    def get(self, request):
        email = request.query_params.get('email', '')
        users = User.objects.filter(email__icontains=email, is_active=True)
        return Response([{'email': user.email, 'full_name': user.full_name} for user in users])

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, order_id):
        try:
            order = Order.objects.select_related('user', 'coupon', 'payment').prefetch_related('order_items__product').get(order_id=order_id)
            serializer = OrderSerializer(order, context={'request': request})
            logger.info(f"Order details for {order_id} fetched by {request.user.email}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            logger.warning(f"Order {order_id} not found for {request.user.email}")
            return Response({'detail': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching order details for {order_id}: {str(e)}")
            return Response({'detail': 'Error fetching order details'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OrderCreateView(APIView):
    permission_classes = [IsAdminUser]
    def post(self, request):
        user_email = request.data.get('user_email')
        items = request.data.get('items', [])
        coupon_code = request.data.get('coupon_code')
        payment_mode = request.data.get('payment_mode', 'Cash')
        try:
            user = User.objects.get(email=user_email, is_active=True)
            total_amount = 0
            for item in items:
                product = Product.objects.get(id=item['product_id'])
                total_amount += Decimal(product.price) * item['quantity']
            if coupon_code:
                coupon = Coupon.objects.get(coupon_code=coupon_code, active=True)
                total_amount -= Decimal(coupon.discount)
            order = Order.objects.create(
                user=user,
                order_id=str(uuid.uuid4()),
                payment_status="completed" if payment_mode == "Cash" else "pending",
                payment_mode=payment_mode,
                status="confirmed",
                coupon=coupon if coupon_code else None,
                total_amount=max(total_amount, 0)
            )
            for item in items:
                product = Product.objects.get(id=item['product_id'])
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item['quantity'],
                    product_price=Decimal(product.price)
                )
                product.stock -= item['quantity']
                product.save()
            if payment_mode == "Cash":
                Payment.objects.create(
                    order=order,
                    amount=total_amount,
                    payment_status="completed",
                    reference=str(uuid.uuid4())
                )
            return Response({"status": True, "order_id": order.order_id}, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({"status": False, "message": "User not found or not active"}, status=status.HTTP_404_NOT_FOUND)
        except Product.DoesNotExist:
            return Response({"status": False, "message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        except Coupon.DoesNotExist:
            return Response({"status": False, "message": "Invalid or inactive coupon"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UserCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        try:
            serializer = UserCreateSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                logger.info(f"User {user.email} created by admin {request.user.email}")
                return Response({'message': 'User created successfully', 'email': user.email}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return Response({'detail': 'Error creating user'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)