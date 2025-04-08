from venv import logger
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.forms import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from psutil import users
import requests

from library_management.settings import DEFAULT_DAILY_FINE_RATE, GRACE_PERIOD_DAYS, MAX_FINE_DAYS  # For SMS API integration


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        (1, 'Admin'),
        (2, 'Librarian'),
        (3, 'Member'),
    )
    
    user_type = models.PositiveSmallIntegerField(choices=USER_TYPE_CHOICES, default=3)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    
    def __str__(self):
        return self.username
    
    def is_admin(self):
        return self.user_type == 1
    
    def is_librarian(self):
        return self.user_type == 2
    
    def is_member(self):
        return self.user_type == 3
    
    def is_librarian_or_admin(self):
        return self.user_type in [1, 2]

class Book(models.Model):
    GENRE_CHOICES = [
        ('FIC', 'Fiction'),
        ('NF', 'Non-Fiction'),
        ('SCI', 'Science'),
        ('HIS', 'History'),
        ('BIO', 'Biography'),
    ]
    
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    publisher = models.CharField(max_length=100)
    genre = models.CharField(max_length=3, choices=GENRE_CHOICES)
    isbn = models.CharField(max_length=13, unique=True)
    publication_date = models.DateField()
    quantity = models.PositiveIntegerField(default=1, verbose_name="Total Copies")
    available = models.PositiveIntegerField(default=1, verbose_name="Available Copies")
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    notify_subscribers = models.BooleanField(
        default=True,
        help_text="Send notifications to genre subscribers when this book is added"
    )

    def __str__(self):
        return f"{self.title} by {self.author}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Check if this is a new book
        super().save(*args, **kwargs)
        if is_new and self.notify_subscribers:
            self.notify_subscribers_about_new_book()

    def notify_subscribers_about_new_book(self):
        """Send notifications to subscribers of this book's genre"""
        from .models import BookSubscription  # Import here to avoid circular imports
        
        subscriptions = BookSubscription.objects.filter(
            genre=self.genre,
            is_active=True
        ).select_related('member')
        
        for subscription in subscriptions:
            self.send_new_book_notification(subscription.member)

    def send_new_book_notification(self, member):
        """Send email notification to a single member"""
        subject = f"New Book in {self.get_genre_display()}: {self.title}"
        context = {
            'book': self,
            'member': member,
            'site_url': settings.SITE_URL
        }
        
        html_message = render_to_string('accounts/emails/new_book_notification.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member.email],
            fail_silently=False
        )

    def can_checkout(self):
        """Check if book is available for checkout"""
        return self.available > 0
    
    @transaction.atomic
    def checkout_copy(self):
        """
        Atomically checks out one copy with database-level locking
        Returns True if successful, False if no copies available
        """
        # Refresh with lock to prevent race conditions
        book = Book.objects.select_for_update().get(pk=self.pk)
        if book.available <= 0:
            return False
        book.available -= 1
        book.save()
        return True
    
    @transaction.atomic
    def checkout_copies(self, quantity):
        """
        Atomically checks out multiple copies
        Returns True if successful, False if not enough copies available
        """
        book = Book.objects.select_for_update().get(pk=self.pk)
        if book.available < quantity:
            return False
        book.available -= quantity
        book.save()
        return True
    
    @transaction.atomic
    def return_copy(self):
        """Return one copy if not already at max"""
        book = Book.objects.select_for_update().get(pk=self.pk)
        if book.available < book.quantity:
            book.available += 1
            book.save()
            return True
        return False
    
    @transaction.atomic
    def return_copies(self, quantity):
        """Return multiple copies if possible"""
        book = Book.objects.select_for_update().get(pk=self.pk)
        if (book.available + quantity) <= book.quantity:
            book.available += quantity
            book.save()
            return True
        return False
    
    def get_absolute_url(self):
        return reverse('book-detail', kwargs={'pk': self.pk})

class Checkout(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    member = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    checkout_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    returned = models.BooleanField(default=False)
    return_date = models.DateTimeField(null=True, blank=True)
    daily_fine_rate = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        default=10.00,  # $10 per day fine
        help_text="Daily fine rate for late returns"
    )
    total_fine = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Total fine accumulated"
    )

    def __str__(self):
        status = "Returned" if self.returned else "Checked Out"
        return f"{self.book.title} - {self.member.username} ({status})"

    def clean(self):
        """Validate before saving"""
        if not self.pk and (not self.book.can_checkout() or self.quantity > self.book.available):
            raise ValidationError(f'Not enough available copies (only {self.book.available} left)')
    
    def save(self, *args, **kwargs):
        """Handle checkout/return logic"""
        if not self.pk:  # New checkout
            if not self.book.checkout_copies(self.quantity):
                raise ValidationError("Not enough copies available")
            if not self.due_date:
                self.due_date = timezone.now() + timezone.timedelta(weeks=2)
        
        elif self.returned and not self.return_date:  # Marking as returned
            self.return_date = timezone.now()
            self.book.return_copies(self.quantity)
        
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Handle book return when checkout record is deleted"""
        if not self.returned:
            self.book.return_copies(self.quantity)
        super().delete(*args, **kwargs)

    def mark_returned(self):
        """Mark this checkout as returned and update book availability"""
        with transaction.atomic():
            if not self.returned:
                self.returned = True
                self.return_date = timezone.now()
                self.save()
                self.book.return_copies(self.quantity)
                return True
        return False
    
    def get_due_status(self):
        """Get human-readable due status"""
        if self.returned:
            return "Returned"
        elif self.is_overdue:
            return f"Overdue by {self.days_overdue} day(s)"
        elif self.due_soon:
            return "Due soon"
        return "On time"

    def get_status(self):
        """Get human-readable status"""
        if self.returned:
            return "Returned on {}".format(self.return_date.strftime('%Y-%m-%d'))
        elif timezone.now() > self.due_date:
            return "Overdue ({} days)".format((timezone.now() - self.due_date).days)
        return "Checked Out"
    
    @transaction.atomic
    def return_copies(self, quantity):
        """Return multiple copies to available stock"""
        book = Book.objects.select_for_update().get(pk=self.pk)
        if (book.available + quantity) <= book.quantity:
            book.available += quantity
            book.save()
            return True
        return False
    
    @classmethod
    def get_issued_books_report(cls):
        """Return all currently checked out books"""
        return cls.objects.filter(returned=False).select_related('book', 'member')

    @classmethod
    def get_overdue_books_report(cls):
        """Return all overdue books"""
        return cls.objects.filter(
            returned=False,
            due_date__lt=timezone.now()
        ).select_related('book', 'member')

    @property
    def is_overdue(self):
        """Check if book is overdue"""
        if self.returned:
            return False
        return timezone.now() > self.due_date

    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if not self.is_overdue:
            return 0
        return (timezone.now() - self.due_date).days

    @property
    def due_soon(self):
        """Check if due within 3 days"""
        if self.returned or self.is_overdue:
            return False
        return (self.due_date - timezone.now()).days <= 3
    

    
    
    def calculate_fine(self):
        """Calculate fine based on grace period and max cap"""
        if not self.returned and self.due_date < timezone.now():
            days_late = (timezone.now().date() - self.due_date).days - GRACE_PERIOD_DAYS
            days_late = min(max(days_late, 0), MAX_FINE_DAYS)  # Clamp to 0...30
            return days_late * self.daily_fine_rate
        return 0.0

    def save(self, *args, **kwargs):
        """Auto-calculate fine when saving"""
        if not self.pk:  # New checkout
            self.daily_fine_rate = DEFAULT_DAILY_FINE_RATE

        if self.returned and self.return_date:
            # Final fine on return
            days_late = (self.return_date - self.due_date).days - GRACE_PERIOD_DAYS
            days_late = min(max(days_late, 0), MAX_FINE_DAYS)
            self.total_fine = days_late * self.daily_fine_rate
        else:
            # Ongoing checkout, update fine
            self.total_fine = self.calculate_fine()

        super().save(*args, **kwargs)
        
    @classmethod
    def get_issued_books_report(cls):
        """Generate report of all currently issued books"""
        return cls.objects.filter(returned=False).select_related('book', 'member')

    @classmethod
    def get_overdue_books_report(cls, days_threshold=0):    
        """Generate report of overdue books"""
        from django.utils import timezone
        from datetime import timedelta
        
        overdue = cls.objects.filter(returned=False,due_date__lt=timezone.now() - timedelta(days=days_threshold))
        return overdue.select_related('book', 'member')
    

    def send_due_notification(self):
        """Send notification about upcoming due date"""
        subject = f"Reminder: {self.book.title} due soon"
        context = {
            'book': self.book,
            'due_date': self.due_date,
            'member': self.member,
            'days_remaining': (self.due_date - timezone.now()).days
        }
        
        # Email notification
        html_message = render_to_string('accounts/emails/due_notification.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.member.email],
            fail_silently=False
        )
        
        # SMS notification (optional)
        if hasattr(settings, 'SMS_API_KEY') and self.member.phone:
            self.send_sms_notification(context)

    def send_sms_notification(self, context):
        """Send SMS using external API (Twilio example)"""
        message = (
            f"Hi {context['member'].first_name}, "
            f"'{context['book'].title}' is due on {context['due_date'].strftime('%b %d')}. "
            f"Please return or renew it soon."
        )
        
        try:
            response = requests.post(
                "https://api.twilio.com/2010-04-01/Accounts/ACXXXXXX/Messages.json",
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                data={
                    'From': settings.TWILIO_PHONE_NUMBER,
                    'To': self.member.phone,
                    'Body': message
                }
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")

class BookRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('FULFILLED', 'Fulfilled'),
    ]

    member = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    book_title = models.CharField(max_length=200)
    author = models.CharField(max_length=100, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    request_date = models.DateTimeField(auto_now_add=True)
    response_date = models.DateTimeField(null=True, blank=True)
    response_notes = models.TextField(blank=True)

    def __str__(self):
            return f"{self.book_title} requested by {self.member.username}"

    class Meta:
        ordering = ['-request_date']


class Reservation(models.Model):
    member = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='reservations'
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='reservations'
    )
    reservation_date = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)
    fulfilled = models.BooleanField(default=False)
    expiry_date = models.DateTimeField(
        default=timezone.now() + timezone.timedelta(days=3)
    )

    def send_available_notification(self):
        """Send notification when reserved book becomes available"""
        subject = f"Your reserved book '{self.book.title}' is available"
        context = {
            'book': self.book,
            'member': self.member,
            'pickup_deadline': timezone.now() + timedelta(days=3),
            'site_name': settings.SITE_NAME,
            'site_url': settings.SITE_URL
        }
        
        html_message = render_to_string('accounts/emails/reservation_available.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.member.email],
            fail_silently=False
        )

    def __str__(self):
        return f"{self.member.username}'s reservation for {self.book.title}"

    class Meta:
        ordering = ['reservation_date']

class BookSubscription(models.Model):
    member = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='book_subscriptions'
    )
    genre = models.CharField(
        max_length=3,
        choices=Book.GENRE_CHOICES
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def send_new_book_notification(self, book):
        subject = f"New Book in {self.get_genre_display()}: {book.title}"
        context = {
            'book': book,
            'member': self.member,
            'genre': self.get_genre_display(),
            'site_url': settings.SITE_URL
        }
        
        html_message = render_to_string('accounts/emails/new_book_notification.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.member.email],
            fail_silently=False
        )