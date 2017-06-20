# -*- coding:utf8 -*-
from __future__ import unicode_literals

from django.db import models
from django.utils.timezone import now
from django.conf import settings
from Business_App.bz_users.models import BusinessUser
from horizon.models import model_to_dict
from django.conf import settings
import os


class DishesManager(models.Manager):
    def get(self, *args, **kwargs):
        object_data = super(DishesManager, self).get(status=1, *args, **kwargs)
        return object_data

    def filter(self, *args, **kwargs):
        object_data = super(DishesManager, self).filter(status=1, *args, **kwargs)
        return object_data


DISHES_PICTURE_DIR = settings.PICTURE_DIRS['business']['dishes']


class Dishes(models.Model):
    """
    菜品信息表
    """
    title = models.CharField('菜品名称', null=False, max_length=200)
    subtitle = models.CharField('菜品副标题', max_length=200, default='')
    description = models.TextField('菜品描述', default='')
    size = models.IntegerField('菜品规格', default=10)         # 默认：10，小份：11，中份：12，大份：13
    price = models.CharField('价格', max_length=50, null=False)
    image = models.ImageField('菜品图片',
                              upload_to=DISHES_PICTURE_DIR,
                              default=os.path.join(DISHES_PICTURE_DIR, 'noImage.png'),)
    user_id = models.IntegerField('创建者ID', null=False)
    created = models.DateTimeField('创建时间', default=now)
    updated = models.DateTimeField('最后修改时间', auto_now=True)
    status = models.IntegerField('数据状态', default=1)   # 1 有效 2 已删除 3 其他（比如暂时不用）
    is_recommend = models.BooleanField('是否推荐该菜品', default=False)   # 0: 不推荐  1：推荐
    extend = models.TextField('扩展信息', default='', blank=True)

    objects = DishesManager()

    class Meta:
        db_table = 'ys_dishes'
        unique_together = ('title', 'user_id', 'size')

    def __unicode__(self):
        return self.title

    @classmethod
    def get_object(cls, **kwargs):
        try:
            return cls.objects.get(**kwargs)
        except Exception as e:
            return e

    @classmethod
    def get_dishes_detail_dict_with_user_info(cls, **kwargs):
        instance = cls.get_object(**kwargs)
        if isinstance(instance, Exception):
            return instance
        user = BusinessUser.get_object(pk=instance.user_id)
        dishes_dict = model_to_dict(instance)
        dishes_dict['business_name'] = getattr(user, 'business_name', '')

        base_dir = str(dishes_dict['image']).split('static', 1)[1]
        if base_dir.startswith(os.path.sep):
            base_dir = base_dir[1:]
        dishes_dict.pop('image')
        dishes_dict['image_url'] = os.path.join(settings.WEB_URL_FIX,
                                                'static',
                                                base_dir)
        return dishes_dict