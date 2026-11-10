from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1 = [
    # A
    path("", include("geo.urls")),
    path("", include("stores.urls")),
    path("", include("items.urls")),
    path("", include("records.urls")),
    path("", include("home.urls")),
    path("", include("demo.urls")),
    # B
    path("", include("uploads.urls")),
    path("", include("scans.urls")),
    path("", include("listings.urls")),
    path("", include("dashboard.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
