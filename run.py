#!/usr/bin/env python3
"""
龙头股动量轮动决策系统 — 一键并行启动脚本
============================================
同时启动：
  - Flask 主壳（http://127.0.0.1:5001）
  - Streamlit 子看板（http://127.0.0.1:8501）

按 Ctrl+C 一键同时关闭所有服务。
"""

from __future__ import annotations

import os

# Prevent Hermes Agent venv pydantic from polluting this project's imports.
# Clear PYTHONPATH so the project venv's pydantic is used, not Hermes'.
os.environ["PYTHONPATH"] = ""
import signal
import subprocess
import sys
import time

# ── 配置 ──────────────────────────────────────────────────────────────────
FLASK_PORT = int(os.environ.get("MOMENTUM_PORT", 5001))
STREAMLIT_PORT = int(os.environ.get("STREAMLIT_PORT", 8501))
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# 可执行路径（优先使用 uv/poetry 管理的 python）
PYTHON = sys.executable
STREAMLIT = os.path.join(os.path.dirname(PYTHON), "streamlit")
# 若 streamlit CLI 不在同一 venv 的 bin 下，回退到 python -m streamlit
if not os.path.isfile(STREAMLIT):
    STREAMLIT = None


def _which_streamlit() -> str:
    """Find the streamlit executable."""
    if STREAMLIT and os.path.isfile(STREAMLIT):
        return STREAMLIT
    # try `which streamlit`
    try:
        result = subprocess.run(
            ["which", "streamlit"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return f"{PYTHON} -m streamlit"


def print_banner():
    border = "=" * 56
    print()
    print(f"  {border}")
    print(f"  🐉  龙头股动量轮动决策系统 — 并行启动")
    print(f"  {border}")
    print(f"  AStock Pro WebUI: http://127.0.0.1:{FLASK_PORT}")
    print(f"    ├ 动量 iframe:  http://127.0.0.1:{FLASK_PORT}/momentum_dashboard")
    print(f"    ├ 动量经典版:   http://127.0.0.1:{FLASK_PORT}/momentum_standalone")
    print(f"    └ 动量 API:     http://127.0.0.1:{FLASK_PORT}/api/v1/market/momentum")
    print(f"  Streamlit 看板:  http://127.0.0.1:{STREAMLIT_PORT}")
    print(f"    └ 嵌入模式:    http://127.0.0.1:{STREAMLIT_PORT}/?embed=true")
    print(f"  {border}")
    print(f"  按 Ctrl+C 一键关闭所有服务")
    print()


def main():
    processes: list[subprocess.Popen] = []

    def _signal_handler(signum, frame):
        """优雅关闭所有子进程。"""
        print(f"\n\n  ⏹  收到关闭信号 ({signal.Signals(signum).name})，正在停止所有服务...")
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        # 给进程一点时间优雅退出
        time.sleep(0.5)
        for proc in processes:
            if proc.poll() is None:
                proc.kill()
        print("  ✅ 所有服务已停止")
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    print_banner()

    # ── 1. 启动原始 AStock Pro Flask ──────────────────────────────────
    flask_script = os.path.join(REPO_DIR, "run_webui.py")
    flask_env = os.environ.copy()
    flask_env["PORT"] = str(FLASK_PORT)

    print(f"  ▶  启动 AStock Pro WebUI（端口 {FLASK_PORT}）...")
    flask_proc = subprocess.Popen(
        [PYTHON, flask_script],
        env=flask_env,
        cwd=REPO_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    processes.append(flask_proc)

    # ── 2. 启动 Streamlit ─────────────────────────────────────────────
    streamlit_script = os.path.join(REPO_DIR, "streamlit_app.py")
    streamlit_env = os.environ.copy()
    streamlit_env["STREAMLIT_PORT"] = str(STREAMLIT_PORT)
    streamlit_env["STREAMLIT_SERVER_PORT"] = str(STREAMLIT_PORT)
    streamlit_env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    streamlit_cmd = _which_streamlit().split()
    cmd = [
        *streamlit_cmd,
        "run",
        streamlit_script,
        "--server.port",
        str(STREAMLIT_PORT),
        "--server.headless",
        "true",
        "--server.runOnSave",
        "false",
        "--browser.gatherUsageStats",
        "false",
        "--client.toolbarMode",
        "minimal",
    ]
    # 如果只用 python -m streamlit
    if streamlit_cmd[0] == PYTHON:
        cmd = [PYTHON, "-m", "streamlit", "run", streamlit_script,
               "--server.port", str(STREAMLIT_PORT),
               "--server.headless", "true",
               "--server.runOnSave", "false",
               "--browser.gatherUsageStats", "false",
               "--client.toolbarMode", "minimal"]

    print(f"  ▶  启动 Streamlit 看板 (端口 {STREAMLIT_PORT})...")
    streamlit_proc = subprocess.Popen(
        cmd,
        env=streamlit_env,
        cwd=REPO_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    processes.append(streamlit_proc)

    # ── 3. 输出日志（流式） ───────────────────────────────────────────
    output_lines = {id(flask_proc): [], id(streamlit_proc): []}
    last_activity = time.time()
    ready_markers = {
        id(flask_proc): "Starting AStock WebUI on http",
        id(streamlit_proc): "You can now view your Streamlit app",
    }
    ready_flags = {id(flask_proc): False, id(streamlit_proc): False}

    # 打印 "等待启动..." 提示
    print(f"  ⏳  正在等待两个服务就绪...\n")

    try:
        while True:
            # 读取 stdout
            for proc in processes:
                pid = id(proc)
                if proc.stdout is None:
                    continue
                line = proc.stdout.readline()
                if line:
                    line = line.rstrip("\n\r")
                    output_lines[pid].append(line)

                    # 检测就绪标记
                    if not ready_flags[pid] and any(m in line for m in [ready_markers[pid]]):
                        ready_flags[pid] = True

                    # 格式化输出
                    tag = "FLASK" if proc is flask_proc else "STREA"
                    print(f"  [{tag}] {line}", flush=True)
                    last_activity = time.time()

            # 检查进程存活
            all_done = all(proc.poll() is not None for proc in processes)
            if all_done:
                print("  ⚠️  所有进程已退出")
                break

            # 检查是否都就绪
            if all(ready_flags.values()):
                print(f"\n  {'─' * 48}")
                print(f"  ✅  所有服务均已就绪！")
                print(f"  {'─' * 48}")
                print(f"     打开 http://127.0.0.1:{FLASK_PORT} 开始使用")
                print(f"     Streamlit 独立: http://127.0.0.1:{STREAMLIT_PORT}")
                print(f"  {'─' * 48}\n")
                # 就绪后保持运行但放慢轮询
                time.sleep(2)
                break  # 跳出启动等待循环，进入维持循环

            # 超时处理
            if time.time() - last_activity > 30:
                print("  ⚠️  启动超时(30s)，进程日志:")
                for proc in processes:
                    tag = "FLASK" if proc is flask_proc else "STREA"
                    for line in output_lines[id(proc)][-5:]:
                        print(f"  [{tag}] {line}")
                    if proc.poll() is not None:
                        print(f"  [{tag}] ⚠️  已退出 (code={proc.poll()})")
                print("  尝试直接访问上述地址查看已就绪的服务")
                break

            time.sleep(0.1)

    except KeyboardInterrupt:
        # 触发信号处理器
        _signal_handler(signal.SIGINT, None)

    # ── 4. 维持运行直到 Ctrl+C ────────────────────────────────────────
    try:
        while True:
            time.sleep(1)
            # 检查进程是否还活着
            for proc in processes:
                if proc.poll() is not None:
                    tag = "FLASK" if proc is flask_proc else "STREA"
                    print(f"  ⚠️  [{tag}] 已意外退出 (code={proc.poll()})")
                    if proc is flask_proc:
                        print("  ⚠️  请重新运行 `python run.py`")
                    # 不自动退出，让用户手动 Ctrl+C
    except KeyboardInterrupt:
        _signal_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()
