export async function postAjaxForm(form, fields) {
    try {
        const response = await fetch(form.action, {
            method: 'POST',
            headers: { 'X-CSRFToken': form.elements.namedItem('csrfmiddlewaretoken').value },
            body: new URLSearchParams(fields),
        });
        if (response.status === 401) {
            const { origin, pathname, search, hash } = window.location;
            const loginUrl = new URL(form.dataset.loginUrl, origin);
            loginUrl.searchParams.set('next', pathname + search + hash);
            window.location.assign(loginUrl);
            return null;
        }

        const payload = await response.json().catch(() => null);
        return response.ok ? { data: payload } : { error: payload?.error };
    } catch {
        return {};
    }
}
