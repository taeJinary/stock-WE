from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ApiPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        page_size = self.get_page_size(self.request) or len(data)
        return Response(
            {
                "status": "success",
                "data": data,
                "meta": {
                    "pagination": {
                        "page": self.page.number,
                        "page_size": page_size,
                        "total_pages": self.page.paginator.num_pages,
                        "total_items": self.page.paginator.count,
                        "next": self.get_next_link(),
                        "previous": self.get_previous_link(),
                    }
                },
            }
        )
