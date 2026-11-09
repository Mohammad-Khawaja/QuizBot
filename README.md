# QuizBot

QuizBot has four user roles: Admin, Teacher, Student, and Regular User.

Teachers can create and manage quizzes for their classes, while students can take quizzes and view their results.

Each teacher can manage multiple classes.

Users who want to become teachers or students must submit a membership request to the admin. The admin reviews and approves or rejects these requests.

## Features
- Student management
- Teacher management
- Class management
- Possibility of testing students
- Multiple-choice quizzes

## Technologies
- Python
- SQLite
- python-telegram-bot
- dotenv

## Installation
Clone the repository:

    git clone https://github.com/Mohammad-Khawaja/QuizBot.git

## Installation prerequisites
anyio==4.15.1
certifi==2026.10.23
charset-normalizer==3.5.2
dotenv==0.9.9
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
jalali_core==1.0.0
jdatetime==6.1.1
python-dotenv==1.2.4
python-telegram-bot==22.8
requests==2.34.2
typing_extensions==4.16.0
urllib3==2.8.0

# Implementation Guide
Before running the bot, you need to complete the following steps:

1. Run the "create_database.py" Python script to create the database.
2. Create a file named "keys.env" in the project's root directory and add your bot token to it using the following format:
   
   TOKEN=YOUR_TOKEN

3. Replace "YOUR_TOKEN" with your actual bot token.
After completing these steps, the bot will be ready to run.
