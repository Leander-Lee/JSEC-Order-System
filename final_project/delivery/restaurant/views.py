from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.utils.timezone import localtime, now
from customer.models import OrderModel

class Dashboard(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.groups.filter(name='Staff').exists()
    
    def get(self, request, *args, **kwargs):
        # Get current date
        today = localtime(now()).date()
        orders = OrderModel.objects.filter(created_on__date=today)

        total_revenue = sum(order.price for order in orders)

        context = {
            'orders': orders,
            'total_revenue': total_revenue,
            'total_orders': len(orders),
        }
        return render(request, 'restaurant/dashboard.html', context)

