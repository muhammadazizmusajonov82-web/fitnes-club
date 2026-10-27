from django.contrib import admin
from .models import BankCard, PaymentTransaction, Trainer, WorkoutType, MembershipPlan, UserSubscription


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'specialty')
    search_fields = ('full_name', 'specialty')


@admin.register(WorkoutType)
class WorkoutTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    filter_horizontal = ('trainers',)


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days')
    search_fields = ('name',)


@admin.register(BankCard)
class BankCardAdmin(admin.ModelAdmin):
    list_display = ('owner_name', 'card_number', 'balance')
    search_fields = ('owner_name', 'card_number')


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('merchant_trans_id', 'user', 'plan', 'amount', 'status', 'created_at')
    list_filter = ('status', 'plan')
    search_fields = ('merchant_trans_id', 'click_trans_id', 'user__username')


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'plan')
    search_fields = ('user__username', 'plan__name')
