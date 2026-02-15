from functools import lru_cache
from django.db.models import Sum, F
from django.db import models
from django.core.validators import MinValueValidator
from phonenumber_field.modelfields import PhoneNumberField


class OrderQuerySet(models.QuerySet):
    def with_total_price(self):
        return self.annotate(
            total_price=Sum(F('items__price') * F('items__quantity'))
        )
        
    def with_available_restaurants(self):
        from .models import RestaurantMenuItem, Restaurant
        from .utils import fetch_coordinates, calculate_distance
        
        @lru_cache(maxsize=None)
        def get_cached_coords(address):
            if not address:
                return None
            return fetch_coordinates(address)
        
        menu_items = RestaurantMenuItem.objects.filter(availability=True).select_related('restaurant')
        
        product_to_restaurants = {}
        for item in menu_items:
            product_to_restaurants.setdefault(item.product_id, set()).add(item.restaurant_id)
        
        all_restaurant_ids = set()
        for restaurant_ids in product_to_restaurants.values():
            all_restaurant_ids.update(restaurant_ids)
            
        restaurants_dict = {
            r.id: r for r in Restaurant.objects.filter(id__in=all_restaurant_ids)
        }    
        
        orders = list(self.prefetch_related('items'))
        for order in orders:
            product_ids = {item.product_id for item in order.items.all()}
            
            if not product_ids:
                order.available_restaurants = []
                continue
            
            common_restaurant_ids = None
            for pid in product_ids:
                restaurant_ids = product_to_restaurants.get(pid, set())
                if common_restaurant_ids is None:
                    common_restaurant_ids = restaurant_ids.copy()
                else:
                    common_restaurant_ids &= restaurant_ids
                if not common_restaurant_ids:
                    break
                
            if not common_restaurant_ids:
                order.available_restaurants = []
                continue
            
            order_coords = get_cached_coords(order.address)
            
            restaurants_with_distance = []
            for rid in common_restaurant_ids:
                restaurant = restaurants_dict.get(rid)
                if not restaurant:
                    continue
                
                restaurant_coords = get_cached_coords(restaurant.address)
                distance = calculate_distance(order_coords, restaurant_coords)
                
                restaurants_with_distance.append({
                    'restaurant': restaurant,
                    'distance': distance
                })
                
            order.available_restaurants = sorted(
                restaurants_with_distance,
                key=lambda x: x['distance'] or float('inf')
            )
        
        return orders 
        
        
ORDER_STATUSES = [
    ('UNPROCESSED', 'Необработанный'),
    ('PROCESSING', 'Готовится'),
    ('DELIVERING', 'Доставляется'),
    ('COMPLETED', 'Выполнен'),
]        


PAYMENT_METHODS = [
    ('ONLINE', 'Электронно'),
    ('CASH', 'Наличностью'),
]


class Order(models.Model):
    address = models.CharField('Адрес доставки', max_length=200)
    firstname = models.CharField('Имя', max_length=50)
    lastname = models.CharField('Фамилия', max_length=50)
    phonenumber = PhoneNumberField('Мобильный номер', db_index=True)
    comment = models.TextField('Комментарий', blank=True)
    
    restaurant = models.ForeignKey(
        'Restaurant',
        verbose_name='Ресторан',
        related_name='orders',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    
    payment_method = models.CharField(
        'Способ оплаты',
        max_length=10,
        choices=PAYMENT_METHODS,
        default='ONLINE',
        db_index=True
    )
    
    registrated_at = models.DateTimeField('Дата создания заказа', auto_now_add=True, db_index=True)
    called_at = models.DateTimeField('Дата звонка', blank=True, null=True, db_index=True)
    delivered_at = models.DateTimeField('Дата доставки', blank=True, null=True, db_index=True)
    
    objects = OrderQuerySet.as_manager()
    
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=ORDER_STATUSES,
        default='UNPROCESSED',
        db_index=True 
        
    )
    
    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'
        
    
    def __str__(self):
        return f"{self.firstname} {self.lastname}, {self.phonenumber}"   


class Restaurant(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    address = models.CharField(
        'адрес',
        max_length=100,
        blank=True,
    )
    contact_phone = models.CharField(
        'контактный телефон',
        max_length=50,
        blank=True,
    )

    class Meta:
        verbose_name = 'ресторан'
        verbose_name_plural = 'рестораны'

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        products = (
            RestaurantMenuItem.objects
            .filter(availability=True)
            .values_list('product')
        )
        return self.filter(pk__in=products)


class ProductCategory(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(
        'название',
        max_length=50
    )
    category = models.ForeignKey(
        ProductCategory,
        verbose_name='категория',
        related_name='products',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    price = models.DecimalField(
        'цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField(
        'картинка'
    )
    special_status = models.BooleanField(
        'спец.предложение',
        default=False,
        db_index=True,
    )
    description = models.TextField(
        'описание',
        max_length=200,
        blank=True,
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'

    def __str__(self):
        return self.name


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        related_name='menu_items',
        verbose_name="ресторан",
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='menu_items',
        verbose_name='продукт',
    )
    availability = models.BooleanField(
        'в продаже',
        default=True,
        db_index=True
    )

    class Meta:
        verbose_name = 'пункт меню ресторана'
        verbose_name_plural = 'пункты меню ресторана'
        unique_together = [
            ['restaurant', 'product']
        ]

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name='items',
        verbose_name='заказ',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        related_name='order_items',
        verbose_name='товар',
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveSmallIntegerField(
        'количество',
        validators=[MinValueValidator(1)]
    )
    price = models.DecimalField(
        'цена',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = 'элемент заказа'
        verbose_name_plural = 'элементы заказа'

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"