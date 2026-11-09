from uuid import uuid4

CALLBACK_SCHEMAS = {
# RTUO
"register_to_this_class": {
	"params": (int,),
	"inline_type": "RTUO",
	"roles": ("normal", "student"),
	"state_id": str(uuid4())
},
"select_correct_option": {
	"params": (str,),
	"inline_type": "RTUO",
	"roles": ("teacher",),
	"state_id": str(uuid4())
},
"select_option_for_edit_answer": {
	"params": (str,),
	"inline_type": "RTUO",
	"roles": ("teacher",),
	"state_id": str(uuid4())
},
"select_true_option_for_edit": {
	"params": (),
	"inline_type": "RTUO",
	"roles": ("teacher",),
	"state_id": str(uuid4())
},
"select_option_as_true": {
	"params": (str,),
	"inline_type": "RTUO",
	"roles": ("teacher",),
	"state_id": str(uuid4())
},

# DNRTUO
"back_to_menu": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("normal", "student", "teacher", "admin"),
	"state_id": None
},
"display_teachers": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"register_for_teacher": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("normal", "teacher"),
	"state_id": None
},
"select_class_become_teacher": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("normal", "teacher"),
	"state_id": None
},
"approve_teacher": {
	"params": (int, int, int),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"reject_teacher": {
	"params": (int, int, int),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"register_for_classes": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("normal", "student"),
	"state_id": None
},
"approve_student": {
	"params": (int, int, int),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"reject_student": {
	"params": (int, int, int),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"display_students": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"display_class_members": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("teacher", "admin"),
	"state_id": None
},
"expel_student": {
	"params": (int, int),
	"inline_type": "DNRTUO",
	"roles": ("teacher", "admin"),
	"state_id": None
},
"expel_teacher": {
	"params": (int, int),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"display_classes": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"rename_class": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"managing_membership_requests": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"student_membership_requests": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"teacher_membership_requests": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("admin",),
	"state_id": None
},
"display_teacher_classes": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"display_teacher_quizs": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"delete_quiz": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"create_new_quize": {
	"params": (),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"sc_for_create_q": {
	"params": (int, str),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"edit_quiz": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"quiz_release": {
	"params": (int, int),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"add_question": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"edit_quiz_title": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"disply_questions_to_teacher": {
	"params": (int,),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"edit_question": {
	"params": (int, int),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"delete_question": {
	"params": (int, int),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"edit_question_text": {
	"params": (int, int),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},
"edit_anwers": {
	"params": (int, int),
	"inline_type": "DNRTUO",
	"roles": ("teacher",),
	"state_id": None
},

}