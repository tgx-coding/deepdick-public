import json
import logging
import os
import time
from typing import Dict, List

# These module-level variables are configured from main.py after import.
CONTEXT_FILE: str = ""
MAX_CONTEXT_MESSAGES: int = 20
conversation_context: List[Dict[str, str]] = []


def cleanup_old_logs(log_dir: str, max_age_days: int = 3) -> None:
	cutoff = time.time() - max_age_days * 86400
	removed = []
	try:
		for entry in os.scandir(log_dir):
			if not entry.is_file() or not entry.name.lower().endswith(".log"):
				continue
			try:
				if os.path.getmtime(entry.path) < cutoff:
					os.remove(entry.path)
					removed.append(entry.name)
			except OSError as exc:
				logging.warning(f"删除日志失败: {entry.path} 错误: {exc}")
	except FileNotFoundError:
		return
	if removed:
		logging.info(f"已清除过期日志: {', '.join(removed)}")


def trim_conversation_context() -> None:
	global conversation_context
	if len(conversation_context) > MAX_CONTEXT_MESSAGES:
		conversation_context[:] = conversation_context[-MAX_CONTEXT_MESSAGES:]


def save_conversation_context() -> None:
	try:
		with open(CONTEXT_FILE, "w", encoding="utf-8") as context_file:
			json.dump(conversation_context, context_file, ensure_ascii=True, indent=2)
	except Exception as exc:
		logging.error(f"保存对话上下文失败: {exc}")


def load_conversation_context() -> None:
	if not CONTEXT_FILE or not os.path.exists(CONTEXT_FILE):
		conversation_context.clear()
		return
	try:
		with open(CONTEXT_FILE, "r", encoding="utf-8") as context_file:
			data = json.load(context_file)
			conversation_context.clear()
			if isinstance(data, list):
				conversation_context.extend(data)
			trim_conversation_context()
	except Exception as exc:
		logging.error(f"加载对话上下文失败: {exc}")
		conversation_context.clear()


def append_conversation_message(role: str, content: str) -> None:
	if not content:
		return
	conversation_context.append({"role": role, "content": content})
	trim_conversation_context()
	save_conversation_context()


def pop_last_conversation_message() -> None:
	if conversation_context:
		conversation_context.pop()
		save_conversation_context()


def clear_conversation_context() -> None:
	conversation_context.clear()
	if CONTEXT_FILE and os.path.exists(CONTEXT_FILE):
		try:
			os.remove(CONTEXT_FILE)
		except OSError as exc:
			logging.error(f"删除对话上下文文件失败: {exc}")
