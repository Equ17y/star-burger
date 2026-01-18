import json
from django.http import JsonResponse
from django.templatetags.static import static
from django.db import transaction
from .models import Order, OrderItem, Product



from .models import Product


def banners_list_api(request):
    # FIXME move data to db?
    return JsonResponse([
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
    ], safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


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
            'restaurant': {
                'id': product.id,
                'name': product.name,
            }
        }
        dumped_products.append(dumped_product)
    return JsonResponse(dumped_products, safe=False, json_dumps_params={
        'ensure_ascii': False,
        'indent': 4,
    })


def register_order(request):
    if request.method == 'POST':
        body = request.body.decode('utf-8')
        data = json.loads(body)
        print("Получен заказ:", data)
        # Получаем продукты
        product_ids = [item['product'] for item in data['products']]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

        if len(products) != len(product_ids):
            return JsonResponse({'error': 'Some products not found'}, status=400)

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

            return JsonResponse({'status': 'ok'})
        except Exception as e:
            print("Ошибка:", e)
            return JsonResponse({'error': 'Failed to save order'}, status=500)

    return JsonResponse({'error': 'Only POST allowed'}, status=405)

# return JsonResponse({})
