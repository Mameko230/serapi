# -*- coding: utf-8 -*-
"""应用版本号（单一来源）。

发版流程：改这里的 APP_VERSION → 提交 → 打同名 tag（如 v1.0.1）推送。
CI 会校验 tag 去掉 v 后与 APP_VERSION 一致，避免客户端版本和 Release 对不上。
"""

APP_VERSION = "1.2.2"
