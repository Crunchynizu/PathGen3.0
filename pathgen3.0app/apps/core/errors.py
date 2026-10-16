"""Friendly error pages (used when DEBUG is off). They never reveal why access failed."""

from django.shortcuts import render


def _error_page(request, status_code, title, message):
    return render(
        request,
        "error/error.html",
        {"status_code": status_code, "error_title": title, "error_message": message},
        status=status_code,
    )


def bad_request(request, exception=None):
    return _error_page(request, 400, "Something went wrong", "That request could not be completed. Please go back and try again.")


def permission_denied(request, exception=None):
    return _error_page(request, 403, "This page isn't available", "You don't have access to this page. Go back to PathGen to continue.")


def page_not_found(request, exception=None):
    return _error_page(request, 404, "Page not found", "This page doesn't exist or isn't available. Go back to PathGen to continue.")


def server_error(request):
    return _error_page(request, 500, "Something went wrong", "PathGen hit a problem. Your saved answers are safe. Please go back and try again.")
