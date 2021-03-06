# -*- encoding: utf-8 -*-
from horizon import forms
from django.conf import settings

class HotSaleListForm(forms.Form):
    #is_recommend = forms.IntegerField(required=False)
    food_court_id = forms.IntegerField(required=False)
    page_size = forms.IntegerField(min_value=1, max_value=settings.MAX_PAGE_SIZE, required=False)
    page_index = forms.IntegerField(min_value=1, required=False)
class DishesGetForm(forms.Form):
    #is_recommend = forms.IntegerField(required=False)
    pk = forms.IntegerField(required=False)

class FoodCourtGetForm(forms.Form):
    pk = forms.IntegerField(required=False)
    # name = forms.CharField(max_length=200, required=False)


class FoodCourtListForm(forms.Form):
    city = forms.CharField(min_length=2, max_length=100, required=False)
    district = forms.CharField(min_length=2, max_length=100, required=False)
    mall = forms.CharField(min_length=2, max_length=200, required=False)
    page_size = forms.IntegerField(min_value=1, max_value=settings.MAX_PAGE_SIZE, required=False)
    page_index = forms.IntegerField(min_value=1, required=False)