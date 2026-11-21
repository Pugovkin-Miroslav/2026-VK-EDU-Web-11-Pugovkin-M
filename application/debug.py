import socket

from debug_toolbar.middleware import show_toolbar_with_docker
from django.conf import settings


def show_toolbar_in_docker(request):
    if not settings.DEBUG:
        return False
    if show_toolbar_with_docker(request):
        return True

    try:
        return request.META.get('REMOTE_ADDR') == socket.gethostbyname('nginx')
    except OSError:
        return False
