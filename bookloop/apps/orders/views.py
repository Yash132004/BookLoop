from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.books.models import BookListing

from .forms import CheckoutForm
from .models import Order


SHIPPING_COST = Decimal('50.00')


@login_required
def checkout(request, book_id):
    book = get_object_or_404(
        BookListing.objects.select_related('seller'),
        pk=book_id,
    )

    if not book.is_available:
        messages.error(request, 'This book is no longer available.')
        return redirect('books:detail', pk=book.pk)

    if book.seller_id == request.user.pk:
        messages.error(request, 'You cannot buy your own listing.')
        return redirect('books:detail', pk=book.pk)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Lock and re-check the listing so two buyers cannot both order it.
                book = get_object_or_404(
                    BookListing.objects.select_for_update(),
                    pk=book_id,
                )
                if not book.is_available:
                    messages.error(request, 'This book was just purchased by someone else.')
                    return redirect('books:detail', pk=book.pk)

                if book.seller_id == request.user.pk:
                    messages.error(request, 'You cannot buy your own listing.')
                    return redirect('books:detail', pk=book.pk)

                order = Order.objects.create(
                    buyer=request.user,
                    book=book,
                    shipping_address=form.cleaned_data['shipping_address'],
                    shipping_cost=SHIPPING_COST,
                    total_price=book.price + SHIPPING_COST,
                    status=Order.Status.PENDING,
                )
                book.is_available = False
                book.save(update_fields=['is_available'])

            return redirect('orders:success', order_id=order.pk)
    else:
        form = CheckoutForm()

    return render(request, 'orders/checkout.html', {
        'book': book,
        'form': form,
        'shipping_cost': SHIPPING_COST,
        'total_price': book.price + SHIPPING_COST,
    })


@login_required
def order_success(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('book', 'book__seller'),
        pk=order_id,
        buyer=request.user,
    )
    return render(request, 'orders/success.html', {'order': order})


@login_required
def my_orders(request):
    orders = (
        Order.objects.filter(buyer=request.user)
        .select_related('book', 'book__seller')
        .order_by('-created_at')
    )
    return render(request, 'orders/my_orders.html', {'orders': orders})
