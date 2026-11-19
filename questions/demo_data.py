from datetime import date, timedelta

ANSWERS = {
    35: [
        {
            'text': f'Вариант решения №{number}.',
            'author': f'Пользователь {number}',
            'created_at': date(2026, 10, 6),
            'rating': 12 - number,
            'is_correct': number == 1,
        }
        for number in range(1, 13)
    ],
}

QUESTIONS = [
    {
        'id': number,
        'title': f'Вопрос №{number}',
        'text': f'Описание вопроса №{number}.',
        'author': f'Автор {number}',
        'created_at': date(2026, 10, 6) - timedelta(days=number - 1),
        'rating': number % 13,
        'tags': ('Python', 'Django') if number % 2 else ('HTML', 'CSS'),
        'answer_count': len(ANSWERS.get(number, [])),
    }
    for number in range(1, 36)
]
