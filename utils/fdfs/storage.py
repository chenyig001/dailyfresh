from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client, get_tracker_conf
from django.conf import settings

class FDSTStorage(Storage):
    def __init__(self,client_conf=None,base_url=None):
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
            self.client_conf = client_conf
        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url =base_url

    def _open(self, name, mode='rb'):
        '''打开文件时使用'''
        pass

    def _save(self, name, content):
        '''保存文件时使用'''
        # name:选择上传文件的名字
        # content :包含上传文件内容的File对象
        client_conf = get_tracker_conf(self.client_conf)
        # 创建一个Fast_client对象
        client = Fdfs_client(client_conf)
        # 上传文件到fast dfs系统中
        res = client.upload_by_buffer(content.read())
        # return dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # } if success else None
        if res.get('Status') != 'Upload successed.':
            # 上传失败
            raise Exception('上传文件到fast dfs失败')
        # 获取返回的文件id
        filename = res.get('Remote file_id')
        return filename.decode()

    def exists(self, name):
        '''django判断文件是否可用'''
        return False

    def url(self, name):
        '''返回访问文件的url路径'''
        return self.base_url+name
