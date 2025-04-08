from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import Checkout, Reservation
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Send notifications for due dates and available reservations'

    def handle(self, *args, **options):
        # Notify about books due in 3 days
        due_soon = Checkout.objects.filter(
            returned=False,
            due_date__lte=timezone.now() + timedelta(days=3),
            due_date__gt=timezone.now()
        )
        
        for checkout in due_soon:
            try:
                checkout.send_due_notification()
                self.stdout.write(f"Sent due notification for {checkout.book.title}")
            except Exception as e:
                logger.error(f"Failed to send due notification: {str(e)}")
        
        # Notify about available reservations
        available_reservations = Reservation.objects.filter(
            notified=False,
            fulfilled=False,
            book__available__gt=0
        )
        
        for reservation in available_reservations:
            try:
                reservation.send_available_notification()
                reservation.notified = True
                reservation.save()
                self.stdout.write(f"Sent reservation notification for {reservation.book.title}")
            except Exception as e:
                logger.error(f"Failed to send reservation notification: {str(e)}")