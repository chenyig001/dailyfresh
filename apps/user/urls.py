from django.conf.urls import url
from user.views import RegisterView, ActiveView, LoginView, UserInfoView, UserOrderView, UserAddressView, LogoutView
from django.contrib.auth.decorators import login_required

urlpatterns = [
    # url(r'^register$', views.register, name='register'), # 注册
    # url(r'^register_handle$', views.register_handle, name='register_handle'),
    url(r'^register$', RegisterView.as_view(), name='register'),
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'), # 用户激活
    url(r'^login$', LoginView.as_view(), name='login'),  # 登录页面
    url(r'^logout$', LogoutView.as_view(), name='logout'),  # 注销登录页面
    # url(r'^$', login_required(UserInfoView.as_view()), name='user'),  # 用户中心页面
    # url(r'^order$', login_required(UserOrderView.as_view()), name='order'),  # 用户订单页面
    # url(r'^address$', login_required(UserAddressView.as_view()), name='address'),  # 用户地址页面
    url(r'^$', UserInfoView.as_view(), name='user'),  # 用户中心信息页面
    url(r'^order/(?P<page>\d+)$', UserOrderView.as_view(), name='order'),  # 用户中心订单页面
    url(r'^address$', UserAddressView.as_view(), name='address'),  # 用户中心地址页面


]