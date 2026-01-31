from django.db import transaction
from .models import Order, OrderItem, Product
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.templatetags.static import static
from rest_framework import serializers
from phonenumber_field.serializerfields import PhoneNumberField


class ProductOrderSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    firstname = serializers.CharField(max_length=50)
    lastname = serializers.CharField(max_length=50)
    phonenumber = PhoneNumberField(region='RU')
    address = serializers.CharField(max_length=200)
    products = ProductOrderSerializer(
        many=True, 
        allow_empty=False,
        write_only=True,
        error_messages={'empty': 'Этот список не может быть пустым'}
    )

    def validate_products(self, value):
        product_ids = [item['product'] for item in value]
        existing_ids = set(Product.objects.filter(id__in=product_ids).values_list('id', flat=True))
        missing_ids = set(product_ids) - existing_ids
        if missing_ids:
            raise serializers.ValidationError(
                f'Недопустимый первичный ключ "{sorted(missing_ids)[0]}"'
            )
        return value


@api_view(['GET'])
def banners_list_api(request):
    return Response([
        {
            'title': 'Burger',
            'src': static('burger.jpg'),
            'text': 'Tasty Burger at your door step',
        },
        {
            'title': 'Spices',
            'src': static('food.jpg'),
            'text': 'All Cuisines',
        },
        {
            'title': 'New York',
            'src': static('tasty.jpg'),
            'text': 'Food is incomplete without a tasty dessert',
        }
    ])


@api_view(['GET'])
def product_list_api(request):
    products = Product.objects.select_related('category').available()

    dumped_products = []
    for product in products:
        dumped_product = {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'special_status': product.special_status,
            'description': product.description,
            'category': {
                'id': product.category.id,
                'name': product.category.name,
            } if product.category else None,
            'image': product.image.url,
        }
        dumped_products.append(dumped_product)
    return Response(dumped_products)

@api_view(['POST'])
def register_order(request):
    serializer = OrderSerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            order = Order.objects.create(
                firstname=serializer.validated_data['firstname'],
                lastname=serializer.validated_data['lastname'],
                phonenumber=serializer.validated_data['phonenumber'],
                address=serializer.validated_data['address']
            )
            items = []
            product_map = {p.id: p for p in Product.objects.filter(
                id__in=[item['product'] for item in serializer.validated_data['products']]
            )}
            for item in serializer.validated_data['products']:
                items.append(OrderItem(
                    order=order,
                    product=product_map[item['product']],
                    quantity=item['quantity'],
                    price=product_map[item['product']].price
                ))
            OrderItem.objects.bulk_create(items)
        response_serializer = OrderSerializer(order)    
        return Response(response_serializer.data, status=201)
    return Response(serializer.errors, status=400)
