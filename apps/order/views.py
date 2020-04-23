from django.shortcuts import render
from django.views.generic import View
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django_redis import get_redis_connection
from django.http import JsonResponse
from django.conf import settings
from django.db import transaction
from alipay import AliPay

from goods.models import GoodsSKU
from user.models import Address
from order.models import OrderInfo, OrderGoods
from utils.mixin import LoginRequiresMixin
from datetime import datetime
import time
import os
# Create your views here.


# /order/place
class OrderPlaceView(LoginRequiresMixin, View):
    '''提交订单页面显示'''
    def post(self,request):
        # 获取登录的用户
        user = request.user
        # 接收post提交的数据sku_ids
        sku_ids = request.POST.getlist('sku_ids')  # [1,3]
        # 数据校验
        if not sku_ids:
            # 跳转购物车页面
            return redirect(reverse('cart:show'))
        conn = get_redis_connection('default')
        # 业务处理：
        # 保存商品的总件数和总价格
        total_count = 0
        total_price = 0
        skus = []
        # 遍历sku_ids获取用户要购买的商品的信息
        for sku_id in sku_ids:
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            cart_key = 'cart_%d' % user.id
            # 根据商品的id获取商品的数量
            count = conn.hget(cart_key, sku_id)
            # 计算商品的小计
            amount = sku.price*int(count)
            # 动态给sku增加属性count，amount,保存购买商品的数量和小计
            sku.count = count
            sku.amount = amount
            # 追加
            skus.append(sku)
            # 累加商品的总件数和总价格
            total_count += int(count)
            total_price += amount

        # 运费：实际开发的时候，属于一个子系统
        transit_price = 10 # 写死
        # 实付款
        total_pay = total_price + transit_price

        # 获取用户的收件地址
        addrs = Address.object.filter(user=user)
        # 组织上下文
        sku_ids = ','.join(sku_ids)
        context ={
            'skus':skus,
            'total_count': total_count,
            'total_price': total_price,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'addrs': addrs,
            'sku_ids': sku_ids}
        # 使用模板
        return render(request, 'place_order.html', context)


# 前端传递的参数：地址id(addr_id) 支付方式(pay_method) 用户要购买的商品id字符串(sku_ids)
# /order/commit
class OrderCommitView(View):
    '''订单创建'''
    @transaction.atomic
    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res':1, 'errmsg':'参数不完整'})
        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的支付方式'})
        # 校验地址
        try:
            addr = Address.object.get(id=addr_id)
        except Address.DoseNotExist:
            # 地址不存在
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})

        # todo:创建订单核心业务
        # 组织参数
        # 订单id :202047112030+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)
        # 运费
        transit_price = 10

        # 总数目和总金额
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # todo:向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(order_id=order_id,
                                     user=user,
                                     addr=addr,
                                     pay_method=pay_method,
                                     total_price=total_price,
                                     total_count=total_count,
                                     transit_price=transit_price
                                     )
            # todo:用户的订单中有几个商品，需要向df_order_goods表中加入几条记录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d'%user.id
            sku_ids = sku_ids.split(',')  # 返回列表
            for sku_id in sku_ids:
                # 获取商品的信息
                try:
                    # select * from GoodsSKU where id=sku_id for update; 悲观锁
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except:
                    # 商品不存在
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 4, 'errmsg': '商品不参在'})
                print('user:%d stock:%d'%(user.id, sku.stock))
                time.sleep(5)
                # 从redis中获取用户所需要购买的商品的数量
                count = conn.hget(cart_key, sku_id)

                # todo: 判断商品的库存
                if int(count)>sku.stock:
                    transaction.savepoint_rollback(save_id)
                    return JsonResponse({'res': 6, 'errmsg': '商品的库存不足'})

                # todo:向df_order_goods添加一条记录
                OrderGoods.objects.create(order=order,
                                          sku=sku,
                                          count=count,
                                          price=sku.price
                                          )
                # todo:更新商品的库存和销量
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()

                # todo:累加计算订单商品的总数量和总价格
                amount = sku.price*int(count)
                total_count += int(count)
                total_price += amount
            print('ok9')
            # todo:更新订单信息表中的商品的总数量和总价格
            order.total_count=total_count
            order.total_price=total_price
            order.save()
        except Exception as e:
            # 事务回滚
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)

        # todo:清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)  # *sku_ids拆包
        # 返回应答
        return JsonResponse({'res': 5, 'errmsg': '创建成功'})


# ajax post
# 前端传递的参数：订单id(order_id)
class OrderPayView(View):
    '''订单支付'''
    def post(self, request):
        '''订单支付'''
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res':1, 'errmsg':'无效的订单id'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res':2, 'errmsg':'订单错误'})
        # 业务处理：使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016102200736882",  # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_string=open(os.path.join(settings.BASE_DIR, 'apps/order/rsa_private_key.pem')).read(),
            alipay_public_key_string=open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read(),  # 支付宝的公钥
            sign_type="RSA2",  # RSA 或 RSA2
            debug=True  # 默认false
        )
        # 调用支付接口
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        total_price = order.total_price+order.transit_price  # DecimalField
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,  # 订单id
            total_amount=str(total_price),  # 支付总金额
            subject='天天生鲜%s' % order_id,  # 标题
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )
        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res':3, 'pay_url':pay_url})


class OrderCheckView(View):
    '''订单查询'''
    def post(self, request):
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})
        # 业务处理：使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016102200736882",  # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_string=open(os.path.join(settings.BASE_DIR, 'apps/order/rsa_private_key.pem')).read(),
            alipay_public_key_string=open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read(),
            # 支付宝的公钥
            sign_type="RSA2",  # RSA 或 RSA2
            debug=True  # 默认false
        )
        while True:
            response = alipay.api_alipay_trade_query(order_id)
            '''
                "alipay_trade_query_response": {
                    "trade_no": "2017032121001004070200176844",
                    "code": "10000",
                    "invoice_amount": "20.00",
                    "open_id": "20880072506750308812798160715407",
                    "fund_bill_list": [
                        {
                            "amount": "20.00",
                            "fund_channel": "ALIPAYACCOUNT"
                        }
                    ],
                    "buyer_logon_id": "csq***@sandbox.com",
                    "send_pay_date": "2017-03-21 13:29:17",
                    "receipt_amount": "20.00",
                    "out_trade_no": "out_trade_no15",
                    "buyer_pay_amount": "20.00",
                    "buyer_user_id": "2088102169481075",
                    "msg": "Success",
                    "point_amount": "0.00",
                    "trade_status": "TRADE_SUCCESS",
                    "total_amount": "20.00"
                }
                '''
            code = response.get('code')
            if code == '10000' and response.get('trade_status')=='TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单的状态
                order.trade_no = trade_no
                order.order_status = 4  # 待评价
                order.save()
                # 返回结果
                return JsonResponse({'res':3, 'message':'支付成功'})
            elif code == '40004' or (code == '10000' and response.get('trade_status')=='WAIT_BUYER_PAY'):
                # 等待买家付款
                import time
                time.sleep(5)
                continue
            else:
                # 支付出错
                print(code)
                return JsonResponse({'res':4, 'errmsg':'支付失败'})





