# -*- coding:utf8 -*-
from __future__ import unicode_literals

from django.db import models
from django.utils.timezone import now
from users.models import ConsumerUser
from Business_App.bz_dishes.models import Dishes
from horizon.models import model_to_dict
from horizon.main import minutes_30_plus
from django.db import transaction
from decimal import Decimal

import json
import datetime


class ShoppingCartManager(models.Manager):
    def get(self, *args, **kwargs):
        kwargs['status'] = 1
        return super(ShoppingCartManager, self).get(*args, **kwargs)

    def filter(self, *args, **kwargs):
        kwargs['status'] = 1
        return super(ShoppingCartManager, self).filter(*args, **kwargs)


class ShoppingCart(models.Model):
    user_id = models.IntegerField('用户ID', db_index=True)
    dishes_id = models.IntegerField('菜品ID', db_index=True, unique=True)
    count = models.IntegerField('数量',)

    # 购物车中商品状态 1：有效 2：已删除 3：其它（预留状态）
    status = models.IntegerField('购物车中商品状态', default=1)
    # 商品是否被选中（用来进行结算） 0：未选中，1：已选中
    selected = models.IntegerField('商品是否被选中', default=0)

    created = models.DateTimeField('创建时间', default=now)
    updated = models.DateTimeField('最后修改时间', auto_now=True)
    extend = models.TextField('扩展信息', default='', blank=True)

    objects = ShoppingCartManager()

    class Meta:
        db_table = 'ys_shopping_cart'
        ordering = ['-updated']

    def __unicode__(self):
        return self.user_id

    @classmethod
    def get_object_by_dishes_id(cls, request, dishes_id):
        kwargs = {'user_id': request.user.id,
                  'dishes_id': dishes_id}
        try:
            return cls.objects.get(**kwargs)
        except Exception as e:
            return e

    @classmethod
    def get_shopping_cart_by_user_id(cls, request):
        return cls.objects.filter(user_id=request.user.id)

    @classmethod
    def get_shopping_cart_detail_by_user_id(cls, request):
        meal_ids = []
        for item in cls.get_shopping_cart_by_user_id(request):
            dishes_data = Dishes.get_dishes_detail_dict_with_user_info(pk=item.dishes_id)
            if isinstance(dishes_data, Exception):
                continue
            dishes_dict = dishes_data
            item_dict = model_to_dict(item)
            item_dict['dishes_detail'] = dishes_dict
            meal_ids.append(item_dict)
        return meal_ids


class DatetimeEncode(json.JSONEncoder):
    def default(self, o):
        from django.db.models.fields.files import ImageFieldFile

        if isinstance(o, datetime.datetime):
            return str(o)
        elif isinstance(o, ImageFieldFile):
            return str(o)
        else:
            return json.JSONEncoder.default(self, o)
