from django.db import transaction
from .models import Order, OrderItem, Product
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.templatetags.static import static


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
    data = request.data
    product_ids = [item['product'] for item in data['products']]
    products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

    if len(products) != len(product_ids):
        return Response({'error': 'Some products not found'}, status=400)

    try:
        with transaction.atomic():
            order = Order.objects.create(
                firstname=data['firstname'],
                lastname=data['lastname'],
                phonenumber=data['phonenumber'],
                address=data['address']
            )
            items = []
            for item in data['products']:
                product = products[item['product']]
                items.append(OrderItem(
                    order=order,
                    product=product,
                    quantity=item['quantity'],
                    price=product.price
                ))
            OrderItem.objects.bulk_create(items)

        return Response({'status': 'ok'})
    except Exception as e:
        print("Ошибка:", e)
        return Response({'error': 'Failed to save order'}, status=500)
