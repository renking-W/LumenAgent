"""增强版 SSH 客户端：交互式 Shell（invoke_shell）、流式执行、日志写入。

设计要点：
- 使用 invoke_shell() + 常驻 bash 进程，支持连续命令执行
- 命令执行日志写入 log/machine_log/{host}.log
- 支持非流式 execute() 和流式 execute_streaming() 两种模式
"""

from __future__ import annotations

import logging
import queue
import threading
import time

import paramiko
from paramiko import SSHClient
from paramiko.channel import Channel

from lumen_agent.application.uitls.dir_guide import DirGuide

logger = logging.getLogger(__name__)

_LOG_DIR = DirGuide.machine_log_dir()


class SshClient:
    """SSH 交互式 Shell 客户端（invoke_shell 常驻 bash）。"""

    def __init__(self, host: str, port: int = 22, username: str = "", password: str = ""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password

        self._client: SSHClient | None = None
        self._channel: Channel | None = None
        # 唯一结束标记，避免与正常命令输出冲突
        self._done_flag = "__CMD_DONE__"
        self._exit_code_prefix = "__EXIT_CODE="
        # 日志文件锁（线程安全）
        self._log_lock = threading.Lock()
        self._log_path: Path | None = None

    # ── 公共属性 ─────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._channel is not None and self._channel.active

    @property
    def log_path(self) -> Path | None:
        return self._log_path

    # ── 连接 ─────────────────────────────────────────────────────

    def connect(self) -> SSHClient:
        """建立 SSH 连接并启动常驻 bash 终端。"""
        # ── 日志归档：将旧的 {host}.log → {host}.MM-DD_HH-MM-SS.log ──
        self._rotate_log()

        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 连接认证：优先私钥，无则使用密码
        connect_kwargs = {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "timeout": 60,
            "banner_timeout": 60,
        }

        self._client.close()
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(**connect_kwargs)

        # 初始化日志文件
        self._log_path = _LOG_DIR / f"{self.host}.log"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.touch(exist_ok=True)

        # 开启交互式 Shell 通道
        self._channel = self._client.invoke_shell(term="vt100", width=500, height=50)
        self._channel.settimeout(30)
        # 开启 SSH 层心跳，防止空闲超时断开
        if self._client.get_transport():
            self._client.get_transport().set_keepalive(40)

        # 等待 shell 就绪
        time.sleep(0.5)
        welcome = self._read_buffer()
        self._log_write(welcome)

        # 关闭终端命令回显
        self._channel.send(b"stty -echo\n")
        time.sleep(0.3)
        self._read_buffer()

        logger.info("SSH 连接已建立: %s@%s:%s", self.username, self.host, self.port)
        return self._client

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """去除 ANSI 转义序列，保留纯文本。

        处理三种转义类型：
        - CSI 序列: ``ESC[参数...字母``，如 ``ESC[31m``
        - OSC 序列: ``ESC]...BEL`` 或 ``ESC]...ST``，如窗口标题
        - 其他单个控制字符（如 ``\\x07`` BEL）
        """
        import re as _re
        # OSC 序列: ESC]...(\x1b\\|\x07|\x9c)
        text = _re.sub(r'\x1b\].*?(?:\x1b\\|\x07|\x9c)', '', text)
        # CSI 序列: ESC[参数...字母（含 ? 开头的私有参数，如 [?2004h）
        text = _re.sub(r'\x1b\[[?0-9;]*[a-zA-Z]', '', text)
        # 剩余的控制字符
        text = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        return text.strip()

    # ── 断开 ─────────────────────────────────────────────────────

    def close(self) -> None:
        """手动关闭 SSH 会话，释放资源。"""
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._channel = None
        self._client = None
        logger.info("SSH 连接已关闭: %s", self.host)

    # ── 日志管理 ─────────────────────────────────────────────────

    def _rotate_log(self) -> None:
        """新建连接前归档旧的 {host}.log → {host}.MM-DD_HH-MM-SS.log。"""
        log_path = _LOG_DIR / f"{self.host}.log"
        if not log_path.exists():
            return
        from datetime import datetime
        ts = datetime.now().strftime("%m-%d_%H-%M-%S")
        new_name = f"{self.host}.{ts}.log"
        new_path = _LOG_DIR / new_name
        try:
            log_path.rename(new_path)
            logger.info("日志已归档: %s → %s", log_path.name, new_name)
        except OSError as exc:
            logger.warning("日志归档失败: %s", exc)

    def _log_write(self, text: str) -> None:
        """向日志文件追加一行文本（线程安全）。"""
        if not self._log_path or not text:
            return
        with self._log_lock:
            try:
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(text)
                    if not text.endswith("\n"):
                        f.write("\n")
            except OSError as exc:
                logger.warning("日志写入失败: %s", exc)

    def _log_write_output(self, output: str, exit_code: int) -> None:
        """向日志写入命令输出。"""
        if output:
            self._log_write(output)

    # ── 非流式执行（简单场景） ──────────────────────────────────

    def execute(self, cmd: str, timeout: int = 30) -> tuple[str, int]:
        """发送 bash 命令并返回执行结果（完整输出 + 退出码）。

        Returns:
            (output_text, exit_code) — 已去除结束标记和退出码行。
        """
        if not self._channel or not self._channel.active:
            raise ConnectionError("SSH 会话未建立或已断开")

        full_cmd = f"{cmd}; echo {self._exit_code_prefix}$?; echo {self._done_flag}\n"
        self._channel.send(full_cmd.encode("utf-8"))

        output = ""
        start_time = time.time()
        while self._done_flag not in output:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"命令执行超时（{timeout}秒）")
            if self._channel.recv_ready():
                output += self._read_buffer()
            else:
                time.sleep(0.1)

        # 解析结果
        output = output.split(self._done_flag)[0].strip()
        lines = output.splitlines()
        exit_code = -1
        result_lines = []
        for line in lines:
            if line.startswith(self._exit_code_prefix):
                exit_code = int(line.replace(self._exit_code_prefix, ""))
            else:
                result_lines.append(line)

        result_text = "\n".join(result_lines).strip()
        return result_text, exit_code

    # ── 流式执行（SSE 场景） ────────────────────────────────────

    def execute_streaming(self, cmd: str, timeout: int, result_queue: queue.Queue) -> None:
        """在线程中执行命令，将输出逐块放入 ``result_queue``。

        队列元素格式：``(kind, data)``
        - ("output", chunk_str)  — 输出增量
        - ("exit_code", int)     — 退出码
        - ("done", "")           — 结束标志
        - ("error", msg_str)     — 错误信息

        此方法应在 ``ThreadPoolExecutor`` 或独立线程中运行。
        """
        try:
            if not self._channel or not self._channel.active:
                result_queue.put(("error", "SSH 会话未建立或已断开"))
                return

            full_cmd = f"{cmd}; echo {self._exit_code_prefix}$?; echo {self._done_flag}\n"
            self._channel.send(full_cmd.encode("utf-8"))

            output = ""
            last_sent_pos = 0
            start_time = time.time()
            while self._done_flag not in output:
                if time.time() - start_time > timeout:
                    result_queue.put(("error", f"命令执行超时（{timeout}秒）"))
                    return
                if self._channel.recv_ready():
                    chunk = self._channel.recv(4096).decode("utf-8", errors="ignore")
                    output += chunk
                    # 只发送标记之前的纯文本，避免 __CMD_DONE__ / __EXIT_CODE= 串到前端
                    clip_pos = len(output)
                    done_idx = output.find(self._done_flag)
                    if done_idx != -1:
                        clip_pos = min(clip_pos, done_idx)
                    exit_idx = output.find(self._exit_code_prefix)
                    if exit_idx != -1:
                        clip_pos = min(clip_pos, exit_idx)
                    new_text = output[last_sent_pos:clip_pos]
                    if new_text:
                        result_queue.put(("output", new_text))
                    last_sent_pos = clip_pos
                else:
                    time.sleep(0.05)

            # 解析退出码（已不会出现在流式输出中）
            exit_code = -1
            for line in output.splitlines():
                if line.startswith(self._exit_code_prefix):
                    exit_code = int(line.replace(self._exit_code_prefix, ""))
                    break

            result_queue.put(("exit_code", exit_code))
            result_queue.put(("done", ""))
        except Exception as e:
            logger.exception("流式执行异常")
            result_queue.put(("error", str(e)))

    # ── 内部 ─────────────────────────────────────────────────────

    def _read_buffer(self) -> str:
        """非阻塞读取当前接收缓冲区中所有已到达的数据。"""
        data = b""
        while self._channel and self._channel.recv_ready():
            data += self._channel.recv(4096)
        return data.decode("utf-8", errors="ignore")