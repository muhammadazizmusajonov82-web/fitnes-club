from datetime import timedelta
from decimal import Decimal, InvalidOperation
from hashlib import md5
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import RegistrationForm
from .models import BankCard, MembershipPlan, PaymentTransaction, Trainer, UserSubscription, WorkoutType


def landing_page(request):
    return render(request, 'ilovalar/landing.html')


def robots_txt(request):
    sitemap_url = request.build_absolute_uri('/sitemap.xml')
    return HttpResponse(
        f'User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /dashboard/\n'
        f'Disallow: /payments/\nSitemap: {sitemap_url}\n',
        content_type='text/plain',
    )


def home(request):
    context = {
        'trainers': Trainer.objects.all(),
        'workouts': WorkoutType.objects.all(),
        'plans': MembershipPlan.objects.all(),
        'form': RegistrationForm(),
    }
    return render(request, 'ilovalar/home.html', context)


def trainer_detail(request, trainer_id):
    trainer = get_object_or_404(Trainer, pk=trainer_id)
    context = {
        'trainer': trainer,
    }
    return render(request, 'ilovalar/trainer_detail.html', context)


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Ro\'yxatdan o\'tdingiz va tizimga kirdingiz.')
            return redirect('home')
    else:
        form = RegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def buy_membership(request, plan_id):
    plan = get_object_or_404(MembershipPlan, pk=plan_id)

    if request.method == 'GET':
        return render(request, 'ilovalar/payment.html', {'plan': plan})

    payment_method = request.POST.get('payment_method', 'cash')
    amount_text = request.POST.get('amount') or str(plan.price)
    full_name = (request.POST.get('full_name') or '').strip()
    card_number = (request.POST.get('card_number') or '').strip()

    if not full_name:
        full_name = request.user.get_full_name() or request.user.username

    try:
        amount = Decimal(amount_text)
    except (InvalidOperation, TypeError, ValueError):
        messages.error(request, 'To`lov summasi noto`g`ri kiritildi.')
        return redirect('buy_membership', plan_id=plan.id)

    if amount < plan.price:
        messages.error(request, 'Mablag` yetarli emas. To`lov summasi abonement narxidan kam bo`lmasligi kerak.')
        return redirect('buy_membership', plan_id=plan.id)

    if payment_method == 'click':
        click_settings = (
            settings.CLICK_SERVICE_ID,
            settings.CLICK_MERCHANT_ID,
            settings.CLICK_SECRET_KEY,
        )
        if not all(click_settings):
            messages.error(request, 'Click to\'lov hali sozlanmagan. Merchant ma\'lumotlarini kiriting.')
            return redirect('buy_membership', plan_id=plan.id)

        transaction = PaymentTransaction.objects.create(
            user=request.user,
            plan=plan,
            merchant_trans_id=f'fitclub-{request.user.pk}-{uuid4().hex}',
            amount=plan.price,
        )
        checkout_url = getattr(settings, 'CLICK_CHECKOUT_URL', 'https://my.click.uz/services/pay')
        return redirect(
            f'{checkout_url}?service_id={settings.CLICK_SERVICE_ID}'
            f'&merchant_id={settings.CLICK_MERCHANT_ID}'
            f'&amount={transaction.amount}'
            f'&transaction_param={transaction.merchant_trans_id}'
            f'&return_url={request.build_absolute_uri("/dashboard/")}'
        )

    if payment_method == 'card':
        if not card_number:
            messages.error(request, 'Karta raqamini kiriting.')
            return redirect('buy_membership', plan_id=plan.id)

        normalized_card = ''.join(ch for ch in card_number if ch.isdigit())
        card = BankCard.objects.filter(card_number__icontains=normalized_card).first()
        if not card:
            messages.error(request, 'Karta mavjud emas.')
            return redirect('buy_membership', plan_id=plan.id)
        if card.balance < amount:
            messages.error(request, 'Kartada yetarli mablag` mavjud emas.')
            return redirect('buy_membership', plan_id=plan.id)
        if request.POST.get('confirm_card') != '1':
            return render(request, 'ilovalar/payment.html', {
                'plan': plan,
                'card_owner': card.owner_name,
                'card_verified': True,
                'amount': amount,
                'full_name': full_name,
                'card_number': card_number,
            })
        card.balance -= amount
        card.save(update_fields=['balance'])

    elif payment_method != 'cash':
        messages.error(request, 'To`lov usuli tanlanmadi.')
        return redirect('buy_membership', plan_id=plan.id)

    today = timezone.localdate()
    subscription, _ = UserSubscription.objects.get_or_create(user=request.user)
    subscription.plan = plan
    subscription.start_date = today
    subscription.end_date = today + timedelta(days=plan.duration_days)
    subscription.is_active = True
    subscription.save()

    payment_label = 'Naqt pul' if payment_method == 'cash' else 'Karta'
    messages.success(request, f'{plan.name} abonementi muvaffaqiyatli sotib olindi. To`lov usuli: {payment_label}.')
    return redirect('dashboard')


@csrf_exempt
def click_callback(request):
    data = request.POST or request.GET
    required = ('click_trans_id', 'service_id', 'merchant_trans_id', 'amount', 'action', 'sign_time', 'sign_string')
    if any(not data.get(field) for field in required):
        return JsonResponse({'error': -8, 'error_note': 'Required parameter is missing'})

    sign_data = (
        data['click_trans_id'] + data['service_id'] + settings.CLICK_SECRET_KEY
        + data['merchant_trans_id'] + data['amount'] + data['action'] + data['sign_time']
    )
    if data['action'] == '1':
        sign_data += data.get('merchant_prepare_id', '')
    if md5(sign_data.encode()).hexdigest() != data['sign_string']:
        return JsonResponse({'error': -1, 'error_note': 'SIGN CHECK FAILED'})

    try:
        transaction = PaymentTransaction.objects.get(merchant_trans_id=data['merchant_trans_id'])
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({'error': -5, 'error_note': 'Transaction does not exist'})

    if data['service_id'] != str(settings.CLICK_SERVICE_ID) or Decimal(data['amount']) != transaction.amount:
        return JsonResponse({'error': -2, 'error_note': 'Invalid transaction data'})

    if data.get('error', '0') != '0':
        transaction.status = 'failed'
        transaction.save(update_fields=['status'])
        return JsonResponse({'error': 0, 'error_note': 'Transaction cancelled'})

    if data['action'] == '0':
        transaction.click_trans_id = data['click_trans_id']
        transaction.merchant_prepare_id = str(transaction.pk)
        transaction.status = 'prepared'
        transaction.save(update_fields=['click_trans_id', 'merchant_prepare_id', 'status'])
        return JsonResponse({
            'click_trans_id': data['click_trans_id'],
            'merchant_trans_id': transaction.merchant_trans_id,
            'merchant_prepare_id': transaction.merchant_prepare_id,
            'error': 0,
            'error_note': 'Success',
        })

    if data['action'] == '1':
        if transaction.status != 'paid':
            transaction.status = 'paid'
            transaction.paid_at = timezone.now()
            transaction.save(update_fields=['status', 'paid_at'])
            subscription, _ = UserSubscription.objects.get_or_create(user=transaction.user)
            subscription.plan = transaction.plan
            subscription.start_date = timezone.localdate()
            subscription.end_date = subscription.start_date + timedelta(days=transaction.plan.duration_days)
            subscription.is_active = True
            subscription.save()
        return JsonResponse({
            'click_trans_id': data['click_trans_id'],
            'merchant_trans_id': transaction.merchant_trans_id,
            'merchant_prepare_id': transaction.merchant_prepare_id,
            'error': 0,
            'error_note': 'Success',
        })

    return JsonResponse({'error': -3, 'error_note': 'Action not found'})


@login_required
def dashboard(request):
    try:
        subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        subscription = None

    context = {
        'subscription': subscription,
    }
    return render(request, 'ilovalar/dashboard.html', context)
