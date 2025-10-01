from rest_framework import generics, serializers
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from orders.models import Order, OrderItem, Payment, Coupon, Cart, CartItem
from products.models import Product, Category, Farmer
from products.serializers import ProductSerializer, CategorySerializer, FarmerSerializer
from .serializers import OrderSerializer, PaymentSerializer, AdminDashboardSerializer, UserCreateSerializer
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid
import logging
from django.db.models import Sum, Count, Max, ExpressionWrapper, DecimalField, F
from django.utils import timezone
from datetime import timedelta
from orders.serializers import CartSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

# Existing views (unchanged)
class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            users = User.objects.all()
            products = Product.objects.all().select_related('category', 'farmer').prefetch_related('images')
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
    queryset = Product.objects.all().select_related('category', 'farmer').prefetch_related('images')
    serializer_class = ProductSerializer
    filterset_fields = ['category', 'farmer', 'is_displayed']
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
                if product.is_displayed:
                    return Response({"status": False, "message": f"Product {product.name} is display-only and cannot be ordered"}, status=status.HTTP_400_BAD_REQUEST)
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

class FarmerSalesView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            base_queryset = OrderItem.objects.filter(
                order__status__in=['confirmed', 'paid', 'shipped', 'delivered'],
                product__farmer__isnull=False
            )
            now = timezone.now()
            periods = {
                'past_day': now - timedelta(days=1),
                'past_week': now - timedelta(days=7),
                'past_month': now - timedelta(days=30),
                'past_year': now - timedelta(days=365),
            }
            if start_date and end_date:
                from django.utils.dateparse import parse_date
                start_date = parse_date(start_date)
                end_date = parse_date(end_date)
                if start_date and end_date:
                    base_queryset = base_queryset.filter(order__created_at__date__range=[start_date, end_date])
            sales_data = {}
            for period, start_time in periods.items():
                period_queryset = base_queryset.filter(order__created_at__gte=start_time) if not (start_date and end_date) else base_queryset
                period_sales = period_queryset.values(
                    'product__farmer__id',
                    'product__farmer__user__email',
                    'product__farmer__user__full_name'
                ).annotate(
                    total_sales=ExpressionWrapper(
                        Sum(F('quantity') * F('product_price')),
                        output_field=DecimalField(max_digits=10, decimal_places=2)
                    ),
                    order_count=Count('order'),
                    last_sale_date=Max('order__created_at')
                )
                sales_data[period] = [
                    {
                        'farmer_id': item['product__farmer__id'],
                        'email': item['product__farmer__user__email'],
                        'full_name': item['product__farmer__user__full_name'],
                        'total_sales': float(item['total_sales']) if item['total_sales'] is not None else 0.0,
                        'order_count': item['order_count'],
                        'last_sale_date': item['last_sale_date'].isoformat() if item['last_sale_date'] else None
                    }
                    for item in period_sales
                ]
            if start_date and end_date:
                sales_data['custom'] = sales_data['past_day']
                del sales_data['past_day']
            logger.info(f"Farmer sales data fetched by {request.user.email}")
            return Response(sales_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching farmer sales data: {str(e)}")
            return Response({'detail': f'Error fetching farmer sales data: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FarmerListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            farmers = Farmer.objects.select_related('user').filter(is_active=True).values(
                'id', 'user__email', 'user__full_name'
            )
            data = [
                {
                    'id': farmer['id'],
                    'email': farmer['user__email'],
                    'full_name': farmer['user__full_name']
                }
                for farmer in farmers
            ]
            logger.info(f"Farmers fetched by {request.user.email}")
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching farmers: {str(e)}")
            return Response({'detail': 'Error fetching farmers'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# New views for admin cart management
class AdminCartListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            carts = Cart.objects.filter(is_paid=False).select_related('user', 'coupon').prefetch_related('cart_items__product')
            serializer = CartSerializer(carts, many=True, context={'request': request})
            logger.info(f"Unpaid carts fetched by {request.user.email}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching unpaid carts: {str(e)}")
            return Response({'detail': 'Error fetching carts'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminCartDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, cart_id):
        try:
            cart = Cart.objects.select_related('user', 'coupon').prefetch_related('cart_items__product').get(uid=cart_id, is_paid=False)
            serializer = CartSerializer(cart, context={'request': request})
            logger.info(f"Cart details for {cart_id} fetched by {request.user.email}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Cart.DoesNotExist:
            logger.warning(f"Cart {cart_id} not found for {request.user.email}")
            return Response({'detail': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error fetching cart details for {cart_id}: {str(e)}")
            return Response({'detail': 'Error fetching cart details'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, cart_id):
        try:
            cart = Cart.objects.get(uid=cart_id, is_paid=False)
            items = request.data.get('items', [])
            coupon_code = request.data.get('coupon_code', '')

            # Validate items
            for item in items:
                product = Product.objects.get(id=item['product_id'])
                if item['quantity'] > product.stock:
                    return Response({
                        "status": False,
                        "message": f"Insufficient stock for {product.name}. Available: {product.stock}"
                    }, status=status.HTTP_400_BAD_REQUEST)

            # Update coupon
            if coupon_code:
                try:
                    coupon = Coupon.objects.get(coupon_code=coupon_code, active=True)
                    cart.coupon = coupon
                except Coupon.DoesNotExist:
                    return Response({"status": False, "message": "Invalid or inactive coupon"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                cart.coupon = None

            # Update cart items
            cart.cart_items.all().delete()
            for item in items:
                product = Product.objects.get(id=item['product_id'])
                CartItem.objects.create(
                    cart=cart,
                    product=product,
                    quantity=item['quantity']
                )

            cart.save()
            serializer = CartSerializer(cart, context={'request': request})
            logger.info(f"Cart {cart_id} updated by {request.user.email}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Cart.DoesNotExist:
            logger.warning(f"Cart {cart_id} not found for {request.user.email}")
            return Response({'detail': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)
        except Product.DoesNotExist:
            return Response({"status": False, "message": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error updating cart {cart_id}: {str(e)}")
            return Response({'detail': f'Error updating cart: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)