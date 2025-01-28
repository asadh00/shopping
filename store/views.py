from django.shortcuts import render, redirect
from django.contrib import messages
from django.views import View

from .models import OrderDetail
from .models.product import Product
from .models.category import Category
from .models.customer import Customer
from .models.cart import Cart
from .models.order import OrderDetail
from django.db.models import Q
from django.http import JsonResponse


import random
import string
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from twilio.rest import Client  # Import Twilio Client
import time
# Twilio setup
TWILIO_ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER = settings.TWILIO_PHONE_NUMBER

otp_store = {}

def generate_otp(length=6):
    """Generate a random OTP."""
    return ''.join(random.choices(string.digits, k=length))

def send_otp_via_sms(to_phone, otp):
    """Send OTP via SMS using Twilio."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=f"Your OTP code is {otp}. It is valid for 5 minutes.",
        from_=TWILIO_PHONE_NUMBER,
        to=to_phone
    )
    return message.sid

def signup(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')

        # Generate OTP
        otp = generate_otp()
        otp_store[phone] = {'otp': otp, 'expiry': time.time() + 300}  # 5 minutes expiry

        # Send OTP
        send_otp_via_sms(phone, otp)

        messages.success(request, "OTP has been sent to your mobile number.")
        return redirect('verify_otp', phone=phone)

    return render(request, 'signup.html')

def verify_otp(request, phone):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')

        # Check if the OTP is valid
        if phone in otp_store:
            otp_data = otp_store[phone]
            if otp_data['otp'] == entered_otp and time.time() < otp_data['expiry']:
                # OTP is valid, proceed with registration
                # Here you can create the user account in the database
                del otp_store[phone]  # Clear OTP after successful verification
                messages.success(request, "Registration successful!")
                return redirect('home')
            else:
                messages.error(request, "Invalid or expired OTP.")
        else:
            messages.error(request, "No OTP request found.")

    return render(request, 'verify_otp.html', {'phone': phone})



# Home view - checks if user is logged in and loads categories and products
def home(request):
    totalitem=0
    if request.session.has_key("phone"):  # Check if session has phone number
        phone = request.session["phone"]
        categories = Category.get_all_categories()  # Get all categories
        customer = Customer.objects.filter(phone=phone).first()  # Get the customer
        totalitem = len(Cart.objects.filter(phone=phone))

        if customer:
            name = customer.name  # Get the customer's name

            # Get category filter from request if available
            categoryID = request.GET.get('category')
            if categoryID:
                products = Product.get_all_product_by_category_id(categoryID)
            else:
                products = Product.get_all_products()  # Get all products if no filter

            data = {
                'name': name,
                'products': products,
                'categories': categories,
                'totalitem':totalitem
            }
            return render(request, "home.html", data)
        else:
            return redirect("login")  # If no customer is found, redirect to login
    else:
        return redirect("login")  # Redirect to login if no session is found


# Signup view - displays signup form and handles registration
class Signup(View):
    def get(self, request):
        return render(request, 'signup.html')

    def post(self, request):
        postData = request.POST
        name = postData.get('name')
        phone = postData.get('phone')
        error_message = None

        value = {
            'phone': phone,
            'name': name,
        }
        customer = Customer(name=name, phone=phone)

        # Basic validation checks
        if not name:
            error_message = 'Please enter your name'
        elif not phone:
            error_message = 'Please enter your mobile number'
        elif len(phone) < 10:
            error_message = 'Mobile number is too short'
        elif Customer.objects.filter(phone=phone).exists():  # Check if phone already exists
            error_message = 'Mobile number is already taken'
        elif len(phone) > 11:
            error_message = 'Mobile number is too long'

        if not error_message:
            customer.save()  # Save the customer to the database
            messages.success(request, "Congratulations! You have successfully registered!")
            return redirect('signup')  # Redirect to avoid form re-submission
        else:
            data = {
                'error': error_message,
                'value': value
            }
            return render(request, 'signup.html', data)


# Login view - handles login form and session creation
class Login(View):
    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        phone = request.POST.get('phone')
        error_message = None
        value = {
            'phone': phone,
        }
        customer = Customer.objects.filter(phone=phone).first()  # Fetch first customer with this phone number
        if customer:
            request.session['phone'] = phone  # Set session with phone number
            return redirect('homepage')
        else:
            error_message = "Mobile number is invalid"
            data = {
                'error': error_message,
                'value': value
            }
            return render(request, 'login.html', data)


# Product detail view - displays details of a specific product
def productdetail(request, pk):
    totalitem=0
    product = Product.objects.get(pk=pk)
    item_already_in_cart=False
    if request.session.has_key('phone'):
        phone=request.session["phone"]
        totalitem=len(Cart.objects.filter(phone=phone))
        item_already_in_cart=Cart.objects.filter(Q(product=product.id) & Q(phone=phone)).exists()

        customer = Customer.objects.filter(phone=phone)
        for c in customer:
            name=c.name

        data={
            'product': product,
            'item_already_in_cart': item_already_in_cart,
            'name':name,
            'totalitem':totalitem
        }

        return render(request, 'productdetail.html',data)


# Logout view - logs out user by removing session data
def logout(request):
    if request.session.has_key('phone'):  # Check if session has phone number
        del request.session['phone']  # Remove phone from session
        return redirect('login')
    else:
        return redirect('login')


def add_to_cart(request):
    phone=request.session["phone"]
    product_id=request.GET.get('prod_id')
    product_name=Product.objects.get(id=product_id)
    product=Product.objects.filter(id=product_id)
    for p in product:
        image=p.image
        price=p.price
        Cart(phone=phone,product=product_name,image=image,price=price).save()
        return redirect(f"/product-detail/{product_id}")

#=======================Cart=====================

def show_cart(request):
    totalitem=0
    if request.session.has_key('phone'):
        phone=request.session["phone"]
        totalitem=len(Cart.objects.filter(phone=phone))

        customer = Customer.objects.filter(phone=phone)
        for c in customer:
            name = c.name

            cart = Cart.objects.filter(phone=phone)
            data={
                'name': name,
                'totalitem': totalitem,
                'cart': cart
            }
            if cart:
                return render(request, 'show_cart.html', data)
            else:
                return render(request, 'empty_cart.html')


def calculate_total_price(phone):
    cart_items = Cart.objects.filter(phone=phone)
    total_price = sum(item.quantity * item.price for item in cart_items)  # Calculate total cart price
    return total_price


def plus_cart(request):
    if request.session.has_key('phone'):
        phone = request.session["phone"]
        product_id = request.GET.get('prod_id')  # Ensure prod_id is captured properly

        if product_id:  # Check if prod_id is valid
            try:
                # Fetch the cart item using phone and product ID
                cart_item = Cart.objects.filter(Q(product=product_id) & Q(phone=phone)).first()

                if cart_item:  # Ensure the cart item exists
                    # Increase the quantity of the product
                    cart_item.quantity += 1
                    cart_item.save()

                    # Prepare data for the response
                    data = {
                        'quantity': cart_item.quantity,
                        'total_price': calculate_total_price(phone)  # Calculate and send the updated total price
                    }
                    return JsonResponse(data)
                else:
                    return JsonResponse({'error': 'Product not found in cart'}, status=404)

            except Exception as e:
                # Handle unexpected errors gracefully and log them if necessary
                return JsonResponse({'error': str(e)}, status=500)
        else:
            return JsonResponse({'error': 'Invalid product ID'}, status=400)
    else:
        return JsonResponse({'error': 'User not logged in'}, status=401)

def minus_cart(request):
    if request.session.has_key('phone'):
        phone = request.session["phone"]
        product_id = request.GET.get('prod_id')  # Ensure prod_id is captured properly

        if product_id:  # Check if prod_id is valid
            try:
                # Fetch the cart item using phone and product ID
                cart_item = Cart.objects.filter(Q(product=product_id) & Q(phone=phone)).first()

                if cart_item:  # Ensure the cart item exists
                    # Increase the quantity of the product
                    cart_item.quantity -= 1
                    cart_item.save()

                    # Prepare data for the response
                    data = {
                        'quantity': cart_item.quantity,
                        'total_price': calculate_total_price(phone)  # Calculate and send the updated total price
                    }
                    return JsonResponse(data)
                else:
                    return JsonResponse({'error': 'Product not found in cart'}, status=404)

            except Exception as e:
                # Handle unexpected errors gracefully and log them if necessary
                return JsonResponse({'error': str(e)}, status=500)
        else:
            return JsonResponse({'error': 'Invalid product ID'}, status=400)
    else:
        return JsonResponse({'error': 'User not logged in'}, status=401)


def remove_cart(request):
    if request.session.has_key('phone'):
        phone = request.session["phone"]
        product_id = request.GET.get('prod_id')

        if product_id:
            try:
                cart_item = Cart.objects.filter(Q(product=product_id) & Q(phone=phone)).first()

                if cart_item:
                    cart_item.delete()
                    return JsonResponse({'success': True})  # Return a success response
                else:
                    return JsonResponse({'error': 'Product not found in cart'}, status=404)

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        else:
            return JsonResponse({'error': 'Invalid product ID'}, status=400)
    else:
        return JsonResponse({'error': 'User not logged in'}, status=401)


def checkout(request):
    totalitem = 0
    if request.session.has_key('phone'):
        phone = request.session["phone"]
        name = request.POST.get('name')
        address = request.POST.get('address')
        mobile = request.POST.get('mobile')

        cart_product = Cart.objects.filter(phone=phone)

        if cart_product.exists():  # Check if cart has items
            for c in cart_product:
                qty = c.quantity
                price = c.price
                product_name = c.product
                image = c.image

                # Save the order details
                OrderDetail(user=phone, product_name=product_name, image=image, qty=qty, price=price).save()

            # Once the order is saved, delete the cart items
            cart_product.delete()

            totalitem = len(Cart.objects.filter(phone=phone))

            customer = Customer.objects.filter(phone=phone).first()
            if customer:
                name = customer.name

            data = {
                'name': name,
                'totalitem': totalitem,
            }

            # Render the empty cart page after checkout is complete
            return render(request, 'empty_cart.html', data)

        else:
            # If no items in the cart, render the empty cart page or handle accordingly
            return render(request, 'empty_cart.html', {'name': name, 'totalitem': totalitem})

    else:
        return redirect('login')


def order(request):

    totalitem=0
    if request.session.has_key('phone'):
        phone = request.session["phone"]


        totalitem = len(Cart.objects.filter(phone=phone))

        customer = Customer.objects.filter(phone=phone)
        for c in customer:
            name = c.name
            order = OrderDetail.objects.filter(user=phone)
            data = {
                'order': order,
                'name': name,
                'totalitem': totalitem,
            }

            if order:
                return render(request, 'order.html', data)
            else:
                return render(request, 'emptyorder.html', data)






    else:
        return redirect('login')


def search(request):
    totalitem = 0
    if request.session.has_key('phone'):
        phone = request.session["phone"]
        query = request.GET.get('query')

        # Searching products with names containing the query
        search = Product.objects.filter(name__icontains=query)  # Use __icontains for case-insensitive search
        categories = Category.get_all_categories()

        totalitem = len(Cart.objects.filter(phone=phone))

        customer = Customer.objects.filter(phone=phone)
        for c in customer:
            name = c.name

        data = {
            'name': name,
            'totalitem': totalitem,
            'search': search,  # Corrected this line to return search results
            'query': query,
            'categories': categories,  # Including categories for the template
        }
        return render(request, 'search.html', data)

    else:
        return redirect('login')