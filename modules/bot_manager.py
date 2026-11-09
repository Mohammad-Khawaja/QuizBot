from telegram import Update
from telegram.ext import (
	Application,
	ApplicationBuilder,
	CommandHandler,
	MessageHandler,
	CallbackQueryHandler,
	ContextTypes,
	filters
)

from .task_performer import TaskPerformer
from .united import UserStates, Tasks, TemporaryUser, TypesInline
from .inline_handler import InlineHandler
from .callack_schemas import CALLBACK_SCHEMAS

from threading import Thread, Lock
import time
import sqlite3
import traceback


class BotManager:
	def __init__(self, token):
		self.token = token

		self.app: Application = (
			ApplicationBuilder()
			.post_init(self.robot_start_warning)
			.token(token)
			.build()
		)

		self.bot = self.app.bot

		self.task_performer = TaskPerformer(bot=self.bot, token=self.token)

		self.users = {}
		self.task_performer.users = self.users
		
		self.database: sqlite3.Connection = None
		self.cursor: sqlite3.Cursor = None

		# جلوگیری از پردازش هم‌زمان دکمه‌های یک کاربر
		self.inline_processing = {}
		self.task_performer.inline_processing = self.inline_processing

		self.thread_lock = Lock()

		self.inline = InlineHandler(
			self.bot,
			self.task_performer.lock,
			self.task_performer
		)

		self.inline_handlers = {
			name: getattr(self.inline, name)
			for name in dir(self.inline)
			if not name.startswith("_")
			and callable(getattr(self.inline, name))
		}

	def start_bot(self):
		"""شروع ربات"""

		self.settings_start()

		self.app.run_polling(timeout=30)

	def settings_start(self):
		"""تنظیمات اولیه ربات"""

		self.event_handle_adder()

		self.database = sqlite3.connect("database/quiz.db")

		self.task_performer.database = self.database
		self.inline.database = self.database

		self.cursor = self.database.cursor()

		self.task_performer.cursor = self.cursor
		self.inline.cursor = self.cursor

		self.temporary_users_remover_thread = Thread(
			target=self.temporary_users_remover,
			daemon=True
		)

		self.temporary_users_remover_thread.start()

		self.cursor.execute(
			"SELECT user_id FROM users WHERE role = 'admin'"
		)

		admin = self.cursor.fetchone()

		if admin is None:
			raise RuntimeError("هیچ ادمینی در دیتابیس وجود ندارد.")

		self.admin_id = admin[0]

		self.inline.admin_id = self.admin_id

		print("Admin ID:", self.admin_id)

	def event_handle_adder(self):
		"""ثبت هندلرهای پیام و callback"""

		# دستور /start
		self.app.add_handler(
			CommandHandler("start", self.handle_get_start_command)
		)

		# پیام‌های خصوصی غیر از دستورها
		self.app.add_handler(
			MessageHandler(
				filters.ChatType.PRIVATE & ~filters.COMMAND,
				self.message_handle
			)
		)

		# دکمه‌های Inline
		self.app.add_handler(
			CallbackQueryHandler(
				self.main_handler_inline_buttons
			)
		)
	
	async def robot_start_warning(self, app):
		print("Robot started!")

	async def handle_get_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		"""هندل دستور /start"""

		await self.task_performer.start(update.message)

	async def message_handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		"""هندل پیام‌های خصوصی"""

		message = update.message
		user_id = update.effective_user.id

		print("handling message...")

		if (
			user_id in self.task_performer.users
			and (user := self.task_performer.users.get(user_id)).type_task != Tasks.NONE
			and not user.processing
		):
			try:
				user.processing = True
				user.last_change_time = time.time()

				type_task = user.type_task.lower()

				method = getattr(
					self.task_performer,
					type_task,
					None
				)

				if method is not None and callable(method):
					print("متد وجود دارد")

					await method(message)

				else:
					print("متدی برای این تسک پیدا نشد.")

			except Exception:
				traceback.print_exc()

			else:
				print("پردازش پیام موفقیت‌آمیز بود")

			finally:
				user.processing = False

	def validate_callback_query(self, action: str, params: tuple, user_id: int) -> tuple:
		schemas = CALLBACK_SCHEMAS.get(action, None)
		if schemas is None:
			return (False, None, "متدی برای این پیدا نشد")
		
		if len(params) == len(schemas["params"]):
			for c_param, r_param in zip(params, schemas["params"]):
				if not isinstance(c_param, r_param):
					return (False, None, "نوع پارامتر ها صحیح نیست.")
		else:
			return (False, None, "تعداد پارامتر ها صحیح نیست.")
		
		self.cursor.execute("SELECT role FROM users WHERE user_id= ?", (user_id,))
		r = self.cursor.fetchone()
		if len(r) == 0 or r[0] not in schemas["roles"]:
			return (False, None, "شما دسترسی مورد نیاز را ندارید")
		
		if schemas["inline_type"] == "RTUO":
			expired = False
			if (user:=self.users.get(user_id)) is None:
				expired = True
			elif schemas["state_id"] not in user.ids:
				expired = True
			if expired:
				return (False, None, "این دکمه منقضی شده است.")
		
		return (True, schemas["inline_type"], "معتبر است!")
	
	def callback_data_parsing(self, callback_data: str):
		"""
		ساختار callback_data:

			data:typeinline:required_role

		خروجی:

			(data, typeinline, required_role)

		در صورت نامعتبر بودن:

			None
		"""

		if not isinstance(callback_data, str):
			return None

		parts = callback_data.split(":")

		if len(parts) not in [1, 2]:
			return None

		action, *params = parts
		print(action, params)
		if not action or "" in params:
			return None
		
		if len(params) == 0:
			params = []
		else:
			params = params[0].split("&")
		
		new_params = []
		for p in list(params):
			if p.isdigit():
				p = int(p)
			elif p.count(".") == 1 and p.replec(".", "").isdigit():
				p = float(p)
			new_params.append(p)
		print(new_params)
		return action, tuple(new_params)

	def remove_inline_from_dict(self, user_id):
		self.inline_processing.pop(user_id, None)

	async def main_handler_inline_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		"""هندل درخواست دکمه‌های Inline"""

		callback_query = update.callback_query
		message = callback_query.message
		user_id = update.effective_user.id

		print(user_id)

		# جلوگیری از پردازش هم‌زمان
		async with self.task_performer.lock:

			if self.inline_processing.get(user_id):
				there_is = True

			else:
				there_is = False
				self.inline_processing[user_id] = True

		if there_is:
			await callback_query.answer(
				text="هنوز دکمه قبلی درحال پردازش است"
			)
			return

		try:
			parsed = self.callback_data_parsing(
				callback_query.data
			)

			if parsed is None:

				await callback_query.answer(
					text="دکمه نامعتبر است."
				)
				self.remove_inline_from_dict(user_id)
				return

			action, params = parsed
			
			is_valid, typeinline, msg = self.validate_callback_query(action, params, user_id)
			if not is_valid:
				await callback_query.answer(msg)
				self.remove_inline_from_dict(user_id)
				return

			print("user_id:", user_id)
			print("action:", action)
			print("params:", params)
			print("typeinline:", typeinline)
			
			if typeinline == TypesInline.RTUO and user_id in self.task_performer.users:
				user = self.users.get(user_id)
				user.last_change_time = time.time()
				
				await self.RTUO_inline_handler(
					action,
					params,
					message,
					user_id,
					callback_query
				)

			elif typeinline == TypesInline.DNRTUO:

				await self.DNRTUO_inline_handler(
					action,
					params,
					message,
					user_id,
					callback_query
				)

		except Exception:

			print("خطا در پردازش inline:")
			traceback.print_exc()

			await callback_query.answer(
				text="خطا در پردازش دستور دکمه"
			)

		else:
			print("اتمام پردازش")

		finally:
			self.inline_processing.pop(user_id, None)
			await callback_query.answer()

	async def RTUO_inline_handler(self, action, params, message, user_id, callback_query):
		"""هندل دکمه‌هایی که به TemporaryUser نیاز دارند"""

		method_name = action

		method = self.inline_handlers.get(
			method_name,
			None
		)

		if method:
			await method(
				params,
				message,
				user_id,
				callback_query
			)

	async def DNRTUO_inline_handler(self, action, params, message, user_id, callback_query):
		"""هندل دکمه‌هایی که به TemporaryUser نیاز ندارند"""

		method_name = action.split("&")[0]

		method = self.inline_handlers.get(
			method_name,
			None
		)

		if method:
			await method(
				params,
				message,
				user_id,
				callback_query
			)

	def temporary_users_remover(self):
		"""حذف کاربران موقت غیرفعال از RAM"""

		time.sleep(30)

		while True:

			with self.thread_lock:

				current_time = time.time()

				users = self.task_performer.users

				keys_users = list(users.keys())

				for user_id in keys_users:

					user = users[user_id]

					if (
						current_time - user.last_change_time
						>= user.waiting_time
					):

						del users[user_id]

			time.sleep(120)