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
    errors = {}

    # === Проверка обязательных полей ===
    required_fields = ['firstname', 'lastname', 'phonenumber', 'address', 'products']
    for field in required_fields:
        if field not in data:
            errors[field] = 'Обязательное поле'
        elif isinstance(data[field], str) and not data[field].strip():
            errors[field] = 'Обязательное поле'

    # === Валидация products ===
    if 'products' in data:
        products_data = data['products']

        if products_data is None:
            errors['products'] = 'Это поле не может быть пустым'
        elif not isinstance(products_data, list):
            errors['products'] = f'Ожидался list со значениями, но был получен "{type(products_data).__name__}"'
        elif len(products_data) == 0:
            errors['products'] = 'Этот список не может быть пустым'
        else:
            # Проверяем каждый элемент списка
            for idx, item in enumerate(products_data):
                if not isinstance(item, dict):
                    errors[f'products[{idx}]'] = 'Должен быть объектом (словарём)'
                    continue

                # Проверка product
                if 'product' not in item:
                    errors[f'products[{idx}].product'] = 'Обязательное поле'
                elif not isinstance(item['product'], int):
                    errors[f'products[{idx}].product'] = 'Должен быть числом'

                # Проверка quantity
                if 'quantity' not in item:
                    errors[f'products[{idx}].quantity'] = 'Обязательное поле'
                elif not isinstance(item['quantity'], int) or item['quantity'] <= 0:
                    errors[f'products[{idx}].quantity'] = 'Должно быть положительным числом'

    # === Если есть ошибки — возвращаем их ===
    if errors:
        return Response(errors, status=400)

    # === Проверка существования продуктов ===
    product_ids = [item['product'] for item in data['products']]
    existing_products = Product.objects.filter(id__in=product_ids)
    found_ids = {p.id for p in existing_products}

    missing_ids = set(product_ids) - found_ids
    if missing_ids:
        return Response(
            {'products': f'Продукты не найдены: {sorted(missing_ids)}'},
            status=400
        )

    # === Сохранение заказа ===
    try:
        with transaction.atomic():
            order = Order.objects.create(
                firstname=data['firstname'].strip(),
                lastname=data['lastname'].strip(),
                phonenumber=data['phonenumber'],
                address=data['address'].strip()
            )
            items = []
            product_map = {p.id: p for p in existing_products}
            for item in data['products']:
                product = product_map[item['product']]
                items.append(OrderItem(
                    order=order,
                    product=product,
                    quantity=item['quantity'],
                    price=product.price
                ))
            OrderItem.objects.bulk_create(items)

        return Response({'status': 'ok'})
    except Exception as e:
        print("Ошибка при сохранении:", e)
        return Response({'error': 'Не удалось сохранить заказ'}, status=500)
