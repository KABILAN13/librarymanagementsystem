from django import template

register = template.Library()

@register.filter(name='filter_genre')
def filter_genre(subscriptions, genre):
    """Filter subscriptions by genre and return the first active one"""
    return subscriptions.filter(genre=genre, is_active=True).first()