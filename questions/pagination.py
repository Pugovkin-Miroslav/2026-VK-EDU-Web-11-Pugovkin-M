from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

PAGE_SIZE = 10


def paginate(objects_list, request, per_page=PAGE_SIZE):
    paginator = Paginator(objects_list, per_page)
    try:
        return paginator.page(request.GET.get('page', 1))
    except (PageNotAnInteger, EmptyPage):
        return paginator.page(1)


def pagination_context(objects_list, request):
    page = paginate(objects_list, request)
    page_numbers = page.paginator.get_elided_page_range(
        page.number, on_each_side=1, on_ends=1,
    )
    return {'page_obj': page, 'page_numbers': page_numbers}
