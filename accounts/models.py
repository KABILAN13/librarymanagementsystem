from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

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
    quantity = models.PositiveIntegerField(default=1)
    available = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.title} by {self.author}"
    
    def save(self, *args, **kwargs):
        # Ensure available copies don't exceed quantity
        if self.available > self.quantity:
            self.available = self.quantity
        super().save(*args, **kwargs)

