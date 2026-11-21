const avatar = document.querySelector('[data-avatar-max-bytes]');

avatar.addEventListener('change', () => {
    const file = avatar.files[0];
    const maxSize = Number(avatar.dataset.avatarMaxBytes);
    const message = file && file.size > maxSize ? avatar.dataset.avatarSizeError : '';
    avatar.setCustomValidity(message);
    if (message) {
        avatar.reportValidity();
    }
});
