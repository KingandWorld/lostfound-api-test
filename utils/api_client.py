"""统一请求封装：Base URL + token 自动注入。

与 Day6 API 文档一致：认证通过自定义 Header `token` 携带（非 Bearer 格式）。
"""

import requests


class ApiClient:
    """统一请求封装：Base URL + token 自动注入。"""

    def __init__(self, base_url, token=None):
        self.session = requests.Session()
        self.base_url = base_url
        if token:
            self.session.headers["token"] = token

    def request(self, method, path, **kwargs):
        kwargs.setdefault("timeout", 10)
        return self.session.request(method, f"{self.base_url}{path}", **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)
