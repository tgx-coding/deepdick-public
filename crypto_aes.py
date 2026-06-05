import zlib
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class CryptoAll:
    """与 JS 中 all 对象完全对应的 Python 实现"""

    def __init__(self):
        # 密钥和 IV（UTF‑8 编码的 16 字节，AES‑128）
        self.K  = "FzE4v4ilaUOZlOoy".encode("utf-8")
        self.I  = "wiI6RL5xeEiMyZo7".encode("utf-8")
        self._K = "jKot3DF6yxzMg0Ek".encode("utf-8")
        self._I = "xpHEUkW1warZMsl5".encode("utf-8")

        # 常量（与 crypto-js 一致）
        self.MODE = AES.MODE_CBC          # crypto_js.mode.CBC
        self.PADDING = "PKCS7"            # crypto_js.pad.Pkcs7

    # ---------- 内部工具方法 ----------
    def _deflate(self, data: bytes) -> bytes:
        """
        完全模拟 pako.deflate 的参数：
        level=6, windowBits=15, memLevel=8, strategy=0, chunkSize=16384
        """
        compressor = zlib.compressobj(
            level=6,
            method=zlib.DEFLATED,
            wbits=15,                    # 15 → zlib 格式
            memLevel=8,
            strategy=zlib.Z_DEFAULT_STRATEGY   # 0
        )
        return compressor.compress(data) + compressor.flush()

    def _inflate(self, data: bytes) -> bytes:
        """解压，对应 pako.inflate"""
        return zlib.decompress(data, wbits=15)

    @staticmethod
    def _base64_url_encode(data: bytes) -> str:
        """URL‑Safe Base64 编码，并去掉末尾的 ="""
        encoded = base64.urlsafe_b64encode(data)
        return encoded.rstrip(b"=").decode("ascii")

    @staticmethod
    def _base64_url_decode(s: str) -> bytes:
        """
        URL‑Safe Base64 解码，自动补齐缺失的 =
        （与 JS 中替换字符 + 补等号的逻辑完全一致）
        """
        # 先还原为标准 Base64 字符
        s = s.replace("-", "+").replace("_", "/")
        # 补齐缺失的填充符
        missing = 4 - len(s) % 4
        if missing != 4:
            s += "=" * missing
        return base64.b64decode(s)

    # ---------- 公开 API ----------
    def en(self, e: str, key: bytes = None, iv: bytes = None) -> str:
        """
        加密：
        e    - 待加密的明文
        key  - 密钥（默认 this.K）
        iv   - 初始向量（默认 this.I）
        """
        if key is None:
            key = self.K
        if iv is None:
            iv = self.I

        # 1. 字符串 → UTF‑8 字节
        plain = e.encode("utf-8")
        # 2. Deflate 压缩
        compressed = self._deflate(plain)
        # 3. AES‑CBC 加密（含 PKCS7 填充）
        cipher = AES.new(key, self.MODE, iv)
        encrypted = cipher.encrypt(pad(compressed, AES.block_size))
        # 4. URL‑Safe Base64 编码
        return self._base64_url_encode(encrypted)

    def de(self, t: str, key: bytes = None, iv: bytes = None) -> str:
        """
        解密：
        t    - URL‑Safe Base64 密文
        key  - 密钥（默认 this.K）
        iv   - 初始向量（默认 this.I）
        """
        if key is None:
            key = self.K
        if iv is None:
            iv = self.I

        try:
            # 1. Base64 解码
            ciphertext = self._base64_url_decode(t)
            # 2. AES 解密 + 去填充
            cipher = AES.new(key, self.MODE, iv)
            compressed = unpad(cipher.decrypt(ciphertext), AES.block_size)
            # 3. Inflate 解压
            plain = self._inflate(compressed)
            # 4. UTF‑8 解码
            return plain.decode("utf-8")
        except Exception as e:
            print(e)
            raise

    # 快捷方法（完全对应 JS 中的命名）
    def en_path(self, path: str) -> str:
        return self.en(path)

    def en_par(self, par: str) -> str:
        return self.en(par, self._K, self._I)

    def de_par(self, par: str) -> str:
        return self.de(par, self._K, self._I)

    def de_path(self, path: str) -> str:
        return self.de(path)


