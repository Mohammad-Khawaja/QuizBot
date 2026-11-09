import sqlite3
import asyncio
from uuid import uuid4

from telegram import Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import modules.long_texts as long_texts
from .united import UserStates, Tasks, TemporaryUser
from .callack_schemas import CALLBACK_SCHEMAS

class TaskPerformer:
	def __init__(self, bot, token):
		self.bot = bot
		self.token = token
		self.users = {}
		self.inline_processing = {}

		self.database: sqlite3.Connection | None = None
		self.cursor: sqlite3.Cursor | None = None

		self.lock = asyncio.Lock()

		wellcome_texts = long_texts.wellcome_text

		self.wellcom_texts = {
			"normal": wellcome_texts["normal"],
			"student": wellcome_texts["student"],
			"teacher": wellcome_texts["teacher"],
			"admin": wellcome_texts["admin"]
		}

		# منوی اصلی کاربران
		# ساختار callback_data:
		# action
		# action:param1&param2&...

		self.return_menu_inline = {
			"normal": [
				[("ثبت نام در کلاس‌ها", "register_for_classes")],
				[("ثبت‌نام به عنوان دبیر", "register_for_teacher")]
			],

			"student": [
				[("نمایش کلاس‌های من", "display_student_classes")],
				[("نمایش آزمون‌ها", "display_student_quizs")],
				[("نمایش نتایج آزمون‌های قبلی", "display_previous_quiz_results")],
				[("ثبت نام در کلاس‌ها", "register_for_classes")]
			],

			"teacher": [
				[("نمایش کلاس‌های من", "display_teacher_classes")],
				[("نمایش آزمون‌ها", "display_teacher_quizs")],
				[("ثبت‌نام در کلاس‌های دیگر", "register_for_teacher")]
			],

			"admin": [
				[
					("نمایش دبیران", "display_teachers"),
					("نمایش دانش‌آموزان", "display_students")
				],
				[("نمایش کلاس‌ها", "display_classes")],
				[("مدیریت درخواست‌های عضویت", "managing_membership_requests")]
			]
		}

		for key in self.return_menu_inline.keys():
			self.return_menu_inline[key].append(
				[("درباره ما", "about")]
			)

		self.back_to_menu_button = [
			("بازگشت به منوی اصلی", "back_to_menu")
		]

		self.back_to_menu_button2 = [
			InlineKeyboardButton(
				text="بازگشت به منوی اصلی",
				callback_data="back_to_menu"
			)
		]

	def create_inline_keyboard(self, inline):
		"""تبدیل ساختار منو به InlineKeyboardMarkup"""

		keyboard = []

		for row in inline:
			buttons = []

			for text, callback_data in row:
				buttons.append(
					InlineKeyboardButton(
						text=text,
						callback_data=callback_data
					)
				)

			keyboard.append(buttons)

		return InlineKeyboardMarkup(keyboard)

	def requires_role(
		self,
		user_role: str,
		required_roles: str,
		hierarchical: bool = True
	) -> bool:
		"""
		بررسی دسترسی کاربر بر اساس نقش.

		خروجی:
			True: دسترسی مجاز است.
			False: دسترسی مجاز نیست.
		"""

		role_hierarchy = {
			"normal": 0,
			"student": 1,
			"teacher": 2,
			"admin": 3
		}

		user_level = role_hierarchy.get(user_role)
		required_level = [
			role_hierarchy.get(role)
			for role in required_roles
		]

		if user_level is None or None in required_level:
			return False

		if hierarchical:
			return user_level >= required_level[0]

		return user_role in required_roles

	async def start(self, message: Message):
		"""هندل دستور /start"""

		role = self.get_user_role(message.chat.id)

		inline = self.return_menu_inline.get(role, [])
		welcome_text = self.wellcom_texts.get(role)

		keyboard = self.create_inline_keyboard(inline)

		await message.reply_text(
			text=welcome_text,
			reply_markup=keyboard
		)

	async def back_to_menu(self, message: Message):
		"""بازگشت به منو"""

		role = self.get_user_role(user_id=message.chat.id)

		inline = self.return_menu_inline.get(role, [])

		keyboard = self.create_inline_keyboard(inline)

		try:
			del self.users[message.chat.id]
		except KeyError:
			pass

		await message.edit_text(
			text=self.wellcom_texts.get(role),
			reply_markup=keyboard
		)

	def get_user_role(self, user_id: int):
		"""
		نقش کاربر را از دیتابیس دریافت می‌کند.

		خروجی:
			'admin'   : مدیر
			'teacher' : دبیر
			'student' : دانش‌آموز
			'normal'  : کاربر ثبت‌نام‌نشده
		"""

		self.cursor.execute(
			"SELECT role FROM users WHERE user_id = ?",
			(user_id,)
		)

		result = self.cursor.fetchone()

		if result is None:
			return "normal"

		return result[0]

	def check_access_to_quiz(self, quiz_id, teacher_id):
		self.cursor.execute(
			"SELECT class_id FROM quizzes WHERE quiz_id = ?",
			(quiz_id,)
		)

		class_id = self.cursor.fetchone()

		if class_id:
			self.cursor.execute(
				"""
				SELECT 1
				FROM teacher_classes
				WHERE class_id = ? AND teacher_id = ?
				""",
				(class_id[0], teacher_id)
			)

			has_access = self.cursor.fetchone()

			if has_access:
				return True

			return False

		return False

	async def rename_class(self, message: Message):
		user_id = message.chat.id

		user: TemporaryUser = self.users.get(user_id)

		if user is None:
			return

		user_state = user.state

		if user_state == UserStates.NAME:

			name = message.text.strip()

			current_name = user.data["current_class_name"]
			class_id = user.data["class_id"]

			async with self.lock:
				self.cursor.execute(
					"UPDATE classes SET class_name = ? WHERE class_id = ?",
					(name, class_id)
				)

				self.database.commit()

			await message.reply_text(
				f"نام کلاس با موفقیت تغییر کرد!\n"
				f"نام قبلی: *{current_name}* و نام جدید: *{name}*",
				parse_mode="Markdown"
			)

			del self.users[user_id]

	async def create_new_quiz(self, message: Message):
		user_id = message.chat.id

		user: TemporaryUser = self.users.get(user_id)

		if user is None:
			print("return")
			return

		user_state = user.state

		if user_state == UserStates.START:
			print("ووو")

			button_id = str(uuid4().hex[:12])
			user.ids.append(button_id)

			async with self.lock:
				self.cursor.execute("""
					SELECT c.class_id, c.class_name
					FROM classes AS c
					INNER JOIN teacher_classes AS tc
						ON c.class_id = tc.class_id
					WHERE tc.teacher_id = ?
					ORDER BY c.class_name
				""", (user_id,))

				classes = self.cursor.fetchall()

			if not classes:
				await message.reply_text(
					"شما هنوز هیچ کلاسی ندارید."
				)
				return

			inline = []

			for class_id, class_name in classes:
				callback_data = (
					f"sc_for_create_q:{class_id}&{class_name}&{button_id}"
				)

				inline.append([
					InlineKeyboardButton(
						text=class_name,
						callback_data=callback_data
					)
				])

			text = "لطفاً کلاس موردنظر خود را برای ایجاد آزمون انتخاب کنید:"

			print("درحال ارسال جواب ...")

			await message.reply_text(
				text=text,
				reply_markup=InlineKeyboardMarkup(inline)
			)

			user.state = UserStates.NONE

		elif user_state == UserStates.TITLE:
			title = message.text.strip()
			class_name = user.data["class_name"]

			user.data["title"] = title

			await message.reply_text(
				f"آزمونی با عنوان *{title}* برای کلاس *{class_name}* ایجاد خواهد شد.\n"
				"لطفا به صورت نهایی تایید کنید. بله یا خیر؟",
				parse_mode="Markdown"
			)

			user.state = UserStates.FINAL_APPROVAL

		elif user_state == UserStates.FINAL_APPROVAL:
			text = message.text.strip()

			if text == "بله":
				async with self.lock:
					self.cursor.execute(
						"""
						SELECT 1
						FROM teacher_classes
						WHERE class_id = ? AND teacher_id = ?
						""",
						(user.data["class_id"], user_id)
					)

					c = self.cursor.fetchone()

				if c:
					print("اجرا میشه")
					user.state = UserStates.FINAL

				else:
					await message.reply_text(
						"کلاس مورد نظر شما دیگر متعلق به شما نیست."
					)

					user.state = UserStates.START
					await self.create_new_quiz(message=message)

			elif text == "خیر":
				await message.reply_text(
					"به درخواست خودتان عملیات لغو شد.",
					reply_markup=InlineKeyboardMarkup(
						[self.back_to_menu_button2]
					)
				)

				del self.users[user_id]

			else:
				await message.reply_text(
					"نمیفهمم. لطفا بگویید بله یا خیر"
				)

		if user.state == UserStates.FINAL:
			async with self.lock:
				self.cursor.execute(
					"""
					INSERT INTO quizzes(class_id, teacher_id, title)
					VALUES(?, ?, ?)
					""",
					(
						user.data["class_id"],
						user_id,
						user.data["title"]
					)
				)

				self.database.commit()

			await message.reply_text(
				f"آزمون *{user.data['title']}* با موفقیت ایجاد شد. "
				"از بخش ویرایش میتوانید سوال‌ها را اضافه کنید.",
				reply_markup=self.create_inline_keyboard(
					[self.back_to_menu_button]
				),
				parse_mode="Markdown"
			)

			del self.users[user_id]

	async def edit_quiz_title(self, message: Message):
		user_id = message.chat.id

		user: TemporaryUser = self.users.get(user_id)

		if user is None:
			return

		user_state = user.state

		if user_state == UserStates.START:
			await message.reply_text(
				text="لطفا عنوان جدید را بفرست"
			)

			user.state = UserStates.TITLE

		elif user_state == UserStates.TITLE:
			title = message.text.strip()

			if self.check_access_to_quiz(
				user.data["quiz_id"],
				user_id
			):
				async with self.lock:
					self.cursor.execute(
						"""
						UPDATE quizzes
						SET title = ?
						WHERE quiz_id = ?
						""",
						(title, user.data["quiz_id"])
					)

					self.database.commit()

				await message.reply_text(
					"تغییر عنوان با موفقیت انجام شد",
					reply_markup=InlineKeyboardMarkup(
						[self.back_to_menu_button2]
					)
				)

			else:
				await message.reply_text(
					text="شما دسترسی مورد نیاز را ندارید",
					reply_markup=self.create_inline_keyboard(
						[self.back_to_menu_button]
					)
				)

	async def add_question(self, message: Message):
		user_id = message.chat.id

		user: TemporaryUser = self.users.get(user_id)

		if user is None:
			return

		user_state = user.state

		if user_state == UserStates.START:
			number = user.data["number_question"]

			await message.reply_text(
				text=f"سوال *{number}*\nلطفا متن سوال را بفرست...",
				reply_markup=self.create_inline_keyboard(
					[
						[
							(
								"کافیه، بازگشت به منو",
								"back_to_menu"
							)
						]
					]
				),
				parse_mode="Markdown"
			)

			user.state = UserStates.QUESTION_TEXT

		elif user_state == UserStates.QUESTION_TEXT:
			user.data["question_text"] = message.text.strip()
			user.data["option"] = "الف"
			user.data["option_num"] = 1

			user.data["options"] = {
				1: "الف",
				2: "ب",
				3: "پ",
				4: "ت"
			}

			await message.reply_text(
				"جواب الف را بفرست..."
			)

			user.state = UserStates.ANSWER

		elif user_state == UserStates.ANSWER:
			answer = message.text.strip()

			user.data[user.data["option"]] = answer

			if user.data["option_num"] != 4:
				user.data["option"] = user.data["options"][
					user.data["option_num"] + 1
				]

				user.data["option_num"] = (
					user.data["option_num"] + 1
				)

				await message.reply_text(
					f"حالا جواب {user.data['option']} را بفرست..."
				)

			else:
				button_id = CALLBACK_SCHEMAS["select_correct_option"]["state_id"]
				user.ids.append(button_id)

				await message.reply_text(
					"حالا جواب درست را انتخاب کن:",
					reply_markup=self.create_inline_keyboard(
						[
							[
								(
									"الف",
									f"select_correct_option:الف"
								)
							],
							[
								(
									"ب",
									f"select_correct_option:ب"
								)
							],
							[
								(
									"پ",
									f"select_correct_option:پ"
								)
							],
							[
								(
									"ت",
									f"select_correct_option:ت"
								)
							]
						]
					)
				)

				user.state = UserStates.NONE

		if user.state == UserStates.FINAL:
			if self.check_access_to_quiz(
				user.data["quiz_id"],
				user_id
			):
				async with self.lock:
					self.cursor.execute(
						"""
						INSERT INTO questions
						(
							quiz_id,
							question_text,
							option_a,
							option_b,
							option_c,
							option_d,
							correct_option,
							position
						)
						VALUES
						(?, ?, ?, ?, ?, ?, ?, ?)
						""",
						(
							user.data["quiz_id"],
							user.data["question_text"],
							user.data["الف"],
							user.data["ب"],
							user.data["پ"],
							user.data["ت"],
							user.data["correct_option"],
							user.data["position"]
						)
					)

					self.database.commit()

				await message.reply_text(
					"سوال با موفقیت ثبت شد!"
				)

				user.data["number_question"] = (
					user.data["number_question"] + 1
				)

				user.state = UserStates.START
				await self.add_question(message)

			else:
				await message.reply_text(
					"شما دسترسی مورد نیاز را ندارید یا این آزمون دیگه وجود نداره"
				)