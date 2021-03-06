import random
import string
import stripe
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from .models import Item, Order, OrderItem, Address, Payment, Coupon, Refund
from .forms import CheckoutForm, CouponForm, RefundForm

stripe.api_key = settings.STRIPE_SECRET_KEY
# Create your views here.


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


class HomeView(ListView):
    model = Item
    template_name = 'ecommerce/home-page.html'
    context_object_name = 'items'
    paginate_by = 10


class ProductView(DetailView):
    model = Item
    template_name = 'ecommerce/product-page.html'


class OrderSummary(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'ecommerce/order-summary.html', context)
        except ObjectDoesNotExist:
            messages.info(self.request, 'You do not have an active order')
            return redirect('/')


class CheckOutView(LoginRequiredMixin ,View):
    def get(self, *args, **kwargs):
        try:
            form = CheckoutForm()
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'form': form,
                'coupon_form': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }
            return render(self.request, 'ecommerce/checkout-page.html', context)
        except ObjectDoesNotExist:
            messages.info(self.request, 'You do not have an active order')
            return redirect('check-out')

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                mobile = form.cleaned_data.get('mobile')
                email = form.cleaned_data.get('email')
                country = form.cleaned_data.get('country')
                state = form.cleaned_data.get('state')
                # payment_option = form.cleaned_data.get('payment_option')
                address = Address(
                    user=self.request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    mobile=mobile,
                    email=email,
                    country=country,
                    state=state
                )
                address.save()
                order.address = address
                order.save()
                return redirect('payment')

                # if payment_option == 'S':
                    # return redirect('payment', payment_option='stripe')
                # elif payment_option == 'P':
                    # messages.warning(self.request, 'Paypal not available, try using Stripe')
                    # return redirect('check-out')
                # else:
                    # messages.warning(self.request, 'Invalid payment option selected')
                    # return redirect('check-out')
            # else:
            #     messages.info(self.request, 'save address for next time')
            #     return redirect('check-out')
        except ObjectDoesNotExist:
            messages.warning(self.request, 'You do not have an active order')
            return redirect('order-summary')


class PaymentView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False
            }
            return render(self.request, 'ecommerce/payment.html', context)
        else:
            messages.warning(self.request, 'You have not added an address')
            return redirect('check-out')

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        token = self.request.POST.get('stripeToken')
        amount = int(order.get_total() * 100)
        try:
            charge = stripe.Charge.create(
                amount=amount,
                currency='usd',
                source=token
            )
            payment = Payment()
            payment.stripe_charge_id = charge['id']
            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            order_items = order.items.all()
            order_items.update(ordered=True)
            for item in order_items:
                item.save()

            order.ordered = True
            order.payment = payment
            order.ref_code = create_ref_code()
            order.save()
            messages.success(self.request, 'Your Order was successful')
            return redirect('/')
        except stripe.error.CardError as e:
            body = e.json_body
            err = body.get('error', {})
            messages.warning(self.request, f"{err.get('message')}")
            return redirect("/")

        except stripe.error.RateLimitError as e:
            messages.warning(self.request, "Rate limit error")
            return redirect("/")

        except stripe.error.InvalidRequestError as e:
            print(e)
            messages.warning(self.request, "Invalid parameters")
            return redirect("/")

        except stripe.error.AuthenticationError as e:
            messages.warning(self.request, "Not authenticated")
            return redirect("/")

        except stripe.error.APIConnectionError as e:
            messages.warning(self.request, "Network error")
            return redirect("/")

        except stripe.error.StripeError as e:
            messages.warning(
                self.request, "Something went wrong. You were not charged. Please try again.")
            return redirect("/")

        except Exception as e:
            messages.warning(
                self.request, "A serious error occurred. We have been notified.")
            return redirect("/")


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.success(request, 'Item quantity has been updated')
            return redirect('product', slug=slug)
        else:
            order.items.add(order_item)
            messages.success(request, 'Item has been added to your cart')
            return redirect('product', slug=slug)
    else:
        created_date = timezone.now()
        order = Order.objects.create(user=request.user, created_date=created_date)
        order.items.add(order_item)
        messages.success(request, 'Item has been added to your cart')
        return redirect('product', slug=slug)


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(item=item, user=request.user, ordered=False)[0]
            order.items.remove(order_item)
            messages.info(request, 'Item has been removed from cart')
            return redirect('product', slug=slug)
        else:
            messages.info(request, 'This item is not in your cart')
            return redirect('product', slug=slug)
    else:
        messages.info(request, 'You do not have an active order')
        return redirect('product', slug=slug)


@login_required
def add_single_item_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.success(request, 'Item quantity has been updated')
            return redirect('order-summary')
        else:
            order.items.add(order_item)
            messages.success(request, 'Item has been added to your cart')
            return redirect('order-summary')
    else:
        created_date = timezone.now()
        order = Order.objects.create(user=request.user, created_date=created_date)
        order.items.add(order_item)
        messages.success(request, 'Item has been added to your cart')
        return redirect('order-summary')


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(item=item, user=request.user, ordered=False)[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, 'Item has been removed from cart')
            return redirect('order-summary')
        else:
            messages.info(request, 'This item is not in your cart')
            return redirect('order-summary')
    else:
        messages.info(request, 'You do not have an active order')
        return redirect('order-summary')


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, 'This coupon does not exist')
        return redirect('check-out')


class AddCoupon(LoginRequiredMixin, View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, 'Successfully added Coupon')
                return redirect('check-out')
            except ObjectDoesNotExist:
                messages.info(self.request, 'You do not have an active order')
                return redirect('check-out')


class RefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, 'ecommerce/request-refund.html', context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.success(self.request, 'Your request was received')
                return redirect('request-refund')
            except ObjectDoesNotExist:
                messages.info(self.request, 'This order does not exist')
                return redirect('request-refund')


class SearchView(ListView):
    model = Item
    template_name = 'ecommerce/search.html'
    context_object_name = 'items'

    def get_queryset(self):
        query = self.request.GET.get('q')
        object_list = Item.objects.filter(Q(title__icontains=query))
        return object_list









