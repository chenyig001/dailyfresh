from django.conf.urls import url
from cart.views import CarAddView, CarInfoView, CartUpdateView, CartDeleteView
urlpatterns = [
    url(r'^add$', CarAddView.as_view(), name='add'),  # 购物车记录添加
    url(r'^$', CarInfoView.as_view(), name='show'),  # 购物车页面显示
    url(r'^update$', CartUpdateView.as_view(), name='update'),  # 更新购物车记录
    url(r'^delete$', CartDeleteView.as_view(), name='delete'),  # 删除购物车记录
]
