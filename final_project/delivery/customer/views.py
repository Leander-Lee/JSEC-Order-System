import json
from django.shortcuts import render, redirect
from django.views import View
from django.db.models import Q
from django.core.mail import send_mail
from .models import MenuItem, Category, OrderModel

class Index(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'customer/index.html')
    
class About(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'customer/about.html') 

class Order(View):
    def get(self, request, *args, **kwargs):
        main = MenuItem.objects.filter(category__name__contains='Main')
        side = MenuItem.objects.filter(category__name__contains='Side')
        extra = MenuItem.objects.filter(category__name__contains='Extra')
        #get item from all the categories

        #pass into context
        context = {
            "main": main,
            'side': side,  
            'extra': extra,
        } 

        #render the template
        return render(request, 'customer/order.html', context)
    
    def post(self, request, *args, **kwargs):
        name = request.POST.get('name')
        email = request.POST.get('email')
        dorm = request.POST.get('dorm')
        is_pickup = request.POST.get('is_pickup') == "true"

        if is_pickup:
            dorm = None 

        order_items = {
            'items': []
        }

        items = request.POST.getlist('items[]')

        #get total price after selection
        price = 0
        item_id=[]

        #we are trying to get all the selected choices for the order
        #basically this is the list of all ticked boxes
        for i in items:
            menu_item = MenuItem.objects.get(pk=int(i))
            item_data = {
                'id': menu_item.pk,
                'name': menu_item.name,
                'price': menu_item.price,
            }
            order_items['items'].append(item_data)

            price += menu_item.price
            item_id.append(menu_item.pk)

        order = OrderModel.objects.create(
            price=price,
            name=name,
            email=email,
            dorm=dorm,
            is_pickup=is_pickup,
        )

        order.items.add(*item_id)

        if is_pickup:
            greeting = "Thank you for your order! Your food is being made and will be ready for pickup soon!"
        else:
            greeting = "Thank you for your order! Your food is being made and will be delivered soon!"
        
        body = (f'{greeting}\n'
            f'Your total: {price}\n'
            'Thank you again for your order!')

        send_mail(
            'Thank You For Your Order!',
            body,
            'example@example.com',
            [email],
            fail_silently=False
        )
        context = {
            'items': order_items['items'], 
            'price': price
        }

        #reflect everything back
        return redirect('order-confirmation', pk=order.pk)


class OrderConfirmation(View):
    def get(self, request, pk, *args, **kwargs):
        order = OrderModel.objects.get(pk=pk)

        context = {
            'pk': order.pk,
            'items': order.items,
            'price': order.price,
        }

        return render(request, 'customer/order_confirmation.html', context)

    def post(self, request, pk, *args, **kwargs):
        data = json.loads(request.body)

        if data['isPaid']:
            order = OrderModel.objects.get(pk=pk)
            order.is_paid = True
            order.save()

        return redirect('payment-confirmation')


class OrderPayConfirmation(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'customer/order_pay_confirmation.html')
    
class Menu(View):
    def get(self, request, *args, **kwargs):
        menu_items = MenuItem.objects.all()

        context = {
            'menu_items': menu_items,
        }

        return render(request, 'customer/menu.html', context)
    
class MenuSearch(View):
    def get(self, request, *args, **kwargs):
        query = self.request.GET.get('q', '')
        
        if query:
            try:
                price_val = float(query)
                menu_items = MenuItem.objects.filter(
                    Q(name__icontains=query) |
                    Q(description__icontains=query) |
                    Q(price=price_val)
                )
            except ValueError:
                menu_items = MenuItem.objects.filter(
                    Q(name__icontains=query) |
                    Q(description__icontains=query)
                )
        else:
            menu_items = MenuItem.objects.all()

        context = {
            'menu_items': menu_items,
            'query': query,
        }

        return render(request, 'customer/menu.html', context)