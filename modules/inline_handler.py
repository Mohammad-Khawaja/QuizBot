from telegram import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from sqlite3 import Connection, Cursor, IntegrityError
from .united import TemporaryUser
from .task_performer import UserStates, Tasks, TaskPerformer


class InlineAttributes:
	def __init__(self, bot, lock, task_performer):
		self.bot = bot
		self.lock = lock
		self.task_performer: TaskPerformer = task_performer

		self.admin_id: int | None = None
		self.database: Connection | None = None
		self.cursor: Cursor | None = None

		self.back_to_menu_button = [
			("بازگشت به منوی اصلی", "back_to_menu")
		]

	def create_inline_keyboard(self, rows):
		keyboard = []

		for row in rows:
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

	async def get_chat_full_name(self, chat_id):
		chat = await self.bot.get_chat(chat_id)

		first_name = chat.first_name or ""
		last_name = chat.last_name or ""

		full_name = f"{first_name} {last_name}".strip()

		return full_name or chat.username or "نامشخص"

	def validate_state_id(self, user, state_id):
		"""بررسی اعتبار شناسه وضعیت و مصرف آن."""

		if user is None:
			return False

		if state_id not in user.ids:
			return False

		user.ids.remove(state_id)
		return True


class RTUOInlines(InlineAttributes):
	"""دکمه‌هایی که به TemporaryUser نیاز دارند."""

	async def register_to_this_class(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""انتخاب یک کلاس برای درخواست ثبت‌نام دانش‌آموز"""

		if len(params) != 2:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		class_id, state_id = params
		class_id = int(class_id)

		user = self.task_performer.users.get(user_id)

		if user is None or not self.validate_state_id(user, state_id):
			await callback_query.answer("این عملیات منقضی شده است.")
			return

		async with self.lock:
			self.cursor.execute(
				"SELECT class_name FROM classes WHERE class_id = ?",
				(class_id,)
			)
			class_row = self.cursor.fetchone()

		if not class_row:
			await message.reply_text(
				"این کلاس دیگر وجود ندارد یا در سامانه ثبت نشده است."
			)
			return

		class_name = class_row[0]

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT user_id
				FROM class_members
				WHERE class_id = ? AND user_id = ?
				""",
				(class_id, user_id)
			)
			r = self.cursor.fetchall()

		if r:
			await message.reply_text(
				f"شما در حال حاضر عضو کلاس «{class_name}» هستید "
				"و نیازی به ثبت‌نام مجدد ندارید."
			)
			return

		try:
			full_name = await self.get_chat_full_name(user_id)

			async with self.lock:
				self.cursor.execute(
					"""
					INSERT INTO join_requests
					(user_id, class_id, requester_name)
					VALUES (?, ?, ?)
					""",
					(user_id, class_id, full_name)
				)

				request_id = self.cursor.lastrowid
				self.database.commit()

		except IntegrityError:
			self.database.rollback()

			await message.reply_text(
				f"درخواست عضویت شما برای کلاس «{class_name}» قبلاً ثبت شده است.\n\n"
				"لطفاً تا بررسی درخواست توسط مدیر منتظر بمانید."
			)
			return

		inline = self.create_inline_keyboard([
			[
				(
					"✅ تأیید عضویت",
					f"approve_student:{user_id}&{class_id}&{request_id}"
				)
			],
			[
				(
					"❌ رد درخواست",
					f"reject_student:{user_id}&{class_id}&{request_id}"
				)
			]
		])

		admin_text = (
			"📩 درخواست جدید عضویت در کلاس\n\n"
			f"👤 نام دانش‌آموز: {full_name}\n"
			f"🆔 شناسه کاربر: {user_id}\n"
			f"📚 کلاس درخواستی: {class_name}\n"
			f"🔢 شناسه کلاس: {class_id}\n"
			f"📋 شماره درخواست: {request_id}\n\n"
			"لطفاً درخواست را بررسی و درباره تأیید یا رد آن تصمیم‌گیری کنید."
		)

		await self.bot.send_message(
			chat_id=self.admin_id,
			text=admin_text,
			reply_markup=inline
		)

		await message.reply_text(
			f"✅ درخواست عضویت شما در کلاس «{class_name}» با موفقیت ثبت شد.\n\n"
			"درخواست برای مدیر سامانه ارسال شده است. "
			"پس از بررسی، نتیجه به شما اطلاع داده خواهد شد."
		)

	async def select_correct_option(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query: CallbackQuery
	):
		"""انتخاب گزینه درست هنگام افزودن سؤال جدید"""

		if len(params) != 2:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		option, state_id = params

		user = self.task_performer.users.get(user_id)

		if user is None:
			await callback_query.answer("این عملیات منقضی شده است.")
			return

		if user.state != UserStates.NONE:
			await callback_query.answer("این دکمه دیگر معتبر نیست.")
			return

		if not self.validate_state_id(user, state_id):
			await callback_query.answer("این دکمه دیگر معتبر نیست.")
			return

		correct_options = {
			"الف": "A",
			"ب": "B",
			"پ": "C",
			"ت": "D"
		}

		correct_option = correct_options.get(option)

		if correct_option is None:
			await callback_query.answer("گزینه انتخاب‌شده معتبر نیست.")
			return

		user.data["correct_option"] = correct_option
		user.state = UserStates.FINAL

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT COUNT(*)
				FROM questions
				WHERE quiz_id = ?
				""",
				(user.data["quiz_id"],)
			)
			count = self.cursor.fetchone()[0]

		user.data["position"] = count + 1

		await self.task_performer.add_question(message)


class DNRTUOInlines(InlineAttributes):
	"""دکمه‌هایی که نیازی به TemporaryUser ندارند."""

	async def back_to_menu(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		await self.task_performer.back_to_menu(message)

	async def display_teachers(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""نمایش دهنده دبیران"""

		inline = []

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT users.user_id, users.full_name, users.created_at,
				classes.class_name, classes.class_id
				FROM users
				JOIN teacher_classes
					ON users.user_id = teacher_classes.teacher_id
				JOIN classes
					ON teacher_classes.class_id = classes.class_id
				WHERE users.role = 'teacher'
				ORDER BY users.full_name
				"""
			)
			teachers = self.cursor.fetchall()

		if teachers:
			text = "👨‍🏫 فهرست معلمان سامانه\n\n"

			for index, th in enumerate(teachers, start=1):
				text += (
					f"🔹 معلم شماره {index}\n"
					f"👤 نام: {th[1] or 'ثبت نشده'}\n"
					f"🆔 شناسه کاربر: {th[0]}\n"
					f"📚 کلاس تحت مدیریت: {th[3] or 'نامشخص'}\n"
					f"📅 تاریخ عضویت: {th[2] or 'نامشخص'}\n"
					"━━━━━━━━━━━━━━\n\n"
				)

				inline.append([
					(
						f"اخراج دبیر شماره {index}",
						f"expel_teacher:{th[0]}&{th[-1]}"
					)
				])

			inline.append(self.back_to_menu_button)

			await message.edit_text(
				text,
				reply_markup=self.create_inline_keyboard(inline)
			)

		else:
			await message.edit_text(
				"👨‍🏫 در حال حاضر هیچ معلمی در سامانه ثبت نشده است.",
				reply_markup=self.create_inline_keyboard(
					[self.back_to_menu_button]
				)
			)

	async def register_for_teacher(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""پردازش دکمه ثبت‌نام برای دبیر شدن"""

		async with self.lock:
			self.cursor.execute(
				"SELECT COUNT(*) FROM users WHERE role = 'teacher'"
			)
			count_teachers = self.cursor.fetchone()[0]

		inline = [self.back_to_menu_button]

		if count_teachers < 6:
			async with self.lock:
				self.cursor.execute(
					"SELECT COUNT(class_id) FROM teacher_classes"
				)
				count_classes = self.cursor.fetchone()[0]

			if count_classes < 6:
				async with self.lock:
					self.cursor.execute(
						"SELECT class_id FROM teacher_classes"
					)
					classes = self.cursor.fetchall()

					self.cursor.execute(
						"SELECT class_id, class_name FROM classes"
					)
					all_classes = self.cursor.fetchall()

				assigned_class_ids = {
					row[0] for row in classes
				}

				all_classes = [
					ac for ac in all_classes
					if ac[0] not in assigned_class_ids
				]

				if all_classes:
					text = (
						"👨‍🏫 درخواست همکاری به‌عنوان معلم\n\n"
						"لطفاً کلاس موردنظر خود را انتخاب کنید.\n"
						"پس از انتخاب کلاس، درخواست شما برای بررسی "
						"به مدیر سامانه ارسال خواهد شد."
					)

					inline = []

					for ac in all_classes:
						inline.append([
							(
								ac[1],
								f"select_class_become_teacher:{ac[0]}"
							)
						])

					inline.append(self.back_to_menu_button)

				else:
					text = (
						"📚 تمام کلاس‌های موجود به معلم اختصاص داده شده‌اند.\n\n"
						"در حال حاضر کلاسی برای انتخاب وجود ندارد."
					)

			else:
				text = (
					"⚠️ ظرفیت اختصاص کلاس به معلمان تکمیل شده است.\n\n"
					"در حال حاضر امکان اختصاص کلاس جدید وجود ندارد."
				)

		else:
			text = (
				"⚠️ ظرفیت ثبت معلمان جدید تکمیل شده است.\n\n"
				"در حال حاضر امکان ثبت درخواست جدید وجود ندارد."
			)

		await message.edit_text(
			text,
			reply_markup=self.create_inline_keyboard(inline)
		)

	async def select_class_become_teacher(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""انتخاب یک کلاس برای دبیر شدن و ارسال درخواست"""

		if len(params) != 1:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		class_id = int(params[0])

		async with self.lock:
			self.cursor.execute(
				"SELECT class_name FROM classes WHERE class_id = ?",
				(class_id,)
			)
			class_row = self.cursor.fetchone()

		if not class_row:
			await callback_query.answer(
				text="این کلاس وجود ندارد یا دیگر در دسترس نیست."
			)
			return

		class_name = class_row[0]

		async with self.lock:
			self.cursor.execute(
				"SELECT class_id FROM teacher_classes WHERE class_id = ?",
				(class_id,)
			)
			classes = self.cursor.fetchall()

		if len(classes) != 0:
			await callback_query.answer(
				text="این کلاس در حال حاضر دارای معلم است. لطفاً کلاس دیگری را انتخاب کنید."
			)
			return

		try:
			full_name = await self.get_chat_full_name(user_id)

			async with self.lock:
				self.cursor.execute(
					"""
					INSERT INTO join_requests_become_teacher
					(user_id, class_id, requester_name)
					VALUES (?, ?, ?)
					""",
					(user_id, class_id, full_name)
				)

				request_id = self.cursor.lastrowid
				self.database.commit()

		except IntegrityError:
			self.database.rollback()

			await callback_query.answer(
				text="درخواست شما قبلاً برای این کلاس ثبت شده است."
			)
			return

		admin_text = (
			"📩 درخواست جدید همکاری به‌عنوان معلم\n\n"
			f"👤 نام متقاضی: {full_name}\n"
			f"🆔 شناسه کاربر: {user_id}\n"
			f"📚 کلاس انتخاب‌شده: {class_name}\n"
			f"🔢 شناسه کلاس: {class_id}\n"
			f"📋 شماره درخواست: {request_id}\n\n"
			"لطفاً درخواست را بررسی کنید."
		)

		admin_inline = self.create_inline_keyboard([
			[
				(
					"✅ تأیید درخواست",
					f"approve_teacher:{class_id}&{user_id}&{request_id}"
				)
			],
			[
				(
					"❌ رد درخواست",
					f"reject_teacher:{class_id}&{user_id}&{request_id}"
				)
			]
		])

		await self.bot.send_message(
			chat_id=self.admin_id,
			text=admin_text,
			reply_markup=admin_inline
		)

		await message.edit_text(
			f"✅ درخواست معلم شدن شما برای کلاس «{class_name}» ثبت شد.\n\n"
			"درخواست برای مدیر سامانه ارسال شده است. "
			"پس از بررسی، نتیجه به شما اطلاع داده خواهد شد.",
			reply_markup=self.create_inline_keyboard(
				[self.back_to_menu_button]
			)
		)

	async def approve_teacher(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""تأیید درخواست دبیر شدن"""

		if len(params) != 3:
			await callback_query.answer("اطلاعات درخواست نامعتبر است.")
			return

		class_id, user_id_teacher, request_id = map(int, params)

		try:
			full_name = await self.get_chat_full_name(user_id_teacher)
		except Exception:
			full_name = "نامشخص"

		async with self.lock:
			self.cursor.execute(
				"""
				UPDATE join_requests_become_teacher
				SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP
				WHERE request_id = ? AND status = 'pending'
				""",
				(request_id,)
			)

			rowcount = self.cursor.rowcount

			if rowcount == 0:
				self.database.rollback()
			else:
				self.cursor.execute(
					"""
					INSERT INTO teacher_classes (teacher_id, class_id)
					SELECT ?, ?
					WHERE NOT EXISTS (
						SELECT 1 FROM teacher_classes
						WHERE teacher_id = ? AND class_id = ?
					)
					""",
					(
						user_id_teacher,
						class_id,
						user_id_teacher,
						class_id
					)
				)

				self.cursor.execute(
					"""
					INSERT INTO users (user_id, full_name, role)
					SELECT ?, ?, ?
					WHERE NOT EXISTS (
						SELECT 1 FROM users WHERE user_id = ?
					)
					""",
					(
						user_id_teacher,
						full_name,
						"teacher",
						user_id_teacher
					)
				)

				self.database.commit()

				self.cursor.execute(
					"SELECT class_name FROM classes WHERE class_id = ?",
					(class_id,)
				)
				class_row = self.cursor.fetchone()

		if rowcount == 0:
			await callback_query.answer(
				text="این درخواست قبلاً بررسی شده است."
			)
			return

		class_name = class_row[0] if class_row else "نامشخص"

		await message.edit_text(
			f"✅ درخواست معلم شدن تأیید شد.\n\n"
			f"👤 معلم جدید: {full_name}\n"
			f"📚 کلاس اختصاص‌یافته: {class_name}\n"
			f"🆔 شناسه کاربر: {user_id_teacher}",
			reply_markup=self.create_inline_keyboard(
				[self.back_to_menu_button]
			)
		)

		await self.bot.send_message(
			text=(
				f"🎉 درخواست شما تأیید شد!\n\n"
				f"از این پس به‌عنوان معلم کلاس «{class_name}» فعالیت خواهید کرد.\n\n"
				"به سامانه خوش آمدید."
			),
			chat_id=user_id_teacher
		)

	async def reject_teacher(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""رد درخواست دبیر شدن"""

		if len(params) != 3:
			await callback_query.answer("اطلاعات درخواست نامعتبر است.")
			return

		class_id, user_id_teacher, request_id = map(int, params)

		async with self.lock:
			self.cursor.execute(
				"""
				UPDATE join_requests_become_teacher
				SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP
				WHERE request_id = ? AND status = 'pending'
				""",
				(request_id,)
			)

			rowcount = self.cursor.rowcount

			if rowcount:
				self.database.commit()
			else:
				self.database.rollback()

		if rowcount == 0:
			await callback_query.answer(
				text="این درخواست قبلاً بررسی شده است."
			)
			return

		async with self.lock:
			self.cursor.execute(
				"SELECT class_name FROM classes WHERE class_id = ?",
				(class_id,)
			)
			class_row = self.cursor.fetchone()

		class_name = class_row[0] if class_row else "نامشخص"

		await message.edit_text(
			f"❌ درخواست معلم شدن رد شد.\n\n"
			f"🆔 شناسه متقاضی: {user_id_teacher}\n"
			f"📚 کلاس انتخاب‌شده: {class_name}\n\n"
			"وضعیت درخواست در سامانه به‌روزرسانی شد.",
			reply_markup=self.create_inline_keyboard(
				[self.back_to_menu_button]
			)
		)

		await self.bot.send_message(
			text=(
				f"درخواست شما برای فعالیت به‌عنوان معلم کلاس "
				f"«{class_name}» تأیید نشد.\n\n"
				"در صورت نیاز، می‌توانید برای کسب اطلاعات بیشتر "
				"با مدیر سامانه تماس بگیرید."
			),
			chat_id=user_id_teacher
		)

	async def register_for_classes(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""نمایش کلاس‌ها برای ثبت‌نام دانش‌آموز"""

		user = TemporaryUser(
			type_task=Tasks.NONE,
			state=UserStates.NONE
		)

		self.task_performer.users[user_id] = user

		async with self.lock:
			self.cursor.execute(
				"SELECT class_id, class_name FROM classes"
			)
			classes = self.cursor.fetchall()

			self.cursor.execute(
				"SELECT user_id, class_id FROM class_members"
			)
			class_members = self.cursor.fetchall()

		classes_for_show = {}

		for class_ in classes:
			classes_for_show[class_[0]] = [class_[1]]

		for member in class_members:
			for class_ in classes:
				if member[1] == class_[0]:
					classes_for_show[class_[0]].append(member[0])
					break

		text = (
			"📚 فهرست کلاس‌های موجود\n\n"
			"لطفاً کلاس موردنظر خود را انتخاب کنید. "
			"تعداد اعضای هر کلاس در ادامه نمایش داده شده است."
		)

		inline = []

		for i, items in enumerate(classes_for_show.items(), start=1):
			class_id, class_ = items

			text += (
				f"\n\n🔹 کلاس {i}: {class_[0]}\n"
				f"👥 تعداد اعضا: {len(class_) - 1} نفر"
			)

			state_id = str(__import__("uuid").uuid4().hex[:12])
			user.ids.append(state_id)

			inline.append([
				(
					class_[0],
					f"register_to_this_class:{class_id}&{state_id}"
				)
			])

		if not classes:
			text += "\n\nهنوز هیچ کلاسی در سامانه ایجاد نشده است."

		text += (
			"\n\nبرای ارسال درخواست عضویت، "
			"دکمه مربوط به کلاس موردنظر را انتخاب کنید."
		)

		inline.append(self.back_to_menu_button)

		await message.edit_text(
			text=text,
			reply_markup=self.create_inline_keyboard(inline)
		)

	async def approve_student(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""تأیید درخواست عضویت در کلاس برای دانش‌آموز"""

		if len(params) != 3:
			await callback_query.answer("اطلاعات درخواست نامعتبر است.")
			return

		user_id_st, class_id, request_id = map(int, params)

		try:
			full_name = await self.get_chat_full_name(user_id_st)
		except Exception:
			full_name = "نامشخص"

		async with self.lock:
			self.cursor.execute(
				"""
				UPDATE join_requests
				SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP
				WHERE request_id = ? AND status = 'pending'
				""",
				(request_id,)
			)

			rowcount = self.cursor.rowcount

			if rowcount == 0:
				self.database.rollback()
			else:
				self.cursor.execute(
					"""
					INSERT INTO class_members (user_id, class_id)
					SELECT ?, ?
					WHERE NOT EXISTS (
						SELECT 1 FROM class_members
						WHERE user_id = ? AND class_id = ?
					)
					""",
					(
						user_id_st,
						class_id,
						user_id_st,
						class_id
					)
				)

				self.cursor.execute(
					"""
					INSERT INTO users (user_id, full_name, role)
					SELECT ?, ?, ?
					WHERE NOT EXISTS (
						SELECT 1 FROM users WHERE user_id = ?
					)
					""",
					(
						user_id_st,
						full_name,
						"student",
						user_id_st
					)
				)

				self.database.commit()

				self.cursor.execute(
					"SELECT class_name FROM classes WHERE class_id = ?",
					(class_id,)
				)
				class_row = self.cursor.fetchone()

				self.cursor.execute(
					"SELECT COUNT(*) FROM class_members WHERE class_id = ?",
					(class_id,)
				)
				member_count = self.cursor.fetchone()[0]

		if rowcount == 0:
			await callback_query.answer(
				text="این درخواست قبلاً بررسی شده است."
			)
			return

		class_name = class_row[0] if class_row else "نامشخص"

		await message.edit_text(
			f"✅ درخواست عضویت تأیید شد.\n\n"
			f"👤 دانش‌آموز: {full_name}\n"
			f"🆔 شناسه کاربر: {user_id_st}\n"
			f"📚 کلاس: {class_name}\n"
			f"👥 تعداد فعلی اعضای کلاس: {member_count} نفر",
			reply_markup=self.create_inline_keyboard(
				[self.back_to_menu_button]
			)
		)

		await self.bot.send_message(
			chat_id=user_id_st,
			text=(
				f"🎉 درخواست عضویت شما تأیید شد!\n\n"
				f"📚 کلاس: {class_name}\n"
				f"👥 تعداد اعضای کلاس: {member_count} نفر\n\n"
				"اکنون عضو این کلاس هستید و می‌توانید "
				"از امکانات مربوط به آن استفاده کنید."
			)
		)

	async def reject_student(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""رد درخواست عضویت در کلاس برای دانش‌آموز"""

		if len(params) != 3:
			await callback_query.answer("اطلاعات درخواست نامعتبر است.")
			return

		user_id_st, class_id, request_id = map(int, params)

		async with self.lock:
			self.cursor.execute(
				"""
				UPDATE join_requests
				SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP
				WHERE request_id = ? AND status = 'pending'
				""",
				(request_id,)
			)

			rowcount = self.cursor.rowcount

			if rowcount:
				self.database.commit()
			else:
				self.database.rollback()

		if rowcount == 0:
			await callback_query.answer(
				text="این درخواست قبلاً بررسی شده است."
			)
			return

		async with self.lock:
			self.cursor.execute(
				"SELECT class_name FROM classes WHERE class_id = ?",
				(class_id,)
			)
			class_row = self.cursor.fetchone()

		class_name = class_row[0] if class_row else "نامشخص"

		await message.edit_text(
			text=(
				f"❌ درخواست عضویت رد شد.\n\n"
				f"🆔 شناسه دانش‌آموز: {user_id_st}\n"
				f"📚 کلاس: {class_name}\n\n"
				"وضعیت درخواست در سامانه به‌روزرسانی شد."
			),
			reply_markup=self.create_inline_keyboard(
				[self.back_to_menu_button]
			)
		)

		await self.bot.send_message(
			chat_id=user_id_st,
			text=(
				f"درخواست عضویت شما در کلاس «{class_name}» تأیید نشد.\n\n"
				"در صورت نیاز، می‌توانید برای کسب اطلاعات بیشتر "
				"با مدیر سامانه تماس بگیرید."
			)
		)

	async def display_students(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""نمایش کلاس‌ها برای مشاهده دانش‌آموزان"""

		async with self.lock:
			self.cursor.execute(
				"SELECT class_id, class_name FROM classes"
			)
			classes = self.cursor.fetchall()

			self.cursor.execute(
				"SELECT user_id, class_id FROM class_members"
			)
			class_members = self.cursor.fetchall()

		classes_for_show = {}

		for class_ in classes:
			classes_for_show[class_[0]] = [class_[1]]

		for member in class_members:
			for class_ in classes:
				if member[1] == class_[0]:
					classes_for_show[class_[0]].append(member[0])
					break

		text = (
			"📚 فهرست کلاس‌های موجود\n\n"
			"لطفاً کلاس موردنظر خود را انتخاب کنید. "
			"تعداد اعضای هر کلاس در ادامه نمایش داده شده است."
		)

		inline = []

		for i, items in enumerate(classes_for_show.items(), start=1):
			class_id, class_ = items

			text += (
				f"\n\n🔹 کلاس {i}: {class_[0]}\n"
				f"👥 تعداد اعضا: {len(class_) - 1} نفر"
			)

			inline.append([
				(
					class_[0],
					f"display_class_members:{class_id}"
				)
			])

		if not classes:
			text += "\n\nهنوز هیچ کلاسی در سامانه ایجاد نشده است."

		text += (
			"\n\nبرای مشاهده اعضای یک کلاس، "
			"دکمه مربوط به کلاس موردنظر را انتخاب کنید."
		)

		inline.append(self.back_to_menu_button)

		await message.edit_text(
			text=text,
			reply_markup=self.create_inline_keyboard(inline)
		)

	async def display_class_members(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""نمایش دانش‌آموزان کلاس انتخاب‌شده"""

		if len(params) != 1:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		class_id = int(params[0])

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT 1
				FROM teacher_classes
				WHERE teacher_id = ? AND class_id = ?
				""",
				(user_id, class_id)
			)
			is_owner = self.cursor.fetchone()

		if not is_owner and user_id != self.admin_id:
			await callback_query.answer(
				text="شما اجازه مشاهده اعضای این کلاس را ندارید."
			)
			return

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT user_id, joined_at
				FROM class_members
				WHERE class_id = ?
				""",
				(class_id,)
			)
			users = self.cursor.fetchall()

		text = "دانش‌آموزان این کلاس در زیر قابل مشاهده هستند."
		inline = []

		for i, user in enumerate(users, start=1):
			try:
				full_name = await self.get_chat_full_name(user[0])
			except Exception:
				full_name = "نامشخص"

			text += (
				f"\n\nدانش‌آموز {i}"
				f"\nنام: {full_name}"
				f"\nشناسه کاربری: {user[0]}"
				f"\nتاریخ ثبت‌نام: {user[1]}"
			)

			inline.append([
				(
					f"اخراج دانش‌آموز {i}",
					f"expel_student:{user[0]}&{class_id}"
				)
			])

		if not users:
			text = "در حال حاضر هیچ دانش‌آموزی عضو این کلاس نیست."

		inline.append(self.back_to_menu_button)

		await message.edit_text(
			text=text,
			reply_markup=self.create_inline_keyboard(inline)
		)

	async def expel_student(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""اخراج یک دانش‌آموز از یک کلاس"""

		if len(params) != 2:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		student_user_id, class_id = map(int, params)

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT 1
				FROM teacher_classes
				WHERE teacher_id = ? AND class_id = ?
				""",
				(user_id, class_id)
			)
			is_owner = self.cursor.fetchone()

		if not is_owner and self.admin_id != user_id:
			await callback_query.answer(
				text="شما به این کلاس دسترسی ندارید."
			)
			return

		async with self.lock:
			self.cursor.execute(
				"""
				DELETE FROM class_members
				WHERE user_id = ? AND class_id = ?
				""",
				(student_user_id, class_id)
			)

			rowcount = self.cursor.rowcount
			self.database.commit()

		if rowcount == 0:
			await callback_query.answer(
				text="این دانش‌آموز از قبل از کلاس اخراج شده است."
			)
			return

		async with self.lock:
			self.cursor.execute(
				"SELECT user_id FROM class_members WHERE user_id = ?",
				(student_user_id,)
			)

			if not self.cursor.fetchall():
				self.cursor.execute(
					"""
					DELETE FROM users
					WHERE user_id = ? AND role != 'admin'
					""",
					(student_user_id,)
				)
				self.database.commit()

			self.cursor.execute(
				"SELECT class_name FROM classes WHERE class_id = ?",
				(class_id,)
			)
			class_row = self.cursor.fetchone()

			self.cursor.execute(
				"SELECT role FROM users WHERE user_id = ?",
				(user_id,)
			)
			role_row = self.cursor.fetchone()

		class_name = class_row[0] if class_row else "نامشخص"
		role = role_row[0] if role_row else "مدیر"

		try:
			name = await self.get_chat_full_name(student_user_id)
		except Exception:
			name = "نامشخص"

		await message.reply_text(
			f"دانش‌آموز موردنظر با موفقیت اخراج شد.\nنام: {name}"
		)

		role = {
			"admin": "مدیر",
			"teacher": "دبیر"
		}.get(role, "مدیر")

		await self.bot.send_message(
			chat_id=student_user_id,
			text=f"شما به درخواست {role} از کلاس {class_name} اخراج شدید."
		)

	async def expel_teacher(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""اخراج یک دبیر از یک کلاس"""

		if len(params) != 2:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		teacher_user_id, class_id = map(int, params)

		async with self.lock:
			self.cursor.execute(
				"""
				DELETE FROM teacher_classes
				WHERE class_id = ? AND teacher_id = ?
				""",
				(class_id, teacher_user_id)
			)

			rowcount = self.cursor.rowcount
			self.database.commit()

		if rowcount == 0:
			await callback_query.answer(
				text="این دبیر از قبل از کلاس حذف شده است."
			)
			return

		async with self.lock:
			self.cursor.execute(
				"SELECT * FROM teacher_classes WHERE teacher_id = ?",
				(teacher_user_id,)
			)

			if not self.cursor.fetchone():
				self.cursor.execute(
					"DELETE FROM users WHERE user_id = ?",
					(teacher_user_id,)
				)

			self.database.commit()

			self.cursor.execute(
				"SELECT class_name FROM classes WHERE class_id = ?",
				(class_id,)
			)
			class_row = self.cursor.fetchone()

		class_name = class_row[0] if class_row else "نامشخص"

		try:
			name = await self.get_chat_full_name(teacher_user_id)
		except Exception:
			name = "نامشخص"

		await message.reply_text(
			f"دبیر موردنظر با موفقیت از کلاس حذف شد.\nنام: {name}"
		)

		await self.bot.send_message(
			chat_id=teacher_user_id,
			text=f"شما از کلاس {class_name} حذف شدید."
		)

	async def display_classes(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""نمایش کلاس‌های موجود برای ویرایش نام"""

		async with self.lock:
			self.cursor.execute(
				"SELECT class_id, class_name FROM classes"
			)
			classes = self.cursor.fetchall()

			self.cursor.execute(
				"SELECT user_id, class_id FROM class_members"
			)
			class_members = self.cursor.fetchall()

		classes_for_show = {}

		for class_ in classes:
			classes_for_show[class_[0]] = [class_[1]]

		for member in class_members:
			for class_ in classes:
				if member[1] == class_[0]:
					classes_for_show[class_[0]].append(member[0])
					break

		text = (
			"📚 فهرست کلاس‌های موجود\n\n"
			"لطفاً کلاس موردنظر خود را انتخاب کنید. "
			"تعداد اعضای هر کلاس در ادامه نمایش داده شده است."
		)

		inline = []

		for i, items in enumerate(classes_for_show.items(), start=1):
			class_id, class_ = items

			text += (
				f"\n\n🔹 کلاس {i}: {class_[0]}\n"
				f"👥 تعداد اعضا: {len(class_) - 1} نفر"
			)

			inline.append([
				(
					class_[0],
					f"rename_class:{class_id}"
				)
			])

		if not classes:
			text += "\n\nهنوز هیچ کلاسی در سامانه ایجاد نشده است."

		text += (
			"\n\nبرای ویرایش نام هر کلاس، "
			"روی دکمه مربوط به آن کلیک کنید."
		)

		inline.append(self.back_to_menu_button)

		await message.edit_text(
			text=text,
			reply_markup=self.create_inline_keyboard(inline)
		)

	async def rename_class(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""شروع درخواست تغییر نام کلاس"""

		if len(params) != 1:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		class_id = int(params[0])

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT class_name, class_id
				FROM classes
				WHERE class_id = ?
				""",
				(class_id,)
			)
			class_ = self.cursor.fetchone()

		if not class_:
			await callback_query.answer(
				text="این کلاس وجود ندارد."
			)
			return

		text = (
			f"نام فعلی کلاس: {class_[0]}\n"
			"لطفاً نام جدید را ارسال کنید..."
		)

		await message.reply_text(text)

		user = TemporaryUser(
			state=UserStates.NAME,
			type_task=Tasks.RENAME_CLASS
		)

		self.task_performer.users[user_id] = user
		user.data["class_id"] = class_[1]
		user.data["current_class_name"] = class_[0]

	async def managing_membership_requests(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""مدیریت درخواست‌های عضویت"""

		await message.edit_text(
			text=(
				"لطفاً مشخص کنید که می‌خواهید درخواست‌های عضویت دبیر "
				"را مدیریت کنید یا درخواست‌های ثبت‌نام دانش‌آموزان."
			),
			reply_markup=self.create_inline_keyboard([
				[
					(
						"درخواست‌های عضویت دانش‌آموزان",
						"student_membership_requests:1"
					)
				],
				[
					(
						"درخواست‌های عضویت دبیران",
						"teacher_membership_requests:1"
					)
				]
			])
		)

	async def student_membership_requests(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""مدیریت درخواست‌های عضویت دانش‌آموزان"""

		if len(params) != 1:
			await callback_query.answer("صفحه درخواستی معتبر نیست.")
			return

		page = params[0]

		if not page.isdigit() or int(page) < 1:
			await callback_query.answer(
				text="صفحه درخواستی معتبر نیست."
			)
			return

		page = int(page)

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT * FROM join_requests
				WHERE status = 'pending'
				ORDER BY requested_at
				LIMIT 10 OFFSET ?
				""",
				((page - 1) * 10,)
			)
			requests = self.cursor.fetchall()

			self.cursor.execute(
				"""
				SELECT COUNT(*)
				FROM join_requests
				WHERE status = 'pending'
				"""
			)
			total_rows = self.cursor.fetchone()[0]
			all_pages = (total_rows + 9) // 10

		if requests:
			text = "*درخواست‌های عضویت بررسی‌نشده*"
			inline = []

			for i, r in enumerate(
				requests,
				start=(page - 1) * 10 + 1
			):
				try:
					full_name = await self.get_chat_full_name(r[1])
				except Exception:
					full_name = "نامشخص"

				async with self.lock:
					self.cursor.execute(
						"SELECT class_name FROM classes WHERE class_id = ?",
						(r[3],)
					)
					class_row = self.cursor.fetchone()

				class_name = class_row[0] if class_row else "نامشخص"

				text += (
					f"\n\nدرخواست شماره {i}"
					f"\nنام: {full_name}"
					f"\nثبت‌نام در: {class_name}"
					f"\nزمان درخواست: {r[-2]}"
				)

				inline.append([
					(
						f"پذیرش درخواست {i}",
						f"approve_student:{r[1]}&{r[2]}&{r[0]}"
					),
					(
						f"رد درخواست {i}",
						f"reject_student:{r[1]}&{r[2]}&{r[0]}"
					)
				])

			text += (
				f"\n\nکل صفحات: {all_pages} صفحه"
				f"\nصفحه فعلی: صفحه {page}"
			)

			pagination = []

			if page < all_pages:
				pagination.append(
					(
						"صفحه بعد",
						f"student_membership_requests:{page + 1}"
					)
				)

			if page > 1:
				pagination.append(
					(
						"صفحه قبل",
						f"student_membership_requests:{page - 1}"
					)
				)

			if pagination:
				inline.append(pagination)

			inline.append(self.back_to_menu_button)

		else:
			text = "هیچ درخواست عضویتی وجود ندارد."
			inline = [self.back_to_menu_button]

		await message.edit_text(
			text=text,
			reply_markup=self.create_inline_keyboard(inline)
		)

	async def teacher_membership_requests(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""مدیریت درخواست‌های عضویت دبیران"""

		if len(params) != 1:
			await callback_query.answer("صفحه درخواستی معتبر نیست.")
			return

		page = params[0]

		if not page.isdigit() or int(page) < 1:
			await callback_query.answer(
				text="صفحه درخواستی معتبر نیست."
			)
			return

		page = int(page)

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT * FROM join_requests_become_teacher
				WHERE status = 'pending'
				ORDER BY requested_at
				LIMIT 10 OFFSET ?
				""",
				((page - 1) * 10,)
			)
			requests = self.cursor.fetchall()

			self.cursor.execute(
				"""
				SELECT COUNT(*)
				FROM join_requests_become_teacher
				WHERE status = 'pending'
				"""
			)
			total_rows = self.cursor.fetchone()[0]
			all_pages = (total_rows + 9) // 10

		if requests:
			text = "*درخواست‌های عضویت بررسی‌نشده*"
			inline = []

			for i, r in enumerate(
				requests,
				start=(page - 1) * 10 + 1
			):
				try:
					full_name = await self.get_chat_full_name(r[1])
				except Exception:
					full_name = "نامشخص"

				async with self.lock:
					self.cursor.execute(
						"SELECT class_name FROM classes WHERE class_id = ?",
						(r[3],)
					)
					class_row = self.cursor.fetchone()

				class_name = class_row[0] if class_row else "نامشخص"

				text += (
					f"\n\nدرخواست دبیری شماره {i}"
					f"\nنام: {full_name}"
					f"\nثبت‌نام در: {class_name}"
					f"\nزمان درخواست: {r[-2]}"
				)

				inline.append([
					(
						f"پذیرش درخواست {i}",
						f"approve_teacher:{r[2]}&{r[1]}&{r[0]}"
					),
					(
						f"رد درخواست {i}",
						f"reject_teacher:{r[2]}&{r[1]}&{r[0]}"
					)
				])

			text += (
				f"\n\nکل صفحات: {all_pages} صفحه"
				f"\nصفحه فعلی: صفحه {page}"
			)

			pagination = []

			if page < all_pages:
				pagination.append(
					(
						"صفحه بعد",
						f"teacher_membership_requests:{page + 1}"
					)
				)

			if page > 1:
				pagination.append(
					(
						"صفحه قبل",
						f"teacher_membership_requests:{page - 1}"
					)
				)

			if pagination:
				inline.append(pagination)

			inline.append(self.back_to_menu_button)

		else:
			text = "هیچ درخواست عضویتی وجود ندارد."
			inline = [self.back_to_menu_button]

		await message.edit_text(
			text=text,
			reply_markup=self.create_inline_keyboard(inline)
		)

	async def display_teacher_classes(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""نمایش کلاس‌های دبیر"""

		async with self.lock:
			self.cursor.execute(
				"SELECT class_id FROM teacher_classes WHERE teacher_id = ?",
				(user_id,)
			)
			classes = self.cursor.fetchall()

		classes_members = {
			class_[0]: []
			for class_ in classes
		}

		if classes:
			async with self.lock:
				self.cursor.execute(
					"SELECT user_id, class_id FROM class_members"
				)
				class_members = self.cursor.fetchall()

			for member in class_members:
				class_id = member[1]

				if class_id in classes_members:
					classes_members[class_id].append(member[0])

			text = "*کلاس‌های شما در زیر قابل مشاهده است*"
			inline = []
			i = 1

			for class_id, members in classes_members.items():
				async with self.lock:
					self.cursor.execute(
						"SELECT class_name FROM classes WHERE class_id = ?",
						(class_id,)
					)
					class_row = self.cursor.fetchone()

				if not class_row:
					continue

				class_name = class_row[0]

				text += (
					f"\n\nکلاس شماره {i}"
					f"\nنام کلاس: {class_name}"
					f"\nتعداد اعضا: {len(members)}"
				)

				inline.append([
					(
						f"نمایش اعضای کلاس {i}",
						f"display_class_members:{class_id}"
					)
				])

				i += 1

			inline.append(self.back_to_menu_button)

			await message.edit_text(
				text=text,
				reply_markup=self.create_inline_keyboard(inline),
				parse_mode="Markdown"
			)

		else:
			await message.reply_text(
				"هیچ کلاسی متعلق به شما نیست."
			)

	async def display_teacher_quizs(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""نمایش آزمون‌های دبیر"""

		async with self.lock:
			self.cursor.execute(
				"SELECT * FROM quizzes WHERE teacher_id = ?",
				(user_id,)
			)
			quizzes = self.cursor.fetchall()

		inline = []

		if quizzes:
			text = "*آزمون‌هایی که ایجاد کردید:*"

			for i, quiz in enumerate(quizzes, start=1):
				async with self.lock:
					self.cursor.execute(
						"SELECT class_name FROM classes WHERE class_id = ?",
						(quiz[1],)
					)
					class_row = self.cursor.fetchone()

				class_name = class_row[0] if class_row else "نامشخص"

				text += (
					f"\n\n*آزمون شماره {i}*"
					f"\nعنوان: {quiz[3]}"
					f"\nکلاس مربوطه: {class_name}"
					f"\nتاریخ ایجاد: {quiz[-2]}"
					f"\nمنتشر شده: {'بله' if quiz[-1] == 1 else 'خیر'}"
				)

				inline.append([
					(
						f"ویرایش آزمون {i}",
						f"edit_quiz:{quiz[0]}"
					)
				])

		else:
			text = "فعلاً هیچ آزمونی اضافه نکرده‌اید."

		inline.extend([
			[
				("ایجاد آزمون جدید", "create_new_quize")
			],
			self.back_to_menu_button
		])

		await message.edit_text(
			text,
			reply_markup=self.create_inline_keyboard(inline),
			parse_mode="Markdown"
		)

	async def create_new_quize(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query
	):
		"""شروع ساخت آزمون جدید"""

		user = TemporaryUser(
			state=UserStates.START,
			type_task=Tasks.CREATE_NEW_QUIZ
		)

		self.task_performer.users[user_id] = user

		await self.task_performer.create_new_quiz(message)

	async def sc_for_create_q(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query: CallbackQuery
	):
		"""انتخاب کلاس برای ساخت آزمون"""

		if len(params) != 3:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		class_id, class_name, state_id = params
		class_id = int(class_id)

		user = self.task_performer.users.get(user_id)

		if user is None:
			await callback_query.answer("این عملیات منقضی شده است.")
			return

		if user.state != UserStates.NONE:
			await callback_query.answer("این دکمه دیگر معتبر نیست.")
			return

		if not self.validate_state_id(user, state_id):
			await callback_query.answer("این دکمه دیگر معتبر نیست.")
			return

		async with self.lock:
			self.cursor.execute(
				"""
				SELECT 1
				FROM teacher_classes
				WHERE teacher_id = ? AND class_id = ?
				""",
				(user_id, class_id)
			)
			there_is = self.cursor.fetchone()

		if there_is:
			user.data["class_id"] = class_id
			user.data["class_name"] = class_name

			await message.reply_text(
				"لطفا عنوان یا نام آزمون را بفرست."
			)

			user.ids.clear()
			user.state = UserStates.TITLE

		else:
			await callback_query.answer(
				"این کلاس دیگر متعلق به شما نیست."
			)

	async def edit_quiz(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query: CallbackQuery
	):
		"""ویرایش آزمون و نمایش منوی ویرایش"""

		if len(params) != 1:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		quiz_id = int(params[0])

		async with self.lock:
			self.cursor.execute(
				"SELECT class_id FROM quizzes WHERE quiz_id = ?",
				(quiz_id,)
			)
			class_id = self.cursor.fetchone()

		if class_id:
			async with self.lock:
				self.cursor.execute(
					"""
					SELECT 1
					FROM teacher_classes
					WHERE class_id = ? AND teacher_id = ?
					""",
					(class_id[0], user_id)
				)
				has_access = self.cursor.fetchone()

			if has_access:
				async with self.lock:
					self.cursor.execute(
						"""
						SELECT title, is_published
						FROM quizzes
						WHERE quiz_id = ?
						""",
						(quiz_id,)
					)
					r = self.cursor.fetchone()

				title, is_published = r

				if is_published == 0:
					published_status = [
						"انتشار عمومی",
						"1"
					]
				else:
					published_status = [
						"برداشتن از انتشار عمومی",
						"0"
					]

				text = (
					f"برای ویرایش آزمون *{title}* "
					"لطفا تعیین کنید چه چیزی اش را میخواهید تغییر دهید."
				)

				inline = [
					[
						(
							"تغییر عنوان",
							f"edit_quiz_title:{quiz_id}"
						),
						(
							"افزودن سوال",
							f"add_question:{quiz_id}"
						)
					],
					[
						(
							published_status[0],
							f"quiz_release:{quiz_id}&{published_status[1]}"
						)
					]
				]

				inline.append(self.back_to_menu_button)

				await message.edit_text(
					text=text,
					reply_markup=self.create_inline_keyboard(inline),
					parse_mode="Markdown"
				)

			else:
				await callback_query.answer(
					"شما دسترسی مورد نیاز را ندارید"
				)

		else:
			await callback_query.answer(
				"این آزمون دیگه وجود نداره"
			)

	async def quiz_release(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query: CallbackQuery
	):
		"""انتشار و برداشتن از حالت انتشار یک آزمون"""

		if len(params) != 2:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		quiz_id, release = map(int, params)

		async with self.lock:
			self.cursor.execute(
				"SELECT class_id FROM quizzes WHERE quiz_id = ?",
				(quiz_id,)
			)
			class_id = self.cursor.fetchone()

		if class_id:
			async with self.lock:
				self.cursor.execute(
					"""
					SELECT 1
					FROM teacher_classes
					WHERE class_id = ? AND teacher_id = ?
					""",
					(class_id[0], user_id)
				)
				has_access = self.cursor.fetchone()

			if has_access:
				async with self.lock:
					self.cursor.execute(
						"""
						UPDATE quizzes
						SET is_published = ?
						WHERE quiz_id = ?
						""",
						(release, quiz_id)
					)
					self.database.commit()

				if release == 0:
					status_text = "از حالت انتشار برداشته شد."
				else:
					status_text = "منتشر شد."

				await message.edit_text(
					text=f"آزمون {status_text}",
					reply_markup=self.create_inline_keyboard(
						[self.back_to_menu_button]
					)
				)

			else:
				await callback_query.answer(
					"شما دسترسی مورد نیاز را ندارید"
				)

		else:
			await callback_query.answer(
				"این آزمون دیگه وجود نداره"
			)

	async def add_question(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query: CallbackQuery
	):
		"""شروع افزودن سوال جدید به آزمون"""

		if len(params) != 1:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		quiz_id = int(params[0])

		if self.task_performer.check_access_to_quiz(
			quiz_id,
			user_id
		):
			user = TemporaryUser(
				state=UserStates.START,
				type_task=Tasks.ADD_QUESTION
			)

			user.data["number_question"] = 1
			user.data["quiz_id"] = quiz_id

			self.task_performer.users[user_id] = user

			await self.task_performer.add_question(message)

		else:
			await callback_query.answer(
				"شما دسترسی مورد نیاز را ندارید"
			)

	async def edit_quiz_title(
		self,
		params: tuple,
		message: Message,
		user_id: int,
		callback_query: CallbackQuery
	):
		"""شروع ویرایش عنوان یک آزمون"""

		if len(params) != 1:
			await callback_query.answer("اطلاعات دکمه نامعتبر است.")
			return

		quiz_id = int(params[0])

		if self.task_performer.check_access_to_quiz(
			quiz_id,
			user_id
		):
			user = TemporaryUser(
				state=UserStates.START,
				type_task=Tasks.EDIT_QUIZ_TITLE
			)

			self.task_performer.users[user_id] = user
			user.data["quiz_id"] = quiz_id

			await self.task_performer.edit_quiz_title(message)

		else:
			await callback_query.answer(
				"شما دسترسی مورد نیاز را ندارید"
			)


class InlineHandler(RTUOInlines, DNRTUOInlines):
	def __init__(self, bot, lock, task_performer):
		InlineAttributes.__init__(
			self,
			bot,
			lock,
			task_performer
		)