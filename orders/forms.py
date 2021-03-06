# -*- encoding: utf-8 -*-
from horizon import forms


class PayOrdersCreateForm(forms.Form):
    dishes_ids = forms.CharField()
    # dishes_ids包含如下信息
    # dishes_ids = [{'dishes_id': 'xxx',
    #                'count': xxx}, {}, ...
    #              ]
    #
    # 生成订单途径
    gateway = forms.ChoiceField(choices=(('shopping_cart', 1), ('other', 2)),
                                error_messages={
                                    'required': u'生成订单途径不能为空'
                                })


class PayOrdersUpdateForm(forms.Form):
    orders_id = forms.CharField(max_length=32)
    # 支付模式 1：钱包 2：微信支付 3：支付宝支付
    payment_mode = forms.IntegerField(min_value=1, max_value=3)
