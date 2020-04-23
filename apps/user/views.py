from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.views.generic import View
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.conf import settings
from django.core.paginator import Paginator

from user.models import User, Address
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods

from itsdangerous import TimedJSONWebSignatureSerializer as Serialize
from itsdangerous import SignatureExpired
from utils.mixin import LoginRequiresMixin
from celery_tasks.tasks import send_register_active_email,generate_static_index_html
from django_redis import get_redis_connection

import re
# Create your views here.


# def register(request):
#     if request.method == 'GET':
#         return render(request, 'register.html')
#     else:
#         # 进行注册处理
#         # 获取信息
#         username = request.POST.get('user_name')
#         password = request.POST.get('pwd')
#         email = request.POST.get('email')
#         allow = request.POST.get('allow')
#         print(username)
#         # 数据校验
#         if not all([username, password, email]):
#             return render(request, 'register.html', {'errmsg': '信息输入不完整'})
#         if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
#             return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
#         if allow != 'on':
#             return render(request, 'register.html', {'errmsg': '请勾选同意'})
#         # 检验用户名是否重复
#         try:
#             user = User.objects.get(username=username)
#         except User.DoesNotExist:
#             # 用户名不存在
#             user = None
#         if user:
#             return render(request, 'register.html', {'errmsg': '用户已存在'})
#         # 业务处理 :用户注册
#         user = User.objects.create_user(username, email, password)
#         user.is_active = 0
#         user.save()
#         # user =User()
#         # user.username = username
#         # user.password = password
#         # user.email =email
#         # user.save()
#         # 返回应答
#         return redirect(reverse('goods:index'))


# /user/register
class RegisterView(View):

    def get(self, request):
        return render(request, 'register.html')
    def post(self, request):
        # 进行注册处理
        # 获取信息
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        print(username)
        # 数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '信息输入不完整'})
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请勾选同意'})
        # 检验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户已存在'})
        # 业务处理 :用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()
        # user =User()
        # user.username = username
        # user.password = password
        # user.email =email
        # user.save()

        # 发送激活邮件，包含激活链接：https://127.0.0.1:8000/user/active/1
        # 激活邮件中需要包含用户的身份信息，并且把身份信息加密

        # 加密用户信息，生成激活token
        serialize = Serialize(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serialize.dumps(info) # byte
        token = token.decode('utf-8')
        # # 发邮件1
        send_register_active_email.delay(email, username, token) # 发出任务
        # 发邮件2
        # subject = '天天生鲜欢迎信息'
        # message = ''
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        # html_message = '<h1>%s,欢迎注册天天生鲜会员</h1>请点击以下链接激活您的账户<br/><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' %(username, token, token)
        # send_mail(subject, message, sender, receiver, html_message=html_message)

        # # 返回应答，跳转首页
        return redirect(reverse('goods:index'))



class ActiveView(View):
    '''用户激活'''
    def get(self, request, token):
        '''进行用户激活'''
        # 解密，获取要激活的用户信息
        serialize = Serialize(settings.SECRET_KEY, 3600)
        try:
            info = serialize.loads(token)
            # 获取待激活用户的id
            user_id = info['confirm']
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 跳转登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已失效
            return HttpResponse('链接已失效')

# /user/login
class LoginView(View):
    '''登录'''
    def get(self, request):
        '''显示登录页面'''

        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})
    def post(self, request):
        '''登录校验'''
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg':'数据不完整'})

        # 业务处理：登录校验
        user = authenticate(username=username, password=password)
        # 用户名密码这么正确
        if user is not None:
            if user.is_active:
                # 用户已激活
                # 记录用户登录状态
                login(request, user)

                # 获取登录后所要跳转的地址
                # 默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index')) # none

                # 跳转到next_url
                response = redirect(next_url) # HttpResponseRedirect
                # 判断是否需要记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')

                # 返回response
                return response
            else:
                return render(request, 'login.html', {'errmsg':'账号未激活'})
        else:
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})
        # 返回应答


# user/logout
class LogoutView(View):
    '''退出登录'''
    def get(self, request):
        # 清除用户的session信息
        logout(request)
        # 跳转首页
        return redirect(reverse('goods:index'))


class UserInfoView(LoginRequiresMixin, View):
    '''用户信息中心页'''
    def get(self, request):
        # request.user
        # 如果用户未登录->AnonymousUser类的一个实例
        # 如果用户登录->User类的一个实例
        # request.user.is_authenticated()

        # 获取用户的个人信息
        user = request.user
        address = Address.object.get_default_adress(user)

        # 获取用户的历史浏览记录
        con = get_redis_connection('default')  # 连接redis数据库
        history_key = 'history_%d'%user.id   # 拼接key
        # 获取用户最新浏览的五个商品的id
        sku_ids = con.lrange(history_key, 0, 4)
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)
        # 组织上下文
        content = {
            'page': 'user',
            'address': address,
            'goods_list': goods_li,
        }

        # 除了开发者给模板文件传递模板变量之外，django框架会把request.user也传递给模板文件
        return render(request, 'user_center_info.html', content)


class UserOrderView(LoginRequiresMixin, View):
    '''用户信息订单页'''
    def get(self, request, page):
        # 获取用户的订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        print(len(orders))
        # 遍历获取订单商品的信息
        for order in orders:
            # 根据order_id查询订单商品信息
            order_skus = OrderGoods.objects.filter(order=order.order_id)
            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.count * order_sku.price
                # 动态给order_sku增加属性amount,保存订单商品的小计
                order_sku.amount = amount

            # 动态给order增加属性，保存订单状态标题
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态给order增加属性，保存订单商品的信息
            order.order_skus = order_skus


        # 分页
        p = Paginator(orders, 1)
        # print(paginator.count)  # 总共数据量
        # print(paginator.num_pages)  # 总页数
        # 处理页码
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page > p.num_pages:
            page = 1
        # 返回第page页的订单实例对象
        order_page = p.page(page)
        print(type(order_page))
        # 进行页码控制，页面上最多显示5个页码
        # num_pages = p.num_pages  # 总页数
        # if num_pages < 5:
        #     pages = range(1, num_pages+1)
        # elif page <= 3:
        #     pages = range(1, 6)
        # elif num_pages - page <= 2:
        #     pages = range(num_pages - 4, num_pages+1)
        # else:
        #     pages = range(page-2, page+3)

        # 组织上下文
        context = {'order_page': order_page,
                   'orders':orders,
                   #'pages': pages,
                   'page': 'order'}
        # 使用模板

        return render(request, 'user_center_order.html', context)


# /user/address
class UserAddressView(LoginRequiresMixin, View):
    '''用户信息地址页'''
    def get(self, request):
        user = request.user  # 获取登录用户的对应的User对象
        # # 获取用户的默认收货地址
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None
        address = Address.object.get_default_adress(user)
        # 使用模板
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        '''地址的添加'''
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        # 检验数据
        if not all([receiver, addr, zip_code, phone]): # 判断数据完整性
            return render(request, 'user_center_site.html', {'errmsg':'数据不完整'})
        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg':'手机号格式不正确'})
        # 业务处理：地址添加
        # 如果用户已存在收货地址，添加的地址不作为默认收货地址
        user = request.user  # 获取登录用户的对应的User对象
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None
        address = Address.object.get_default_adress(user)
        if address:
            is_default = False
        else:
            is_default = True
        # 添加地址
        Address.object.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)

        # 返回应答,刷新地址页面
        return redirect(reverse('user:address'))  # get请求方式
