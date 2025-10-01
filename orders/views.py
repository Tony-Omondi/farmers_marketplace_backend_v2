from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Cart, CartItem, Order, OrderItem, Payment, Coupon
from products.models import Product
from .serializers import CartSerializer, CartItemSerializer, OrderSerializer, PaymentSerializer
from django.conf import settings
from django.core.mail import send_mail
from rest_framework import serializers
from django.contrib.auth import get_user_model
import requests
import hmac
import hashlib
import logging
from decimal import Decimal
import uuid

logger = logging.getLogger(__name__)
User = get_user_model()

# Existing views (unchanged)
class CartListCreateView(generics.ListCreateAPIView):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user, is_paid=False)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class CartItemListCreateView(generics.ListCreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user, cart__is_paid=False)

    def perform_create(self, serializer):
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']
        cart, _ = Cart.objects.get_or_create(user=self.request.user, is_paid=False)
        if quantity > product.stock:
            raise serializers.ValidationError({"quantity": f"Insufficient stock. Available: {product.stock}"})
        serializer.save(cart=cart)

class CartItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user, cart__is_paid=False)

    def perform_update(self, serializer):
        instance = serializer.instance
        product = instance.product
        quantity = serializer.validated_data.get('quantity')
        if quantity is not None and quantity > product.stock:
            raise serializers.ValidationError({"quantity": f"Insufficient stock. Available: {product.stock}"})
        serializer.save()

class ApplyCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart = Cart.objects.filter(user=request.user, is_paid=False).first()
        if not cart:
            return Response({"error": "No active cart found."}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = CartSerializer(cart, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class OrderListCreateView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        cart = Cart.objects.filter(user=self.request.user, is_paid=False).first()
        if not cart or not cart.cart_items.exists():
            raise serializers.ValidationError({"cart": "Cart is empty."})
        
        total_amount = Decimal('0.00')
        for item in cart.cart_items.all():
            if item.quantity > item.product.stock:
                raise serializers.ValidationError({
                    "items": f"Insufficient stock for {item.product.name}. Available: {item.product.stock}"
                })
            price = Decimal(item.product.price)
            total_amount += price * item.quantity
        
        order = serializer.save(
            user=self.request.user,
            coupon=cart.coupon,
            total_amount=total_amount
        )
        
        for item in cart.cart_items.all():
            price = Decimal(item.product.price)
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                product_price=price
            )
            item.product.stock -= item.quantity
            item.product.save()
        
        cart.cart_items.all().delete()
        cart.coupon = None
        cart.save()

class OrderDetailView(generics.RetrieveUpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.all()
        return Order.objects.filter(user=self.request.user)

class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(f"Payment initiation started for user: {request.user.email}")
        cart_id = request.data.get('cart_id')
        cart = None
        if cart_id and request.user.is_staff:
            try:
                cart = Cart.objects.get(uid=cart_id, is_paid=False)
            except Cart.DoesNotExist:
                logger.error(f"Cart not found: cart_id={cart_id}")
                return Response({"status": False, "message": "Cart not found"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            cart = Cart.objects.filter(user=self.request.user, is_paid=False).first()
        
        if not cart or not cart.cart_items.exists():
            logger.error("Cart is empty or not found")
            return Response({"status": False, "message": "Your cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

        for item in cart.cart_items.all():
            if item.quantity > item.product.stock:
                logger.error(f"Insufficient stock for {item.product.name}. Available: {item.product.stock}")
                return Response({
                    "status": False,
                    "message": f"Insufficient stock for {item.product.name}. Available: {item.product.stock}"
                }, status=status.HTTP_400_BAD_REQUEST)

        amount = int(cart.get_cart_total_price_after_coupon() * 100)
        if amount <= 0:
            logger.error("Invalid cart total")
            return Response({"status": False, "message": "Invalid cart total"}, status=status.HTTP_400_BAD_REQUEST)

        data = {
            "email": cart.user.email,
            "amount": amount,
            "callback_url": 'http://localhost:5173/payment-callback',
            "metadata": {
                "cart_id": str(cart.uid),
                "custom_fields": [
                    {
                        "display_name": "Cart Items",
                        "variable_name": "cart_items",
                        "value": ", ".join([item.product.name for item in cart.cart_items.all()])
                    }
                ]
            }
        }

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        try:
            logger.info(f"Sending Paystack request: {data}")
            response = requests.post(settings.PAYSTACK_INITIALIZE_URL, headers=headers, json=data)
            logger.info(f"Paystack response: status={response.status_code}, body={response.text}")
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status'):
                    logger.info(f"Payment initiated successfully: {response_data['data']['reference']}")
                    return Response({
                        'status': True,
                        'authorization_url': response_data['data']['authorization_url'],
                        'reference': response_data['data']['reference']
                    })
                logger.error(f"Paystack error: {response_data.get('message', 'Unknown error')}")
                return Response({
                    'status': False,
                    'message': response_data.get('message', 'Payment initialization failed')
                }, status=status.HTTP_400_BAD_REQUEST)
            logger.error(f"Paystack request failed: status={response.status_code}, body={response.text}")
            return Response({
                'status': False,
                'message': response.json().get('message', 'Payment initialization failed')
            }, status=response.status_code)
        except Exception as e:
            logger.error(f"Payment initiation error: {str(e)}", exc_info=True)
            return Response({
                'status': False,
                'message': f"Payment initiation error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PaymentCallbackView(APIView):
    permission_classes = []

    def get(self, request):
        reference = request.query_params.get('reference')
        if not reference:
            logger.error("No reference provided for payment callback")
            return Response({"status": False, "message": "Payment verification failed"}, status=status.HTTP_400_BAD_REQUEST)

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        try:
            logger.info(f"Verifying Paystack payment: reference={reference}")
            response = requests.get(f"{settings.PAYSTACK_VERIFY_URL}{reference}", headers=headers)
            logger.info(f"Paystack verify response: status={response.status_code}, body={response.text}")
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') and response_data['data']['status'] == 'success':
                    cart_id = response_data['data']['metadata']['cart_id']
                    try:
                        cart = Cart.objects.get(uid=cart_id, is_paid=False)
                    except Cart.DoesNotExist:
                        logger.error(f"Cart not found: cart_id={cart_id}")
                        return Response({"status": False, "message": "Cart not found"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    email = response_data['data']['customer']['email']
                    try:
                        user = User.objects.get(email=email)
                    except User.DoesNotExist:
                        logger.error(f"User not found: email={email}")
                        return Response({"status": False, "message": "User not found"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    for item in cart.cart_items.all():
                        if item.quantity > item.product.stock:
                            logger.error(f"Insufficient stock for {item.product.name}. Available: {item.product.stock}")
                            return Response({
                                "status": False,
                                "message": f"Insufficient stock for {item.product.name}. Available: {item.product.stock}"
                            }, status=status.HTTP_400_BAD_REQUEST)
                    
                    total_amount = Decimal('0.00')
                    for item in cart.cart_items.all():
                        price = Decimal(item.product.price)
                        total_amount += price * item.quantity
                    
                    paystack_amount = Decimal(response_data['data']['amount']) / 100
                    if total_amount != paystack_amount:
                        logger.error(f"Amount mismatch: calculated={total_amount}, Paystack={paystack_amount}")
                        return Response({"status": False, "message": "Amount mismatch"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    order = Order.objects.create(
                        user=user,
                        order_id=str(uuid.uuid4()),
                        payment_status="completed",
                        payment_mode="Paystack",
                        status="confirmed",
                        coupon=cart.coupon,
                        total_amount=total_amount
                    )
                    
                    for item in cart.cart_items.all():
                        price = Decimal(item.product.price)
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            quantity=item.quantity,
                            product_price=price
                        )
                        item.product.stock -= item.quantity
                        item.product.save()

                    payment = Payment.objects.create(
                        order=order,
                        amount=total_amount,
                        reference=reference,
                        payment_status="completed"
                    )
                    cart.is_paid = True
                    cart.cart_items.all().delete()
                    cart.coupon = None
                    cart.save()

                    items = OrderItem.objects.filter(order=order)
                    item_list = "\n".join([f"- {item.product.name} (Qty: {item.quantity}, Price: KSh {item.product_price:.2f})" for item in items])
                    subject = f"Order Confirmation: {order.order_id}"
                    message = (
                        f"Dear {user.email},\n\n"
                        f"Thank you for your order!\n\n"
                        f"Order ID: {order.order_id}\n"
                        f"Total Amount: KSh {total_amount:.2f}\n"
                        f"Status: {order.status}\n"
                        f"Payment Status: {order.payment_status}\n"
                        f"Coupon Applied: {order.coupon.coupon_code if order.coupon else 'None'}\n\n"
                        f"Items:\n{item_list}\n\n"
                        f"Thank you for shopping with us!"
                    )

                    try:
                        send_mail(
                            subject=subject,
                            message=message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[order.user.email],
                            fail_silently=False,
                        )
                        logger.info(f"Order confirmation email sent for order_id={order.order_id}")
                    except Exception as e:
                        logger.error(f"Failed to send order confirmation email: {str(e)}", exc_info=True)

                    logger.info(f"Order created successfully: order_id={order.order_id}")
                    return Response({"status": True, "order_id": order.order_id}, status=status.HTTP_200_OK)
            
            logger.error(f"Payment verification failed: status={response.status_code}, body={response.text}")
            return Response({"status": False, "message": "Payment verification failed"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}", exc_info=True)
            return Response({"status": False, "message": f"Payment verification error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        paystack_secret = settings.PAYSTACK_SECRET_KEY
        signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
        raw_body = request.body.decode('utf-8') if request.body else ''
        computed_signature = hmac.new(
            paystack_secret.encode('utf-8'),
            raw_body.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        if signature != computed_signature:
            logger.error(f"Invalid Paystack signature: received={signature}, computed={computed_signature}")
            return Response({"status": False, "message": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        if data.get('event') == 'charge.success':
            reference = data['data']['reference']
            cart_id = data['data']['metadata']['cart_id']
            email = data['data']['customer']['email']
            try:
                cart = Cart.objects.get(uid=cart_id, is_paid=False)
                user = User.objects.get(email=email)
            except (Cart.DoesNotExist, User.DoesNotExist):
                logger.error(f"Cart or user not found: cart_id={cart_id}, email={email}")
                return Response({"status": False, "message": "Cart or user not found"}, status=status.HTTP_400_BAD_REQUEST)
            
            total_amount = Decimal('0.00')
            for item in cart.cart_items.all():
                price = Decimal(item.product.price)
                total_amount += price * item.quantity
            
            paystack_amount = Decimal(data['data']['amount']) / 100
            if total_amount != paystack_amount:
                logger.error(f"Amount mismatch: calculated={total_amount}, Paystack={paystack_amount}")
                return Response({"status": False, "message": "Amount mismatch"}, status=status.HTTP_400_BAD_REQUEST)
            
            order = Order.objects.create(
                user=user,
                order_id=str(uuid.uuid4()),
                payment_status="completed",
                payment_mode="Paystack",
                status="confirmed",
                coupon=cart.coupon,
                total_amount=total_amount
            )
            
            for item in cart.cart_items.all():
                price = Decimal(item.product.price)
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    product_price=price
                )
                item.product.stock -= item.quantity
                item.product.save()

            payment = Payment.objects.create(
                order=order,
                amount=total_amount,
                reference=reference,
                payment_status="completed"
            )
            cart.is_paid = True
            cart.cart_items.all().delete()
            cart.coupon = None
            cart.save()

            items = OrderItem.objects.filter(order=order)
            item_list = "\n".join([f"- {item.product.name} (Qty: {item.quantity}, Price: KSh {item.product_price:.2f})" for item in items])
            subject = f"Order Confirmation: {order.order_id}"
            message = (
                f"Dear {user.email},\n\n"
                f"Thank you for your order!\n\n"
                f"Order ID: {order.order_id}\n"
                f"Total Amount: KSh {total_amount:.2f}\n"
                f"Status: {order.status}\n"
                f"Payment Status: {order.payment_status}\n"
                f"Coupon Applied: {order.coupon.coupon_code if order.coupon else 'None'}\n\n"
                f"Items:\n{item_list}\n\n"
                f"Thank you for shopping with us!"
            )

            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.user.email],
                    fail_silently=False,
                )
                logger.info(f"Order confirmation email sent for order_id={order.order_id}")
            except Exception as e:
                logger.error(f"Failed to send order confirmation email: {str(e)}", exc_info=True)

            logger.info(f"Webhook order created successfully: order_id={order.order_id}")
            return Response({"status": True, "order_id": order.order_id}, status=status.HTTP_200_OK)
        
        return Response({"status": False, "message": "Invalid webhook event"}, status=status.HTTP_400_BAD_REQUEST)

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