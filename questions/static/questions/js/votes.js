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
    const body = new URLSearchParams({
        id: form.elements.namedItem('id').value,
        value: button.value,
    });
    const csrfToken = form.elements.namedItem('csrfmiddlewaretoken').value;
    const fallbackError = 'Не удалось сохранить голос. Попробуйте ещё раз.';

    error.hidden = true;
    buttons.forEach((voteButton) => { voteButton.disabled = true; });

    try {
        const response = await fetch(form.action, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body,
        });
        if (response.status === 401) {
            const { origin, pathname, search, hash } = window.location;
            const loginUrl = new URL(form.dataset.loginUrl, origin);
            loginUrl.searchParams.set('next', pathname + search + hash);
            window.location.assign(loginUrl);
            return;
        }

        const result = await response.json().catch(() => null);
        if (!response.ok || !Number.isInteger(result?.rating)) {
            error.textContent = result?.error || fallbackError;
            error.hidden = false;
            return;
        }

        rating.textContent = String(result.rating);
        buttons.forEach((voteButton) => {
            voteButton.setAttribute('aria-pressed', String(voteButton.value === String(result.value)));
        });
    } catch {
        error.textContent = fallbackError;
        error.hidden = false;
    } finally {
        buttons.forEach((voteButton) => {
            voteButton.disabled = voteButton.getAttribute('aria-pressed') === 'true';
        });
    }
});
