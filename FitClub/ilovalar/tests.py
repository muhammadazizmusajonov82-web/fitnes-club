from datetime import date, timedelta
from hashlib import md5

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import BankCard, MembershipPlan, PaymentTransaction, Trainer, UserSubscription, WorkoutType


class FitClubViewsTestCase(TestCase):
    def setUp(self):
        self.trainer = Trainer.objects.create(
            full_name='Alisher Karimov',
            bio='Jismoniy tayyorgarlik bo‘yicha mutaxassis.',
            specialty='Kardio trening',
        )
        self.workout = WorkoutType.objects.create(
            name='Yoga',
            description="Kundalik muvozanatli mashg'ulot.",
        )
        self.workout.trainers.add(self.trainer)

        self.plan = MembershipPlan.objects.create(
            name='Premium',
            price=250000,
            duration_days=30,
            description="To'liq vaqtdagi mashg'ulotlar.",
        )

        self.user = User.objects.create_user(username='demo', password='secret123')
        self.subscription = UserSubscription.objects.create(
            user=self.user,
            plan=self.plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
        )

    def test_landing_page_renders_welcome_and_register_button(self):
        response = self.client.get(reverse('landing_page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'FitClubga hush kelibsiz')
        self.assertContains(response, 'Kirish')
        self.assertNotContains(response, 'id_username')

    def test_public_seo_routes_are_available(self):
        landing = self.client.get(reverse('landing_page'))
        robots = self.client.get(reverse('robots_txt'))
        sitemap = self.client.get(reverse('sitemap'))

        self.assertContains(landing, 'FitClub | Toshkentdagi fitnes klubi')
        self.assertContains(landing, 'name="description"')
        self.assertEqual(robots.status_code, 200)
        self.assertContains(robots, 'Sitemap:')
        self.assertEqual(sitemap.status_code, 200)
        self.assertContains(sitemap, '/home/')

    def test_dashboard_shows_subscription_status_for_remaining_days(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Obuna holati')
        self.assertContains(response, 'kun qoldi')

    def test_user_can_buy_membership_plan(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('buy_membership', args=[self.plan.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

        subscription = UserSubscription.objects.get(user=self.user)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.days_left, self.plan.duration_days)

    def test_trainer_detail_page_shows_profile_details_without_signup_cta(self):
        response = self.client.get(reverse('trainer_detail', args=[self.trainer.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.trainer.full_name)
        self.assertContains(response, self.trainer.specialty)
        self.assertContains(response, 'yillik')
        self.assertNotContains(response, 'Ro\'yxatdan o\'tish')
        self.assertNotContains(response, reverse('register'))

    def test_card_payment_debits_balances_when_card_exists(self):
        self.client.force_login(self.user)
        BankCard.objects.create(owner_name='Demo User', card_number='5555000011112222', balance=500000)

        response = self.client.post(reverse('buy_membership', args=[self.plan.pk]), {
            'payment_method': 'card',
            'amount': '250000',
            'full_name': 'Demo User',
            'card_number': '5555 0000 1111 2222',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Karta egasi:')
        self.assertContains(response, 'Demo User')

        response = self.client.post(reverse('buy_membership', args=[self.plan.pk]), {
            'payment_method': 'card',
            'amount': '250000',
            'full_name': 'Demo User',
            'card_number': '5555 0000 1111 2222',
            'confirm_card': '1',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'muvaffaqiyatli sotib olindi')
        card = BankCard.objects.get(owner_name='Demo User')
        self.assertEqual(card.balance, 250000)

    def test_card_payment_rejects_insufficient_balance(self):
        self.client.force_login(self.user)
        BankCard.objects.create(owner_name='Demo User', card_number='5555000011112222', balance=100000)

        response = self.client.post(reverse('buy_membership', args=[self.plan.pk]), {
            'payment_method': 'card',
            'amount': '250000',
            'full_name': 'Demo User',
            'card_number': '5555 0000 1111 2222',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kartada yetarli mablag` mavjud emas.')
        self.assertEqual(BankCard.objects.get(owner_name='Demo User').balance, 100000)

    def test_card_payment_rejects_amount_below_membership_price(self):
        self.client.force_login(self.user)
        BankCard.objects.create(owner_name='Demo User', card_number='5555000011112222', balance=500000)

        response = self.client.post(reverse('buy_membership', args=[self.plan.pk]), {
            'payment_method': 'card',
            'amount': '100000',
            'full_name': 'Demo User',
            'card_number': '5555 0000 1111 2222',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mablag` yetarli emas.')
        self.assertEqual(BankCard.objects.get(owner_name='Demo User').balance, 500000)

    def test_cash_payment_rejects_amount_below_membership_price(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('buy_membership', args=[self.plan.pk]), {
            'payment_method': 'cash',
            'amount': '12000',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mablag` yetarli emas.')
        self.assertEqual(UserSubscription.objects.get(user=self.user).plan, self.plan)

    def test_payment_page_does_not_show_recipient_card(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('buy_membership', args=[self.plan.pk]))

        self.assertNotContains(response, '9860170112383857')

    def test_card_payment_rejects_missing_card(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('buy_membership', args=[self.plan.pk]), {
            'payment_method': 'card',
            'amount': '250000',
            'full_name': 'Not Found User',
            'card_number': '1111222233334444',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Karta mavjud emas')

    def test_user_can_register_and_land_on_home(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'StrongPass123',
            'password2': 'StrongPass123',
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_payment_page_requires_card_number_for_card_payment(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('buy_membership', args=[self.plan.pk]), {
            'payment_method': 'card',
            'amount': '250000',
            'full_name': 'Demo User',
            'card_number': '',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Karta raqamini kiriting.')

    @override_settings(CLICK_SERVICE_ID='123', CLICK_MERCHANT_ID='456', CLICK_SECRET_KEY='secret')
    def test_click_payment_creates_transaction_and_redirects(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('buy_membership', args=[self.plan.pk]), {
            'payment_method': 'click',
        })

        transaction = PaymentTransaction.objects.get(user=self.user)
        self.assertEqual(response.status_code, 302)
        self.assertIn('service_id=123', response['Location'])
        self.assertIn(transaction.merchant_trans_id, response['Location'])

    @override_settings(CLICK_SERVICE_ID='123', CLICK_SECRET_KEY='secret')
    def test_click_complete_callback_activates_subscription(self):
        transaction = PaymentTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            merchant_trans_id='fitclub-test-transaction',
            amount=self.plan.price,
        )
        callback_data = {
            'click_trans_id': 'click-1',
            'service_id': '123',
            'merchant_trans_id': transaction.merchant_trans_id,
            'amount': str(transaction.amount),
            'action': '1',
            'sign_time': '2026-09-08 12:00:00',
            'merchant_prepare_id': str(transaction.pk),
        }
        sign_data = ''.join(callback_data[field] for field in (
            'click_trans_id', 'service_id',
        )) + settings.CLICK_SECRET_KEY + ''.join(callback_data[field] for field in (
            'merchant_trans_id', 'amount', 'action', 'sign_time', 'merchant_prepare_id',
        ))
        callback_data['sign_string'] = md5(sign_data.encode()).hexdigest()

        response = self.client.post(reverse('click_callback'), callback_data)

        self.assertEqual(response.json()['error'], 0)
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, 'paid')
        self.assertEqual(UserSubscription.objects.get(user=self.user).plan, self.plan)
