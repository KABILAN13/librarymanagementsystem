from django.contrib.auth.models import AbstractUser
from django.db import models
from django.forms import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from datetime import timedelta


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
    
    def __str__(self):
        return f"{self.title} by {self.author}"
    
    def save(self, *args, **kwargs):
        """Ensure availability stays within bounds"""
        if not self.pk:  # New book
            self.available = self.quantity
        self.available = max(0, min(self.available, self.quantity))
        super().save(*args, **kwargs)

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
        """Calculate and update the fine for late returns"""
        if not self.returned and self.due_date < timezone.now():
            days_late = (timezone.now() - self.due_date).days
            self.total_fine = days_late * self.daily_fine_rate
            self.save()
        return self.total_fine
    
    def save(self, *args, **kwargs):
        """Auto-calculate fine when saving"""
        if not self.pk:  # New checkout
            self.daily_fine_rate = settings.DEFAULT_DAILY_FINE_RATE
        
        if self.returned and self.return_date:
            # Calculate final fine if returned late
            if self.return_date > self.due_date:
                days_late = (self.return_date - self.due_date).days
                self.total_fine = days_late * self.daily_fine_rate
        else:
            # Calculate current fine for active late checkouts
            self.calculate_fine()
            
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