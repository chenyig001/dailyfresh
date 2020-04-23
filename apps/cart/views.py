from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse

from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiresMixin
# Create your views here.


# 添加商品到购物车：
# 请求方式：采用ajax post
# detail.html传递参数：商品id(sku_id) 商品数量(count)
# /cart/add
class CarAddView(View):
    '''购物车记录添加'''
    def post(self, request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})

        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 检验数据
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 检验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        # 检验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})
        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 先尝试获取sku_id的值
        cart_count = conn.hget(cart_key, sku_id)  # 如果sku_id不存在，hget返回none
        if cart_count:
            # 累加购物车商品的数目
            count += int(cart_count)
        # 检验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})
        # 设置hash中sku_id对应的值
        print(cart_key,sku_id,count)
        conn.hset(cart_key, sku_id, count)
        total_count = conn.hlen(cart_key)
        # 返回应答
        return JsonResponse({'res': 5, 'total_count':total_count, 'errmsg': '添加成功'})


class CarInfoView(LoginRequiresMixin, View):
    '''购物车显示'''
    def get(self, request):
        # 获取登录的用户
        user = request.user
        conn = get_redis_connection('default')
        # 获取用户购物车商品的信息
        cart_key = 'cart_%d' % user.id
        # {'商品id':商品数量}
        cart_dict = conn.hgetall(cart_key)
        skus = []
        # 保存用户购物车商品的总数目和总价格
        total_count = 0
        total_price = 0
        # 遍历获取商品的信息
        for sku_id, count in cart_dict.items(): # 遍历字典项
            # 根据商品id获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计
            amount = sku.price*int(count)
            # 动态给sku对象增加属性amount,保存商品的小计
            sku.amount = amount
            # 动态给sku对象增加属性count,保存购物车中对应商品的数量
            sku.count = count
            skus.append(sku)
            # 累加计算商品的总价格和数目
            total_count += int(count)
            total_price += amount
        # 组织上下文
        context = {
            'total_count': total_count,
            'total_price': total_price,
            'skus': skus,
        }

        return render(request, 'cart.html', context)


# 采用ajax post请求
# cart.html前端需要传递的参数：商品id(sku_id),更新的商品数目(count）
# /cart/updata
class CartUpdateView(View):
    '''购物车记录更新'''
    def post(self, request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})
        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 检验数据
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 检验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        # 检验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})
        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 检验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})
        # 更新
        conn.hset(cart_key, sku_id, count)
        # 计算用户购物车商品的总件数{'1':5,'1':3}
        vals = conn.hvals(cart_key)
        total_count = 0
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({'res': 5, 'total_count': total_count, 'message':'更新成功'})


# 购物车删除记录
# 采用ajax post请求
# 前端需要传递的参数：商品的id(sku_id)
# /cart/delete
class CartDeleteView(View):
    '''购物车记录删除'''
    def post(self, request):
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})
        # 获取参数
        sku_id = request.POST.get('sku_id')
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 检验参数
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})
        # 业务处理：删除购物车商品的记录
        conn = get_redis_connection('default')
        # 获取用户购物车商品的信息
        cart_key = 'cart_%d' % user.id
        conn.hdel(cart_key, sku_id)
        # 计算用户购物车商品的总件数{'1':5,'1':3}
        vals = conn.hvals(cart_key)
        total_count = 0
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({'res': 3,'total_count':total_count, 'errmsg': '删除成功'})




