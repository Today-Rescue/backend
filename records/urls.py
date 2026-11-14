from django.urls import path, register_converter

from . import closing, production, views


class DateConverter:
    regex = r"\d{4}-\d{2}-\d{2}"

    def to_python(self, value):
        from datetime import date
        return date.fromisoformat(value)

    def to_url(self, value):
        return value.isoformat()


register_converter(DateConverter, "date")

urlpatterns = [
    path("stores/<int:store_id>/records", views.RecordListView.as_view()),
    path("stores/<int:store_id>/records/calendar", views.CalendarView.as_view()),
    path("stores/<int:store_id>/records/<date:date>", views.RecordUpsertView.as_view()),
    path("stores/<int:store_id>/productions", production.ProductionView.as_view()),
    path("stores/<int:store_id>/closings/<date:date>", closing.ClosingView.as_view()),
]