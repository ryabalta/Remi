import pandas as pd

# Create sample questions
questions = {
    'Question Text': [
        'What day of the week is it today?',
        'What did you have for breakfast this morning?',
        'What is your favorite color?',
        'Can you name three animals that start with the letter B?',
        'What season are we in right now?',
        'What is the capital of France?',
        'How many months are there in a year?',
        'What is 25 plus 15?',
        'Name three types of fruits.',
        'What year is it currently?'
    ],
    'Difficulty Level': ['E', 'E', 'E', 'M', 'E', 'M', 'E', 'M', 'M', 'E']
}

# Create DataFrame and save to Excel
df = pd.DataFrame(questions)
df.to_excel('Game_Questions.xlsx', index=False) 