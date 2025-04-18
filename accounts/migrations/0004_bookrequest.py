# Generated by Django 5.2 on 2025-04-07 06:09

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_checkout_quantity_alter_book_available_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book_title', models.CharField(max_length=200)),
                ('author', models.CharField(blank=True, max_length=100)),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('FULFILLED', 'Fulfilled')], default='PENDING', max_length=10)),
                ('request_date', models.DateTimeField(auto_now_add=True)),
                ('response_date', models.DateTimeField(blank=True, null=True)),
                ('response_notes', models.TextField(blank=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-request_date'],
            },
        ),
    ]
