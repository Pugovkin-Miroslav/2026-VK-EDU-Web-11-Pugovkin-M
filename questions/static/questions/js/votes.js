import { postAjaxForm } from './ajax.js';

document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!form.matches('[data-vote-form]')) {
        return;
    }
    event.preventDefault();

    const button = event.submitter;
    if (!button || button.disabled) {
        return;
    }

    const buttons = form.querySelectorAll('button[name="value"]');
    const error = form.parentElement.querySelector('[data-vote-error]');
    const rating = form.querySelector('[data-vote-rating]');
    const fields = {
        id: form.elements.namedItem('id').value,
        value: button.getAttribute('aria-pressed') === 'true' ? '0' : button.value,
    };

    error.hidden = true;
    buttons.forEach((voteButton) => { voteButton.disabled = true; });

    try {
        const result = await postAjaxForm(form, fields);
        if (result === null) {
            return;
        }

        const { data } = result;
        if (!Number.isInteger(data?.rating)) {
            error.textContent = result.error || 'Не удалось сохранить голос. Попробуйте ещё раз.';
            error.hidden = false;
            return;
        }

        rating.textContent = String(data.rating);
        buttons.forEach((voteButton) => {
            voteButton.setAttribute('aria-pressed', String(voteButton.value === String(data.value)));
        });
    } finally {
        buttons.forEach((voteButton) => { voteButton.disabled = false; });
    }
});
