from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.utils.timezone import now
from customer.models import OrderModel

class Dashboard(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.groups.filter(name='Staff').exists()
    
    def get(self, request, *args, **kwargs):
        #get current date
        today = now().date()
        orders = OrderModel.objects.filter(created_on__date=today)
    
        #loop orders and add price value
        total_revenue = 0
        for order in orders:
            total_revenue += order.price
        
        #pass total num of orders and total revenue into template
        context = {
            'orders': orders,
            'total_revenue': total_revenue,
            'total_orders': len(orders),
        }
        return render(request, 'restaurant/dashboard.html', context)

