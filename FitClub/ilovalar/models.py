from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class BankCard(models.Model):
    owner_name = models.CharField(max_length=120, verbose_name="Karta egasining ismi va familyasi")
    card_number = models.CharField(max_length=20, unique=True, verbose_name="Karta raqami")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Balans")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bank kartasi'
        verbose_name_plural = 'Bank kartalari'

    def __str__(self):
        return f"{self.owner_name} - {self.card_number[-4:]}"


class PaymentTransaction(models.Model):
    STATUS_CHOICES = (
        ('created', 'Yaratilgan'),
        ('prepared', 'Tayyorlangan'),
        ('paid', 'To\'langan'),
        ('failed', 'Xatolik'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_transactions')
    plan = models.ForeignKey('MembershipPlan', on_delete=models.PROTECT)
    merchant_trans_id = models.CharField(max_length=100, unique=True)
    click_trans_id = models.CharField(max_length=100, blank=True)
    merchant_prepare_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Click to\'lov tranzaksiyasi'
        verbose_name_plural = 'Click to\'lov tranzaksiyalari'

    def __str__(self):
        return f'{self.merchant_trans_id} - {self.status}'

class Trainer(models.Model):
    full_name = models.CharField(max_length=100, verbose_name="To'liq ismi")
    age = models.IntegerField(default=25, verbose_name="Yoshi")
    specialty = models.CharField(max_length=100, verbose_name="Mutaxassisligi")
    experience_years = models.IntegerField(default=3, verbose_name="Tajribasi (yil)")
    location = models.CharField(max_length=100, default='Toshkent', verbose_name="Joylashuvi")
    phone = models.CharField(max_length=20, blank=True, default='', verbose_name="Telefon")
    bio = models.TextField(verbose_name="Biografiyasi")
    image = models.ImageField(upload_to='trainers/', blank=True, null=True, verbose_name="Rasmi")

    class Meta:
        verbose_name = 'Trener'
        verbose_name_plural = 'Trenerlar'

    @property
    def experience_text(self):
        return f"{self.experience_years} yillik tajriba"

    def __str__(self):
        return self.full_name


class WorkoutType(models.Model):
    name = models.CharField(max_length=50, verbose_name="Mashg'ulot nomi")
    description = models.TextField(verbose_name="Tavsifi")
    trainers = models.ManyToManyField(Trainer, related_name="workouts", verbose_name="Trenerlar")

    class Meta:
        verbose_name = 'Mashg\'ulot turi'
        verbose_name_plural = 'Mashg\'ulot turlari'

    def __str__(self):
        return self.name


class MembershipPlan(models.Model):
    name = models.CharField(max_length=50, verbose_name="Abonement nomi")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Narxi")
    duration_days = models.IntegerField(default=30, verbose_name="Amal qilish muddati (kun)")
    description = models.TextField(verbose_name="Batafsil")

    class Meta:
        verbose_name = 'Abonement turi'
        verbose_name_plural = 'Abonement turlari'

    def __str__(self):
        return f"{self.name} - {self.price} UZS"


class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Foydalanuvchi abonementi'
        verbose_name_plural = 'Foydalanuvchi abonementlari'

    def save(self, *args, **kwargs):
        if self.plan and not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
        self.is_active = bool(self.plan and self.end_date and self.end_date >= timezone.localdate())
        super().save(*args, **kwargs)

    @property
    def days_left(self):
        today = timezone.localdate()
        if not self.plan or not self.end_date or self.end_date < today:
            return 0
        return (self.end_date - today).days

    @property
    def status_message(self):
        days = self.days_left
        if days <= 0:
            return "Obuna muddati tugagan ❌"
        if days <= 5:
            return f"Ogohlantirish: obuna tugashiga {days} kun qoldi! ⚠️"
        return f"Faol: obuna amal qilishiga {days} kun qoldi ✅"

    def __str__(self):
        return f"{self.user.username} - {self.plan.name if self.plan else 'Plan yoq'}"
