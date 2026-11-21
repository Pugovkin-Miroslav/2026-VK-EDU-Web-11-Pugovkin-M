import { postAjaxForm } from './ajax.js';

document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!form.matches('[data-correct-form]')) {
        return;
    }
    event.preventDefault();

    const button = event.submitter;
    if (!button || button.disabled || form.hidden) {
        return;
    }

    const question = form.closest('[data-question-detail]');
    const forms = question.querySelectorAll('[data-correct-form]');
    const buttons = Array.from(forms, (choice) => choice.querySelector('button'));
    const fields = {
        question_id: form.elements.namedItem('question_id').value,
        answer_id: form.elements.namedItem('answer_id').value,
    };
    const error = form.parentElement.querySelector('[data-correct-error]');

    forms.forEach((choice) => {
        choice.parentElement.querySelector('[data-correct-error]').hidden = true;
    });
    buttons.forEach((choice) => { choice.disabled = true; });

    try {
        const result = await postAjaxForm(form, fields);
        if (result === null) {
            return;
        }
        if (!Number.isInteger(result.data?.answer_id)) {
            error.textContent = result.error || 'Не удалось отметить правильный ответ. Попробуйте ещё раз.';
            error.hidden = false;
            return;
        }

        const template = question.querySelector('[data-correct-badge-template]');
        const badge = template.content.firstElementChild.cloneNode(true);
        badge.setAttribute('data-correct-label', '');
        question.querySelectorAll('[data-correct-label]').forEach((label) => label.remove());
        forms.forEach((choice) => { choice.hidden = choice === form; });
        form.before(badge);
    } finally {
        buttons.forEach((choice) => { choice.disabled = false; });
    }
});
