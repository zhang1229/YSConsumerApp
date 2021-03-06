# -*- coding:utf8 -*-
from __future__ import unicode_literals

from django.db import models
from django.utils.timezone import now
from horizon.models import model_to_dict
from horizon.main import minutes_30_plus, DatetimeEncode
from django.db import transaction
from decimal import Decimal

from Business_App.bz_dishes.models import Dishes
from Business_App.bz_orders.models import OrdersIdGenerator

import json
import datetime


class OrdersManager(models.Manager):
    def get(self, *args, **kwargs):
        object_data = super(OrdersManager, self).get(*args, **kwargs)
        if now() >= object_data.expires and object_data.payment_status == 0:
            object_data.payment_status = 400
        return object_data

    def filter(self, *args, **kwargs):
        object_data = super(OrdersManager, self).filter(*args, **kwargs)
        for item in object_data:
            if now() >= item.expires and item.payment_status == 0:
                item.payment_status = 400
        return object_data


class PayOrders(models.Model):
    """
    支付订单（主订单）
    """
    orders_id = models.CharField('订单ID', db_index=True, unique=True, max_length=32)
    user_id = models.IntegerField('用户ID', db_index=True)
    food_court_id = models.IntegerField('美食城ID')
    food_court_name = models.CharField('美食城名字', max_length=200)

    dishes_ids = models.TextField('订购列表', default='')
    # 订购列表详情
    # {business_id_1: [订购菜品信息],
    #  business_id_2: [订购菜品信息],
    # }
    #
    total_amount = models.CharField('订单总计', max_length=16)
    member_discount = models.CharField('会员优惠', max_length=16, default='0')
    other_discount = models.CharField('其他优惠', max_length=16, default='0')
    payable = models.CharField('应付金额', max_length=16)

    # 0:未支付 200:已支付 400: 已过期 500:支付失败
    payment_status = models.IntegerField('订单支付状态', default=0)
    # 支付方式：0:未指定支付方式 1：钱包 2：微信支付 3：支付宝支付
    payment_mode = models.IntegerField('订单支付方式', default=0)
    # 订单类型 1: 在线订单 2：堂食订单 3：外卖订单
    orders_type = models.IntegerField('订单类型', default=1)

    created = models.DateTimeField('创建时间', default=now)
    updated = models.DateTimeField('最后修改时间', auto_now=True)
    expires = models.DateTimeField('订单过期时间', default=minutes_30_plus)
    extend = models.TextField('扩展信息', default='', blank=True)

    objects = OrdersManager()

    class Meta:
        db_table = 'ys_pay_orders'
        ordering = ['-orders_id']

    def __unicode__(self):
        return self.orders_id

    @classmethod
    def get_object(cls, **kwargs):
        try:
            return cls.objects.get(**kwargs)
        except Exception as e:
            return e

    @classmethod
    def get_valid_orders(cls, **kwargs):
        kwargs['payment_status'] = 0
        kwargs['expires__gt'] = now()
        try:
            return cls.objects.get(**kwargs)
        except Exception as e:
            setattr(e, 'args', ('Orders %s does not existed or is expired' % kwargs['orders_id'],))
            return e

    @classmethod
    def get_success_orders(cls, **kwargs):
        kwargs['payment_status'] = 200
        try:
            return cls.objects.get(**kwargs)
        except Exception as e:
            return e

    @property
    def dishes_ids_json_detail(self):
        import json
        return self.dishes_ids

    @classmethod
    def get_dishes_ids_detail(cls, dishes_ids):
        dishes_details = {}
        dishes_details_list = []
        food_court_id = None
        food_court_name = None
        for item in dishes_ids:
            dishes_id = item['dishes_id']
            count = item['count']
            detail_dict = Dishes.get_dishes_detail_dict_with_user_info(pk=dishes_id)
            if isinstance(detail_dict, Exception):
                raise ValueError('Dishes ID %s does not existed' % dishes_id)
            detail_dict['count'] = count

            business_list = dishes_details.get(detail_dict['business_id'], [])
            business_list.append(detail_dict)
            dishes_details[detail_dict['business_id']] = business_list
            if not food_court_id:
                food_court_id = detail_dict['food_court_id']
                food_court_name = detail_dict['food_court_name']
            if food_court_id != detail_dict['food_court_id']:
                raise ValueError('One orders cannot contain multiple food court')

        for business_id in sorted(dishes_details.keys()):
            detail_dict = {'dishes_detail': dishes_details[business_id],
                           'business_id': business_id,
                           'business_name': dishes_details[business_id][0]['business_name']}
            dishes_details_list.append(detail_dict)

        return food_court_id, food_court_name, dishes_details_list

    @classmethod
    def make_orders_by_dishes_ids(cls, request, dishes_ids):
        meal_ids = []
        total_amount = '0'
        try:
            food_court_id, food_court_name, dishes_details = \
                cls.get_dishes_ids_detail(dishes_ids)
        except Exception as e:
            return e
        for _details in dishes_details:
            for item2 in _details['dishes_detail']:
                total_amount = str(Decimal(total_amount) +
                                   Decimal(item2['price']) * item2['count'])
        # 会员优惠及其他优惠
        member_discount = 0
        other_discount = 0
        orders_data = {'user_id': request.user.id,
                       'orders_id': OrdersIdGenerator.get_orders_id(),
                       'food_court_id': food_court_id,
                       'food_court_name': food_court_name,
                       'dishes_ids': json.dumps(dishes_details, ensure_ascii=False, cls=DatetimeEncode),
                       'total_amount': total_amount,
                       'member_discount': str(member_discount),
                       'other_discount': str(other_discount),
                       'payable': str(Decimal(total_amount) -
                                      Decimal(member_discount) -
                                      Decimal(other_discount))
                       }
        return orders_data

    @classmethod
    def update_payment_status_by_pay_callback(cls, orders_id, validated_data):
        if not isinstance(validated_data, dict):
            raise ValueError('Parameter error')

        payment_status = validated_data.get('payment_status')
        payment_mode = validated_data.get('payment_mode')
        if payment_status not in (200, 400, 500):
            raise ValueError('Payment status must in range [200, 400, 500]')
        if payment_mode not in [1, 2, 3]:    # 钱包支付、微信支付和支付宝支付
            raise ValueError('Payment mode must in range [1, 2, 3]')
        instance = None
        # 数据库加排它锁，保证更改信息是列队操作的，防止数据混乱
        with transaction.atomic():
            try:
                _instance = cls.objects.select_for_update().get(orders_id=orders_id)
            except cls.DoesNotExist:
                raise cls.DoesNotExist
            if _instance.payment_status != 0:
                raise Exception('Cannot perform this action')
            _instance.payment_status = payment_status
            _instance.payment_mode = payment_mode
            _instance.save()
            instance = _instance
        return instance


class ConsumeOrders(models.Model):
    """
    消费订单（子订单）
    """
    orders_id = models.CharField('订单ID', db_index=True, unique=True, max_length=32)
    user_id = models.IntegerField('用户ID', db_index=True)

    business_name = models.CharField('商户名字', max_length=200)
    business_id = models.IntegerField('商户ID')
    food_court_id = models.IntegerField('美食城ID')
    food_court_name = models.CharField('美食城名字', max_length=200)

    dishes_ids = models.TextField('订购列表', default='')

    total_amount = models.CharField('订单总计', max_length=16)
    member_discount = models.CharField('会员优惠', max_length=16, default='0')
    other_discount = models.CharField('其他优惠', max_length=16, default='0')
    payable = models.CharField('应付金额', max_length=16)

    # 0:未支付 200:已支付 201:待消费 206:已完成 400: 已过期 500:支付失败
    payment_status = models.IntegerField('订单支付状态', default=201)
    # 支付方式：0:未指定支付方式 1：现金支付 2：微信支付 3：支付宝支付
    payment_mode = models.IntegerField('订单支付方式', default=0)
    # 订单类型 1: 在线订单 2：堂食订单
    orders_type = models.IntegerField('订单类型', default=1)
    # 所属主订单
    master_orders_id = models.CharField('所属主订单订单ID', max_length=32)

    created = models.DateTimeField('创建时间', default=now)
    updated = models.DateTimeField('最后修改时间', auto_now=True)
    expires = models.DateTimeField('订单过期时间', default=minutes_30_plus)
    extend = models.TextField('扩展信息', default='', blank=True)

    objects = OrdersManager()

    class Meta:
        db_table = 'ys_consume_orders'
        ordering = ['-orders_id']

    def __unicode__(self):
        return self.orders_id

#
#     @classmethod
#     def update_payment_status_by_pay_callback(cls, orders_id, validated_data):
#         if not isinstance(validated_data, dict):
#             raise ValueError('Parameter error')
#
#         payment_status = validated_data.get('payment_status')
#         payment_mode = validated_data.get('payment_mode')
#         if payment_status not in (200, 400, 500):
#             raise ValueError('Payment status must in range [200, 400, 500]')
#         if payment_mode not in [2, 3]:    # 微信支付和支付宝支付
#             raise ValueError('Payment mode must in range [2, 3]')
#         instance = None
#         # 数据库加排它锁，保证更改信息是列队操作的，防止数据混乱
#         with transaction.atomic():
#             try:
#                 _instance = cls.objects.select_for_update().get(orders_id=orders_id)
#             except cls.DoesNotExist:
#                 raise cls.DoesNotExist
#             if _instance.payment_status != 0:
#                 raise Exception('Cannot perform this action')
#             _instance.payment_status = payment_status
#             _instance.payment_mode = payment_mode
#             _instance.save()
#             instance = _instance
#         return instance


class TradeRecord(models.Model):
    """
    交易记录
    """
    serial_number = models.CharField('交易流水号', db_index=True, max_length=64)
    orders_id = models.CharField('订单ID', db_index=True, max_length=32)
    user_id = models.IntegerField('用户ID')

    total_amount = models.CharField('应付金额', max_length=16)
    member_discount = models.CharField('会员优惠', max_length=16, default='0')
    other_discount = models.CharField('其他优惠', max_length=16, default='0')
    payment = models.CharField('实付金额', max_length=16)

    # 支付结果: SUCCESS: 成功 FAIL：失败 UNKNOWN: 未知
    payment_result = models.IntegerField('支付结果', default='UNKNOWN')
    # 支付方式：0:未指定支付方式 1：钱包支付 2：微信支付 3：支付宝支付
    payment_mode = models.IntegerField('订单支付方式', default=0)

    # 第三方支付订单号
    out_orders_id = models.CharField('第三方订单号', max_length=64, null=True)

    created = models.DateTimeField('创建时间', default=now)
    extend = models.TextField('扩展信息', default='', blank=True)

    objects = OrdersManager()


def date_for_model():
    return now().date()


class SerialNumberGenerator(models.Model):
    date = models.DateField('日期', primary_key=True, default=date_for_model)
    serial_number = models.IntegerField('订单ID', default=1)
    created = models.DateTimeField('创建日期', default=now)
    updated = models.DateTimeField('最后更改日期', auto_now=True)

    class Meta:
        db_table = 'ys_serial_number_generator'

    def __unicode__(self):
        return str(self.date)

    @classmethod
    def int_to_string(cls, serial_no):
        return "%06d" % serial_no

    @classmethod
    def get_serial_number(cls):
        date_day = date_for_model()
        # 数据库加排它锁，保证订单号是唯一的
        with transaction.atomic():
            try:
                _instance = cls.objects.select_for_update().get(pk=date_day)
            except cls.DoesNotExist:
                cls().save()
                serial_no = 1
            else:
                serial_no = _instance.serial_number + 1
                _instance.serial_number = serial_no
                _instance.save()
        serial_no_str = cls.int_to_string(serial_no)
        return 'LS%s%s' % (date_day.strftime('%Y%m%d'), serial_no_str)
