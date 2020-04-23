from django.conf.urls import url
from goods.views import IndexView, DetailView, ListView
urlpatterns = [
    url(r'^index$', IndexView.as_view(), name='index'),   # 商品首页
    url(r'^detail/(?P<good_id>.*)$', DetailView.as_view(), name='detail'),  # 详情页面
    url(r'^list/(?P<type_id>\d+)/(?P<page>\d+)$', ListView.as_view(), name='list'),  # 列表页面

]
