from django.db import models
from django.urls import reverse
from django_countries.fields import CountryField
from django.contrib.auth.models import User
# Create your models here.
CATEGORY_CHOICES = (
    ('S', 'Shirt'),
    ('OW', 'Out wear'),
    ('SW', 'Sport wear')
)
LABEL_CHOICES = (
    ('P', 'primary'),
    ('S', 'secondary'),
    ('D', 'danger')
)

class Item(models.Model):
    title = models.CharField(max_length=100)
    price = models.FloatField()
    discount_price = models.FloatField(blank=True, null=True)
    category = models.CharField(max_length=2, choices=CATEGORY_CHOICES)
    label = models.CharField(max_length=1, choices=LABEL_CHOICES)
    slug = models.SlugField()
    description = models.TextField()
    image = models.ImageField()
    def __str__(self):
        return self.title
    def get_absolute_url(self):
        return reverse('product', kwargs={'slug': self.slug})
    def get_add_to_cart_url(self):
        return reverse('add-to-cart', kwargs={'slug': self.slug})
    def get_remove_from_cart_url(self):
        return reverse('remove-from-cart', kwargs={'slug': self.slug})

class OrderItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    item = models.ForeignKey('Item', on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    def __str__(self):
        return f'{self.quantity} of {self.item.title}'
    def get_total_item_price(self):
        return self.quantity * self.item.price
    def get_total_item_discount_price(self):
        return self.quantity * self.item.discount_price
    def get_amount_saved(self):
        return self.get_total_item_price() - self.get_total_item_discount_price()
    def get_final_price(self):
        if self.item.discount_price:
            return self.get_total_item_discount_price()
        else:
            return self.get_total_item_price()

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ref_code = models.CharField(max_length=20)
    items = models.ManyToManyField(OrderItem)
    start_date = models.DateTimeField(auto_now_add=True)
    created_date = models.DateTimeField()
    ordered = models.BooleanField(default=False)
    address = models.ForeignKey('Address', on_delete=models.SET_NULL, blank=True, null=True)
    payment = models.ForeignKey('Payment', on_delete=models.SET_NULL, blank=True, null=True)
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, blank=True, null=True)
    being_delivered = models.BooleanField(default=False)
    received = models.BooleanField(default=False)
    refund_requested = models.BooleanField(default=False)
    refund_granted = models.BooleanField(default=False)
    def __str__(self):
        return f'{self.user.username}'
    def get_total(self):
        total = 0
        for order_item in self.items.all():
            total += order_item.get_final_price()
        if self.coupon:
            total -= self.coupon.amount
        return total

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    street_address = models.CharField(max_length=100)
    apartment_address = models.CharField(max_length=100)
    country = CountryField(multiple=False)
    zip = models.CharField(max_length=8)
    def __str__(self):
        return f'{self.user.username}'
    class Meta:
        verbose_name_plural = 'Addresses'
class Payment(models.Model):
    stripe_charge_id = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    amount = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'{self.user.username}'

class Coupon(models.Model):
    code = models.CharField(max_length=20)
    amount = models.FloatField()
    def __str__(self):
        return self.code

class Refund(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    reason = models.TextField()
    accepted = models.BooleanField(default=False)
    email = models.EmailField()
    def __str__(self):
        return f'{self.pk}'



