from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import Checkout
from django.conf import settings

class Command(BaseCommand):
    help = 'Calculate fines for overdue books'

    def handle(self, *args, **options):
        overdue_checkouts = Checkout.objects.filter(returned=False,due_date__lt=timezone.now() - timedelta(days=settings.GRACE_PERIOD_DAYS))
        
        for checkout in overdue_checkouts:
            days_late = (timezone.now() - checkout.due_date).days - settings.GRACE_PERIOD_DAYS
            days_late = min(days_late, settings.MAX_FINE_DAYS)  # Cap at max days
            checkout.total_fine = days_late * checkout.daily_fine_rate
            checkout.save()
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully updated fines for {overdue_checkouts.count()} checkouts'))