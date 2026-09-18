from django.urls import path

from .views import MediaUploadAPIView, MediaRetrieveAPIView

urlpatterns = [
    path('upload/', MediaUploadAPIView.as_view()),
    path('<path:key>/', MediaRetrieveAPIView.as_view()),
]
